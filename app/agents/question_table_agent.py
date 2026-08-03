"""
问题表意图识别 Agent

为已解析的 QA 对生成轻量意图识别（intent/dimension/level），单次 LLM 调用。
prompt 构建由 interview_review._build_question_table_prompt 纯函数负责。
"""

from typing import Any, Dict

from app.agents.base_agent import BaseAgent
from app.core.llm import model
from app.tools.interview_review import (
    _QuestionTableOut,
    _build_question_table_prompt,
)
from app.tools.llm_json import invoke_structured


class QuestionTableAgent(BaseAgent):
    """生成问题表意图识别结果（单次 LLM 调用）"""

    def _get_output_schema(self):
        return _QuestionTableOut

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """为 QA 对生成意图识别。

        :param state: {"company", "position", "round_type", "qa_pairs", "jd_text"}
        :return: {"intent_by_seq": {sequence: {intent, dimension, level}}}
        """
        prompt = _build_question_table_prompt(
            company=state.get("company", ""),
            position=state.get("position", ""),
            round_type=state.get("round_type", ""),
            qa_pairs=state.get("qa_pairs", []),
            jd_text=state.get("jd_text", ""),
        )
        raw = invoke_structured(
            model,
            _QuestionTableOut,
            prompt,
            debug_label="interview_question_table",
            max_tokens=2048,
        )
        intent_by_seq = {q.sequence: q.model_dump() for q in raw.questions}
        return {"intent_by_seq": intent_by_seq}
