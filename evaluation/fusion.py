"""
Hybrid 融合权重实验的纯函数模块（确定性离线融合）.

实验目标：回答 "Local signal 是否给语义匹配增加价值"，
而非证明某个权重更好。因此 A/B/C 三个变体必须在**同一份 LLM 分数**上
做确定性融合，隔离 LLM 非确定性这一变量。

变体定义：
- hybrid_a (weighted 0.4/0.6): 现状 Local 40% + LLM 60%
- hybrid_b (weighted 0.2/0.8): LLM-heavy，降低 Local 权重
- hybrid_c (max): max(Local, LLM)，Local 只在不抢跑时抬升

所有函数为纯函数，无 LLM 调用，可直接单测。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.tools.jobcraft_analyze import _local_score

from evaluation.strategies import (
    _experiences_to_cards,
    _job_to_jd_req,
    score_to_relevance,
)

logger = logging.getLogger("jobcraft.evaluation.fusion")

# 变体名称 -> (mode, local_weight, llm_weight)；max 模式忽略权重
FUSION_MODES: Dict[str, tuple[str, float, float]] = {
    "hybrid_a": ("weighted", 0.4, 0.6),
    "hybrid_b": ("weighted", 0.2, 0.8),
    "hybrid_c": ("max", 0.0, 0.0),
}


def local_scores_for_case(case: Dict[str, Any]) -> Dict[str, float]:
    """计算一条 gold case 内每段经历的本地关键词分数（确定性）。

    :param case: gold case dict
    :return: {experience_id: local_pct}
    """
    jd_req = _job_to_jd_req(case["job"])
    cards = _experiences_to_cards(case["experiences"])
    scores = {}
    for card in cards:
        local_pct, _matched, _missing = _local_score(card, jd_req)
        scores[card.get("exp_id") or card["id"]] = float(local_pct)
    return scores


def fused_score(
    local: float, llm: float, local_weight: float, llm_weight: float
) -> float:
    """加权融合：local * local_weight + llm * llm_weight。"""
    return round(float(local) * local_weight + float(llm) * llm_weight, 1)


def max_score(local: float, llm: float) -> float:
    """Max 融合：取两者较大者，Local 只在该值更高时生效。"""
    return round(max(float(local), float(llm)), 1)


def generate_fused(
    llm_pred: Dict[str, Any], case: Dict[str, Any], mode: str
) -> List[Dict[str, Any]]:
    """在共享的 LLM 预测上融合本地分，生成该 case 的融合预测。

    :param llm_pred: 该 case 的 LLM 预测 {"case_id", "predictions": [...]}
    :param case: gold case dict（用于计算本地分）
    :param mode: hybrid_a / hybrid_b / hybrid_c
    :return: [{"experience_id", "label", "score"}, ...]
    """
    if mode not in FUSION_MODES:
        raise ValueError(f"未知融合模式: {mode}，可选 {list(FUSION_MODES)}")
    mode_name, local_w, llm_w = FUSION_MODES[mode]

    local_scores = local_scores_for_case(case)
    predictions = []
    for item in llm_pred.get("predictions", []):
        exp_id = item["experience_id"]
        llm_score = float(item.get("score") or 0.0)
        local_score = local_scores.get(exp_id, 0.0)
        if mode_name == "max":
            score = max_score(local_score, llm_score)
        else:
            score = fused_score(local_score, llm_score, local_w, llm_w)
        predictions.append(
            {
                "experience_id": exp_id,
                "label": score_to_relevance(score),
                "score": score,
            }
        )
    return predictions
