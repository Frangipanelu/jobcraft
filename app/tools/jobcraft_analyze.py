"""
岗位分析纯函数模块（无 LLM 调用）

提供本地关键词匹配、缺口分析与 LLM 分数融合等纯函数。
LLM 语义评分 / 优化建议 / 缺口润色等逻辑由 app/agents/ 下各 Agent 负责。
"""

import re
from typing import Any, Dict, List, Optional


from app.schemas.jobcraft import (
    ATSProfile,
    CapabilityGap,
    JDRequirements,
    PerCardScore,
    SuggestionItem,
    SuggestionsResult,
)
from app.tools.card_render import get_card_render_text


def _fuse_score(local: float, llm: float) -> float:
    """确定性融合：取 local 与 llm 的较大者。

    :param local: 本地关键词匹配分（0-100）
    :param llm: LLM 语义分（0-100）
    :return: 融合分（0-100）
    """
    return round(max(float(local), float(llm)), 1)


def _normalize(term: str) -> str:
    """归一化术语用于匹配"""
    return re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", term).lower()


def _card_text_blob(card: Dict[str, Any]) -> str:
    """
    把经历卡文本拼成一段，用于关键词匹配（收敛至 get_card_render_text，纯文本+tags）。

    匹配源优先级：
      1. ai_structured.achievements（S/A/R 拼接，结构清晰）
      2. raw_text（用户原始文本）
      3. tags（扁平标签，作为补充）
    """
    return get_card_render_text(card, include_tags=True)


def _match_term_to_blob(term: str, blob: str, tags_norm: set) -> int:
    """
    单个术语与经历卡文本的匹配得分
    :return: 0/1/2 (未命中/文本命中/tag命中)
    """
    term_norm = _normalize(term)
    if not term_norm:
        return 0
    blob_norm = _normalize(blob)
    # tag 精确匹配权重更高
    if term_norm in tags_norm:
        return 2
    if term_norm in blob_norm:
        return 1
    # 子串匹配（2 字符以上）
    if len(term_norm) >= 2 and term_norm in blob_norm:
        return 1
    return 0


def _ats_to_jdreq(ats: ATSProfile) -> JDRequirements:
    """把 ATSProfile 转成 JDRequirements（供匹配使用）"""
    return JDRequirements(
        position_title=ats.job_title or "",
        hard_skills=ats.required_skills or [],
        soft_skills=ats.preferred_skills or [],
        keywords=(ats.required_skills or []) + (ats.culture_keywords or []),
        nice_to_have=ats.preferred_skills or [],
        responsibilities=ats.responsibilities or [],
        dimension_requirements=ats.dimension_requirements or [],
    )


def _local_score(
    card: Dict[str, Any], jd_req: JDRequirements
) -> tuple[float, List[str], List[str]]:
    """
    本地关键词匹配：计算单张卡的命中分与命中/缺失术语

    :param card: 经历卡 dict
    :param jd_req: JD 需求
    :return: (local_pct, matched, missing)
    """
    all_terms = set(jd_req.hard_skills + jd_req.soft_skills + jd_req.keywords)
    blob = _card_text_blob(card)
    tags_norm = {_normalize(t) for t in (card.get("tags") or [])}
    matched: List[str] = []
    missing: List[str] = []
    local_score = 0.0
    for term in all_terms:
        s = _match_term_to_blob(term, blob, tags_norm)
        if s > 0:
            matched.append(term)
            local_score += s * 10
        else:
            missing.append(term)
    local_max = max(len(all_terms) * 10, 1)
    local_pct = round(min(100, local_score / local_max * 100), 1)
    return local_pct, matched, missing


def compute_match(
    cards: List[Dict[str, Any]],
    jd_req: JDRequirements,
    llm_scores: Optional[Dict[int, float]] = None,
) -> Dict[str, Any]:
    """
    本地关键词匹配 + LLM 评分融合

    :return: {"overall": float, "per_card": [PerCardScore, ...], "gap": str}
    """
    per_card: List[PerCardScore] = []
    total_score = 0.0

    for card in cards:
        local_pct, matched, missing = _local_score(card, jd_req)
        # 融合 LLM 评分（max：local 只抬升不拉低）
        llm_pct = llm_scores.get(card["id"], 0.0) if llm_scores else 0.0
        final_score = _fuse_score(local_pct, llm_pct)

        total_score += final_score
        per_card.append(
            PerCardScore(
                card_id=card["id"],
                score=final_score,
                local_score=local_pct,
                llm_score=round(llm_pct, 1),
                matched=matched,
                missing=missing,
            )
        )

    overall = round(total_score / max(len(cards), 1), 1)
    gap = _build_gap_text(jd_req, per_card)
    return {"overall": overall, "per_card": per_card, "gap": gap}


