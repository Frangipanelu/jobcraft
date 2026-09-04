"""
Step 2 岗位分析 Agent: 缺口分析 + 润色建议

逐卡分析缺口并给出修改建议（单次 LLM 调用）。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.core.llm import model
from app.core.prompts import load_prompt
from app.schemas.jobcraft import ATSProfile
from app.tools.llm_json import invoke_structured


class CardDimensionScore(BaseModel):
    """单张卡片在某能力维度（D1-D8）上的评估"""

    dimension: str = Field("", description="维度编码 D1-D8")
    score: int = Field(0, ge=0, le=100, description="该维度得分 0-100")
    note: str = Field("", description="评估依据（卡片原文证据）")


class CardGapItem(BaseModel):
    """单张卡片的缺口+建议"""

    card_id: int
    score: float = Field(..., ge=0, le=100, description="融合后最终分数")
    local_score: float = Field(0.0, ge=0, le=100, description="本地关键词匹配分数")
    llm_score: float = Field(0.0, ge=0, le=100, description="LLM 语义匹配分数")
    matched: List[str] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)
    action: str = "good"  # 'polish' | 'supplement' | 'good'
    rewrite_suggestion: Optional[str] = None
    supplement_suggestion: Optional[str] = None
    supplement_steps: List[str] = Field(default_factory=list)
    # —— 多维评估（v0.9 新增，前向兼容，默认空）——
    dimension_analysis: List[CardDimensionScore] = Field(
        default_factory=list, description="D1-D8 逐维打分"
    )
    transferable_skills: List[str] = Field(
        default_factory=list, description="可迁移的通用能力"
    )
    domain_overlap: str = Field("", description="领域经验契合度评价")
    quantified_note: str = Field("", description="量化成果对标评价")


class GlobalSuggestion(BaseModel):
    """全局补充建议（所有已有卡片都覆盖不了的能力）"""

    missing_ability: str = ""
    priority: str = "medium"  # 'high' | 'medium' | 'low'
    action: str = ""
    steps: List[str] = Field(default_factory=list)


class GapPolishResult(BaseModel):
    """Step 2 合并输出"""

    per_card: List[CardGapItem]
    global_suggestions: List[GlobalSuggestion] = Field(default_factory=list)


class GapPolishAgent(BaseAgent):
    """Step 2: 缺口分析 + 润色建议（单次 LLM 调用）"""

    def _get_output_schema(self):
        return GapPolishResult

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """逐卡缺口分析 + 润色建议。

        :param state: {"ats": ATSProfile dict, "jd_text": str,
                       "selected_cards": [card dict, ...]}
        :return: {"gap_polish": {per_card, global_suggestions}}（LLM 原始分）
        """
        ats_dict = state.get("ats", {})
        ats = ATSProfile(**ats_dict) if ats_dict else ATSProfile()
        selected_cards = state.get("selected_cards", [])

        from app.tools.jobcraft_analyze import _card_text_blob

        cards_text = []
        for c in selected_cards:
            cards_text.append(
                f"card_id={c['id']}\ntitle={c.get('title', '')}\n"
                f"tags={','.join(c.get('tags') or [])}\n"
                f"全文：{_card_text_blob(c)[:800]}"
            )
        cards_section = "\n---\n".join(cards_text)

        dims_text = "; ".join(
            [
                f"{d.dimension}: {d.evidence} (level {d.level})"
                for d in (ats.dimension_requirements or [])
            ]
        )
        subtext_text = "; ".join(
            [
                f"『{s.surface_requirement}』→实际期望『{s.hidden_meaning}』"
                f"（关键能力：{s.key_ability}）"
                for s in (ats.subtext_decoded or [])
            ]
        )
        prompt = load_prompt(
            "jd",
            "gap_polish",
            job_title=ats.job_title,
            required_skills=", ".join(ats.required_skills),
            preferred_skills=", ".join(ats.preferred_skills),
            responsibilities=", ".join(ats.responsibilities),
            key_metrics=", ".join(ats.key_metrics),
            culture_keywords=", ".join(ats.culture_keywords),
            dims_text=dims_text,
            subtext_text=subtext_text if subtext_text else "（无）",
            cards_section=cards_section,
        )

        parsed = invoke_structured(
            model, GapPolishResult, prompt, debug_label="gap_polish"
        )
        return {
            "gap_polish": {
                "per_card": [p.model_dump() for p in parsed.per_card],
                "global_suggestions": [
                    g.model_dump() for g in parsed.global_suggestions
                ],
            }
        }
