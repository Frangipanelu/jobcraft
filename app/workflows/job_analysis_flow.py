"""
岗位分析 Workflow

- run_job_analysis_workflow: 完整分析（4 节点：ATS → 语义评分 → 建议 → 落库，每节点 1 次 LLM）；
  可选 duties/requirements 结构化注入（T-M4-1 / Q2 裁决 C）
- run_structured_job_analysis_workflow: 结构化前端分析（跳过 structurer，
  注入 §14.2 结构化状态跑完整 4 节点，产出真实 job_analysis_id 与 match 字段）
- run_structured_ats_split: 把粘贴的原始 JD 拆成结构化块（职责/要求，含 preferred 分流）
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.jd_ats_agent import (
    JdAtsAgent,
    _structured_to_text,
    analyze_structured_jd,
)
from app.agents.score_match_agent import ScoreMatchAgent
from app.agents.sug_agent import SugAgent
from app.schemas.jobcraft import (
    ATSProfile,
    JobAnalysisResult,
    StructuredRequirementItem,
    SuggestionsResult,
)
from app.tools import db_job_entity, db_raw_jd, db_tools, jobcraft_analyze

logger = logging.getLogger(__name__)

# P4-1：分析产物版本标记（Prompt 版本化，AGENTS §7）。
# 落库到 job_analysis.analysis_version，供历史分析回溯「哪一版分析逻辑产出」。
ANALYSIS_VERSION = "v1"


class JobAnalysisState(TypedDict):
    user_id: int
    company: str
    position: str
    jd_text: str
    # 结构化注入（T-M4-1）：两者为 None 时走原文 ats 节点，否则走结构化注入节点
    duties: Optional[List[str]]
    requirements: Optional[List[StructuredRequirementItem]]
    card_ids: List[int]
    cards: List[Dict[str, Any]]
    ats: Optional[Any]
    jd_req: Optional[Any]
    match: Optional[Dict[str, Any]]
    suggestions: Optional[Any]
    result: Optional[Dict[str, Any]]


# ============================================================
#  旧版完整岗位分析（兼容 /job/analyze，拆为 4 节点，每节点 1 次 LLM）
# ============================================================


def _load_cards(user_id: int, card_ids: List[int]) -> List[Dict[str, Any]]:
    """加载所选经历卡并挂载当前激活表达（ats 节点共用，原文/结构化两路同语义）。

    :param user_id: 当前用户 id。
    :param card_ids: 所选经历卡 id 列表。
    :return: 可用卡片列表（is_active）。
    :raises ValueError: 所选卡片均不可用。
    """
    cards: List[Dict[str, Any]] = []
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
    if not cards:
        raise ValueError("所选卡片均不可用")
    return cards


def _run_legacy_ats(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点 1：加载卡片 + ATS 解析（1 次 LLM，原文 jd_text 路径）。"""
    cards = _load_cards(state["user_id"], state["card_ids"])
    ats_out = JdAtsAgent().run({"jd_text": state["jd_text"]})
    ats = ATSProfile(**ats_out["ats"])
    return {"cards": cards, "ats": ats, "jd_req": jobcraft_analyze._ats_to_jdreq(ats)}


