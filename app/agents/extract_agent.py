"""
经历抽取 / 简历解析 / 标签推荐 Agent

三个独立节点，各封装 1 次 LLM 调用：
- ExtractStructuredAgent: raw_text → {cache, tags}（结构化成就缓存 + 扁平标签，
  EXPERIENCE_SPEC §26/§55：标签并入 STAR 抽取，规则标签池无候选时同次 LLM 输出）
- ParseResumeEntriesAgent: resume_text → 经历条目列表
- RecommendTagsAgent: raw_text → 扁平标签列表（规则标签池无候选时的 LLM 兜底）
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.core.llm import model
from app.core.prompts import load_prompt
from app.schemas.jobcraft import (
    CardStructuredCache,
    CardStructuredCacheWithTags,
    ResumeParseResult,
)
from app.tools.llm_json import invoke_structured


class ExtractStructuredAgent(BaseAgent):
    """从 raw_text 抽取结构化成就缓存 + 扁平标签（单次 LLM 调用）"""

    def _get_output_schema(self):
        return CardStructuredCacheWithTags

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """解析一段经历原始文本，返回结构化成就缓存与扁平标签。

        :param state: {"raw_text": str}
        :return: {"cache": CardStructuredCache dict | None, "tags": [str, ...]}
        """
        raw_text = state.get("raw_text", "")
        if not raw_text or not raw_text.strip():
            return {"cache": None, "tags": []}

        prompt = load_prompt(
            "experience", "extract_structured", version=3, raw_text=raw_text[:6000]
        )
        parsed = invoke_structured(
            model, CardStructuredCacheWithTags, prompt, debug_label="extract_structured"
        )
        if not parsed:
            return {"cache": None, "tags": []}
        if not parsed.achievements:
            return {"cache": None, "tags": parsed.tags[:8]}
        cache = CardStructuredCache(
            summary=parsed.summary, achievements=parsed.achievements
        ).model_dump()
        return {"cache": cache, "tags": parsed.tags[:8]}


class ParseResumeEntriesAgent(BaseAgent):
    """解析完整简历文本，提取每段经历（工作/实习/项目）（单次 LLM 调用）"""

    def _get_output_schema(self):
        return ResumeParseResult

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """提取简历中的工作/实习/项目经历。

        :param state: {"resume_text": str}
        :return: {"entries": [ResumeExperience dict, ...]}
        """
        resume_text = state.get("resume_text", "")
        if not resume_text or not resume_text.strip():
            return {"entries": []}

        prompt = load_prompt(
            "experience",
            "parse_resume_entries",
            version=2,
            resume_text=resume_text[:8000],
        )
        parsed = invoke_structured(
            model, ResumeParseResult, prompt, debug_label="parse_resume"
        )
        if not parsed or not parsed.entries:
            return {"entries": []}
        return {"entries": [e.model_dump() for e in parsed.entries]}


class _TagList(BaseModel):
    tags: List[str] = Field(default_factory=list)


class RecommendTagsAgent(BaseAgent):
    """根据 raw_text 推荐 3-5 个扁平标签（单次 LLM 调用）"""

    def _get_output_schema(self):
        return _TagList

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """推荐扁平标签。

        :param state: {"raw_text": str}
        :return: {"tags": [str, ...]}
        """
        raw_text = state.get("raw_text", "")
        if not raw_text or not raw_text.strip():
            return {"tags": []}

        prompt = load_prompt("experience", "recommend_tags", raw_text=raw_text[:3000])
        parsed = invoke_structured(
            model, _TagList, prompt, debug_label="recommend_tags"
        )
        return {"tags": parsed.tags[:8] if parsed else []}
