"""
公司背调 Agent

通过 Tavily 搜索 + LLM 汇总，生成公司画像；结果缓存 7 天。
搜索部分保留在工具层调用，LLM 汇总在此 Agent 内。

T-P7-2 query 工程：7 条配方表（模块级常量，运行时渲染）+ topic 参数启用 +
动态年份 + 单失败跳过继续 + 全失败守卫（成功查询为 0 或累计结果为 0 →
不调 LLM、不写缓存）+ search_data 体积瘦身投影。

T-P7-3 降级矩阵：全失败守卫/LLM 失败回退旧缓存（顶层 ``stale: True``，
不 upsert）或返回 None；LLM 汇总失败重试 1 次（同一份 search_data）；
半成品不落库（upsert 仅最终成功后执行一次）；检索投影保留 Tavily
``published_date``（D4 新闻条目日期）。
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
#: domain_refocus=True 的配方（配方 1 官网 / 配方 5 新闻）在首轮结果后
#: 按回捞域名再做一次聚焦检索（质量审查 Minor-8 拍板沿用已证策略）
_QUERY_RECIPES: List[Dict[str, Any]] = [
    {
        "template": "{company} 官网 关于我们 产品服务",
        "topic": "general",
        "domain_refocus": True,
    },
    {"template": "{company} 主营业务 产品线 自研", "topic": "general"},
    {"template": "{company} 行业 地位 竞争对手 融资", "topic": "finance"},
    {"template": "{company} 创始人 高管 背景", "topic": "general"},
    {
        "template": "{company} 最新新闻 {year}",
        "topic": "news",
        "domain_refocus": True,
    },
    {"template": "{company} 面经 面试经验 牛客", "topic": "general"},
    {"template": "{company} 脉脉 知乎 员工评价", "topic": "general"},
]

#: search_data 序列化预算：低于 _build_company_prompt 的 8000 硬截断，
#: 保证 7 条配方（含聚焦补检）的检索结果全部进入 prompt 不被饿死
_SEARCH_DATA_BUDGET = 7600
#: 每条结果 content 摘要初始上限（字符），超预算时逐级减半，
#: 实际下限 = _SNIPPET_FLOOR（质量审查 Minor-6：先判下限再减半，不落到 22）
_SNIPPET_LIMIT = 180
_SNIPPET_FLOOR = 40
_TITLE_LIMIT = 120
#: url 单项上限（质量审查 Minor-1）：追踪参数堆叠的超长 url 截断，
#: 防止单条 url 击穿预算
_URL_LIMIT = 120

#: 搜索引擎/聚合站域名后缀：对这些域名做聚焦复检无意义，回捞时跳过
#: （质量审查 Minor-2；匹配 = 精确命中或子域名后缀命中）
_DOMAIN_DENY_SUFFIXES = (
    "baidu.com",
    "google.com",
    "bing.com",
    "sogou.com",
    "so.com",
    "360.cn",
    "sm.cn",
    "wikipedia.org",
)


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

    渲染层自防（质量审查 Minor-9）：company 先 strip、渲染结果再 strip，
    空串/前后空白不会产出前导空格；入口 ``get_or_search_company`` 亦已 strip，
    此处重复仅为直调安全。

    :param company: 公司名
    :param year: 新闻配方年份；缺省取当前年（T-P7-2 动态年份）
    :return: 与 _QUERY_RECIPES 等长的 [{"query", "topic", "domain_refocus"}]
    """
    company = company.strip()
    if year is None:
        year = datetime.now().year
    return [
        {
            "query": recipe["template"].format(company=company, year=year).strip(),
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
    域名做收敛复检（T-P7-2 官网/新闻聚焦策略）。护栏（质量审查 Minor-2）：
    跳过搜索引擎/聚合站 denylist、全数字 IP host，去尾点与 www 前缀。

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
        host = host.split("@")[-1].split(":")[0].rstrip(".")
        if host.startswith("www."):
            host = host[4:]
        if not host or "." not in host:
            continue
        if host.replace(".", "").isdigit():  # IPv4 地址不做聚焦
            continue
        if any(
            host == suffix or host.endswith("." + suffix)
            for suffix in _DOMAIN_DENY_SUFFIXES
        ):
            continue
        if host not in domains:
            domains.append(host)
        if len(domains) >= limit:
            break
    return domains


def _dedup_key(url: str) -> str:
    """去重键归一化：去 fragment + 去尾部 ``/`` + 小写（质量审查 Minor-5）。

    query 串刻意不剥离——参数不同可能是不同页面，宁可少去重不误删。

    :param url: 原始 url
    :return: 归一化去重键
    """
    return url.split("#", 1)[0].rstrip("/").lower()


def _project_items(
    items: List[Dict[str, Any]], snippet_limit: int
) -> List[Dict[str, Any]]:
    """把原始结果条目投影为 prompt 条目（title/url/content 摘要截断）。

    D4（T-P7-3）：Tavily 条目级 ``published_date``（topic=news 等结果才带）
    原样保留进投影，缺省不造键——新闻条目日期不得丢失，供 prompt 约束
    「必须使用检索结果中的发布日期」引用；字段极小，对预算/去重/url
    cap 逻辑免疫（投影键并集不变）。
    """
    projected: List[Dict[str, Any]] = []
    for item in items:
        entry: Dict[str, Any] = {
            "title": str(item.get("title") or "")[:_TITLE_LIMIT],
            "url": str(item.get("url") or "")[:_URL_LIMIT],
            "content": str(item.get("content") or "")[:snippet_limit],
        }
        published = item.get("published_date")
        if published:
            entry["published_date"] = str(published)
        projected.append(entry)
    return projected


def _slim_search_data(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """search_data 的 prompt 体积瘦身投影（T-P7-2 体积防线）。

    每条检索结果只保留 title/url/content 摘要（T-P7-3 D4：另保留条目级
    ``published_date`` 发布日期，缺省不造键），去掉 query 回显、score、
    response_time 等冗余；url 按归一化键去重（去 fragment/尾斜杠/小写，
    query 串保留）。预算策略：content 摘要逐级减半至 _SNIPPET_FLOOR（=40，
    质量审查 Minor-6）仍超预算时，按条丢弃尾部结果并 logger.warning
    显式上报丢弃条数（Minor-1），不依赖 _build_company_prompt 的
    [:8000] 静默砍。

    :param results: 原始检索条目 [{"query": ..., "result": Tavily响应}, ...]
    :return: {"search_results": [{"title", "url", "content"[, "published_date"]}, ...]}
    """
    items: List[Dict[str, Any]] = []
    seen_keys: set = set()
    for entry in results:
        raw = entry.get("result") if isinstance(entry, dict) else None
        for item in _extract_items(raw):
            url = str(item.get("url") or "")
            key = _dedup_key(url) if url else ""
            if key:
                if key in seen_keys:
                    continue
                seen_keys.add(key)
            items.append(item)

    # 阶段一：content 摘要逐级减半，实际下限 _SNIPPET_FLOOR
    snippet_limit = _SNIPPET_LIMIT
    slim = _project_items(items, snippet_limit)
    data: Dict[str, Any] = {"search_results": slim}
    while len(json.dumps(data, ensure_ascii=False)) > _SEARCH_DATA_BUDGET:
        if snippet_limit <= _SNIPPET_FLOOR:
            break
        snippet_limit = max(snippet_limit // 2, _SNIPPET_FLOOR)
        slim = _project_items(items, snippet_limit)
        data = {"search_results": slim}

    # 阶段二（floor 路径）：按条丢弃尾部结果直至进预算，显式可观测
    dropped = 0
    while (
        len(slim) > 1
        and len(json.dumps(data, ensure_ascii=False)) > _SEARCH_DATA_BUDGET
    ):
        slim.pop()
        dropped += 1
        data = {"search_results": slim}
    if dropped:
        logger.warning(
            "search_data 超预算（budget=%d），按条丢弃尾部检索结果 %d 条",
            _SEARCH_DATA_BUDGET,
            dropped,
        )
    return data


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


#: 六维 aspect 键（与 CompanyResearchAspects 对齐），供缺维可观测日志使用
_ASPECT_KEYS: List[str] = [
    "overview",
    "business",
    "ecosystem",
    "team",
    "recent",
    "reputation",
]


def _stale_fallback(
    company: str, cached: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """降级矩阵回退：旧缓存非空 → 返回旧 info + ``stale: True``；无缓存 → None。

    T-P7-3 契约：stale 只出现在回退返回值上，**永不** upsert 进全局缓存行
    （调用方在回退路径零写库）；形状与实时/缓存命中路径同构
    （``{**info, cached_at, from_cache: True, stale: True}``）。

    :param company: 公司名（日志上下文）
    :param cached: ``get_company_research`` 返回行（{info, cached_at, fresh}）
    :return: stale 回退 dict 或 None（无可用旧缓存）
    """
    info = (cached or {}).get("info") or {}
    if not info:
        return None
    logger.warning(
        "公司调研降级回退旧缓存 company=%s cached_at=%s（stale=True，不写缓存）",
        company,
        (cached or {}).get("cached_at"),
    )
    return {
        **info,
        "cached_at": (cached or {}).get("cached_at") or datetime.now().isoformat(),
        "from_cache": True,
        "stale": True,
    }


def _log_empty_aspects(company: str, info: Dict[str, Any]) -> None:
    """成功解析后记录缺维（空列表）维度，observability（矩阵行3）。

    wire 不加字段：缺维=空列表语义 P7-1 已定，此处仅日志可观测，
    「insufficient」措辞差异由 prep 控制器登记。

    :param company: 公司名
    :param info: 汇总后的 CompanyResearchInfo dict
    """
    aspects = (info or {}).get("aspects") or {}
    empty_dims = [k for k in _ASPECT_KEYS if not aspects.get(k)]
    if empty_dims:
        logger.info(
            "公司调研完成 company=%s 缺维（空列表）=%s",
            company,
            ",".join(empty_dims),
        )


def get_or_search_company(
    company: str, force: bool = False
) -> Optional[Dict[str, Any]]:
    """查缓存或实时搜索公司调研。

    :param company: 公司名
    :param force: 是否强制重新搜索（忽略缓存）
    :return: CompanyResearchInfo dict + ``{cached_at, from_cache}`` 元数据
        （fresh 命中时 ``from_cache=True``）；降级路径（T-P7-3）：全 query
        失败/0 结果或 LLM 重试后仍失败 → 旧缓存非空时返回旧 info +
        ``stale: True``（不写缓存），否则返回 None
    """
    from app.tools import db_tools
    from app.tools.tavily_tool import internet_search

    if not company or not company.strip():
        return None
    company = company.strip()
    cached = db_tools.get_company_research(company)
    if cached and cached.get("fresh") and not force:
        info = cached.get("info") or {}
        if not info:
            # 空壳缓存视同未命中，避免元数据空壳进 prompt（不渲染空壳）
            return None
        # 质量审查 Minor-3：命中路径与实时路径形状统一
        # （cached_at 取行内值，from_cache=True，顶层 = aspects + 元数据）
        return {
            **info,
            "cached_at": cached.get("cached_at") or datetime.now().isoformat(),
            "from_cache": True,
        }

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

        # include_domains 聚焦（官网配方 1 / 新闻配方 5）：仅用首轮结果回捞
        # 的域名做收敛复检，聚焦失败只跳过不致命，首轮结果已在账上不会滤空
        if not spec.get("domain_refocus"):
            continue
        domains = _harvest_domains(response)
        logger.info(
            "公司调研域名回捞 company=%s query=%s domains=%s",
            company,
            spec["query"],
            domains,
        )
        if not domains:
            continue
        attempted += 1
        try:
            focused = internet_search.invoke(
                {**payload, "max_results": 2, "include_domains": domains}
            )
        except Exception as exc:
            logger.warning("公司调研聚焦搜索「%s」失败，跳过: %s", spec["query"], exc)
            continue
        success_queries += 1
        total_items += len(_extract_items(focused))
        results.append({"query": f"{spec['query']}（域名聚焦）", "result": focused})

    logger.info(
        "公司调研搜索完成 company=%s 成功查询=%d/%d 累计结果=%d 条",
        company,
        success_queries,
        attempted,
        total_items,
    )
    # 全失败守卫（矩阵「全 query 失败/0 结果 → 不调 LLM」）：
    # 不调 CompanyResearchAgent、不写缓存；旧缓存非空 → stale 回退，无缓存 → None
    if success_queries == 0 or total_items == 0:
        logger.warning(
            "公司调研全失败守卫触发 company=%s 成功查询=%d 累计结果=%d，不调 LLM、不写缓存",
            company,
            success_queries,
            total_items,
        )
        return _stale_fallback(company, cached)

    search_data = _slim_search_data(results)

    # LLM 汇总（矩阵行4）：失败重试 1 次（同一份 search_data，不重跑搜索）；
    # 仍失败 → 与全失败守卫相同的回退（旧缓存 stale 或 None）；
    # 半成品不落库：upsert 仅在最终成功后执行一次
    agent = CompanyResearchAgent()
    try:
        out = agent.run({"company": company, "search_data": search_data})
    except Exception as exc:
        logger.error(
            "公司调研 LLM 汇总失败 company=%s，重试 1 次（同一份 search_data）: %s",
            company,
            exc,
            exc_info=True,
        )
        try:
            out = agent.run({"company": company, "search_data": search_data})
        except Exception as retry_exc:
            logger.error(
                "公司调研 LLM 汇总重试后仍失败 company=%s 重试次数=1，"
                "回退旧缓存（stale）或 None，不写缓存: %s",
                company,
                retry_exc,
                exc_info=True,
            )
            return _stale_fallback(company, cached)
    info = out.get("info")

    _log_empty_aspects(company, info)

    db_tools.upsert_company_research(company, info)
    return {**info, "cached_at": datetime.now().isoformat(), "from_cache": False}
