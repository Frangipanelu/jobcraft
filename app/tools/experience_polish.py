"""
经历卡 AI 润色工具

从 API 层提取出的 1 次 LLM 调用，遵循四层架构规则，
统一经由 llm_json.invoke_structured 出口（审计/缓存/观测）。
"""

import logging

from pydantic import BaseModel, Field

from app.core.llm import model
from app.core.prompts import load_prompt
from app.tools.llm_json import invoke_structured

logger = logging.getLogger(__name__)


class PolishOutput(BaseModel):
    """润色输出结构：polished_text 为润色后的经历文本"""

    polished_text: str = Field("", description="润色后的经历文本")


def polish_experience(
    raw_text: str,
    company: str = "",
    role: str = "",
) -> str:
    """
    AI 润色一段工作经历：优化措辞、强化量化指标、提升专业表述。

    :param raw_text: 原始经历文本
    :param company: 公司名（可选）
    :param role: 岗位名（可选）
    :return: 润色后的经历文本
    :raises ValueError: 输入内容过短时抛出
    :raises RuntimeError: LLM 调用失败时抛出
    """
    prompt = load_prompt(
        "experience",
        "polish",
        version=2,
        company=company or "未知",
        role=role or "未知",
        raw_text=raw_text,
    )

    parsed = invoke_structured(
        model,
        PolishOutput,
        prompt,
        debug_label="experience_polish",
    )
    polished = parsed.polished_text.strip()
    if not polished:
        raise RuntimeError("AI 润色返回内容为空")
    return polished
