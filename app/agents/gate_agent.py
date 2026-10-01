"""
质检 Agent

检查 Tech/Soft Agent 的分析结果是否存在矛盾、幻觉或遗漏。
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.core.llm import model
from app.core.prompts import load_prompt
from app.tools.llm_json import invoke_structured


class _GateIssue(BaseModel):
    type: str = Field(..., description="问题类型: contradiction|hallucination|omission")
    description: str = Field(..., description="问题描述")
    related_sequences: List[int] = Field(
        default_factory=list, description="相关问题序号"
    )


class _GateOut(BaseModel):
    issues: List[_GateIssue] = Field(default_factory=list, description="发现的问题")
    overall_quality: str = Field(..., description="整体质量: high|medium|low")


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

        return load_prompt(
            "interview",
            "gate_check",
            position=state.get("position", ""),
            company=state.get("company", ""),
            results_text=results_text,
        )

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        tech = state.get("tech_results", []) or []
        soft = state.get("soft_results", []) or []
        if not tech and not soft:
            return {"gate_report": {"issues": [], "overall_quality": "high"}}
        schema = self._get_output_schema()
        prompt = self._build_prompt(state)
        raw = invoke_structured(
            model,
            schema,
            prompt,
            debug_label="gate_agent",
            prompt_version="1",
        )
        return {"gate_report": raw.model_dump()}
