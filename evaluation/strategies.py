"""
三种匹配策略的预测生成器（Experience Matching Evaluation）.

针对远端 model-agnostic 评估器（run_matching_eval.py）的输入格式，
每种策略把一条 gold case（1 岗位 + 多经历）映射为统一预测：
{"case_id": "...", "predictions": [{"experience_id": "...", "label": "...", "score": ...}, ...]}

策略复用现有生产代码：
- Keyword: app.tools.jobcraft_analyze._local_score（纯本地关键词匹配）
- LLM: app.agents.score_match_agent.ScoreMatchAgent（LLM 语义匹配，每 case 一次 LLM 调用）
- Hybrid: keyword × 0.4 + LLM × 0.6（与 fuse_gap_scores 权重一致）
"""

import logging
from typing import Any, Dict, List

from app.agents.score_match_agent import ScoreMatchAgent
from app.schemas.jobcraft import JDRequirements
from app.tools.jobcraft_analyze import (
    LOCAL_WEIGHT,
    LLM_WEIGHT,
    _local_score,
)

logger = logging.getLogger("jobcraft.evaluation.strategies")

# relevance 分级对应 score 阈值（与 _match_level 80/60/40 对齐）
_RELEVANCE_BY_SCORE: List[tuple[float, str]] = [
    (80.0, "high"),
    (60.0, "medium"),
    (40.0, "low"),
]


def score_to_relevance(score: float) -> str:
    """把 0-100 分数映射为 relevance 分级（high/medium/low/irrelevant）。"""
    for threshold, label in _RELEVANCE_BY_SCORE:
        if score >= threshold:
            return label
    return "irrelevant"


def _job_to_jd_req(job: Dict[str, Any]) -> JDRequirements:
    """把 gold case 的 job 字段转为 JDRequirements（硬技能与关键词取 requirements）。"""
    requirements = job.get("requirements") or []
    return JDRequirements(
        position_title=job.get("title", ""),
        hard_skills=list(requirements),
        soft_skills=[],
        keywords=list(requirements),
        responsibilities=job.get("responsibilities") or [],
    )


def _experiences_to_cards(experiences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """把 gold case 的 experiences 列表转为经历卡（使用整数 card id，附带 exp_id）。"""
    cards = []
    for exp in experiences:
        cards.append(
            {
                "id": len(cards),
                "exp_id": exp.get("id"),
                "title": exp.get("title", ""),
                "raw_text": exp.get("raw_text", ""),
                "tags": exp.get("tags") or [],
                "summary": exp.get("title", ""),
            }
        )
    return cards


class BaseStrategy:
    """策略基类：输入一条 gold case，输出该 case 的预测列表。"""

    name: str = ""

    def predict_case(self, case: Dict[str, Any]) -> List[Dict[str, Any]]:
        """对单条 case 生成预测。

        :param case: gold case dict
        :return: [{"experience_id", "label", "score"}, ...]
        """
        raise NotImplementedError

    def _card_score(self, card: Dict[str, Any], jd_req: JDRequirements) -> float:
        """单张经历卡的打分（策略内实现）。"""
        raise NotImplementedError

    def _finalize(
        self,
        cards: List[Dict[str, Any]],
        card_scores: Dict[int, float],
    ) -> List[Dict[str, Any]]:
        """把 card 分数映射回 experience_id，并附加 relevance 标签。"""
        predictions = []
        for card in cards:
            score = float(card_scores.get(card["id"], 0.0))
            predictions.append(
                {
                    "experience_id": card.get("exp_id") or card["id"],
                    "label": score_to_relevance(score),
                    "score": round(score, 1),
                }
            )
        return predictions


class KeywordStrategy(BaseStrategy):
    """Keyword: 复用 _local_score 纯关键词匹配。"""

    name = "keyword"

    def _card_score(self, card: Dict[str, Any], jd_req: JDRequirements) -> float:
        local_pct, _matched, _missing = _local_score(card, jd_req)
        return local_pct

    def predict_case(self, case: Dict[str, Any]) -> List[Dict[str, Any]]:
        jd_req = _job_to_jd_req(case["job"])
        cards = _experiences_to_cards(case["experiences"])
        card_scores = {card["id"]: self._card_score(card, jd_req) for card in cards}
        return self._finalize(cards, card_scores)


class LLMStrategy(BaseStrategy):
    """LLM: 复用 ScoreMatchAgent 做语义匹配（每 case 一次 LLM 调用）。"""

    name = "llm"

    def _card_score(self, card: Dict[str, Any], jd_req: JDRequirements) -> float:
        raise NotImplementedError("LLM 策略按 case 整体调用，请使用 predict_case")

    def predict_case(self, case: Dict[str, Any]) -> List[Dict[str, Any]]:
        jd_req = _job_to_jd_req(case["job"])
        cards = _experiences_to_cards(case["experiences"])
        agent = ScoreMatchAgent()
        result = agent.run({"jd_req": jd_req.model_dump(), "cards": cards})
        items = result.get("llm_match_items") or {}
        card_scores = {}
        for card in cards:
            item = items.get(card["id"])
            card_scores[card["id"]] = float(item.get("match") or 0.0) if item else 0.0
        return self._finalize(cards, card_scores)


class HybridStrategy(BaseStrategy):
    """Hybrid: keyword × 0.4 + LLM × 0.6（与 fuse_gap_scores 权重一致）。"""

    name = "hybrid"

    def _card_score(self, card: Dict[str, Any], jd_req: JDRequirements) -> float:
        raise NotImplementedError("混合策略按 case 整体调用，请使用 predict_case")

    def predict_case(self, case: Dict[str, Any]) -> List[Dict[str, Any]]:
        jd_req = _job_to_jd_req(case["job"])
        cards = _experiences_to_cards(case["experiences"])

        local_scores: Dict[int, float] = {}
        for card in cards:
            local_pct, _matched, _missing = _local_score(card, jd_req)
            local_scores[card["id"]] = local_pct

        agent = ScoreMatchAgent()
        result = agent.run({"jd_req": jd_req.model_dump(), "cards": cards})
        items = result.get("llm_match_items") or {}

        card_scores: Dict[int, float] = {}
        for card in cards:
            llm_match = 0.0
            item = items.get(card["id"])
            if item:
                llm_match = float(item.get("match") or 0.0)
            fused = local_scores[card["id"]] * LOCAL_WEIGHT + llm_match * LLM_WEIGHT
            card_scores[card["id"]] = fused
        return self._finalize(cards, card_scores)


def get_strategy(name: str) -> BaseStrategy:
    """按名称返回策略实例。"""
    strategies = {
        "keyword": KeywordStrategy,
        "llm": LLMStrategy,
        "hybrid": HybridStrategy,
    }
    if name not in strategies:
        raise ValueError(f"未知策略: {name}，可选 {list(strategies)}")
    return strategies[name]()