def _build_gap_text(jd_req: JDRequirements, per_card: List[PerCardScore]) -> str:
    """根据匹配结果生成缺口描述"""
    all_terms = set(jd_req.hard_skills + jd_req.soft_skills + jd_req.keywords)
    covered = set()
    for pc in per_card:
        covered.update(pc.matched)
    missing = list(all_terms - covered)
    if not missing:
        return "经历卡已较好覆盖岗位要求。"
    return f"经历卡在以下要求上覆盖较弱：{', '.join(missing[:8])}。建议补充相关项目或调整表述。"


def _match_level(score: float) -> str:
    """按综合得分判定匹配等级（job_analysis_flow 使用）。"""
    if score >= 80:
        return "高度匹配"
    if score >= 60:
        return "基本匹配"
    if score >= 40:
        return "部分匹配"
    return "匹配度低"


def build_rule_capability_gaps(
    jd_req: JDRequirements,
    per_card_scores: List[PerCardScore],
) -> List[CapabilityGap]:
    """规则兜底：无 LLM 时确定性产出能力缺口任务清单（T-M4-2 / Q3）。

    口径：dimension_requirements × per_card_scores 覆盖的结构化 join——
    维度证据与已命中术语有交集 → 已覆盖不产缺口；未覆盖维度产
    evidence/missing 缺口（仅 B 类 weak 无法规则判定，规则只产 A 类）；
    未命中且不归属任何维度的术语归 EXT 扩展码（Q3-a）。

    :param jd_req: JD 需求（含 dimension_requirements）。
    :param per_card_scores: 逐卡评分（提供 matched 覆盖事实）。
    :return: 缺口列表（维度缺口在前，EXT 在后，至多 50 条）。
    """
    if not per_card_scores:
        return []
    covered: set = set()
    for pc in per_card_scores:
        covered.update(pc.matched)
    covered_norm = {t for t in (_normalize(x) for x in covered) if t}

    gaps: List[CapabilityGap] = []
    dim_requirements = jd_req.dimension_requirements or []
    evidence_blob = _normalize(" ".join((d.evidence or "") for d in dim_requirements))
    for d in dim_requirements:
        evidence = (d.evidence or "").strip()
        if not evidence or not _normalize(evidence):
            continue
        if any(t in _normalize(evidence) for t in covered_norm):
            continue
        gaps.append(
            CapabilityGap(
                dimension=d.dimension,
                kind="evidence",
                status="missing",
                severity="high" if d.level >= 4 else "medium",
                jd_evidence=evidence,
                rewrite_hint=f"围绕「{evidence[:40]}」补充可量化经历，或改写相关经历卡表述",
            )
        )

    all_terms = list(
        dict.fromkeys(jd_req.hard_skills + jd_req.soft_skills + jd_req.keywords)
    )
    ext_terms = [
        t
        for t in all_terms
        if t not in covered and _normalize(t) and _normalize(t) not in evidence_blob
    ][:6]
    for term in ext_terms:
        gaps.append(
            CapabilityGap(
                dimension="EXT",
                kind="evidence",
                status="missing",
                severity="medium",
                jd_evidence=term,
                rewrite_hint=f"补充或改写一条能体现「{term}」的经历",
            )
        )
    return gaps[:50]


def build_rule_suggestions(
    jd_req: JDRequirements,
    per_card_scores: List[PerCardScore],
) -> SuggestionsResult:
    """规则兜底：根据匹配结果生成建议（无 LLM），供 Agent 失败时使用。"""
    if not per_card_scores:
        return SuggestionsResult(gap_analysis="", gap_items=[], suggestions=[])

    suggestions: List[SuggestionItem] = []
    gap_items: List[str] = []
    all_terms = set(jd_req.hard_skills + jd_req.soft_skills + jd_req.keywords)
    covered = set()
    for pc in per_card_scores:
        covered.update(pc.matched)
        if pc.score < 50:
            suggestions.append(
                SuggestionItem(
                    card_id=pc.card_id,
                    type="gap",
                    message=f"卡片 #{pc.card_id} 与岗位匹配度较低 ({pc.score}分)，建议补充与岗位相关的关键词。",
                    priority=4,
                )
            )
    missing = list(all_terms - covered)
    if missing:
        gap_items = missing[:8]
        suggestions.append(
            SuggestionItem(
                type="supplement",
                message=f"建议补充能体现 {'、'.join(missing[:5])} 的经历或项目。",
                priority=5,
            )
        )

    return SuggestionsResult(
        gap_analysis=_build_gap_text(jd_req, per_card_scores),
        gap_items=gap_items,
        suggestions=suggestions,
        capability_gaps=build_rule_capability_gaps(jd_req, per_card_scores),
    )
