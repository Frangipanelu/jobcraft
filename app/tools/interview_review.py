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

from app.tools import db_tools
from app.tools.interview_dialogue import (
    _build_qa_pairs,  # noqa: F401  (re-export，供外部沿用原公开契约)
    _parse_dialogue,  # noqa: F401  (re-export，供外部沿用原公开契约)
)
from app.tools.question_table import (
    ABILITY_DIMENSIONS,  # noqa: F401  (re-export，供外部沿用原公开契约)
    DIMENSION_RUBRIC,  # noqa: F401  (re-export，供外部沿用原公开契约)
    LEVEL_SCORE_MAP,  # noqa: F401  (re-export，供外部沿用原公开契约)
    MAX_QUESTION_TABLE_QA_PAIRS,  # noqa: F401  (re-export，供外部沿用原公开契约)
    RUBRIC_TEXT,  # noqa: F401  (re-export，供外部沿用原公开契约)
    _QuestionIntentItem,  # noqa: F401  (re-export，供外部沿用原公开契约)
    _QuestionTableOut,  # noqa: F401  (re-export，供外部沿用原公开契约)
    _build_question_table_prompt,  # noqa: F401  (re-export，供外部沿用原公开契约)
    _truncate_text,  # noqa: F401  (re-export，供外部沿用原公开契约)
)

# 8 维能力矩阵与问题表意图识别所需的 schema / prompt 构建 / 常量已下沉至
# app.tools.question_table（叶子模块），此处仅 re-export 保持向后兼容。

# 分析时最多处理的 QA 对数（受 Groq TPM 限制）
MAX_ANALYSIS_QA_PAIRS = 8


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
