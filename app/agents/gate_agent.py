"""
质检 Agent

检查 Tech/Soft Agent 的分析结果是否存在矛盾、幻觉或遗漏。
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent


class _GateIssue(BaseModel):
    type: str = Field(..., description="问题类型: contradiction|hallucination|omission")
    description: str = Field(..., description="问题描述")
    related_sequences: List[int] = Field(
        default_factory=list, description="相关问题序号"
    )


class _GateOut(BaseModel):
    issues: List[_GateIssue] = Field(default_factory=list, description="发现的问题")
    overall_quality: str = Field(..., description="整体质量: high|medium|low")


SYSTEM_PROMPT = """你是一个质量审核官。检查以下分析结果是否存在：
1. 矛盾：不同问题对同一维度的评分明显冲突
2. 幻觉：分析了经历卡中不存在的细节
3. 遗漏：明显相关的问题缺失分析

只输出质检结果，不修改分析内容。"""


class GateAgent(BaseAgent):
    """检查分析结果质量"""

    def _get_output_schema(self):
        return _GateOut

    def _build_prompt(self, state: Dict[str, Any]) -> str:
        results = []
        for item in state.get("tech_results", []) or []:
            results.append(
                f"[tech] Q{item['sequence']}: score={item['score']} dim={item['dimension']}"
            )
        for item in state.get("soft_results", []) or []:
            results.append(
                f"[soft] Q{item['sequence']}: score={item['score']} dim={item['dimension']}"
            )
        results_text = "\n".join(results) if results else "无分析结果"

        return (
            f"{SYSTEM_PROMPT}\n\n"
            f"岗位: {state.get('position', '')}  公司: {state.get('company', '')}\n\n"
            "===== 分析结果摘要 =====\n"
            f"{results_text}\n\n"
            "请检查是否存在问题，输出质检结果。"
        )

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        tech = state.get("tech_results", []) or []
        soft = state.get("soft_results", []) or []
        if not tech and not soft:
            return {"gate_report": {"issues": [], "overall_quality": "high"}}
        schema = self._get_output_schema()
        prompt = self._build_prompt(state)
        raw = self._invoke(schema, prompt)
        return {"gate_report": raw.model_dump()}

    def _invoke(self, schema, prompt):
        """轻量调用，不使用 model.bind_tools 的兜底"""
        from app.core.llm import model
        from langchain_core.messages import HumanMessage

        llm = model.bind_tools([schema], tool_choice=True)
        response = llm.invoke([HumanMessage(content=prompt)])
        tool_calls = getattr(response, "tool_calls", None)
        if tool_calls:
            args = tool_calls[0].get("args", {})
            return schema.model_validate(args)
        return schema()
