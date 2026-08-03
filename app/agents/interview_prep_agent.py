"""
面试准备稿生成 Agent

基于 JD + 选中经历卡 + 公司调研 + 已投简历 + 面试轮次，生成完整面试逐字稿（单次 LLM 调用）。
prompt 由纯函数 _build_interview_prompt 构建，Agent 只负责 LLM 调用。
"""

from typing import Any, Dict

from app.agents.base_agent import BaseAgent
from app.core.llm import model
from app.schemas.jobcraft import InterviewPrepResult
from app.tools.llm_json import invoke_structured


class InterviewPrepAgent(BaseAgent):
    """生成面试准备稿（单次 LLM 调用）"""

    def _get_output_schema(self):
        return InterviewPrepResult

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """生成面试逐字稿。

        :param state: {"prompt": str}
        :return: {"prep_result": InterviewPrepResult dict}
        """
        prompt = state.get("prompt", "")
        if not prompt:
            raise ValueError("面试准备 prompt 为空")
        result = invoke_structured(
            model, InterviewPrepResult, prompt, debug_label="interview_prep"
        )
        return {"prep_result": result.model_dump()}
