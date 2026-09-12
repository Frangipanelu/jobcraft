"""JD 条目规则分类器（Pipeline L1 · 纯确定性，无 LLM）。

把 :class:`~app.pipeline.jd_structurer.SectionItem` 按
``Section + Trigger + Verb + Context`` 联合判定为五类：

- ``REQUIRED``：任职硬门槛（含学历/年限 gate、能力动词句、技能名词短语）。
- ``PREFERRED``：加分/优先（区块或显式标记如「优先/加分/尤佳/Bonus」）。
- ``RESPONSIBILITY``：职责（动作动词开头或职责区块默认）。
- ``SOFT_SKILL``：软实力要求（软技能词 + 程度语境，如「沟通能力较强」）。
- ``UNKNOWN``：规则无法可靠判定，留给 L2 LLM fallback（不硬猜）。

设计基线（`docs/evaluation/JobCraft ATS Pipeline v0.5` §六-§九）：

- **放弃「技术词 = Required」的朴素二分**：分类由区块先验 + 显式标记 +
  动词首发 + 软技能词典共同决定；词典仅做候选生成，不替代语义判断。
- **Uncertain → UNKNOWN**：只输出把握足够的结论，其余交给 LLM，避免把
  边界案例当高置信处理（吸取"朴素端点分类全错"实验教训）。
- 动词判定复用 ``app.agents.evidence.classify_sentence_role``，与既有
  reclassifier 保持行为一致，避免维护两套词表。
"""

from __future__ import annotations

import json
import re
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from app.agents.evidence import (
    _EDU_PATTERNS,
    _YEARS_RE,
    classify_sentence_role,
)
from app.pipeline.jd_structurer import SectionItem, SectionKind, StructuredJD

_DATA_DIR = Path(__file__).parent / "data"


class ClassLabel(StrEnum):
    """条目分类标签（v0.5 §六）。"""

    REQUIRED = "required"
    PREFERRED = "preferred"
    RESPONSIBILITY = "responsibility"
    SOFT_SKILL = "soft_skill"
    UNKNOWN = "unknown"


class ClassifiedItem(BaseModel):
    """一条+分类结果（保留原文 Span，供证据层复用）。"""

    item_id: str
    section: SectionKind
    text: str
    start: int
    end: int
    label: ClassLabel
    confidence: float = Field(ge=0.0, le=1.0)
    rule: str = Field(description="命中规则，如 verb:capability / marker:preferred")


def _load_words(name: str, key: str) -> tuple[str, ...]:
    """从 ``app/pipeline/data/*.json`` 加载词表。"""
    data = json.loads((_DATA_DIR / name).read_text(encoding="utf-8"))
    return tuple(str(w) for w in data[key])


_SOFT_WORDS = _load_words("soft_skills.json", "soft_skills")
_TECH_WORDS = _load_words("technical_skills.json", "technical_skills")

_PREFERRED_MARKERS = (
    "优先",
    "加分",
    "尤佳",
    "Bonus",
    "Preferred",
    "preferred",
    "Nice to have",
    "nice to have",
)

# 软能力程度语境：沟通能力较强 / 较强的业务理解能力 / 执行力强
_SOFT_STRENGTH = r"(?:(?:较强|很强|极强|优秀|出色|良好|扎实|比较好|较好|卓越)(?:的)?)?"
# 组合模式：
#   a) 沟通能力强 / 抗压能力较强 / 责任心强
#   b) (较强的)业务理解能力  —— 强度词在前
_SOFT_TRAIT_RE = re.compile(
    "|".join(
        re.escape(w)
        + r"(?:能力|素养|精神|意识|思维|态度|水平|习惯)?"
        + r"(?:的)?(?:较|很|极)?(?:强|好|高|优秀|出色|扎实|良好|清晰)"
        + "|"
        + _SOFT_STRENGTH
        + re.escape(w)
        + r"(?:能力|素养|精神|意识|思维|态度|水平|习惯)?"
        for w in _SOFT_WORDS
    ),
    re.IGNORECASE,
)

# 学历/年限 gate（复用 evidence.py 常量，保持单一词表来源）
_EDU_RE_LIST = _EDU_PATTERNS
_YEARS_RE_LIST = (_YEARS_RE,)

# 条目仅在这些区块内才享«默认归属»（section 语境越强、置信越高）
_REQLIKE = {SectionKind.REQUIREMENTS, SectionKind.UNKNOWN}


