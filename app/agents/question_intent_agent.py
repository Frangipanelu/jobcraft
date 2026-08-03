"""
问题意图预览 Agent

为解析预览场景的 QA 对生成轻量意图识别（intent/dimension/level），
**不写入数据库**，单次 LLM 调用。
"""

from typing import Any, Dict

from app.agents.base_agent import BaseAgent
from app.core.llm import model
from app.tools.interview_review import (
    _QuestionTableOut,
    _build_question_table_prompt,
)
from app.tools.llm_json import invoke_structured


class QuestionIntentAgent(BaseAgent):
    """为 QA 对生成轻量意图识别结果，仅用于解析预览（单次 LLM 调用）"""

    def _get_output_schema(self):
        return _QuestionTableOut

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """生成意图标签并合并回 QA 对。

        :param state: {"company", "position", "round_type", "qa_pairs", "jd_text"}
        :return: {"qa_pairs": [qa dict with intent/dimension/level, ...]}
        """
        qa_pairs = state.get("qa_pairs", [])
        if not qa_pairs:
            return {"qa_pairs": []}

        prompt = _build_question_table_prompt(
            company=state.get("company", ""),
            position=state.get("position", ""),
            round_type=state.get("round_type", ""),
            qa_pairs=qa_pairs,
            jd_text=state.get("jd_text", ""),
        )
        raw = invoke_structured(
            model,
            _QuestionTableOut,
            prompt,
            debug_label="interview_preview_intents",
            max_tokens=2048,
        )
        intent_by_seq = {q.sequence: q.model_dump() for q in raw.questions}
        result = []
        for qa in qa_pairs:
            seq = qa["sequence"]
            intent_data = intent_by_seq.get(seq, {})
            result.append(
                {
                    **qa,
                    "intent": intent_data.get("intent", ""),
                    "dimension": intent_data.get("dimension", "D7 协作沟通"),
                    "level": intent_data.get("level", "L3"),
                }
            )
        return {"qa_pairs": result}
