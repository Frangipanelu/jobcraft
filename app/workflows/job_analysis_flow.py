"""
岗位分析 Workflow

- run_step1_workflow: ATS 解析 + 推荐卡片（AtsRecommendAgent，合并一次 LLM）
- run_step2_workflow: 缺口分析 + 润色建议（GapPolishAgent + 本地融合）
- run_job_analysis_workflow: 旧版完整分析（JdAtsAgent → ScoreMatchAgent → 融合 → SugAgent）
- run_analyze_ats_workflow: 仅 ATS 解析（JdAtsAgent）
- run_resume_preview_workflow: 简历预览重新匹配（JdAtsAgent → ScoreMatchAgent → 融合）
"""

import logging
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.ats_recommend_agent import AtsRecommendAgent
from app.agents.gap_polish_agent import GapPolishAgent
from app.agents.jd_ats_agent import JdAtsAgent
from app.agents.score_match_agent import ScoreMatchAgent
from app.agents.sug_agent import SugAgent
from app.schemas.jobcraft import ATSProfile, JobAnalysisResult, SuggestionsResult
from app.tools import db_tools, jobcraft_analyze

logger = logging.getLogger(__name__)


class JobAnalysisState(TypedDict):
    user_id: int
    company: str
    position: str
    jd_text: str
    card_ids: List[int]
    result: Optional[Dict[str, Any]]


class Step1State(TypedDict):
    user_id: int
    company: str
    position: str
    jd_text: str
    cards: List[Dict[str, Any]]
    result: Optional[Dict[str, Any]]


class Step2State(TypedDict):
    job_analysis_id: int
    card_ids: List[int]
    result: Optional[Dict[str, Any]]


class ATSOnlyState(TypedDict):
    jd_text: str
    result: Optional[Dict[str, Any]]


class ResumePreviewState(TypedDict):
    job_id: int
    selected_card_ids: List[int]
    result: Optional[Dict[str, Any]]


# ============================================================
#  Step 1: ATS 解析 + 推荐卡片
# ============================================================


def _run_step1(state: Dict[str, Any]) -> Dict[str, Any]:
    agent = AtsRecommendAgent()
    out = agent.run({"jd_text": state["jd_text"], "cards": state.get("cards", [])})
    return {"result": out}


