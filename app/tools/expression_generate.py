"""
Standardized Expression 生成工具

从 API 层提取出的 1 次 LLM 调用（EXPERIENCE_SPEC §9 / EXPERIENCE_SPEC §2.2），
统一经由 llm_json.invoke_structured 出口（审计/缓存/观测），
不持有状态，输入=经历原文，输出=Expression.content。
"""

import logging

from pydantic import BaseModel, Field

from app.core.llm import model
from app.core.prompts import load_prompt
from app.tools.llm_json import invoke_structured

logger = logging.getLogger(__name__)


class StandardizedExpressionOutput(BaseModel):
    """标准化表达输出结构：content 为对任意岗位可理解的表达文本"""

    content: str = Field("", description="标准化表达文本（事实保留、不针对岗位）")


def generate_standardized_expression(
    raw_text: str,
    company: str = "",
    role: str = "",
) -> str:
    """
    AI 生成一条经历的标准化表达（Standardized Expression）。

    保留原始事实完整、中性化（不针对岗位/JD），输出跨岗位可理解的表达文本。

    :param raw_text: 原始经历文本（Original Facts 是唯一事实来源）
    :param company: 公司名（可选）
    :param role: 岗位名（可选）
    :return: 标准化表达文本（Expression.content）
    :raises ValueError: 输入内容过短时抛出
    :raises RuntimeError: LLM 调用失败或返回为空时抛出
    """
    raw_text = raw_text.strip() if raw_text else ""
    if not raw_text:
        raise ValueError("经历内容不能为空")
    if len(raw_text) < 10:
        raise ValueError("经历内容过短，请补充后再试")

    prompt = load_prompt(
        "experience",
        "expression_standardized",
        version=1,
        company=company or "未知",
        role=role or "未知",
        raw_text=raw_text,
    )

    parsed = invoke_structured(
        model,
        StandardizedExpressionOutput,
        prompt,
        debug_label="expression_standardized",
    )
    content = parsed.content.strip()
    if not content:
        raise RuntimeError("AI 标准化表达返回内容为空")
    return content
