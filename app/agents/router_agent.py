"""
问题分类 Agent

将面试问题分为 tech / soft 两类：
- tech: 技术深度、系统设计、算法、代码、架构
- soft: 行为、沟通、业务理解、项目管理、职业规划
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.core.prompts import load_prompt


class _QuestionCategory(BaseModel):
    sequence: int = Field(..., description="问题序号")
    category: str = Field(..., description="分类: tech 或 soft")


class _RouterOut(BaseModel):
    classified: List[_QuestionCategory] = Field(..., description="分类结果")


class RouterAgent(BaseAgent):
    """将问题分类为 tech / soft"""

    def _get_output_schema(self):
        return _RouterOut

    def _build_prompt(self, state: Dict[str, Any]) -> str:
        qa_pairs = state.get("selected_qa_pairs", [])
        questions_text = "\n".join(
            f"Q{qa['sequence']}: {qa['question_text']}" for qa in qa_pairs
        )
        return load_prompt(
            "interview",
            "question_router",
            position=state.get("position", ""),
            company=state.get("company", ""),
            questions_text=questions_text,
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
