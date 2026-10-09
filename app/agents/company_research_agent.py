"""
公司背调 Agent

通过 Tavily 搜索 + LLM 汇总，生成公司画像；结果缓存 7 天。
搜索部分保留在工具层调用，LLM 汇总在此 Agent 内。

T-P7-2 query 工程：7 条配方表（模块级常量，运行时渲染）+ topic 参数启用 +
动态年份 + 单失败跳过继续 + 全失败守卫（成功查询为 0 或累计结果为 0 →
不调 LLM、不写缓存，返回 None）+ search_data 体积瘦身投影。
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.agents.base_agent import BaseAgent
from app.core.llm import model
from app.core.prompts import load_prompt
from app.schemas.jobcraft import CompanyResearchInfo
from app.tools.llm_json import invoke_structured

logger = logging.getLogger("jobcraft.agents.company_research")

#: T-P7-2 query 配方表（矩阵「query 配方 7 条」原文，语义不得改动）。
#: template 运行时渲染；topic 首次全仓启用（news/finance/general）。
#: domain_refocus=True 的配方在首轮结果后按回捞域名再做一次聚焦检索
_QUERY_RECIPES: List[Dict[str, Any]] = [
    {
        "template": "{company} 官网 关于我们 产品服务",
        "topic": "general",
        "domain_refocus": True,
    },
    {"template": "{company} 主营业务 产品线 自研", "topic": "general"},
    {"template": "{company} 行业 地位 竞争对手 融资", "topic": "finance"},
    {"template": "{company} 创始人 高管 背景", "topic": "general"},
    {"template": "{company} 最新新闻 {year}", "topic": "news"},
    {"template": "{company} 面经 面试经验 牛客", "topic": "general"},
    {"template": "{company} 脉脉 知乎 员工评价", "topic": "general"},
]

#: search_data 序列化预算：低于 _build_company_prompt 的 8000 硬截断，
#: 保证 7 条配方（含聚焦补检）的检索结果全部进入 prompt 不被饿死
_SEARCH_DATA_BUDGET = 7600
#: 每条结果 content 摘要初始上限（字符），超预算时逐级减半压缩
_SNIPPET_LIMIT = 180
_SNIPPET_FLOOR = 40
_TITLE_LIMIT = 120


def _build_company_prompt(company: str, search_data: Dict[str, Any]) -> str:
    return load_prompt(
        "interview",
        "company_research",
        version=2,
        company=company,
        search_data=json.dumps(search_data, ensure_ascii=False, default=str)[:8000],
    )


def _render_queries(company: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
    """按配方表渲染本次公司调研的全部 query。

    :param company: 公司名
    :param year: 新闻配方年份；缺省取当前年（T-P7-2 动态年份）
    :return: 与 _QUERY_RECIPES 等长的 [{"query", "topic", "domain_refocus"}]
    """
    if year is None:
        year = datetime.now().year
    return [
        {
            "query": recipe["template"].format(company=company, year=year),
            "topic": recipe["topic"],
            "domain_refocus": recipe.get("domain_refocus", False),
        }
        for recipe in _QUERY_RECIPES
    ]


def _extract_items(response: Any) -> List[Dict[str, Any]]:
    """从 Tavily 响应中取结果条目列表（非 dict / 无 results 时返回空）。

    :param response: internet_search 返回的原始响应
    :return: 结果条目 dict 列表
    """
    if not isinstance(response, dict):
        return []
    items = response.get("results")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _harvest_domains(response: Any, limit: int = 2) -> List[str]:
    """从首轮检索结果 URL 回捞域名，供 include_domains 聚焦检索使用。

    白名单不静态编造：域名全部来自真实返回的首轮结果，只对已出现的
    域名做收敛复检（T-P7-2 官网聚焦策略）。

    :param response: 首轮 internet_search 响应
    :param limit: 最多回捞域名数
    :return: 去重后的域名列表（如 ["example.com", "foo.org"]）
    """
    domains: List[str] = []
    for item in _extract_items(response):
        url = str(item.get("url") or "")
        try:
            host = urlparse(url).netloc.lower()
        except ValueError:
            continue
        host = host.split("@")[-1].split(":")[0]
        if host.startswith("www."):
            host = host[4:]
        if host and "." in host and host not in domains:
            domains.append(host)
        if len(domains) >= limit:
            break
    return domains


def _slim_search_data(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """search_data 的 prompt 体积瘦身投影（T-P7-2 体积防线）。

    每条检索结果只保留 title/url/content 摘要，去掉 query 回显、score、
    response_time 等冗余；按 url 去重。序列化超过预算时逐级压缩 content
    摘要长度，保证全部配方结果都留在预算内（不被 8000 硬截断砍掉尾部
    的面经/口碑配方）。

    :param results: 原始检索条目 [{"query": ..., "result": Tavily响应}, ...]
    :return: {"search_results": [{"title", "url", "content"}, ...]}
    """
    items: List[Dict[str, Any]] = []
    seen_urls: set = set()
    for entry in results:
        raw = entry.get("result") if isinstance(entry, dict) else None
        for item in _extract_items(raw):
            url = str(item.get("url") or "")
            if url:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
            items.append(item)

    snippet_limit = _SNIPPET_LIMIT
    while True:
        slim = [
            {
                "title": str(item.get("title") or "")[:_TITLE_LIMIT],
                "url": str(item.get("url") or ""),
                "content": str(item.get("content") or "")[:snippet_limit],
            }
            for item in items
        ]
        data: Dict[str, Any] = {"search_results": slim}
        if (
            len(json.dumps(data, ensure_ascii=False)) <= _SEARCH_DATA_BUDGET
            or snippet_limit <= _SNIPPET_FLOOR
        ):
            return data
        snippet_limit //= 2


class CompanyResearchAgent(BaseAgent):
    """公司背调 LLM 汇总（单次 LLM 调用）"""

    def _get_output_schema(self):
        return CompanyResearchInfo

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """根据搜索结果汇总公司画像。

        :param state: {"company": str, "search_data": dict}
        :return: {"info": CompanyResearchInfo dict}
        """
        company = state.get("company", "")
        search_data = state.get("search_data", {})
        prompt = _build_company_prompt(company, search_data)
        info = invoke_structured(
            model,
            CompanyResearchInfo,
            prompt,
            debug_label="company_research",
            prompt_version="2",
        )
        return {"info": info.model_dump()}


def get_or_search_company(
    company: str, force: bool = False
) -> Optional[Dict[str, Any]]:
    """查缓存或实时搜索公司调研。

    :param company: 公司名
    :param force: 是否强制重新搜索（忽略缓存）
    :return: CompanyResearchInfo dict；全 query 失败或 0 结果时返回 None
        （全失败守卫：不调 LLM、不写缓存）
    """
    from app.tools import db_tools
    from app.tools.tavily_tool import internet_search

    if not company or not company.strip():
        return None
    company = company.strip()
    cached = db_tools.get_company_research(company)
    if cached and cached.get("fresh") and not force:
        return cached.get("info")

    # 搜索：按配方表逐条执行，单条失败跳过继续（语义与 T-P7-1 前一致）
    results: List[Dict[str, Any]] = []
    attempted = 0
    success_queries = 0
    total_items = 0
    for spec in _render_queries(company):
        payload = {
            "query": spec["query"],
            "topic": spec["topic"],
            "max_results": 3,
            "include_raw_content": False,
        }
        attempted += 1
        try:
            response = internet_search.invoke(payload)
        except Exception as exc:
            logger.warning("公司调研搜索「%s」失败，跳过该查询: %s", spec["query"], exc)
            continue
        success_queries += 1
        total_items += len(_extract_items(response))
        results.append({"query": spec["query"], "result": response})

        # include_domains 官网聚焦：仅用首轮结果回捞的域名做收敛复检，
        # 聚焦失败只跳过不致命，首轮结果已在账上不会滤空
        if not spec.get("domain_refocus"):
            continue
        domains = _harvest_domains(response)
        if not domains:
            continue
        attempted += 1
        try:
            focused = internet_search.invoke(
                {**payload, "max_results": 2, "include_domains": domains}
            )
        except Exception as exc:
            logger.warning(
                "公司调研官网聚焦搜索「%s」失败，跳过: %s", spec["query"], exc
            )
            continue
        success_queries += 1
        total_items += len(_extract_items(focused))
        results.append({"query": f"{spec['query']}（官网聚焦）", "result": focused})

    logger.info(
        "公司调研搜索完成 company=%s 成功查询=%d/%d 累计结果=%d 条",
        company,
        success_queries,
        attempted,
        total_items,
    )
    # 全失败守卫（矩阵「全 query 失败/0 结果 → 不调 LLM」）：
    # 不调 CompanyResearchAgent、不写缓存，返回 None
    if success_queries == 0 or total_items == 0:
        logger.warning(
            "公司调研全失败守卫触发 company=%s 成功查询=%d 累计结果=%d，不调 LLM、不写缓存",
            company,
            success_queries,
            total_items,
        )
        return None

    search_data = _slim_search_data(results)

    agent = CompanyResearchAgent()
    out = agent.run({"company": company, "search_data": search_data})
    info = out.get("info")

    db_tools.upsert_company_research(company, info)
    return {**info, "cached_at": datetime.now().isoformat(), "from_cache": False}
