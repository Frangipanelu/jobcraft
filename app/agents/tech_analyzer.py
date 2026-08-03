"""
技术题分析 Agent

专注分析技术/项目类面试问题，输出结构化标准答案、评分、反馈和建议。
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.tools.llm_json import invoke_structured as llm_call
from app.core.llm import model


class _TechQuestionAnalysis(BaseModel):
    sequence: int = Field(..., description="问题序号")
    dimension: str = Field(..., description="维度编码 D1-D8")
    level: str = Field(..., description="难度等级 L1-L5")
    intent: str = Field(..., description="面试官考察意图")
    expected_answer: Union[str, List[str]] = Field(..., description="结构化标准答案")
    score: int = Field(..., ge=0, le=100, description="评分")
    feedback: List[str] = Field(default_factory=list, description="诊断反馈")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    related_card_id: Optional[int] = Field(None, description="推荐经历卡 ID")


class _TechAnalyzeOut(BaseModel):
    analyses: List[_TechQuestionAnalysis]


RUBRIC_TEXT = (
    "D1 技术深度: L5 原理+选型+优化+踩坑；L3 原理和步骤清楚；L1 概念错误或答不出\n"
    "D3 问题拆解: L5 有框架，定位根因；L3 能列原因缺框架；L1 无法定位\n"
    "D4 方案设计: L5 多方案对比+路线图；L3 基本方案缺细节/风险；L1 无方案\n"
    "D5 落地执行: L5 项目管理+协作+可验证结果；L3 能讲做了什么但较粗；L1 无细节"
)


class TechAnalyzer(BaseAgent):
    """专注分析技术/项目类问题"""

    def _get_output_schema(self):
        return _TechAnalyzeOut

    def _build_prompt(self, state: Dict[str, Any]) -> str:
        selected_qa = state.get("selected_qa_pairs", [])
        tech_seqs = set(state.get("classified", {}).get("tech", []))
        tech_qa = [qa for qa in selected_qa if qa["sequence"] in tech_seqs]

        qa_text = "\n\n".join(
            f"Q{qa['sequence']} [{qa.get('start_time', '')}] {qa['question_text']}\n"
            f"A{qa['sequence']} {qa.get('my_answer', '')}"
            for qa in tech_qa
        )

        jd_text = state.get("jd_text", "")
        jd_section = f"JD:\n{jd_text[:400]}\n\n" if jd_text else ""

        cards_text = state.get("cards_text", "无")

        return (
            f"你正在复盘一场{state.get('round_type', '')}面试，"
            f"岗位:{state.get('position', '')}，公司:{state.get('company', '')}\n"
            "你负责分析其中的技术/项目类问题。请为每个问题生成完整分析。\n\n"
            "===== 评分标准 =====\n"
            f"{RUBRIC_TEXT}\n"
            "L5=90-100 L4=80-89 L3=60-79 L2=40-59 L1=0-39\n\n"
            f"{jd_section}"
            "===== 经历卡 =====\n"
            f"{cards_text}\n\n"
            "===== 需要分析的技术类 QA 对 =====\n"
            f"{qa_text}\n\n"
            "输出要求：\n"
            "1. analyses 数组长度必须等于上面问题数量，按 sequence 顺序\n"
            "2. expected_answer 须给出完整结构化回答: 核心观点 + 要点 + 结合经历卡案例\n"
            "3. score 根据回答完整度、深度、结构化程度评分\n"
            "4. related_card_id 从经历卡中选最相关的1张，无则 null"
        )

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        tech_seqs = set(state.get("classified", {}).get("tech", []))
        if not tech_seqs:
            return {"tech_results": []}
        schema = self._get_output_schema()
        prompt = self._build_prompt(state)
        raw = llm_call(
            model,
            schema,
            prompt,
            debug_label="tech_analyzer",
            max_tokens=4096,
        )
        return {"tech_results": [a.model_dump() for a in raw.analyses]}
