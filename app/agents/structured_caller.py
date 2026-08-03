"""
结构化 LLM 调用封装

在 llm_json.py 之上加一层适配，方便 Agent 节点统一调用。
提供日志、监控埋点和错误重试能力。
"""

import logging
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel

from app.core.llm import model
from app.tools.llm_json import invoke_structured as _invoke_structured

logger = logging.getLogger(__name__)


def invoke_structured(
    schema: Type[BaseModel],
    prompt: str,
    *,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    debug_label: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> BaseModel:
    """封装 invoke_structured，增加日志和上下文注入

    参数:
        schema: Pydantic 输出模型
        prompt: 用户提示词
        temperature: 可选温度
        max_tokens: 可选最大 token
        debug_label: 调试标签
        context: 额外上下文（仅日志，不注入 prompt）
    """
    logger.info(
        "LLM call | schema=%s | label=%s | context_keys=%s",
        schema.__name__,
        debug_label,
        list(context.keys()) if context else None,
    )
    return _invoke_structured(
        model,
        schema,
        prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        debug_label=debug_label,
    )
