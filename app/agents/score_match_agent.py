"""
LLM 语义匹配评分 Agent

对每张经历卡与岗位要求做 LLM 语义匹配评分（单次 LLM 调用）。
"""

from typing import Any, Dict, List

from pydantic import BaseModel

from app.agents.base_agent import BaseAgent
from app.core.llm import model
from app.core.prompts import load_prompt
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
        prompt = load_prompt(
            "jd",
            "score_match",
            hard_skills=", ".join(jd_req.hard_skills),
            soft_skills=", ".join(jd_req.soft_skills),
            keywords=", ".join(jd_req.keywords),
            responsibilities=", ".join(jd_req.responsibilities),
            cards_section=cards_section,
        )

        parsed = invoke_structured(model, _Items, prompt, debug_label="llm_score_match")
        return {"llm_match_items": {it.card_id: it.model_dump() for it in parsed.items}}
