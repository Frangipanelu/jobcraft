"""
岗位分析纯函数模块（无 LLM 调用）

提供本地关键词匹配、缺口分析、匹配等级判定与 LLM 分数融合等纯函数。
LLM 语义评分 / 优化建议 / 缺口润色等逻辑由 app/agents/ 下各 Agent 负责。
"""

import re
from typing import Any, Dict, List, Optional


from app.schemas.jobcraft import (
    ATSProfile,
    JDRequirements,
    PerCardScore,
    SuggestionItem,
    SuggestionsResult,
)

LOCAL_WEIGHT = 0.4
LLM_WEIGHT = 0.6


def _normalize(term: str) -> str:
    """归一化术语用于匹配"""
    return re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", term).lower()


def _card_text_blob(card: Dict[str, Any]) -> str:
    """
    把经历卡文本拼成一段，用于关键词匹配。

    匹配源优先级：
      1. ai_structured.achievements（S/A/R 拼接，结构清晰）
      2. raw_text（用户原始文本）
      3. tags（扁平标签，作为补充）
    """
    parts = []
    ai_struct = card.get("ai_structured")
    if ai_struct and isinstance(ai_struct, dict):
        achievements = ai_struct.get("achievements") or []
        if achievements:
            for ach in achievements:
                if ach.get("situation"):
                    parts.append(str(ach["situation"]))
                if ach.get("action") and isinstance(ach["action"], dict):
                    if ach["action"].get("main"):
                        parts.append(str(ach["action"]["main"]))
                    if ach["action"].get("difficulty"):
                        parts.append(str(ach["action"]["difficulty"]))
                    if ach["action"].get("resolution"):
                        parts.append(str(ach["action"]["resolution"]))
                if ach.get("result"):
                    parts.append(str(ach["result"]))
            tags = card.get("tags") or []
            parts.extend([str(t) for t in tags])
            return " ".join(parts)
    # fallback: raw_text
    raw = card.get("raw_text") or card.get("content") or ""
    if raw:
        parts.append(raw)
    tags = card.get("tags") or []
    parts.extend([str(t) for t in tags])
    return " ".join(parts)


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
        # 融合 LLM 评分
        llm_pct = llm_scores.get(card["id"], 0.0) if llm_scores else 0.0
        final_score = round(local_pct * LOCAL_WEIGHT + llm_pct * LLM_WEIGHT, 1)

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
    if score >= 80:
        return "高度匹配"
    if score >= 60:
        return "基本匹配"
    if score >= 40:
        return "部分匹配"
    return "匹配度低"


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
    )


def fuse_gap_scores(
    ats: ATSProfile,
    selected_cards: List[Dict[str, Any]],
    per_card_raw: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    融合本地关键词分（40%）与 LLM 语义分（60%），产出最终缺口分析结果。

    :param ats: ATS 岗位画像
    :param selected_cards: 用户勾选的经历卡
    :param per_card_raw: GapPolishAgent 返回的 per_card 列表（含 LLM 原始 score）
    :return: {"per_card": [...], "global_suggestions": [...],
              "overall_score": float, "match_level": str, "score_weights": {...}}
    """
    jd_req = _ats_to_jdreq(ats)
    card_by_id = {c["id"]: c for c in selected_cards}
    per_card_out: List[Dict[str, Any]] = []
    for p in per_card_raw:
        llm_score = round(float(p.get("score") or 0.0), 1)
        card = card_by_id.get(p.get("card_id"))
        local_score = _local_score(card, jd_req)[0] if card else 0.0
        final_score = round(local_score * LOCAL_WEIGHT + llm_score * LLM_WEIGHT, 1)
        per_card_out.append(
            {
                **p,
                "score": final_score,
                "local_score": local_score,
                "llm_score": llm_score,
            }
        )

    overall_score = round(
        sum(pc["score"] for pc in per_card_out) / max(len(per_card_out), 1), 1
    )

    return {
        "per_card": per_card_out,
        "overall_score": overall_score,
        "match_level": _match_level(overall_score),
        "score_weights": {"local": LOCAL_WEIGHT, "llm": LLM_WEIGHT},
    }
