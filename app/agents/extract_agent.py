"""
经历抽取 / 简历解析 / 标签推荐 Agent

三个独立节点，各封装 1 次 LLM 调用：
- ExtractStructuredAgent: raw_text → CardStructuredCache（结构化成就缓存）
- ParseResumeEntriesAgent: resume_text → 经历条目列表
- RecommendTagsAgent: raw_text → 扁平标签列表
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.core.llm import model
from app.schemas.jobcraft import CardStructuredCache, ResumeParseResult
from app.tools.llm_json import invoke_structured


class ExtractStructuredAgent(BaseAgent):
    """从 raw_text 抽取结构化成就缓存（单次 LLM 调用）"""

    def _get_output_schema(self):
        return CardStructuredCache

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """解析一段经历原始文本，返回结构化成就缓存。

        :param state: {"raw_text": str}
        :return: {"cache": CardStructuredCache dict | None}
        """
        raw_text = state.get("raw_text", "")
        if not raw_text or not raw_text.strip():
            return {"cache": None}

        prompt = (
            "你是一名求职顾问，擅长从原始经历描述中抽取结构化的成就信息。\n"
            "请仔细阅读以下经历描述，抽取 1-3 条核心成就。\n\n"
            "每条成就包含：\n"
            "- title: 成就标题（精简）\n"
            "- situation: 背景/情境 (S)\n"
            "- action.main: 采取的主要行动 (A)\n"
            "- action.difficulty: 遇到的困难（有则写，无则空）\n"
            "- action.resolution: 如何解决困难（有则写，无则空）\n"
            "- result: 结果/收益 (R)，尽量包含量化指标\n\n"
            "如果描述中没有明确区分 S/A/R，基于原文合理推断，不要编造。\n"
            "输出 JSON: {\n"
            '  "summary": "一句话总结这段经历",\n'
            '  "achievements": [Achievement, ...]\n'
            "}\n\n"
            "经历描述：\n"
            "---\n"
            f"{raw_text[:6000]}\n"
            "---"
        )
        parsed = invoke_structured(
            model, CardStructuredCache, prompt, debug_label="extract_structured"
        )
        if not parsed or not parsed.achievements:
            return {"cache": None}
        return {"cache": parsed.model_dump()}


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

        prompt = (
            "你是一名简历解析专家。请从以下简历文本中提取所有 **工作经历 / 实习经历 / 项目经历**。\n\n"
            "规则：\n"
            "1. 只提取工作经历、实习经历、项目经历三个部分\n"
            "2. 跳过：个人信息（姓名/电话/邮箱/地址）、教育背景、专业技能、自我评价、个人作品链接\n"
            "3. 每段经历输出一条 entry\n"
            "4. 如果某段经历包含多条 bullet 项，每个 bullet 拆成一个 achievement\n"
            "5. summary 写一句总概括，格式：'参与/负责了xx项目/xx流程，实现/达成xx目标，带来xx%提升'\n"
            "6. company/role/period 从原文提取，原文没有则填空字符串\n"
            "7. 每条 achievement 的 title 写 bullet 的核心动作，situation/action/result 尽量提取量化结果\n\n"
            "输出 JSON: {\n"
            '  "entries": [\n'
            "    {\n"
            '      "company": "公司名",\n'
            '      "role": "职位",\n'
            '      "period": "2020.03 - 2022.06",\n'
            '      "title": "经历标题",\n'
            '      "summary": "一句话总概括",\n'
            '      "achievements": [\n'
            '        { "title": "...", "situation": "...", "action": {"main": "...", "difficulty": "", "resolution": ""}, "result": "..." },\n'
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "简历文本：\n---\n"
            f"{resume_text[:8000]}\n---"
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

        prompt = (
            "读这段经历描述，推荐 3-5 个标签。\n"
            "标签是扁平关键词，不分类、不层级、不加#。\n"
            "参考方向：技术栈 / 业务领域 / 能力维度 / 行业。\n"
            "只输出标签列表。\n\n"
            f"经历描述：\n{raw_text[:3000]}"
        )
        parsed = invoke_structured(
            model, _TagList, prompt, debug_label="recommend_tags"
        )
        return {"tags": parsed.tags[:8] if parsed else []}
