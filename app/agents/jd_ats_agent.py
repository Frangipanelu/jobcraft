"""
JD ATS 解析 Agent

从 JD 文本提取 8 维能力要求与岗位画像。

支持 prompt 版本：
- v1：基础抽取（默认，向后兼容）
- v2：显式规则抽取（Issue 4，把 E1-E8 错误类写成硬性规则，单次调用，输出同 v1）
- v3：evidence-first（先抽证据、后出画像），输出附 `evidence_items`，
      后端以 `reconcile_evidence` 做确定性证据校验。
- v4：分层收窄（v0.5 Task06）——先跑确定性 L1 管道
      （structurer→classifier→extractor→evidence），LLM 只收结构化摘要 +
      截断 JD，只出「岗位名/文化词/D1-D8/潜台词/歧义裁决」，
      再由确定性合并回 ATSProfile。
"""

import json
import re
from itertools import count
from typing import Any, Dict, Sequence

from app.agents.base_agent import BaseAgent
from app.agents.evidence import (
    normalize,
    reconcile_evidence,
    reclassify_claims,
    split_ontology_claims,
)
from app.core.llm import model
from app.core.prompts import load_prompt
from app.pipeline.evidence_builder import build_source_evidence
from app.pipeline.jd_classifier import ClassLabel, ClassifiedItem, classify_jd
from app.pipeline.jd_extractor import JDExtraction, extract_jd
from app.pipeline.jd_structurer import (
    SectionItem,
    SectionKind,
    StructuredJD,
    structure_jd,
)
from app.schemas.jobcraft import (
    ATSProfile,
    AtsInference,
    EvidenceItem,
    StructuredRequirementItem,
)
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

# 支持的 prompt 版本（v2 为显式规则版 Prompt B，v4 为分层收窄版）
_ATS_PROMPT_VERSIONS = {"v1": 1, "v2": 2, "v3": 3, "v4": 4}

# LLM 歧义裁决标签 → ATSProfile 列表字段
_LABEL_TO_FIELD = {
    "required": "required_skills",
    "preferred": "preferred_skills",
    "responsibility": "responsibilities",
    "soft_skill": "soft_skills",
}

# 低置信阈值：低于此值或 UNKNOWN 的条目交由 LLM 复核
_REVIEW_CONFIDENCE = 0.6

# 格式/薪资 stub 判据：markdown 标题行（`##Al Builder - 产品`），或
# 全粗体薪资 stub（如「欣旺达**生产经理****17-22k**」）。这类文本不是需求，
# L1 无法归类（UNKNOWN），也不应被 LLM 裁决成 required。
_REQUIREMENT_STUB_RE = re.compile(
    r"(?:^\s*#{1,6}\s*\S|\*{2}[^*]*\d+\s*[-~]\s*\d+\s*[kKwW万]?[^*]*\*{2})"
)


def _build_ats_prompt(jd_text: str, *, version: str = "v1") -> str:
    dims = "\n".join([f"{k}: {v}" for k, v in DIMENSION_DESCRIPTIONS.items()])
    ver = _ATS_PROMPT_VERSIONS.get(version, 1)
    return load_prompt(
        "jd", "jd_ats_analysis", version=ver, dims=dims, jd_text=jd_text[:6000]
    )


def _needs_review(classified: Sequence[ClassifiedItem]) -> list[ClassifiedItem]:
    """算法把握不足的条目（UNKNOWN 或低置信），交由 LLM 裁决。"""
    return [
        c
        for c in classified
        if c.label.value == "unknown" or c.confidence < _REVIEW_CONFIDENCE
    ]


