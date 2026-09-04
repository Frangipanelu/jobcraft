"""
面试准备单节点 Workflow

流程：
1. 从 DB 读取岗位分析、经历卡、公司调研、简历、上轮复盘摘要
2. 纯函数构建 prompt（interview_pre._build_interview_prompt）
3. InterviewPrepAgent 单次 LLM 生成逐字稿
4. 结果落库 interview_preps
"""

import logging
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.interview_prep_agent import InterviewPrepAgent
from app.schemas.jobcraft import InterviewPrepResult
from app.tools import db_tools, interview_pre

logger = logging.getLogger(__name__)


class InterviewPrepState(TypedDict):
    job_analysis_id: int
    round_type: str
    card_ids: List[int]
    user_id: int
    submission_id: Optional[int]
    company_research: Optional[Dict[str, Any]]
    resume_markdown: Optional[str]
    previous_review_summary: Optional[str]
    result: Optional[Dict[str, Any]]


def _generate_prep(state: Dict[str, Any]) -> Dict[str, Any]:
    job_analysis_id = state["job_analysis_id"]
    round_type = state["round_type"]
    card_ids = state["card_ids"]
    user_id = state.get("user_id", 1)
    submission_id = state.get("submission_id")

    analysis = db_tools.get_job_analysis(job_analysis_id, user_id)
    if not analysis:
        raise ValueError(f"job_analysis #{job_analysis_id} 不存在")

    company = analysis.get("company", "")
    position = analysis.get("position", "")
    jd_text = analysis.get("jd_text", "")
    dimension_requirements = analysis.get("dimension_requirements") or []

    # 拉经历卡 + 定制版本
    cards = []
    card_versions: Dict[int, str] = {}
    for cid in card_ids:
        c = db_tools.get_card(cid, user_id)
        if c and c.get("is_active"):
            cards.append(c)
    for version in db_tools.get_card_versions_by_source(
        "job_analysis", job_analysis_id
    ):
        card_versions[version["card_id"]] = version.get("raw_text", "")
    if not cards:
        raise ValueError("所选经历卡不可用")

    # 纯函数构建 prompt
    prompt = interview_pre._build_interview_prompt(
        round_type=round_type,
        position=position,
        company=company,
        jd_text=jd_text,
        cards=cards,
        dimension_requirements=dimension_requirements,
        card_versions=card_versions,
        company_research=state.get("company_research"),
        resume_markdown=state.get("resume_markdown"),
        previous_review_summary=state.get("previous_review_summary"),
    )

    # Agent 单次 LLM 生成
    out = InterviewPrepAgent().run({"prompt": prompt})
    result = InterviewPrepResult(**out["prep_result"])
    result.job_analysis_id = job_analysis_id
    result.round_type = round_type

    # 落库
    ability_matrix = [q.model_dump() for q in result.dimension_questions]
    record_id = db_tools.insert_interview_prep(
        {
            "job_analysis_id": job_analysis_id,
            "user_id": user_id,
            "round_type": round_type,
            "duration": result.duration,
            "elevator_pitch": result.elevator_pitch,
            "standard_version": {},
            "extended_version": {"full_version": result.full_version},
            "ability_matrix": ability_matrix,
            "html_content": result.html_content,
            "submission_id": submission_id,
            "company_research": state.get("company_research"),
        }
    )
    result.id = record_id
    return {"result": result.model_dump()}


def run_interview_prep_workflow(
    job_analysis_id: int,
    round_type: str,
    card_ids: List[int],
    user_id: int = 1,
    submission_id: Optional[int] = None,
    company_research: Optional[Dict[str, Any]] = None,
    resume_markdown: Optional[str] = None,
    previous_review_summary: Optional[str] = None,
) -> Dict[str, Any]:
    """执行面试准备 Workflow，返回 InterviewPrepResult dict。"""
    workflow = StateGraph(InterviewPrepState)
    workflow.add_node("generate_prep", _generate_prep)
    workflow.add_edge(START, "generate_prep")
    workflow.add_edge("generate_prep", END)

    app = workflow.compile()
    initial_state: InterviewPrepState = {
        "job_analysis_id": job_analysis_id,
        "round_type": round_type,
        "card_ids": card_ids,
        "user_id": user_id,
        "submission_id": submission_id,
        "company_research": company_research,
        "resume_markdown": resume_markdown,
        "previous_review_summary": previous_review_summary,
        "result": None,
    }
    result = app.invoke(initial_state)
    return result.get("result", {})
