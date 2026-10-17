"""
问题分类 Agent

将面试问题分为 tech / soft 两类：
- tech: 技术深度、系统设计、算法、代码、架构
- soft: 行为、沟通、业务理解、项目管理、职业规划
"""

import logging
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.core.prompts import load_prompt

logger = logging.getLogger(__name__)


class _QuestionCategory(BaseModel):
    sequence: int = Field(..., description="问题序号")
    category: str = Field(..., description="分类: tech 或 soft")


class _RouterOut(BaseModel):
    classified: List[_QuestionCategory] = Field(..., description="分类结果")


class RouterAgent(BaseAgent):
    """将问题分类为 tech / soft"""

    #: 分类必须可复现（T-EVAL-3）：分类漂移会把题漏出分析范围 → 空 feedback
    DEFAULT_TEMPERATURE = 0.0

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

        # 分类覆盖保证（T-EVAL-3）：selected 全集必须落桶，LLM 漏分类的题
        # 补入 soft 默认桶并告警——否则该题不进任何分析器 → assemble 静默空 feedback
        covered = set(classified["tech"]) | set(classified["soft"])
        missing = [
            qa["sequence"]
            for qa in state.get("selected_qa_pairs", [])
            if qa["sequence"] not in covered
        ]
        if missing:
            logger.warning(
                "router 未覆盖 %d 题（补入 soft 默认桶）: %s",
                len(missing),
                missing,
            )
            classified["soft"].extend(missing)

        return {"classified": classified}
