"""
Step 2 岗位分析 Agent: 缺口分析 + 润色建议

逐卡分析缺口并给出修改建议（单次 LLM 调用）。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.core.llm import model
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
        prompt = (
            "你是一名资深求职顾问。请根据岗位要求和经历卡片，逐卡分析缺口并给出修改建议。\n\n"
            "=== 岗位画像 ===\n"
            f"岗位名称：{ats.job_title}\n"
            f"硬性技能：{', '.join(ats.required_skills)}\n"
            f"加分技能：{', '.join(ats.preferred_skills)}\n"
            f"核心职责：{', '.join(ats.responsibilities)}\n"
            f"关键指标：{', '.join(ats.key_metrics)}\n"
            f"文化关键词：{', '.join(ats.culture_keywords)}\n"
            f"8维能力要求：{dims_text}\n\n"
            "=== 暗话解码（JD 潜台词，需重点验证）===\n"
            f"{subtext_text if subtext_text else '（无）'}\n\n"
            "=== 评价规则 ===\n"
            "1. 忽略学历要求（本科/硕士等不可通过经历卡补充的信息）\n"
            "2. 从以下维度综合评估：专业技能、业务理解、问题拆解、方案设计、"
            "落地执行、数据复盘、协作沟通等，而不只看软硬技能列表\n"
            "3. 重点评估：是否有可迁移的通用能力、类似领域经验、可量化的成果\n"
            "4. 暗话解码的要求需要重点验证：如果卡片没有直接写，但经历可推导出该能力，"
            "应给出 'polish' 建议把能力显性化，而不是简单地判为缺失\n\n"
            "=== 经历卡片 ===\n"
            "---\n"
            f"{cards_section}\n"
            "---\n\n"
            "对每张卡片输出：\n"
            "1. score: 0-100 匹配度\n"
            "2. matched: 已覆盖的岗位要求列表\n"
            "3. missing: 未覆盖的岗位要求列表\n"
            "4. action: 操作类型\n"
            "   - 'polish': 卡里有相关内容但表述不足 → 给出 rewrite_suggestion\n"
            "   - 'supplement': 卡里缺乏相关内容 → 给出 supplement_suggestion + 操作步骤 steps\n"
            "   - 'good': 已覆盖且表述充分\n\n"
            "rewrite_suggestion 必须基于卡片现有内容改写，不能编造不存在的事实。\n"
            "supplement_suggestion 必须给出具体写什么，steps 给出 2-3 步操作指引。\n\n"
            "5. 每张卡片还需多维评估：\n"
            "   - dimension_analysis: 对与本卡相关的 8 维能力（D1-D8）逐项打分 0-100，"
            "note 写明卡片原文中的依据\n"
            "   - transferable_skills: 该经历可迁移到本岗位的 3-5 个通用能力\n"
            "   - domain_overlap: 用一句话评价领域经验契合度（高/中/低 + 理由）\n"
            "   - quantified_note: 量化成果对标评价：卡中已有量化成果是否对标岗位关键指标，"
            "缺少哪些可量化的描述\n\n"
            "此外，如果所有卡片都覆盖不了某些关键能力，输出 global_suggestions。\n"
            '输出 JSON: {"per_card": [CardGapItem], "global_suggestions": [GlobalSuggestion]}'
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