def _run_structured_full_ats(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点 1（结构化注入，T-M4-1 / Q2 裁决 C）：加载卡片 + 结构化 ATS 解析。

    跳过 structurer（用户已在表单拆分，_build_structured_from_input 按
    hard/required/preferred 标签确定性入桶，classifier 不覆盖用户标签）；
    3 档标签经 required/preferred 桶作评分与建议的 priority 初值。
    """
    cards = _load_cards(state["user_id"], state["card_ids"])
    out = analyze_structured_jd(
        duties=state.get("duties") or [],
        requirements=state.get("requirements") or [],
    )
    ats = ATSProfile(**out["ats"])
    return {"cards": cards, "ats": ats, "jd_req": jobcraft_analyze._ats_to_jdreq(ats)}


def _run_legacy_score(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点 2：LLM 语义评分 + 本地融合（1 次 LLM，融合为确定性计算）。"""
    sm_out = ScoreMatchAgent().run(
        {"jd_req": state["jd_req"].model_dump(), "cards": state["cards"]}
    )
    llm_score_map = {
        cid: it.get("match", 0.0) for cid, it in sm_out["llm_match_items"].items()
    }
    return {
        "match": jobcraft_analyze.compute_match(
            state["cards"], state["jd_req"], llm_scores=llm_score_map
        )
    }


def _run_legacy_suggestions(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点 3：优化建议（1 次 LLM + 规则兜底）。"""
    suggestions = SuggestionsResult()
    try:
        sug_out = SugAgent().run(
            {
                "jd_req": state["jd_req"].model_dump(),
                "cards": state["cards"],
                "per_card_scores": [
                    pc.model_dump() for pc in state["match"]["per_card"]
                ],
            }
        )
        suggestions = SuggestionsResult(**sug_out["suggestions"])
    except Exception as e:
        logger.warning("SugAgent 调用失败，使用规则兜底: %s", e)
        suggestions = jobcraft_analyze.build_rule_suggestions(
            state["jd_req"], state["match"]["per_card"]
        )
    return {"suggestions": suggestions}


def _run_legacy_collate(state: Dict[str, Any]) -> Dict[str, Any]:
    """节点 4：落库 + 组装返回（无 LLM，纯确定性）。"""
    ats = state["ats"]
    jd_req = state["jd_req"]
    match = state["match"]
    suggestions = state["suggestions"]
    cards = state["cards"]
    company = state.get("company", "")
    position = state["position"]
    jd_text = state["jd_text"]
    match_level = jobcraft_analyze._match_level(match["overall"])

    db_data = {
        "user_id": state["user_id"],
        "company": company,
        "position": position or ats.job_title or "",
        "jd_text": jd_text,
        "jd_requirements": jd_req.model_dump(),
        "match_score": match["overall"],
        "gap_analysis": suggestions.gap_analysis or match["gap"],
        "dimension_requirements": [
            d.model_dump() for d in (ats.dimension_requirements or [])
        ],
        # P4-1：分析物随插入落库（V0011 五列），历史列表/单条读取不再退化为空壳
        "ats_profile": ats.model_dump(),
        "suggestions": [s.model_dump() for s in (suggestions.suggestions or [])],
        "per_card_scores": [pc.model_dump() for pc in (match["per_card"] or [])],
        "match_level": match_level,
        "analysis_version": ANALYSIS_VERSION,
    }
    job_id = db_tools.insert_job_analysis(db_data)

    # P4-2：原始 JD 以不可变快照入库（raw_jd），权威原文以此为准；
    # job_analysis.jd_text 仅作展示副本，后续不再被覆写。
    # 快照写入失败不阻断分析（辅助链路，降级告警）。
    try:
        raw_jd_id = db_raw_jd.insert_raw_jd(
            jd_text=jd_text,
            user_id=state["user_id"],
            job_analysis_id=job_id,
            source="job_analysis",
        )
    except Exception as e:
        logger.warning("RawJD 快照写入失败（分析已落库，快照缺失）: %s", e)
        raw_jd_id = None
    # P4-4a：快照 id 回链 Job 实体，使岗位直接持有权威原文（失败仅告警）
    if raw_jd_id:
        try:
            db_job_entity.link_raw_jd_by_analysis(job_id, raw_jd_id)
        except Exception as e:
            logger.warning("RawJD 快照回链岗位失败（analysis_id=%s）: %s", job_id, e)

    for c in cards:
        db_tools.upsert_job_mapping(job_id, c["id"])

    result = JobAnalysisResult(
        job_analysis_id=job_id,
        user_id=state["user_id"],
        company=company,
        position=position or ats.job_title or "",
        jd_text=jd_text,
        jd_requirements=jd_req,
        ats_profile=ats,
        company_context=None,
        match_score=match["overall"],
        match_level=match_level,
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
    duties: Optional[List[str]] = None,
    requirements: Optional[List[StructuredRequirementItem]] = None,
) -> Dict[str, Any]:
    """执行完整岗位分析 Workflow，返回 JobAnalysisResult dict。

    拆为 ats → score → suggestions → collate 四节点，每节点最多 1 次 LLM 调用
    （AGENTS.md §1.2.5：单节点内不循环、不递归）。

    :param duties: 结构化注入（T-M4-1）：岗位职责列表；与 requirements 同时
        提供时 ats 节点走结构化分支（跳过 structurer），否则走原文分支。
    :param requirements: 结构化注入：任职要求列表（含 hard/required/preferred 标签）。
    """
    workflow = StateGraph(JobAnalysisState)
    structured = duties is not None or requirements is not None
    ats_node = "_run_structured_full_ats" if structured else "_run_legacy_ats"
    workflow.add_node(
        ats_node,
        _run_structured_full_ats if structured else _run_legacy_ats,
    )
    workflow.add_node("_run_legacy_score", _run_legacy_score)
    workflow.add_node("_run_legacy_suggestions", _run_legacy_suggestions)
    workflow.add_node("_run_legacy_collate", _run_legacy_collate)
    workflow.add_edge(START, ats_node)
    workflow.add_edge(ats_node, "_run_legacy_score")
    workflow.add_edge("_run_legacy_score", "_run_legacy_suggestions")
    workflow.add_edge("_run_legacy_suggestions", "_run_legacy_collate")
    workflow.add_edge("_run_legacy_collate", END)

    app = workflow.compile()
    initial_state: JobAnalysisState = {
        "user_id": user_id,
        "company": company,
        "position": position,
        "jd_text": jd_text,
        "duties": duties,
        "requirements": requirements,
        "card_ids": card_ids,
        "cards": [],
        "ats": None,
        "jd_req": None,
        "match": None,
        "suggestions": None,
        "result": None,
    }
    result = app.invoke(initial_state)
    return result.get("result", {})


# ============================================================
#  结构化 JD 分析（前端已分好 duties/requirements + 标签）
# ============================================================


def run_structured_job_analysis_workflow(
    user_id: int,
    company: str,
    position: str,
    duties: List[str],
    requirements: List[StructuredRequirementItem],
    card_ids: List[int],
) -> Dict[str, Any]:
    """结构化 JD 完整分析 Workflow（T-M4-1 / Q2 裁决 C）。

    结构化字段注入 job_analysis_flow §14.2 结构化状态后 4 节点照跑：

    - 跳过 structurer（用户已在表单拆分，标签即事实，classifier 不覆盖）；
    - 3 档标签经 required/preferred 桶作评分与建议的 priority 初值；
    - score/suggestions/collate 与原文路径共用，落库产出真实
      job_analysis_id 与 match 字段（FE-JD-REPORT-01 根因修复，
      前端降级展示自此仅作兜底）。

    :param user_id: 当前用户 id。
    :param company: 公司名称。
    :param position: 岗位名称（空则回落 ATS 岗位名）。
    :param duties: 岗位职责逐条。
    :param requirements: 任职要求逐条（含 hard/required/preferred 标签）。
    :param card_ids: 所选经历卡 id 列表（至少 1 张）。
    :return: JobAnalysisResult dict（与 /job/analyze 同构）。
    :raises ValueError: 卡片不可用等入参问题。
    """
    jd_text = _structured_to_text(duties, requirements)
    return run_job_analysis_workflow(
        user_id=user_id,
        company=company,
        position=position,
        jd_text=jd_text,
        card_ids=card_ids,
        duties=duties,
        requirements=requirements,
    )


def prepare_structured_jd(
    duties: List[Any],
    requirements: List[Any],
) -> Tuple[List[str], List[StructuredRequirementItem]]:
    """结构化 JD 入口清洗与校验（API 与异步任务共用，BE-TASKDIV-01）。

    清洗空文本条目；tag 仅允许 hard/required/preferred，非法即 ValueError
    （不再静默丢弃）；职责与任职要求不能同时为空。

    :param duties: 岗位职责文本列表
    :param requirements: 每项含 text 与可选 tag 的映射
    :return: (清洗后的 duties, StructuredRequirementItem 列表)
    :raises ValueError: 非法标签或两者同时为空
    """
    clean_duties = [str(d).strip() for d in duties if d and str(d).strip()]
    reqs: List[Dict[str, str]] = []
    for r in requirements:
        text = str(r.get("text", "")).strip()
        if not text:
            continue
        tag = str(r.get("tag", "required")).strip().lower()
        if tag not in ("hard", "required", "preferred"):
            raise ValueError(f"标签 {tag} 非法，仅支持 hard/required/preferred")
        reqs.append({"text": text, "tag": tag})
    if not clean_duties and not reqs:
        raise ValueError("岗位职责与任职要求不能同时为空")
    return clean_duties, [StructuredRequirementItem(**r) for r in reqs]


def run_structured_ats_split(jd_text: str) -> Dict[str, Any]:
    """把粘贴的原始 JD 文本拆分为结构化块，供前端表单预填。

    duties ← 职责区块；requirements ← 任职要求区块（含"优先/加分/尤佳"
    标记的进 preferred 标签；从官方语料看硬性要求常直接出现在任职要求中，
    此处保留原文不拆，由结构化标签在分析时区分）。

    :param jd_text: 从招聘网站复制的原始 JD 全文。
    :return: {"duties": [str], "requirements": [{"text": str, "tag": str}]}。
    """
    from app.pipeline.jd_extractor import _PREF_TAIL_RE
    from app.pipeline.jd_structurer import SectionKind, structure_jd

    doc = structure_jd(jd_text)
    duties: List[str] = []
    requirements: List[str] = []
    preferred: List[str] = []
    for item in doc.items:
        text = (item.text or "").strip()
        if not text:
            continue
        if item.section is SectionKind.RESPONSIBILITIES:
            duties.append(text)
        elif item.section is SectionKind.REQUIREMENTS:
            if _PREF_TAIL_RE.search(text):
                preferred.append(text)
            else:
                requirements.append(text)
        elif item.section is SectionKind.PREFERRED:
            preferred.append(text)
    req_out = [{"text": t, "tag": "required"} for t in requirements]
    req_out += [{"text": t, "tag": "preferred"} for t in preferred]
    return {"duties": duties, "requirements": req_out}
