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


def _get_previous_review_summary(
    submission_id: Optional[int], user_id: Optional[int] = None
) -> Optional[str]:
    """取该投递最近一条面试复盘摘要（优势/劣势/改进项），无则 None。"""
    if not submission_id:
        return None
    try:
        rows = db_tools.list_interview_records_by_submission(
            submission_id, user_id=user_id
        )
        if not rows:
            return None
        latest = rows[0]
        analysis = latest.get("analysis_json") or {}
        parts = []
        if analysis.get("strengths"):
            parts.append(f"优势：{'、'.join(analysis['strengths'][:3])}")
        if analysis.get("weaknesses"):
            parts.append(f"劣势：{'、'.join(analysis['weaknesses'][:3])}")
        if analysis.get("action_items"):
            parts.append(f"改进项：{'、'.join(analysis['action_items'][:3])}")
        return "\n".join(parts) if parts else None
    except Exception as exc:
        logger.warning("读取上一轮复盘摘要失败，返回空: %s", exc)
        return None


def load_interview_prep_enrichment(
    job_analysis_id: int,
    user_id: int,
    submission_id: Optional[int] = None,
) -> Dict[str, Any]:
    """加载面试准备增强上下文（公司调研 / 简历 markdown / 上轮复盘摘要）。

    API 同步端点与异步任务路径共用本函数，保证两路径行为一致
    （BE-TASKDIV-01）。加载失败容忍，对应字段为 None。
    调用方显式提供的值应优先于本函数返回值。

    :param job_analysis_id: 岗位分析 id
    :param user_id: 当前用户
    :param submission_id: 投递 id（缺省时按岗位反查）
    :return: {"company_research", "resume_markdown", "previous_review_summary"}
    """
    company_research: Optional[Dict[str, Any]] = None
    resume_markdown: Optional[str] = None
    previous_review_summary: Optional[str] = None
    try:
        analysis = db_tools.get_job_analysis(job_analysis_id, user_id)
        company = (analysis or {}).get("company", "")
        if company:
            from app.agents.company_research_agent import get_or_search_company

            company_research = get_or_search_company(company)

        submission = None
        if submission_id:
            submission = db_tools.get_submission(submission_id, user_id)
        elif analysis:
            for s in db_tools.list_submissions(user_id):
                if s.get("job_analysis_id") == job_analysis_id:
                    submission = db_tools.get_submission(s["id"], user_id)
                    break
        if submission:
            resume_markdown = submission.get("resume_markdown")

        previous_review_summary = _get_previous_review_summary(
            submission_id or (submission.get("id") if submission else None),
            user_id,
        )
    except Exception:
        logger.warning("加载面试增强数据失败", exc_info=True)
    return {
        "company_research": company_research,
        "resume_markdown": resume_markdown,
        "previous_review_summary": previous_review_summary,
    }


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

    # 卡片选择下沉（BE-TASKDIV-01）：空 card_ids 回退岗位默认选择，
    # 与 API 同步路径行为一致；仍无可用卡则报错（HTTP 层映射为 400）
    if not card_ids:
        card_ids = db_tools.get_selected_card_ids_by_job(job_analysis_id) or []
    if not card_ids:
        raise ValueError("该岗位分析未关联经历卡，请从岗位分析页重新分析")

    # 拉经历卡 + 定制版本
    cards = []
    card_versions: Dict[int, str] = {}
    for cid in card_ids:
        c = db_tools.get_card(cid, user_id)
        if c and c.get("is_active"):
            try:
                from app.tools.db_expression import (
                    get_active_expression_content,
                    increment_active_expression_usage,
                )

                c["active_expression"] = get_active_expression_content(cid, user_id)
                if c["active_expression"]:
                    increment_active_expression_usage(cid, user_id)
            except Exception:
                c["active_expression"] = None
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
    out = InterviewPrepAgent().run(
        {
            "prompt": prompt,
            "prompt_version": str(interview_pre.INTERVIEW_PREP_PROMPT_VERSION),
        }
    )
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
