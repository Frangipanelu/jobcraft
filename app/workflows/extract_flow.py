"""
结构化成就抽取 & 标签推荐 Workflow

分别包装 agent 为单节点 StateGraph：
- run_extract_structured_workflow: raw_text → CardStructuredCache
- run_recommend_tags_workflow: raw_text → 标签列表
- run_parse_resume_entries_workflow: resume_text → 经历条目
- run_backfill_workflow: 单卡装整份简历的旧数据拆卡（Agent + DB）
"""

import logging
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.extract_agent import (
    ExtractStructuredAgent,
    ParseResumeEntriesAgent,
    RecommendTagsAgent,
)
from app.tools import db_tools

logger = logging.getLogger(__name__)


class ExtractStructuredState(TypedDict):
    raw_text: str
    result: Optional[Dict[str, Any]]


class RecommendTagsState(TypedDict):
    raw_text: str
    result: Optional[List[str]]


class ParseResumeEntriesState(TypedDict):
    resume_text: str
    result: Optional[List[Dict[str, Any]]]


class BackfillState(TypedDict):
    user_id: int
    min_chars: int
    result: Optional[Dict[str, Any]]


def _run_extract_structured(state: Dict[str, Any]) -> Dict[str, Any]:
    out = ExtractStructuredAgent().run({"raw_text": state["raw_text"]})
    return {"result": out["cache"]}


def _run_recommend_tags(state: Dict[str, Any]) -> Dict[str, Any]:
    out = RecommendTagsAgent().run({"raw_text": state["raw_text"]})
    return {"result": out["tags"]}


def _run_parse_resume_entries(state: Dict[str, Any]) -> Dict[str, Any]:
    out = ParseResumeEntriesAgent().run({"resume_text": state["resume_text"]})
    return {"result": out["entries"]}


def _run_backfill(state: Dict[str, Any]) -> Dict[str, Any]:
    user_id = state.get("user_id", 1)
    min_chars = state.get("min_chars", 100)

    cards = db_tools.list_full_resume_cards(user_id, min_chars)
    result: Dict[str, Any] = {"checked": 0, "splits": []}
    if not cards:
        return {"result": result}

    # checked 统计所有卡片数，与旧接口对齐
    result["checked"] = len(db_tools.list_cards(user_id, include_inactive=False))
    for card in cards:
        out = ParseResumeEntriesAgent().run({"resume_text": card.get("raw_text") or ""})
        entries = out["entries"]
        if len(entries) < 2:
            continue
        created_ids = db_tools.split_resume_card_by_entries(user_id, card, entries)
        result["splits"].append(
            {
                "from_card_id": card["id"],
                "from_title": card["title"],
                "created_ids": created_ids,
            }
        )
    return {"result": result}


def run_extract_structured_workflow(raw_text: str) -> Optional[Dict[str, Any]]:
    """抽取结构化成就缓存"""
    workflow = StateGraph(ExtractStructuredState)
    workflow.add_node("extract", _run_extract_structured)
    workflow.add_edge(START, "extract")
    workflow.add_edge("extract", END)

    app = workflow.compile()
    initial_state: ExtractStructuredState = {"raw_text": raw_text, "result": None}
    result = app.invoke(initial_state)
    return result.get("result")


def run_recommend_tags_workflow(raw_text: str) -> List[str]:
    """推荐标签"""
    workflow = StateGraph(RecommendTagsState)
    workflow.add_node("recommend", _run_recommend_tags)
    workflow.add_edge(START, "recommend")
    workflow.add_edge("recommend", END)

    app = workflow.compile()
    initial_state: RecommendTagsState = {"raw_text": raw_text, "result": None}
    result = app.invoke(initial_state)
    return result.get("result", [])


def run_parse_resume_entries_workflow(resume_text: str) -> List[Dict[str, Any]]:
    """解析完整简历文本，提取经历条目"""
    workflow = StateGraph(ParseResumeEntriesState)
    workflow.add_node("parse", _run_parse_resume_entries)
    workflow.add_edge(START, "parse")
    workflow.add_edge("parse", END)

    app = workflow.compile()
    initial_state: ParseResumeEntriesState = {
        "resume_text": resume_text,
        "result": None,
    }
    result = app.invoke(initial_state)
    return result.get("result", [])


def run_backfill_workflow(user_id: int = 1, min_chars: int = 100) -> Dict[str, Any]:
    """把「单卡装下整份简历」的旧数据拆分成多张经历卡"""
    workflow = StateGraph(BackfillState)
    workflow.add_node("backfill", _run_backfill)
    workflow.add_edge(START, "backfill")
    workflow.add_edge("backfill", END)

    app = workflow.compile()
    initial_state: BackfillState = {
        "user_id": user_id,
        "min_chars": min_chars,
        "result": None,
    }
    result = app.invoke(initial_state)
    return result.get("result", {"checked": 0, "splits": []})
