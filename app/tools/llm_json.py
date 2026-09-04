"""
LLM 结构化输出工具

统一封装 Pydantic schema 调用：
1. 优先使用 model.bind_tools(schema) 走 function calling
2. 失败时回退到手动 JSON 解析
"""

import json
import re
from typing import Any, Dict, Optional, Type, get_args, get_origin

from pydantic import BaseModel

from app.core.prompts import load_prompt


def _extract_json(text: str) -> Optional[str]:
    """从文本中提取 JSON 对象/数组（兼容 Qwen3 / DeepSeek 等模型的 <think> 标签）"""
    # 过滤掉思考过程标签，避免污染 JSON 提取
    text = re.sub(r"<think>[\s\S]*?</think>", "", text)
    text = text.strip()
    if not text:
        return None

    # 先尝试整个文本就是 JSON
    if text.startswith("{") and text.endswith("}"):
        return text
    if text.startswith("[") and text.endswith("]"):
        return text

    # 尝试 ```json ... ```
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # 尝试第一个 { ... }
    start = text.find("{")
    if start != -1:
        depth = 0
        in_str = False
        escape = False
        for i, ch in enumerate(text[start:], start):
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return text[start : i + 1]
    return None


def _invoke_with_bind_tools(
    model,
    schema: Type[BaseModel],
    prompt: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> BaseModel:
    """使用 LangChain bind_tools 调用结构化输出"""
    llm = model.bind_tools([schema], tool_choice=True)
    bind_kwargs = {}
    if temperature is not None:
        bind_kwargs["temperature"] = temperature
    if max_tokens is not None:
        bind_kwargs["max_tokens"] = max_tokens
    if bind_kwargs:
        llm = llm.bind(**bind_kwargs)
    response = llm.invoke(prompt)

    # 从 tool_calls 取参数
    tool_calls = getattr(response, "tool_calls", None)
    if tool_calls:
        args = tool_calls[0].get("args", {})
        return schema.model_validate(args)

    # 兼容部分模型把结果放 content
    content = getattr(response, "content", None)
    if content:
        json_str = _extract_json(content)
        if json_str:
            return schema.model_validate_json(json_str)

    raise ValueError("模型未返回 tool_call 或 JSON")


def _compact_schema_hint(schema: Type[BaseModel]) -> str:
    """用字段名+示例值生成紧凑 JSON 提示，避免完整 JSON Schema 占用过多 token"""

    def _type_example(annotation: Any) -> Any:
        origin = get_origin(annotation)
        args = get_args(annotation)
        if origin is list or annotation is list:
            inner = args[0] if args else str
            if isinstance(inner, type) and issubclass(inner, BaseModel):
                return [_build_example(inner)]
            return ["..."]
        if origin is set:
            return ["..."]
        if origin is dict:
            return {}
        if origin is Optional or (args and type(None) in args):
            for arg in args:
                if arg is not type(None):
                    return _type_example(arg)
            return None
        if isinstance(annotation, type):
            if issubclass(annotation, BaseModel):
                return _build_example(annotation)
            if issubclass(annotation, bool):
                return False
            if issubclass(annotation, int):
                return 0
            if issubclass(annotation, float):
                return 0.0
        return ""

    def _build_example(model: Type[BaseModel]) -> Dict[str, Any]:
        example: Dict[str, Any] = {}
        for name, field_info in model.model_fields.items():
            example[name] = _type_example(field_info.annotation)
        return example

    return json.dumps(_build_example(schema), ensure_ascii=False)


def _invoke_with_plain_json(
    model,
    schema: Type[BaseModel],
    prompt: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> BaseModel:
    """手动 JSON 解析兜底（使用紧凑 schema 提示，避免 token 超限）"""
    final_prompt = prompt + "\n\n" + load_prompt(
        "core",
        "json_fallback_suffix",
        schema_hint=_compact_schema_hint(schema),
    )
    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    response = model.invoke(final_prompt, **kwargs)
    content = getattr(response, "content", str(response))
    json_str = _extract_json(content)
    if not json_str:
        raise ValueError(f"无法从模型输出中提取 JSON: {content[:500]}")
    return schema.model_validate_json(json_str)


def invoke_structured(
    model,
    schema: Type[BaseModel],
    prompt: str,
    *,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    debug_label: Optional[str] = None,
    fallback: bool = True,
) -> BaseModel:
    """
    调用 LLM 并返回 Pydantic 结构化对象

    :param model: LangChain BaseChatModel
    :param schema: Pydantic 输出模型类
    :param prompt: 用户提示词
    :param temperature: 可选温度
    :param max_tokens: 可选最大输出 token 数
    :param debug_label: 调试标签，失败时打印
    :param fallback: 是否允许手动 JSON 兜底
    :return: schema 实例
    """
    try:
        return _invoke_with_bind_tools(model, schema, prompt, temperature, max_tokens)
    except Exception as e:
        if not fallback:
            raise
        try:
            return _invoke_with_plain_json(
                model, schema, prompt, temperature, max_tokens
            )
        except Exception as e2:
            label = f"[{debug_label}] " if debug_label else ""
            raise RuntimeError(f"{label}结构化调用失败: {e}; 兜底也失败: {e2}")
