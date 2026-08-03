"""
优化建议 Agent

根据岗位要求与卡片匹配情况，生成 3-5 条具体优化建议（单次 LLM 调用）。
"""

from typing import Any, Dict

from app.agents.base_agent import BaseAgent
from app.core.llm import model
from app.schemas.jobcraft import JDRequirements, SuggestionsResult
from app.tools.llm_json import invoke_structured


class SugAgent(BaseAgent):
    """生成简历/经历卡优化建议（单次 LLM 调用）"""

    def _get_output_schema(self):
        return SuggestionsResult

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """生成优化建议。

        :param state: {"jd_req": JDRequirements dict, "cards": [card dict],
                       "per_card_scores": [PerCardScore dict]}
        :return: {"suggestions": SuggestionsResult dict}
        """
        jd_req_dict = state.get("jd_req", {})
        jd_req = JDRequirements(**jd_req_dict) if jd_req_dict else JDRequirements()
        cards = state.get("cards", [])
        per_card_scores = state.get("per_card_scores", [])

        cards_text = []
        for c in cards:
            pc = next((p for p in per_card_scores if p.get("card_id") == c["id"]), None)
            cards_text.append(
                f"card_id={c['id']} title={c.get('title', '')} score={pc.get('score', 0) if pc else 0} "
                f"matched={pc.get('matched', []) if pc else []} missing={pc.get('missing', []) if pc else []}"
            )
        cards_lines = "\n".join(cards_text)
        prompt = (
            "你是求职优化专家。请根据岗位要求和卡片匹配情况，给出 3-5 条具体优化建议。\n\n"
            f"岗位要求：{', '.join(jd_req.hard_skills + jd_req.soft_skills)}\n"
            f"卡片情况：\n{cards_lines}\n\n"
            '输出 JSON: {"gap_analysis": str, "gap_items": [str], "suggestions": [{"card_id": int|none, "type": str, "message": str, "priority": 1-5, "optimization": str}]}'
        )
        parsed = invoke_structured(
            model, SuggestionsResult, prompt, debug_label="suggest"
        )
        return {"suggestions": parsed.model_dump()}
