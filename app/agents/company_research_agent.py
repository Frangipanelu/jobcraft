"""
公司背调 Agent

通过 Tavily 搜索 + LLM 汇总，生成公司画像；结果缓存 7 天。
搜索部分 `_search_company` 保留在工具层，LLM 汇总在此 Agent 内。
"""

import json
from typing import Any, Dict, Optional

from app.agents.base_agent import BaseAgent
from app.core.llm import model
from app.core.prompts import load_prompt
from app.schemas.jobcraft import CompanyResearchInfo
from app.tools.llm_json import invoke_structured


def _build_company_prompt(company: str, search_data: Dict[str, Any]) -> str:
    return load_prompt(
        "interview",
        "company_research",
        company=company,
        search_data=json.dumps(search_data, ensure_ascii=False, default=str)[:8000],
    )


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
            model, CompanyResearchInfo, prompt, debug_label="company_research"
        )
        return {"info": info.model_dump()}


def get_or_search_company(
    company: str, force: bool = False
) -> Optional[Dict[str, Any]]:
    """查缓存或实时搜索公司调研。

    :param company: 公司名
    :param force: 是否强制重新搜索（忽略缓存）
    :return: CompanyResearchInfo dict 或 None
    """
    from datetime import datetime

    from app.tools import db_tools
    from app.tools.tavily_tool import internet_search

    if not company or not company.strip():
        return None
    company = company.strip()
    cached = db_tools.get_company_research(company)
    if cached and cached.get("fresh") and not force:
        return cached.get("info")

    # 搜索
    queries = [
        f"{company} 公司介绍 业务 融资",
        f"{company} 最新新闻 2025 2026",
        f"{company} 行业地位 竞争对手",
        f"{company} 创始人 高管团队",
        f"{company} 企业文化 工作体验",
    ]
    results = []
    for q in queries:
        try:
            r = internet_search.invoke(
                {"query": q, "max_results": 3, "include_raw_content": False}
            )
            results.append({"query": q, "result": r})
        except Exception:
            continue
    search_data = {"search_results": results}

    agent = CompanyResearchAgent()
    out = agent.run({"company": company, "search_data": search_data})
    info = out.get("info")

    db_tools.upsert_company_research(company, info)
    return {**info, "cached_at": datetime.now().isoformat(), "from_cache": False}
