"""
Workflow 基类

所有 Workflow 继承此类，提供统一的 StateGraph 构建、执行和错误处理。
简单功能 = 单节点，复杂功能 = 多节点 + 条件边。
"""

import logging
from typing import Any, Callable, Dict, Optional, Type

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)


class BaseWorkflow:
    """Workflow 基类

    用法:
        class MyWorkflow(BaseWorkflow):
            def _build_graph(self):
                self.graph.add_node("step1", self.step1)
                self.graph.add_edge("step1", END)
    """

    def __init__(self):
        self.state_schema: Optional[Type[Dict]] = None
        self.graph: Optional[StateGraph] = None
        self.app = None

    def _define_state(self, state_schema: Type) -> None:
        """定义状态模型（TypedDict 或 Pydantic）"""
        self.state_schema = state_schema
        self.graph = StateGraph(state_schema)

    def _build_graph(self) -> None:
        """子类实现：添加节点和边"""
        raise NotImplementedError

    def compile(self) -> None:
        """编译图，生成可调用的 app"""
        self._build_graph()
        self.app = self.graph.compile()

    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """执行 Workflow"""
        if self.app is None:
            self.compile()
        try:
            result = self.app.invoke(initial_state)
            return result
        except Exception as e:
            logger.exception("Workflow 执行失败: %s", e)
            raise

    def add_simple_node(self, name: str, fn: Callable) -> None:
        """添加普通节点"""
        if self.graph is not None:
            self.graph.add_node(name, fn)

    def add_conditional_edge(
        self, from_node: str, condition_fn: Callable, path_map: Dict[str, str]
    ) -> None:
        """添加条件边"""
        if self.graph is not None:
            self.graph.add_conditional_edges(from_node, condition_fn, path_map)

    def add_edge(self, from_node: str, to_node: str) -> None:
        """添加普通边"""
        if self.graph is not None:
            if to_node == END:
                self.graph.add_edge(from_node, END)
            else:
                self.graph.add_edge(from_node, to_node)
