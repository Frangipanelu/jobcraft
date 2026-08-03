"""
LLM 语义匹配评分 Agent

对每张经历卡与岗位要求做 LLM 语义匹配评分（单次 LLM 调用）。
"""

from typing import Any, Dict, List

from pydantic import BaseModel

from app.agents.base_agent import BaseAgent
from app.core.llm import model
from app.schemas.jobcraft import CardLLMMatchItem, JDRequirements
from app.tools.llm_json import invoke_structured


class _Items(BaseModel):
    items: List[CardLLMMatchItem]


class ScoreMatchAgent(BaseAgent):
    """使用 LLM 对每张卡片做语义匹配评分（单次 LLM 调用）"""

    def _get_output_schema(self):
        return _Items

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """语义匹配评分。

        :param state: {"jd_req": JDRequirements dict, "cards": [card dict, ...]}
        :return: {"llm_match_items": {card_id: CardLLMMatchItem dict}}
        """
        jd_req_dict = state.get("jd_req", {})
        jd_req = JDRequirements(**jd_req_dict) if jd_req_dict else JDRequirements()
        cards = state.get("cards", [])
        if not cards:
            return {"llm_match_items": {}}

        cards_text = []
        from app.tools.jobcraft_analyze import _card_text_blob

        for c in cards:
            cards_text.append(
                f"card_id={c['id']}\ntitle={c.get('title', '')}\nsummary={c.get('summary', '')}\n"
                f"tags={','.join(c.get('tags') or [])}\ncontent={_card_text_blob(c)[:600]}"
            )
        cards_section = "\n---\n".join(cards_text)
        prompt = (
            "你是一名资深 HR，正在评估候选人的经历卡片与岗位要求的匹配度。\n\n"
            "岗位要求：\n"
            f"- 硬性技能：{', '.join(jd_req.hard_skills)}\n"
            f"- 软性/加分技能：{', '.join(jd_req.soft_skills)}\n"
            f"- 关键词：{', '.join(jd_req.keywords)}\n"
            f"- 职责：{', '.join(jd_req.responsibilities)}\n\n"
            "经历卡片：\n"
            "---\n"
            f"{cards_section}\n"
            "---\n\n"
            "请为每张卡片输出：\n"
            "- card_id: 卡片 ID\n"
            "- match: 0-100 的匹配分数\n"
            "- covered: 已覆盖的岗位要求点\n"
            "- missing: 未覆盖但岗位要求的点\n"
            "- reason: 一句话评分理由\n\n"
            '输出 JSON: {"items": [CardLLMMatchItem, ...]}'
        )

        parsed = invoke_structured(model, _Items, prompt, debug_label="llm_score_match")
        return {"llm_match_items": {it.card_id: it.model_dump() for it in parsed.items}}
