"""
面试复盘分析模块（Phase 1：无 RAG）

职责（业务层）：
1. 创建面试记录（仅解析，不触发 LLM）
2. 构建问题表意图识别 prompt 并做轻量预览
3. 提取岗位维度要求与经历卡上下文

对话解析逻辑已拆至 app.tools.interview_dialogue，本模块直接复用并向外部 re-export
（_parse_dialogue / _build_qa_pairs），保持原有公开契约不变。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.prompts import load_prompt
from app.tools import db_tools
from app.tools.interview_dialogue import (
    _build_qa_pairs,  # noqa: F401  (re-export，供外部沿用原公开契约)
    _parse_dialogue,  # noqa: F401  (re-export，供外部沿用原公开契约)
)

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

# 分析时最多处理的 QA 对数（受 Groq TPM 限制）
MAX_ANALYSIS_QA_PAIRS = 8


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


def _find_my_answer(dialogue: List[Dict[str, Any]], question_seq: int) -> str:
    """找到某个面试官问题之后、下一个面试官问题之前的候选人回答"""
    answer_parts = []
    found = False
    for d in dialogue:
        if d["sequence"] == question_seq:
            found = True
            continue
        if found:
            if d.get("role") == "interviewer":
                break
            answer_parts.append(d["content"])
    return " ".join(answer_parts).strip()


def create_interview_record(
    user_id: int,
    title: str,
    company: str,
    position: str,
    round_type: str,
    raw_text: str,
    job_analysis_id: Optional[int] = None,
    submission_id: Optional[int] = None,
) -> int:
    """创建面试记录，仅做解析，不触发 LLM 分析。"""
    parsed_dialogue = _parse_dialogue(raw_text)
    record_id = db_tools.insert_interview_record(
        {
            "user_id": user_id,
            "title": title or f"{company}-{position}-{round_type}",
            "company": company,
            "position": position,
            "round_type": round_type,
            "job_analysis_id": job_analysis_id,
            "submission_id": submission_id,
            "raw_text": raw_text,
            "parsed_dialogue": parsed_dialogue,
            "analysis": {},
            "status": "parsed",
        }
    )
    return record_id


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


def preview_question_intents(
    qa_pairs: List[Dict[str, Any]],
    company: str = "",
    position: str = "",
    round_type: str = "",
    jd_text: str = "",
) -> List[Dict[str, Any]]:
    """
    为 QA 对生成轻量意图识别结果，**不写入数据库**，仅用于解析预览。

    当问题数量过多时，只识别前 MAX_QUESTION_TABLE_QA_PAIRS 个。
    """
    if not qa_pairs:
        return []

    from app.agents.question_intent_agent import QuestionIntentAgent

    agent = QuestionIntentAgent()
    out = agent.run(
        {
            "company": company,
            "position": position,
            "round_type": round_type,
            "qa_pairs": qa_pairs,
            "jd_text": jd_text,
        }
    )
    return out["qa_pairs"]


def _get_job_context(record: Dict[str, Any], user_id: int = 1) -> Dict[str, Any]:
    """根据面试记录关联的岗位分析，提取 JD、维度要求、经历卡等上下文。"""
    context = {
        "jd_text": "",
        "dimension_requirements": [],
        "selected_card_ids": [],
        "cards": [],
    }
    job_id = record.get("job_analysis_id")
    if not job_id:
        context["cards"] = db_tools.list_cards(user_id=user_id, include_inactive=False)
        return context

    analysis = db_tools.get_job_analysis(job_id, user_id)
    if analysis:
        context["jd_text"] = analysis.get("jd_text", "")
        context["dimension_requirements"] = analysis.get("dimension_requirements") or []

    selected_ids = db_tools.get_selected_card_ids_by_job(job_id)
    context["selected_card_ids"] = selected_ids
    if selected_ids:
        cards = []
        for cid in selected_ids:
            card = db_tools.get_card(cid, user_id)
            if card:
                cards.append(card)
        context["cards"] = cards

    if not context["cards"]:
        context["cards"] = db_tools.list_cards(user_id=user_id, include_inactive=False)

    return context


def _format_cards_for_prompt(cards: List[Dict[str, Any]], max_cards: int = 5) -> str:
    """把经历卡格式化为 prompt 文本，优先展示完整 STAR 内容。"""
    lines = []
    for c in cards[:max_cards]:
        card_id = c.get("id")
        title = c.get("title") or ""
        summary = c.get("summary") or ""
        content = c.get("content") or ""
        background = c.get("background") or ""
        problem = c.get("problem") or ""
        solution = c.get("solution") or ""
        execution = c.get("execution") or ""
        result = c.get("result") or ""
        metrics = c.get("metrics") or {}
        tags = c.get("tags") or []

        parts = [
            f"ID:{card_id} 标题:{title}",
            f"标签:{','.join(tags)}",
            f"概要:{summary}",
        ]
        if content:
            parts.append(f"完整内容:{content[:300]}")
        else:
            for label, text in [
                ("背景", background),
                ("问题", problem),
                ("方案", solution),
                ("执行", execution),
                ("结果", result),
            ]:
                if text:
                    parts.append(f"{label}:{text[:200]}")
        if metrics:
            parts.append(f"指标:{metrics}")
        lines.append(" | ".join(parts))
    return "\n".join(lines) or "无"
