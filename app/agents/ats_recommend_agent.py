"""
Step 1 岗位分析 Agent: ATS 解析 + 推荐卡片

合并一次 LLM 调用完成 ATS 岗位画像、卡片推荐与 JD 暗话解码。
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.core.llm import model
from app.core.prompts import load_prompt
from app.schemas.jobcraft import ATSProfile
from app.tools.llm_json import invoke_structured


class RecommendedCard(BaseModel):
    """AI 推荐的卡片"""

    card_id: int
    score: int = Field(..., ge=0, le=100)
    reason: str = ""


class ATSRecommendResult(BaseModel):
    """Step 1 合并输出"""

    ats: ATSProfile
    recommended_cards: List[RecommendedCard]


class AtsRecommendAgent(BaseAgent):
    """Step 1: ATS 解析 + 推荐卡片（单次 LLM 调用）"""

    def _get_output_schema(self):
        return ATSRecommendResult

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """解析 JD + 推荐经历卡。

        :param state: {"jd_text": str, "cards": [card dict, ...]}
        :return: {"ats": ATSProfile dict, "recommended_cards": [{card_id, score, reason}]}
        """
        jd_text = state.get("jd_text", "")
        cards = state.get("cards", [])

        cards_text = []
        for c in cards:
            cards_text.append(
                f"card_id={c['id']}\ntitle={c.get('title', '')}\n"
                f"tags={','.join(c.get('tags') or [])}\n"
                f"摘要：{(c.get('raw_text') or c.get('content') or '')[:300]}"
            )
        cards_section = "\n---\n".join(cards_text)

        prompt = load_prompt(
            "jd",
            "ats_recommend",
            jd_text=jd_text[:5000],
            cards_section=cards_section,
        )

        parsed = invoke_structured(
            model, ATSRecommendResult, prompt, debug_label="ats_recommend"
        )

        return {
            "ats": parsed.ats.model_dump(),
            "recommended_cards": [r.model_dump() for r in parsed.recommended_cards],
        }