def run_step1_workflow(
    user_id: int,
    company: str,
    position: str,
    jd_text: str,
    cards: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Step 1: ATS 解析 + 推荐卡片。返回 {ats, recommended_cards}。"""
    workflow = StateGraph(Step1State)
    workflow.add_node("step1", _run_step1)
    workflow.add_edge(START, "step1")
    workflow.add_edge("step1", END)

    app = workflow.compile()
    initial_state: Step1State = {
        "user_id": user_id,
        "company": company,
        "position": position,
        "jd_text": jd_text,
        "cards": cards,
        "result": None,
    }
    result = app.invoke(initial_state)
    return result.get("result", {})


# ============================================================
#  Step 2: 缺口分析 + 润色建议
# ============================================================


def _run_step2(state: Dict[str, Any]) -> Dict[str, Any]:
    job_analysis_id = state["job_analysis_id"]
    analysis = db_tools.get_job_analysis(job_analysis_id)
    if not analysis:
        raise ValueError(f"job_analysis #{job_analysis_id} 不存在")

    ats_dict = analysis.get("jd_requirements") or {}
    ats = ATSProfile(**ats_dict)

    cards = []
    for cid in state.get("card_ids", []):
        c = db_tools.get_card(cid)
        if c and c.get("is_active"):
            cards.append(c)

    agent = GapPolishAgent()
    out = agent.run(
        {
            "ats": ats_dict,
            "jd_text": analysis.get("jd_text", ""),
            "selected_cards": cards,
        }
    )
    gap_polish = out["gap_polish"]

    # 本地分与 LLM 分融合（本地 40% + LLM 60%）
    fused = jobcraft_analyze.fuse_gap_scores(
        ats=ats,
        selected_cards=cards,
        per_card_raw=gap_polish["per_card"],
    )
    return {
        "result": {
            "per_card": fused["per_card"],
            "global_suggestions": gap_polish["global_suggestions"],
            "overall_score": fused["overall_score"],
            "match_level": fused["match_level"],
            "score_weights": fused["score_weights"],
        }
    }


def run_step2_workflow(
    job_analysis_id: int,
    card_ids: List[int],
) -> Dict[str, Any]:
    """Step 2: 缺口分析 + 润色建议。返回 {per_card, global_suggestions, ...}。"""
    workflow = StateGraph(Step2State)
    workflow.add_node("step2", _run_step2)
    workflow.add_edge(START, "step2")
    workflow.add_edge("step2", END)

    app = workflow.compile()
    initial_state: Step2State = {
        "job_analysis_id": job_analysis_id,
        "card_ids": card_ids,
        "result": None,
    }
    result = app.invoke(initial_state)
    return result.get("result", {})


# ============================================================
#  旧版完整岗位分析（兼容 /job/analyze）
# ============================================================


def _run_legacy_analysis(state: Dict[str, Any]) -> Dict[str, Any]:
    user_id = state["user_id"]
    company = state.get("company", "")
    position = state["position"]
    jd_text = state["jd_text"]
    card_ids = state["card_ids"]

    cards = []
    for cid in card_ids:
        c = db_tools.get_card(cid)
        if c and c.get("is_active"):
            cards.append(c)
    if not cards:
        raise ValueError("所选卡片均不可用")

    # 1. ATS 解析
    ats_out = JdAtsAgent().run({"jd_text": jd_text})
    ats = ATSProfile(**ats_out["ats"])
    jd_req = jobcraft_analyze._ats_to_jdreq(ats)

    # 2. LLM 语义评分
    sm_out = ScoreMatchAgent().run({"jd_req": jd_req.model_dump(), "cards": cards})
    llm_score_map = {
        cid: it.get("match", 0.0) for cid, it in sm_out["llm_match_items"].items()
    }

    # 3. 本地匹配融合
    match = jobcraft_analyze.compute_match(cards, jd_req, llm_scores=llm_score_map)

    # 4. 优化建议（Agent + 规则兜底）
    suggestions = SuggestionsResult()
    try:
        sug_out = SugAgent().run(
            {
                "jd_req": jd_req.model_dump(),
                "cards": cards,
                "per_card_scores": [pc.model_dump() for pc in match["per_card"]],
            }
        )
        suggestions = SuggestionsResult(**sug_out["suggestions"])
    except Exception as e:
        logger.warning("SugAgent 调用失败，使用规则兜底: %s", e)
        suggestions = jobcraft_analyze.build_rule_suggestions(jd_req, match["per_card"])

    # 5. 落库
    db_data = {
        "user_id": user_id,
        "company": company or "",
        "position": position or ats.job_title or "",
        "jd_text": jd_text,
        "jd_requirements": jd_req.model_dump(),
        "match_score": match["overall"],
        "gap_analysis": suggestions.gap_analysis or match["gap"],
        "dimension_requirements": [
            d.model_dump() for d in (ats.dimension_requirements or [])
        ],
    }
    job_id = db_tools.insert_job_analysis(db_data)

    # 6. 写关联 mapping
    for c in cards:
        db_tools.upsert_job_mapping(job_id, c["id"])

    # 7. 组装返回
    result = JobAnalysisResult(
        job_analysis_id=job_id,
        user_id=user_id,
        company=company or "",
        position=position or ats.job_title or "",
        jd_text=jd_text,
        jd_requirements=jd_req,
        ats_profile=ats,
        company_context=None,
        match_score=match["overall"],
        match_level=jobcraft_analyze._match_level(match["overall"]),
        customization_needed=match["overall"] < 75,
        gap_analysis=suggestions.gap_analysis or match["gap"],
        gap_items=suggestions.gap_items,
        per_card_scores=match["per_card"],
        suggestions=suggestions.suggestions,
        dimension_requirements=ats.dimension_requirements or [],
    )
    return {"result": result.model_dump()}


def run_job_analysis_workflow(
    user_id: int,
    company: str,
    position: str,
    jd_text: str,
    card_ids: List[int],
) -> Dict[str, Any]:
    """执行旧版完整岗位分析 Workflow，返回 JobAnalysisResult dict。"""
    workflow = StateGraph(JobAnalysisState)
    workflow.add_node("run_analysis", _run_legacy_analysis)
    workflow.add_edge(START, "run_analysis")
    workflow.add_edge("run_analysis", END)

    app = workflow.compile()
    initial_state: JobAnalysisState = {
        "user_id": user_id,
        "company": company,
        "position": position,
        "jd_text": jd_text,
        "card_ids": card_ids,
        "result": None,
    }
    result = app.invoke(initial_state)
    return result.get("result", {})


# ============================================================
#  仅 ATS 解析（/job/analyze-ats）
# ============================================================


def _run_ats_only(state: Dict[str, Any]) -> Dict[str, Any]:
    out = JdAtsAgent().run({"jd_text": state["jd_text"]})
    return {"result": out["ats"]}


def run_analyze_ats_workflow(jd_text: str) -> Dict[str, Any]:
    """仅 ATS 解析。返回 ATSProfile dict。"""
    workflow = StateGraph(ATSOnlyState)
    workflow.add_node("ats", _run_ats_only)
    workflow.add_edge(START, "ats")
    workflow.add_edge("ats", END)

    app = workflow.compile()
    initial_state: ATSOnlyState = {"jd_text": jd_text, "result": None}
    result = app.invoke(initial_state)
    return result.get("result", {})


# ============================================================
#  简历预览重新匹配（/job/{job_id}/resume-preview）
# ============================================================


def _run_resume_preview(state: Dict[str, Any]) -> Dict[str, Any]:
    job_id = state["job_id"]
    analysis = db_tools.get_job_analysis(job_id)
    if not analysis:
        raise ValueError(f"job_analysis #{job_id} 不存在")

    selected_ids = state.get("selected_card_ids") or []
    cards = []
    for cid in selected_ids:
        c = db_tools.get_card(cid)
        if c and c.get("is_active"):
            cards.append(c)
    if not cards:
        raise ValueError("无可用经历卡")

    jd_text = analysis.get("jd_text") or ""
    ats_out = JdAtsAgent().run({"jd_text": jd_text})
    ats = ATSProfile(**ats_out["ats"])
    jd_req = jobcraft_analyze._ats_to_jdreq(ats)

    sm_out = ScoreMatchAgent().run({"jd_req": jd_req.model_dump(), "cards": cards})
    llm_map = {
        cid: it.get("match", 0.0) for cid, it in sm_out["llm_match_items"].items()
    }
    match = jobcraft_analyze.compute_match(cards, jd_req, llm_scores=llm_map)

    from app.tools.jobcraft_resume_gen import generate_resume_markdown

    md = generate_resume_markdown(
        user_id=analysis.get("user_id", 1),
        company=analysis.get("company", ""),
        position=analysis.get("position", ""),
        jd_text=jd_text,
        ats=ats,
        company_ctx=None,
        cards=cards,
        per_card_scores=match["per_card"],
        suggestions=[],
        gap_items=[],
    )
    return {
        "result": {
            "job_analysis_id": job_id,
            "resume_markdown": md,
            "match_score": match["overall"],
            "ats_profile": ats.model_dump(),
        }
    }


def run_resume_preview_workflow(
    job_id: int,
    selected_card_ids: List[int],
) -> Dict[str, Any]:
    """简历预览重新匹配。返回 {job_analysis_id, resume_markdown, match_score, ats_profile}。"""
    workflow = StateGraph(ResumePreviewState)
    workflow.add_node("preview", _run_resume_preview)
    workflow.add_edge(START, "preview")
    workflow.add_edge("preview", END)

    app = workflow.compile()
    initial_state: ResumePreviewState = {
        "job_id": job_id,
        "selected_card_ids": selected_card_ids,
        "result": None,
    }
    result = app.invoke(initial_state)
    return result.get("result", {})