def _has_preferred_marker(text: str) -> bool:
    return any(m in text for m in _PREFERRED_MARKERS)


def _soft_trait_match(text: str) -> bool:
    return bool(_SOFT_TRAIT_RE.search(text))


def _soft_word_match(text: str) -> bool:
    low = text.lower()
    return any(w.lower() in low for w in _SOFT_WORDS)


def _is_gate(text: str) -> bool:
    """学历/年限 hard gate（Same as both型：命中即必需项，抽取交 jd_extractor）。"""
    return any(p.search(text) for p in _EDU_RE_LIST) or any(
        p.search(text) for p in _YEARS_RE_LIST
    )


def classify_item(item: SectionItem) -> ClassifiedItem:
    """对单条 SectionItem 做五类判定（纯函数，无 LLM）。

    :param item: jd_structurer 产出的条目（含区块与原文 Span）。
    :return: 分类结果（含置信度与命中规则说明）。
    """
    text = item.text
    section = item.section
    label: ClassLabel
    confidence: float
    rule: str

    # 1) 区块先验：加分/优先区块 → PREFERRED
    if section is SectionKind.PREFERRED:
        label, confidence, rule = ClassLabel.PREFERRED, 1.0, "section:preferred"
    # 2) 显式标记：优先/加分/尤佳/Bonus…（任意区块，标记即语义）
    elif _has_preferred_marker(text):
        label, confidence, rule = ClassLabel.PREFERRED, 1.0, "marker:preferred"
    # 3) 软能力程度语境：沟通能力较强 / 较强的业务理解能力 / 执行力强
    elif _soft_trait_match(text):
        conf = 0.95 if section in _REQLIKE else 0.7
        label, confidence, rule = ClassLabel.SOFT_SKILL, conf, "context:soft_trait"
    else:
        role = classify_sentence_role(text)
        if role == "responsibility":
            label, confidence, rule = ClassLabel.RESPONSIBILITY, 1.0, "verb:action"
        elif section is SectionKind.RESPONSIBILITIES:
            label, confidence, rule = (
                ClassLabel.RESPONSIBILITY,
                0.9,
                "section:responsibilities",
            )
        else:
            soft = _soft_word_match(text)
            if role == "skill":
                # 能力动词句：软实力 → SOFT_SKILL，否则 → REQUIRED
                if soft:
                    label, confidence, rule = (
                        ClassLabel.SOFT_SKILL,
                        0.9,
                        "verb:capability+soft",
                    )
                else:
                    conf = 0.9 if section in _REQLIKE else 0.6
                    label, confidence, rule = (
                        ClassLabel.REQUIRED,
                        conf,
                        "verb:capability",
                    )
            elif _is_gate(text):
                label, confidence, rule = ClassLabel.REQUIRED, 0.95, "gate:edu/years"
            elif section is SectionKind.REQUIREMENTS:
                # 无动词名词短语（如「MySQL、Redis」），区块语境兜底为必需
                if soft:
                    label, confidence, rule = (
                        ClassLabel.SOFT_SKILL,
                        0.7,
                        "context:soft_phrase",
                    )
                else:
                    label, confidence, rule = (
                        ClassLabel.REQUIRED,
                        0.6,
                        "section:requirements",
                    )
            elif section is SectionKind.UNKNOWN or section is SectionKind.JOB_OVERVIEW:
                label, confidence, rule = ClassLabel.UNKNOWN, 0.3, "section:no_prior"
            else:
                label, confidence, rule = (
                    ClassLabel.UNKNOWN,
                    0.2,
                    f"section:{section.value}",
                )

    return ClassifiedItem(
        item_id=item.item_id,
        section=item.section,
        text=item.text,
        start=item.start,
        end=item.end,
        label=label,
        confidence=confidence,
        rule=rule,
    )


def classify_jd(structured: StructuredJD) -> list[ClassifiedItem]:
    """对结构化 JD 的所有分析条目依次分类。

    meta（薪资/地点）区块不属于分析内容，由 L0 元数据/抽取器处理，不进入
    分类结果；也不会因此污染 LLM fallback 队列。

    :param structured: :func:`jd_structurer.structure_jd` 的输出。
    :return: 按文档顺序排列的条目分类结果列表。
    """
    return [
        classify_item(item)
        for item in structured.items
        if item.section not in (SectionKind.META_SALARY, SectionKind.META_LOCATION)
    ]
