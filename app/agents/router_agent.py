"""
问题分类 Agent

将面试问题分为 tech / soft 两类：
- tech: 技术深度、系统设计、算法、代码、架构
- soft: 行为、沟通、业务理解、项目管理、职业规划
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent


class _QuestionCategory(BaseModel):
    sequence: int = Field(..., description="问题序号")
    category: str = Field(..., description="分类: tech 或 soft")


class _RouterOut(BaseModel):
    classified: List[_QuestionCategory] = Field(..., description="分类结果")


SYSTEM_PROMPT = """你是一个面试问题分类器。
判断每个问题属于哪个类别：
- tech: 技术深度、系统设计、算法、代码实现、技术选型、性能优化、架构设计
- soft: 行为经历、沟通协作、业务理解、项目管理、职业规划、团队管理

只输出分类结果，不分析问题内容。"""


class RouterAgent(BaseAgent):
    """将问题分类为 tech / soft"""

    def _get_output_schema(self):
        return _RouterOut

    def _build_prompt(self, state: Dict[str, Any]) -> str:
        qa_pairs = state.get("selected_qa_pairs", [])
        questions_text = "\n".join(
            f"Q{qa['sequence']}: {qa['question_text']}" for qa in qa_pairs
        )
        return (
            f"{SYSTEM_PROMPT}\n\n"
            f"岗位: {state.get('position', '')}  公司: {state.get('company', '')}\n\n"
            "===== 问题列表 =====\n"
            f"{questions_text}\n\n"
            "输出 classified 数组，每个元素包含 sequence 和 category。"
        )

    def _transform_result(
        self, result: BaseModel, state: Dict[str, Any]
    ) -> Dict[str, Any]:
        out: _RouterOut = result
        classified = {"tech": [], "soft": []}
        for item in out.classified:
            cat = item.category.lower()
            if cat in classified:
                classified[cat].append(item.sequence)
            else:
                classified["soft"].append(item.sequence)
        return {"classified": classified}
