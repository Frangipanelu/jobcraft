"""
JD ATS 解析 Agent

从 JD 文本提取 8 维能力要求与岗位画像（单次 LLM 调用）。

支持 prompt 版本：
- v1：基础抽取（默认，向后兼容）
- v2：显式规则抽取（Issue 4，把 E1-E8 错误类写成硬性规则，单次调用，输出同 v1）
- v3：evidence-first（先抽证据、后出画像），输出附 `evidence_items`，
      后端以 `reconcile_evidence` 做确定性证据校验。
"""

from typing import Any, Dict

from app.agents.base_agent import BaseAgent
from app.agents.evidence import reconcile_evidence, reclassify_claims, split_ontology_claims
from app.core.llm import model
from app.core.prompts import load_prompt
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

# 支持的 prompt 版本（v2 为显式规则版 Prompt B）
_ATS_PROMPT_VERSIONS = {"v1": 1, "v2": 2, "v3": 3}


def _build_ats_prompt(jd_text: str, *, version: str = "v1") -> str:
    dims = "\n".join([f"{k}: {v}" for k, v in DIMENSION_DESCRIPTIONS.items()])
    ver = _ATS_PROMPT_VERSIONS.get(version, 1)
    return load_prompt(
        "jd", "jd_ats_analysis", version=ver, dims=dims, jd_text=jd_text[:6000]
    )


class JdAtsAgent(BaseAgent):
    """解析 JD，返回 ATSProfile（单次 LLM 调用）

    state 支持 ``prompt_version``（"v1" / "v2" / "v3"，默认 "v1"）：
    v3 证据模式返回原始输出 raw 与证据校验后的 ats 两份结果。
    """

    _DEFAULT_OUTPUT_SCHEMA = ATSProfile

    def _get_output_schema(self):
        return ATSProfile

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """解析 JD 文本。

        :param state: {"jd_text": str, "prompt_version"?: "v1"|"v2"|"v3"}
        :return: {"ats": ATSProfile dict}；v3 时另含 {"raw": 校验前原始 dict}
        """
        jd_text = state.get("jd_text", "")
        if not jd_text or not jd_text.strip():
            raise ValueError("JD 文本不能为空")
        version = state.get("prompt_version", "v1")
        prompt = _build_ats_prompt(jd_text, version=version)
        ats = invoke_structured(model, ATSProfile, prompt, debug_label="jd_ats")
        result: Dict[str, Any] = {"ats": ats.model_dump()}
        if version == "v3":
            result["raw"] = result["ats"]
            # 确定性后处理：本体归位（学历/年限移出技能列表）→ 职责/技能错位纠正
            # → 证据软校验
            result["ats"] = reconcile_evidence(
                reclassify_claims(split_ontology_claims(result["ats"]))
            )
        return result