def _build_structured_summary(
    structured: StructuredJD,
    classified: Sequence[ClassifiedItem],
    extraction: JDExtraction,
) -> str:
    """构造给 LLM 的紧凑结构化摘要（JSON 字符串）。"""
    payload = {
        "sections": sorted({c.section.value for c in classified}),
        "items": [
            {
                "id": c.item_id,
                "section": c.section.value,
                "label": c.label.value,
                "confidence": round(c.confidence, 2),
                "text": c.text[:80],
            }
            for c in classified
        ],
        "needs_review": [c.item_id for c in _needs_review(classified)],
        "extraction": {
            "required_skills": extraction.required_skills,
            "preferred_skills": extraction.preferred_skills,
            "responsibilities": extraction.responsibilities,
            "soft_skills": extraction.soft_skills,
            "education": extraction.education,
            "years_of_experience": extraction.years_of_experience,
            "salary": extraction.salary,
            "location": extraction.location,
            "key_metrics": extraction.key_metrics,
        },
        "candidate_signals": [
            {"keyword": k.keyword, "category": k.category, "importance": k.importance}
            for k in extraction.core_keywords
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def _build_v4_prompt(
    jd_text: str,
    structured: StructuredJD,
    classified: Sequence[ClassifiedItem],
    extraction: JDExtraction,
) -> str:
    dims = "\n".join([f"{k}: {v}" for k, v in DIMENSION_DESCRIPTIONS.items()])
    return load_prompt(
        "jd",
        "jd_ats_analysis",
        version=4,
        dims=dims,
        structured_summary=_build_structured_summary(
            structured, classified, extraction
        ),
        jd_text=jd_text[:3000],
    )


# 结构化路径：用户标签 → ClassLabel（取代 L1 区块检测与 required/preferred 猜测）
_STRUCT_TAG_TO_SECTION = {
    "hard": SectionKind.REQUIREMENTS,
    "required": SectionKind.REQUIREMENTS,
    "preferred": SectionKind.PREFERRED,
}
_STRUCT_TAG_TO_LABEL = {
    "hard": ClassLabel.REQUIRED,
    "required": ClassLabel.REQUIRED,
    "preferred": ClassLabel.PREFERRED,
}


def _build_structured_from_input(
    duties: Sequence[str],
    requirements: Sequence[StructuredRequirementItem],
) -> tuple[StructuredJD, list[ClassifiedItem]]:
    """把前端已分好类的 duties/requirements 转成 L1 管线输入。

    - 每条 duty → ``responsibilities`` 区块 + ``RESPONSIBILITY`` 标签。
    - 每条 requirement 按用户标签（hard/required/preferred）直接给出
      section 与 label，确定性分流，不再依赖区块检测或 LLM 猜 preferred。
    - ``unknown`` 条目不存在：用户没打标签的诉求由前端兜底补标签，
      后端绝不把硬门槛/加分项误判进 required（此前 preferred 召回差的根因）。

    :param duties: 岗位职责逐条文本。
    :param requirements: 任职要求逐条（含用户标签）。
    :return: (结构化输入, 确定性分类结果)。
    """
    doc = StructuredJD(source="")
    classified: list[ClassifiedItem] = []
    seq = count(1)
    for text in duties:
        item_id = f"resp_{next(seq):03d}"
        raw = text if text.endswith(("\n", "、", "。", ";", "；")) else text + "。"
        item = SectionItem(
            item_id=item_id,
            section=SectionKind.RESPONSIBILITIES,
            text=text,
            raw=raw,
            start=0,
            end=len(text),
        )
        doc.items.append(item)
        classified.append(
            ClassifiedItem(
                item_id=item_id,
                section=SectionKind.RESPONSIBILITIES,
                text=text,
                start=0,
                end=len(text),
                label=ClassLabel.RESPONSIBILITY,
                confidence=1.0,
                rule="structured:duty",
            )
        )
    for req in requirements:
        text = (req.text or "").strip()
        if not text:
            continue
        tag = req.tag or "required"
        section = _STRUCT_TAG_TO_SECTION.get(tag, SectionKind.REQUIREMENTS)
        label = _STRUCT_TAG_TO_LABEL.get(tag, ClassLabel.REQUIRED)
        item_id = f"{'req' if section is SectionKind.REQUIREMENTS else 'pref'}_{next(seq):03d}"
        item = SectionItem(
            item_id=item_id,
            section=section,
            text=text,
            raw=text,
            start=0,
            end=len(text),
        )
        doc.items.append(item)
        classified.append(
            ClassifiedItem(
                item_id=item_id,
                section=section,
                text=text,
                start=0,
                end=len(text),
                label=label,
                confidence=1.0,
                rule=f"structured:{tag}",
            )
        )
    return doc, classified


def _structured_to_text(
    duties: Sequence[str], requirements: Sequence[StructuredRequirementItem]
) -> str:
    """把两条结构化块拼回可读文本，供 LLM 细节分析（地址/薪资不传入）。"""
    lines: list[str] = []
    if duties:
        lines.extend(["【岗位职责】", *duties])
    if requirements:
        lines.append("【任职要求】")
        for r in requirements:
            head = {
                "hard": "（硬性门槛）",
                "required": "（必选）",
                "preferred": "（加分项）",
            }.get(r.tag, "")
            lines.append(f"{head}{r.text.strip()}")
    return "\n".join(lines)


def analyze_structured_jd(
    duties: Sequence[str],
    requirements: Sequence[StructuredRequirementItem],
) -> Dict[str, Any]:
    """结构化 JD 分析入口：L1 确定性 + LLM 细节（文化词/D1-D8/潜台词）一次调用。

    与 ``v4`` 分层路径区别：不需要 ``structure_jd`` 区块检测，
    也不需要 classifier 猜 required/preferred——用户标签即事实。
    L1 仍负责 学历/年限/指标/技能token/经验证据 的确定性抽取。

    :param duties: 岗位职责逐条。
    :param requirements: 任职要求逐条（用户已打 hard/required/preferred 标签）。
    :return: {"ats": ATSProfile dict, "raw": AtsInference dict}。
    """
    structured, classified = _build_structured_from_input(duties, requirements)
    if not classified:
        raise ValueError("岗位职责与任职要求不能同时为空")
    extraction = extract_jd(structured, classified)
    jd_text = _structured_to_text(duties, requirements)

    inference = invoke_structured(
        model,
        AtsInference,
        _build_v4_prompt(jd_text, structured, classified, extraction),
        debug_label="jd_ats_v4_structured",
    )
    merged = merge_ats(extraction, classified, inference, jd_text)
    return {
        "ats": merged.model_dump(),
        "raw": inference.model_dump(),
    }


def merge_ats(
    extraction: JDExtraction,
    classified: Sequence[ClassifiedItem],
    inference: AtsInference,
    jd_text: str,
) -> ATSProfile:
    """把 L1 算法抽取与收窄 LLM 推理确定性地合并为 ATSProfile。

    :param extraction: :func:`jd_extractor.extract_jd` 的算法抽取结果。
    :param classified: :func:`jd_classifier.classify_jd` 的分类结果（供歧义裁决定位）。
    :param inference: 收窄 LLM 输出（文化词/维度/潜台词/歧义裁决）。
    :param jd_text: JD 原文（用于 EvidenceItem 的 span 校验语义）。
    :return: 合并后的 ATSProfile。
    """
    text_by_id = {c.item_id: c.text for c in classified}
    label_by_id = {c.item_id: c.label for c in classified}
    bucket = {
        "required_skills": list(extraction.required_skills),
        "preferred_skills": list(extraction.preferred_skills),
        "responsibilities": list(extraction.responsibilities),
        "soft_skills": list(extraction.soft_skills),
    }
    for decision in inference.ambiguous:
        field = _LABEL_TO_FIELD.get(decision.label)
        text = text_by_id.get(decision.item_id)
        # LLM 只裁决 L1 未定论（UNKNOWN）的条目：L1 已确定性归类时不覆盖，
        # 防止缓存远期 raw 的陈旧裁决在重建时污染 L1 核心结果。
        if label_by_id.get(decision.item_id) is not ClassLabel.UNKNOWN:
            continue
        # 纯格式/薪资 stub 不是需求，LLM 也不应收编（如「**17-22k**」）。
        if not field or not text or _REQUIREMENT_STUB_RE.search(text):
            continue
        existing = {normalize(v) for v in bucket[field]}
        if normalize(text) not in existing:
            bucket[field].append(text)

    evidence = [
        EvidenceItem(id=i, field=e.field, span=e.text, derived=e.text)
        for i, e in enumerate(build_source_evidence(classified), start=1)
    ]

    ats = ATSProfile(
        job_title=inference.job_title or "",
        location=extraction.location,
        salary=extraction.salary,
        years_of_experience=extraction.years_of_experience,
        education=extraction.education,
        required_skills=bucket["required_skills"],
        preferred_skills=bucket["preferred_skills"],
        responsibilities=bucket["responsibilities"],
        soft_skills=bucket["soft_skills"],
        key_metrics=list(extraction.key_metrics),
        culture_keywords=list(inference.culture_keywords),
        core_keywords=list(extraction.core_keywords),
        dimension_requirements=list(inference.dimension_requirements),
        subtext_decoded=list(inference.subtext_decoded),
        evidence_items=evidence,
        raw_summary=jd_text[:500],
    )
    return ats


class JdAtsAgent(BaseAgent):
    """解析 JD，返回 ATSProfile

    state 支持 ``prompt_version``（"v1" / "v2" / "v3" / "v4"，默认 "v1"）：
    v3 证据模式返回原始输出 raw 与证据校验后的 ats 两份结果；
    v4 分层模式返回 L1 合并后的 ats 与 LLM 原始推理 raw。
    """

    _DEFAULT_OUTPUT_SCHEMA = ATSProfile

    def _get_output_schema(self):
        return ATSProfile

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """解析 JD 文本。

        :param state: {"jd_text": str, "prompt_version"?: "v1"|"v2"|"v3"|"v4"}
        :return: {"ats": ATSProfile dict}；v3/v4 时另含 {"raw": ...}
        """
        jd_text = state.get("jd_text", "")
        if not jd_text or not jd_text.strip():
            raise ValueError("JD 文本不能为空")
        version = state.get("prompt_version", "v1")

        if version == "v4":
            return self._run_v4(jd_text)

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

    def _run_v4(self, jd_text: str) -> Dict[str, Any]:
        """分层收窄路径：L1 管道（确定性）+ 收窄 LLM 推理 + 确定性合并。"""
        structured = structure_jd(jd_text)
        classified = classify_jd(structured)
        extraction = extract_jd(structured, classified)

        prompt = _build_v4_prompt(jd_text, structured, classified, extraction)
        inference = invoke_structured(
            model, AtsInference, prompt, debug_label="jd_ats_v4"
        )

        merged = merge_ats(extraction, classified, inference, jd_text)
        return {
            "ats": merged.model_dump(),
            "raw": inference.model_dump(),
        }
