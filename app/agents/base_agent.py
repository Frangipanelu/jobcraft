"""
Agent 节点基类

所有 Agent 节点继承此类，确保统一的调用接口和错误处理。
每个节点职责单一，单次调用内最多 1 次 LLM 调用。
"""

from typing import Any, Dict, Optional, Type

from pydantic import BaseModel

from app.core.llm import model
from app.tools.llm_json import invoke_structured


class BaseAgent:
    """Agent 节点基类

    子类只需实现 _build_prompt() 和 _get_output_schema() 两个方法。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def _get_output_schema(self) -> Type[BaseModel]:
        """子类返回输出 Pydantic Schema"""
        raise NotImplementedError

    def _build_prompt(self, state: Dict[str, Any]) -> str:
        """子类从 state 构建 prompt 文本"""
        raise NotImplementedError

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行 LLM 调用，返回更新后的 state 片段"""
        schema = self._get_output_schema()
        prompt = self._build_prompt(state)
        result = invoke_structured(
            model,
            schema,
            prompt,
            temperature=self.config.get("temperature"),
            max_tokens=self.config.get("max_tokens"),
            debug_label=self.__class__.__name__,
        )
        return self._transform_result(result, state)

    def _transform_result(
        self, result: BaseModel, state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """子类可按需重写，将结构化输出转为 state 更新"""
        schema = self._get_output_schema()
        return {schema.__name__: result.model_dump()}
