"""
行为/业务题分析 Agent

专注分析行为/业务/管理类面试问题，输出结构化标准答案、评分、反馈和建议。
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.tools.llm_json import invoke_structured as llm_call
from app.core.llm import model


class _SoftQuestionAnalysis(BaseModel):
    sequence: int = Field(..., description="问题序号")
    dimension: str = Field(..., description="维度编码 D1-D8")
    level: str = Field(..., description="难度等级 L1-L5")
    intent: str = Field(..., description="面试官考察意图")
    expected_answer: Union[str, List[str]] = Field(..., description="结构化标准答案")
    score: int = Field(..., ge=0, le=100, description="评分")
    feedback: List[str] = Field(default_factory=list, description="诊断反馈")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    related_card_id: Optional[int] = Field(None, description="推荐经历卡 ID")


class _SoftAnalyzeOut(BaseModel):
    analyses: List[_SoftQuestionAnalysis]


RUBRIC_TEXT = (
    "D2 业务理解: L5 关联商业目标并量化；L3 知道场景但缺深度；L1 对业务无理解\n"
    "D6 数据复盘: L5 指标体系完整+AB/归因；L3 有数据缺体系；L1 无数据支撑\n"
    "D7 协作沟通: L5 结构化+说服力+推动对齐；L3 能沟通但欠打磨；L1 表达混乱\n"
    "D8 职业规划: L5 目标清晰且匹配岗位；L3 模糊但方向对；L1 敷衍或与岗位无关"
)


class SoftAnalyzer(BaseAgent):
    """专注分析行为/业务/管理类问题"""

    def _get_output_schema(self):
        return _SoftAnalyzeOut

    def _build_prompt(self, state: Dict[str, Any]) -> str:
        selected_qa = state.get("selected_qa_pairs", [])
        soft_seqs = set(state.get("classified", {}).get("soft", []))
        soft_qa = [qa for qa in selected_qa if qa["sequence"] in soft_seqs]

        qa_text = "\n\n".join(
            f"Q{qa['sequence']} [{qa.get('start_time', '')}] {qa['question_text']}\n"
            f"A{qa['sequence']} {qa.get('my_answer', '')}"
            for qa in soft_qa
        )

        jd_text = state.get("jd_text", "")
        jd_section = f"JD:\n{jd_text[:400]}\n\n" if jd_text else ""

        cards_text = state.get("cards_text", "无")

        return (
            f"你正在复盘一场{state.get('round_type', '')}面试，"
            f"岗位:{state.get('position', '')}，公司:{state.get('company', '')}\n"
            "你负责分析其中的行为/业务类问题。请为每个问题生成完整分析。\n\n"
            "===== 评分标准 =====\n"
            f"{RUBRIC_TEXT}\n"
            "L5=90-100 L4=80-89 L3=60-79 L2=40-59 L1=0-39\n\n"
            f"{jd_section}"
            "===== 经历卡 =====\n"
            f"{cards_text}\n\n"
            "===== 需要分析的行为/业务类 QA 对 =====\n"
            f"{qa_text}\n\n"
            "输出要求：\n"
            "1. analyses 数组长度必须等于上面问题数量，按 sequence 顺序\n"
            "2. expected_answer 须给出完整结构化回答: 核心观点 + 要点 + 结合经历卡案例\n"
            "3. score 根据回答完整度、结构化程度和岗位匹配度评分\n"
            "4. related_card_id 从经历卡中选最相关的1张，无则 null"
        )

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        soft_seqs = set(state.get("classified", {}).get("soft", []))
        if not soft_seqs:
            return {"soft_results": []}
        schema = self._get_output_schema()
        prompt = self._build_prompt(state)
        raw = llm_call(
            model,
            schema,
            prompt,
            debug_label="soft_analyzer",
            max_tokens=4096,
        )
        return {"soft_results": [a.model_dump() for a in raw.analyses]}
