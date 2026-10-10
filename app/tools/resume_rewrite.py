"""
简历要点 AI 改写工具（T-M6-3）

从 API 层提取出的 1 次 LLM 调用，遵循四层架构规则，
统一经由 llm_json.invoke_structured 出口（审计/缓存/观测）。
"""

import logging

from pydantic import BaseModel, Field

from app.core.llm import model
from app.core.prompts import load_prompt
from app.tools.llm_json import invoke_structured

logger = logging.getLogger(__name__)


class RewriteOutput(BaseModel):
    """改写输出结构：rewritten_text 为改写后的要点文本"""

    rewritten_text: str = Field("", description="改写后的简历要点文本")


def rewrite_resume_bullet(
    original_bullet: str,
    *,
    dimension: str = "",
    gap_current: str = "",
    jd_evidence: str = "",
    rewrite_hint: str = "",
) -> str:
    """按能力缺口 AI 改写一条简历要点（只算不写，落库走 PATCH）。

    :param original_bullet: 用户选中的要点原文
    :param dimension: 能力维度（如 D1-编程语言）
    :param gap_current: 缺口现状描述
    :param jd_evidence: JD 原文证据
    :param rewrite_hint: 改写方向提示
    :return: 改写后的完整要点文本
    :raises ValueError: 要点原文为空时抛出
    :raises RuntimeError: LLM 返回空内容时抛出
    """
    if not original_bullet or not original_bullet.strip():
        raise ValueError("要点原文为空，无法改写")

    prompt = load_prompt(
        "resume",
        "rewrite",
        version=2,
        dimension=dimension or "未指定",
        gap_current=gap_current or "未提供",
        jd_evidence=jd_evidence or "未提供",
        rewrite_hint=rewrite_hint or "按岗位要求优化表达",
        original_bullet=original_bullet.strip(),
    )

    parsed = invoke_structured(
        model,
        RewriteOutput,
        prompt,
        debug_label="resume_rewrite",
        prompt_version="2",
    )
    rewritten = parsed.rewritten_text.strip()
    if not rewritten:
        raise RuntimeError("AI 改写返回内容为空")
    return rewritten
