"""
面试准备稿模块（纯函数 + DB，无 LLM 调用）

提供 prompt 构建与 DB 读取能力；LLM 生成逻辑在 app/agents/interview_prep_agent.py。
"""

import json
from typing import Any, Dict, List, Optional

from app.schemas.jobcraft import DimensionQuestion, InterviewPrepResult
from app.tools import db_tools

# 8 维能力说明
DIMENSION_DESCRIPTIONS = {
    "D1": "技术深度",
    "D2": "业务理解",
    "D3": "问题拆解",
    "D4": "方案设计",
    "D5": "落地执行",
    "D6": "数据复盘",
    "D7": "协作沟通",
    "D8": "职业规划",
}


def _card_text(card: Dict[str, Any], card_versions: Dict[int, str]) -> str:
    """获取卡片文本：card_versions 优先"""
    cid = card.get("id")
    if cid in card_versions:
        return card_versions[cid]
    return card.get("raw_text") or card.get("content") or card.get("summary", "")


def _build_interview_prompt(
    round_type: str,
    position: str,
    company: str,
    jd_text: str,
    cards: List[Dict[str, Any]],
    dimension_requirements: List[Dict[str, Any]],
    card_versions: Optional[Dict[int, str]] = None,
    company_research: Optional[Dict[str, Any]] = None,
    resume_markdown: Optional[str] = None,
    previous_review_summary: Optional[str] = None,
) -> str:
    card_versions = card_versions or {}
    cards_text = []
    for c in cards:
        text = _card_text(c, card_versions)[:300]
        cards_text.append(
            f"- {c.get('title', '')}: {c.get('summary', '')}\n  "
            f"内容：{text}\n  "
            f"标签：{', '.join(c.get('tags') or [])}"
        )
    cards_section = "\n".join(cards_text)

    dim_text = (
        "\n".join(
            [
                f"- {d.get('dimension', '')}: 等级 {d.get('level', 3)}，证据 {d.get('evidence', '')}"
                for d in dimension_requirements
            ]
        )
        or "- D1-D8 均要求等级 3"
    )

    # 公司调研段落
    company_section = ""
    if company_research:
        try:
            cr = json.dumps(company_research, ensure_ascii=False, default=str)[:3000]
            company_section = (
                "公司调研信息（面试前了解目标公司，在回答中适当融入）:\n"
                "---\n"
                f"{cr}\n"
                "---\n\n"
            )
        except Exception:
            pass

    # 已投简历段落
    resume_section = ""
    if resume_markdown:
        resume_section = (
            "候选人实际投出的简历（面试官手上拿的就是这份）:\n"
            "---\n"
            f"{resume_markdown[:2000]}\n"
            "---\n\n"
        )

    # 上一轮复盘段落
    review_section = ""
    if previous_review_summary:
        review_section = (
            "上一轮面试复盘摘要（本轮需针对性加强）:\n"
            "---\n"
            f"{previous_review_summary}\n"
            "---\n\n"
        )

    section_order = ""
    if round_type in ("二面", "三面", "四面", "五面"):
        section_order = (
            "1. 开场自我介绍（150 字左右，融入公司调研 + 针对上轮复盘调整重点）；\n"
            "2. 维度问题逐字稿：每个维度输出 1 道面试题 + 完整回答逐字稿，结合简历实际经历 + 公司业务语境；\n"
            "3. 针对该公司的反问（3-5 个，基于公司调研）；\n"
            "4. 收尾。\n"
        )
    else:
        section_order = (
            "1. 开场自我介绍（150 字左右，融入公司调研）；\n"
            "2. 维度问题逐字稿：每个维度输出 1 道面试题 + 完整回答逐字稿，结合简历实际经历 + 公司业务语境；\n"
            "3. 针对该公司的反问（3-5 个，基于公司调研）；\n"
            "4. 收尾。\n"
        )

    return (
        f"你是一名面试辅导专家。请为「{position}」{round_type}生成一份完整面试逐字稿。\n\n"
        f"目标公司：{company}\n\n"
        "JD 文本：\n---\n"
        f"{jd_text[:3000]}\n---\n\n"
        "8 维能力要求：\n"
        f"{dim_text}\n\n"
        "候选人经历卡片：\n"
        f"{cards_section}\n\n"
        f"{company_section}"
        f"{resume_section}"
        f"{review_section}"
        "输出结构（按顺序）：\n"
        f"{section_order}\n"
        "输出 JSON: InterviewPrepResult（dimension_questions 内每个元素需包含 question + 完整 answer 逐字稿 + card_ids）"
    )


def get_interview_prep(job_analysis_id: int) -> Optional[InterviewPrepResult]:
    """从数据库读取面试准备稿"""
    row = db_tools.get_interview_prep_by_job(job_analysis_id)
    if not row:
        return None

    ability_matrix = row.get("ability_matrix") or []
    dimension_questions = [DimensionQuestion.model_validate(q) for q in ability_matrix]
    extended = row.get("extended_version") or {}

    return InterviewPrepResult(
        job_analysis_id=job_analysis_id,
        round_type=row.get("round_type", "技术面"),
        duration=row.get("duration", "10-15 分钟"),
        elevator_pitch=row.get("elevator_pitch", ""),
        dimension_questions=dimension_questions,
        full_version=extended.get("full_version", ""),
        html_content=row.get("html_content", ""),
        created_at=row.get("created_at"),
    )
