"""
Step 1 岗位分析 Agent: ATS 解析 + 推荐卡片

合并一次 LLM 调用完成 ATS 岗位画像、卡片推荐与 JD 暗话解码。
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.core.llm import model
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

        prompt = (
            "你是一名招聘专家。请完成以下三个任务：\n\n"
            "【任务一】ATS 解析\n"
            "从以下 JD 中提取结构化岗位画像，包括：\n"
            "- job_title / department / location / salary / education\n"
            "- years_of_experience\n"
            "- required_skills（硬性要求）\n"
            "- preferred_skills（加分项）\n"
            "- responsibilities（核心职责条目）\n"
            "- key_metrics（量化指标）\n"
            "- culture_keywords（文化价值观关键词）\n"
            "- dimension_requirements（D1-D8，level 1-5，evidence 原文证据）\n"
            "- subtext_decoded（见任务三，同步填入 ats.subtext_decoded）\n\n"
            "【任务二】推荐卡片\n"
            "从以下经历卡片中推荐与岗位最相关的 3-5 张。\n"
            "对每张推荐卡输出：\n"
            "- card_id\n"
            "- score: 0-100 的匹配度\n"
            "- reason: 为什么匹配（一句话）\n\n"
            "【任务三】暗话分析（JD 潜台词解码）\n"
            "识别 JD 中没说透、但实际会重点考察的隐性要求。"
            "常见潜台词类型：\n"
            "- '熟悉XXX' → 实际要求有 XXX 的生产级实践经验\n"
            "- '抗压能力强' → 期望能接受加班/高节奏\n"
            "- '有大型项目经验' → 期望经历过复杂系统/团队协作\n"
            "- '了解XXX' → 期望至少接触过并有自己的理解\n"
            "- '对数据敏感' → 期望用数据驱动决策的能力\n"
            "对每条潜台词输出：\n"
            "- surface_requirement: JD 表面原话\n"
            "- hidden_meaning: 实际期望\n"
            "- key_ability: 真正需要证明的关键能力\n"
            "- how_to_prove: 如何用经历/量化成果证明\n"
            "输出 3-6 条最重要的暗话，并同步写入 ats.subtext_decoded。\n\n"
            "JD 文本：\n"
            "---\n"
            f"{jd_text[:5000]}\n"
            "---\n\n"
            "经历卡片：\n"
            "---\n"
            f"{cards_section}\n"
            "---\n\n"
            '输出 JSON: {"ats": ATSProfile, "recommended_cards": [{"card_id": int, "score": int, "reason": str}]}'
        )

        parsed = invoke_structured(
            model, ATSRecommendResult, prompt, debug_label="ats_recommend"
        )

        return {
            "ats": parsed.ats.model_dump(),
            "recommended_cards": [r.model_dump() for r in parsed.recommended_cards],
        }
