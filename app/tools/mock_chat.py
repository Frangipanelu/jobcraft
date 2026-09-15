"""
模拟面试对话工具

从 API 层提取出的 1 次 LLM 调用，遵循四层架构规则。
复用 app.core.llm 统一 model 实例，不直接创建 OpenAI 客户端。
"""

import logging
from typing import Any, Dict, List

from app.core.llm import model
from app.core.prompts import load_prompt

logger = logging.getLogger(__name__)


def mock_interview_chat(
    *,
    round_type: str,
    company: str,
    position: str,
    experience_context: str = "",
    messages: List[Dict[str, str]],
) -> str:
    """
    模拟面试实时对话（1 次 LLM 调用）。

    :param round_type: 面试轮次类型
    :param company: 公司名
    :param position: 岗位名
    :param experience_context: 候选人经历上下文
    :param messages: 对话历史 [{role, content}]
    :return: 模拟面试官回复文本
    """
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    system_prompt = load_prompt(
        "interview",
        "mock_interview_chat",
        round_type=round_type,
        company=company or "某科技公司",
        position=position or "技术岗位",
        candidate_background=(
            f"候选人背景：{experience_context}" if experience_context else ""
        ),
    )

    lc_messages: List[Any] = [SystemMessage(content=system_prompt)]
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "assistant":
            lc_messages.append(AIMessage(content=content))
        else:
            lc_messages.append(HumanMessage(content=content))

    resp = model.invoke(lc_messages)
    reply = resp.content.strip()
    if not reply:
        raise RuntimeError("模拟面试对话返回内容为空")
    return reply
