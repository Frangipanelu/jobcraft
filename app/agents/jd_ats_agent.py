"""
JD ATS 解析 Agent

从 JD 文本提取 8 维能力要求与岗位画像（单次 LLM 调用）。
"""

from typing import Any, Dict

from app.agents.base_agent import BaseAgent
from app.core.llm import model
from app.schemas.jobcraft import ATSProfile
from app.tools.llm_json import invoke_structured

# 8 维能力说明，用于 prompts
DIMENSION_DESCRIPTIONS = {
    "D1": "技术深度：专业技术能力、工具熟练度、领域知识深度",
    "D2": "业务理解：对行业、商业模式、用户价值的理解",
    "D3": "问题拆解：把复杂问题拆成可执行子问题的能力",
    "D4": "方案设计：设计可落地方案、架构、产品形态的能力",
    "D5": "落地执行：推进项目、协调资源、按时交付的能力",
    "D6": "数据复盘：用数据验证效果、总结经验的能力",
    "D7": "协作沟通：跨团队沟通、推动共识、汇报表达的能力",
    "D8": "职业规划：自我定位、成长路径与岗位匹配度",
}


def _build_ats_prompt(jd_text: str) -> str:
    dims = "\n".join([f"{k}: {v}" for k, v in DIMENSION_DESCRIPTIONS.items()])
    return (
        "你是一名专业的招聘 ATS 解析助手。请从以下 JD 中提取关键信息，"
        "并输出结构化的岗位画像。\n\n"
        "8 维能力矩阵说明（为每个维度输出 level 1-5 与证据）：\n"
        f"{dims}\n\n"
        "JD 文本：\n"
        "---\n"
        f"{jd_text[:6000]}\n"
        "---\n\n"
        "要求：\n"
        "1. required_skills 只放岗位硬性要求的技能；\n"
        "2. preferred_skills 放加分项；\n"
        "3. responsibilities 按条目列出核心职责；\n"
        "4. key_metrics 列出 JD 中提到的量化指标或 KPI；\n"
        "5. culture_keywords 提取公司文化/价值观关键词；\n"
        "6. dimension_requirements 必须包含 D1-D8，level 1-5，evidence 引用原文关键词。"
    )


class JdAtsAgent(BaseAgent):
    """解析 JD，返回 ATSProfile（单次 LLM 调用）"""

    def _get_output_schema(self):
        return ATSProfile

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """解析 JD 文本。

        :param state: {"jd_text": str}
        :return: {"ats": ATSProfile dict}
        """
        jd_text = state.get("jd_text", "")
        if not jd_text or not jd_text.strip():
            raise ValueError("JD 文本不能为空")
        prompt = _build_ats_prompt(jd_text)
        ats = invoke_structured(model, ATSProfile, prompt, debug_label="jd_ats")
        return {"ats": ats.model_dump()}
