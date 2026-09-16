"""
问题表意图识别共享叶子模块（解除 Tool → Agent 循环依赖）

这些 schema / prompt 构建函数 / 常量原定义于 app.tools.interview_review（业务编排模块），
被两个同级 Agent（question_intent_agent / question_table_agent）在**模块级**引用，同时还被
interview_review 的业务函数沿用，形成环：

    tools.interview_review →(运行时, 函数体)→ agents.question_intent_agent
    agents.question_intent_agent →(模块级)→ tools.interview_review

本模块是双方的公共稳定接口，仅依赖 app.core.prompts（叶子模块），不依赖任何 agent / 业务编排。
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.core.prompts import load_prompt

# 8 维能力矩阵定义
ABILITY_DIMENSIONS = [
    ("D1", "技术深度"),
    ("D2", "业务理解"),
    ("D3", "问题拆解"),
    ("D4", "方案设计"),
    ("D5", "落地执行"),
    ("D6", "数据复盘"),
    ("D7", "协作沟通"),
    ("D8", "职业规划"),
]

# 8 维能力评分 rubric（精简但保留关键区分度）
DIMENSION_RUBRIC = {
    "D1 技术深度": "L5 原理+选型+优化+踩坑；L3 原理和步骤清楚；L1 概念错误或答不出",
    "D2 业务理解": "L5 关联商业目标并量化；L3 知道场景但缺深度；L1 对业务无理解",
    "D3 问题拆解": "L5 有框架，定位根因；L3 能列原因缺框架；L1 无法定位或思路错",
    "D4 方案设计": "L5 多方案对比+路线图；L3 基本方案缺细节/风险；L1 无方案或明显错误",
    "D5 落地执行": "L5 项目管理+协作+可验证结果；L3 能讲做了什么但较粗；L1 无细节或结果不可验证",
    "D6 数据复盘": "L5 指标体系完整+AB/归因；L3 有数据缺体系/关键指标；L1 无数据支撑",
    "D7 协作沟通": "L5 结构化+说服力+推动对齐；L3 能沟通但欠打磨；L1 表达混乱难理解",
    "D8 职业规划": "L5 目标清晰且匹配岗位；L3 模糊但方向对；L1 敷衍或与岗位无关",
}
RUBRIC_TEXT = "\n".join(f"{k}: {v}" for k, v in DIMENSION_RUBRIC.items())
LEVEL_SCORE_MAP = "L5=90-100 L4=80-89 L3=60-79 L2=40-59 L1=0-39"


def _truncate_text(text: str, max_chars: int) -> str:
    """按字符截断文本，保留前半部分和后半部分，中间用省略号连接"""
    if not text or len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n...[内容过长，已截断]...\n" + text[-half:]


class _QuestionIntentItem(BaseModel):
    """单个问题的轻量意图识别结果"""

    sequence: int = Field(..., description="QA 对编号")
    intent: str = Field(..., description="面试官真实考察意图，一句话")
    dimension: str = Field(..., description="维度编码与名称，如 D1 技术深度")
    level: str = Field(..., description="难度等级 L1-L5")


class _QuestionTableOut(BaseModel):
    """问题表输出"""

    questions: List[_QuestionIntentItem] = Field(
        ..., description="所有识别到的问题，按 sequence 排序"
    )


# 问题表可识别的问题上限（轻量意图识别，可略高于详细分析上限）
MAX_QUESTION_TABLE_QA_PAIRS = 20


def _build_question_table_prompt(
    company: str,
    position: str,
    round_type: str,
    qa_pairs: List[Dict[str, Any]],
    jd_text: str = "",
) -> str:
    """构造问题表意图识别 prompt（轻量，不分析回答）。"""
    questions_text = "\n".join(
        f"Q{qa['sequence']} [{qa.get('start_time', '')}] {qa['question_text']}"
        for qa in qa_pairs[:MAX_QUESTION_TABLE_QA_PAIRS]
    )
    jd_section = f"JD:{_truncate_text(jd_text, 400)}\n\n" if jd_text else ""
    return load_prompt(
        "interview",
        "question_table_intent",
        round_type=round_type,
        position=position,
        company=company,
        jd_section=jd_section,
        rubric_text=RUBRIC_TEXT,
        level_score_map=LEVEL_SCORE_MAP,
        questions_text=questions_text,
    )
