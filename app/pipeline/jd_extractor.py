"""JD 字段抽取器（Pipeline L1 · 纯确定性，无 LLM）。

v0.5 §十/§十四 的落地：education/years/skills/soft_skills/key_metrics/
core_keywords/salary/location 全部优先算法化，不调用 LLM。

- education/years：复用 evidence.py 的 ``_EDU_PATTERNS`` / ``_YEARS_RE``，
  优先取"整条即门槛短语"的条目，否则取首个命中片段。
- skills / soft_skills：直接来自 jd_classifier 的 REQUIRED/PREFERRED/
  SOFT_SKILL 桶，再通过技术词典（``data/technical_skills.json``）从词条
  中抽 token 级技能（技能词典只做候选生成，归属判断已由 classifier 完成）。
- key_metrics：数字 + 单位/量词正则抽取（百分比/金额/人天/客户数等）。
- core_keywords：Recruitment Signal（v0.5 §十五/§十六），category 分类 +
  importance 算法打分（section_weight + 强调词 + 频次），不是"高频词"。
- salary/location：元数据区块候选（v0.5 §三 Data completion，非核心分析）。

每个字段只产出确定性结果；culture_keywords / D1-D8 / subtext 不在此层
（属于 L2 LLM 推理，见 Task06）。
"""

from __future__ import annotations

import re
from typing import Sequence

from pydantic import BaseModel, Field

from app.agents.evidence import _EDU_PATTERNS, _YEARS_RE, normalize
from app.pipeline.jd_classifier import (
    ClassLabel,
    ClassifiedItem,
    _TECH_WORDS,
    _SOFT_WORDS,
)
from app.pipeline.jd_structurer import SectionKind, StructuredJD
from app.schemas.jobcraft import KeywordSignal

# 多词/带标点技术词优先（长词先匹配，避免 "Vue" 抢走 "Vue.js"）
_TECH_BY_LEN = tuple(sorted(_TECH_WORDS, key=len, reverse=True))

_PRODUCT_WORDS = (
    "需求分析",
    "需求调研",
    "用户研究",
    "PRD",
    "原型设计",
    "项目管理",
    "产品规划",
    "产品迭代",
    "指标体系",
    "数据分析",
    "可视化",
)


class JDExtraction(BaseModel):
    """算法抽取结果（Task05 并入 ATSProfile 的确定性字段来源）。"""

    education: str | None = None
    years_of_experience: str | None = None
    salary: str | None = None
    location: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    key_metrics: list[str] = Field(default_factory=list)
    core_keywords: list[KeywordSignal] = Field(default_factory=list)


# 数字 + 单位/量词（百分比/金额/数量；容忍 "500+"、"30 家" 写法）
_METRIC_RE = re.compile(
    r"\d+(?:\.\d+)?\+?\s*(?:%|％|万|k|K|万元|元|人天|人|名|位|家|个|条|份|次|项|"
    r"客户|用户|项目|任务|日|年|小时|分钟|tb|GB|MB|ms)"
)

# 强调词（strength += 2）；普通能力动词（strength += 1）
_EMPHASIS = ("必须", "核心", "重点", "必备", "硬性", "精通", "熟练掌握", "严格")
_MILD_VERBS = (
    "熟练掌握",
    "精通",
    "熟悉",
    "掌握",
    "熟练",
    "了解",
    "具备",
    "拥有",
    "理解",
)

# 软能力前置引导与程度词（用于复合软词识别，如「较强的沟通协调能力」）
_STRENGTH_CLEAN_RE = re.compile(
    r"^(?:具备|拥有|具有|具备较强|具备良好|有)?\s*(?:较强|很强|极强|强|良好|较好|很好|优秀|出色|扎实|卓越|基本的?)?\s*"
)

# section_weight（v0.5 §十六）
_SECTION_WEIGHT = {
    SectionKind.REQUIREMENTS: 3,
    SectionKind.PREFERRED: 1,
    SectionKind.RESPONSIBILITIES: 2,
    SectionKind.JOB_OVERVIEW: 1,
}


def _find_tech_tokens(text: str) -> list[str]:
    """在条目文本中找技术词典 token（长词优先、忽略子串重复、大小写不敏感）。"""
    low = text.lower()
    found: list[str] = []
    for token in _TECH_BY_LEN:
        if token.lower() in low:
            found.append(token)
    # 去掉被更长的已匹配 token 覆盖的子串（如 Vue ⊂ Vue.js）
    kept: list[str] = []
    for token in found:
        if any(token.lower() in other.lower() and token != other for other in found):
            continue
        kept.append(token)
    return kept


def _capability_parts(text: str) -> list[str]:
    """去掉句首能力动词，返回能力对象短语片段（技能兜底抽取）。

    动词后的并列名词列表（「熟悉功能测试、回归测试」）逐个返回。
    """
    head = text.strip()
    for v in _MILD_VERBS:
        if head.startswith(v):
            rest = head[len(v) :].lstrip("、，，并且及和与 ")
            parts: list[str] = []
            for seg in re.split(r"[，。；、,]", rest):
                seg = seg.strip().rstrip("。；，、")
                seg = (
                    seg.removeprefix("和")
                    .removeprefix("与")
                    .removeprefix("及")
                    .removeprefix("以及")
                )
                if len(seg) >= 2 and _soft_keyword(seg) is None:
                    parts.append(seg)
            return parts
    return []


def _soft_keyword(text: str) -> str | None:
    """识别条目中的软能力词，兼容复合写法（沟通协调能力）。

    先查软词表子串命中；未命中则剥离引导语/程度词后，用软词核心词干
    （去 能力/精神/意识 后缀）做宽匹配，返回命中的名词短语。
    """
    low = text.lower()
    for w in _SOFT_WORDS:
        if w.lower() in low:
            return w
    remainder = _STRENGTH_CLEAN_RE.sub("", text).strip("，。；、 ")
    for w in _SOFT_WORDS:
        core = w.lower().removesuffix("能力").removesuffix("精神").removesuffix("意识")
        if core and core in remainder.lower():
            return remainder
    return None


def _extract_skills(items: Sequence[str]) -> list[str]:
    """从条目桶中抽 token 级技能（技术词典）+ 能力短语兜底。"""
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        tokens = _find_tech_tokens(item)
        if not tokens:
            tokens = _capability_parts(item)
        for token in tokens:
            key = normalize(token)
            if key not in seen:
                seen.add(key)
                result.append(token)
    return result


def _match_edu(item: str) -> str:
    """返回条目中首个学历命中片段（含上下文，如「本科及以上学历」）。"""
    best = ""
    for pat in _EDU_PATTERNS:
        m = pat.search(item)
        if m:
            seg = item[m.start() : m.end()]
            if len(seg) > len(best):
                best = seg
    return best


def _match_years(item: str) -> str:
    m = _YEARS_RE.search(item)
    if not m:
        return ""
    return item[m.start() : m.end()].strip()


def _extract_education(items: Sequence[str]) -> str | None:
    for item in items:
        if any(p.search(item) for p in _EDU_PATTERNS):
            return _match_edu(item) or item.strip()[:24]
    return None


def _extract_years(items: Sequence[str]) -> str | None:
    for item in items:
        y = _match_years(item)
        if y:
            return y
    return None


def _extract_metrics(items: Sequence[str]) -> list[str]:
    """抽取数量短语并把上下文窗口一并保留（如「提升20%转化率」）。"""
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        for m in _METRIC_RE.finditer(item):
            start = max(0, m.start() - 8)
            end = min(len(item), m.end() + 6)
            phrase = item[start:end].strip("，。；、")
            key = normalize(phrase)
            if key and key not in seen:
                seen.add(key)
                out.append(phrase)
    return out


def extract_keywords(
    classified: Sequence[ClassifiedItem],
) -> list[KeywordSignal]:
    """按 v0.5 §十六 的公式生成 Recruitment Signal 关键词。

    ``score = section_weight + strength + max(0, freq-1)``，
    score>=5 → high，3-4 → medium，<3 → low。
    """
    agg: dict[tuple[str, str], dict] = {}
    for c in classified:
        text = c.text
        tokens: list[tuple[str, str]] = []
        for t in _find_tech_tokens(text):
            category = "product" if t in _PRODUCT_WORDS else "technical"
            tokens.append((t, category))
        for w in _SOFT_WORDS:
            if w.lower() in text.lower():
                tokens.append((w, "soft"))
                break
        else:
            soft = _soft_keyword(text)
            if soft is not None:
                tokens.append((soft, "soft"))
        if not tokens:
            continue
        strength = (
            2
            if any(e in text for e in _EMPHASIS)
            else (1 if any(v in text for v in _MILD_VERBS) else 0)
        )
        weight = _SECTION_WEIGHT.get(c.section, 0)
        for token, category in tokens:
            key = (token, category)
            entry = agg.setdefault(
                key, {"score": weight + strength, "freq": 1, "evidence": text}
            )
            entry["score"] = max(entry["score"], weight + strength)
            if entry["freq"] == 1 and key[1] == "product":
                entry["evidence"] = text
            entry["freq"] += 1
    signals: list[KeywordSignal] = []
    for (keyword, category), entry in agg.items():
        score = entry["score"] + max(0, entry["freq"] - 1)
        importance = "high" if score >= 5 else ("medium" if score >= 3 else "low")
        signals.append(
            KeywordSignal(
                keyword=keyword,
                category=category,
                importance=importance,
                score=score,
                evidence=entry["evidence"],
            )
        )
    signals.sort(key=lambda s: (-(s.importance == "high"), -s.score, s.keyword))
    return signals


def extract_jd(
    structured: StructuredJD,
    classified: Sequence[ClassifiedItem],
) -> JDExtraction:
    """全程确定性抽取 JD 字段（无 LLM 调用）。

    :param structured: :func:`jd_structurer.structure_jd` 的结构化结果。
    :param classified: :func:`jd_classifier.classify_jd` 的分类结果。
    :return: 抽取结果；culture/dimension/subtext 留待 L2 LLM。
    """
    buckets: dict[ClassLabel, list[str]] = {}
    for c in classified:
        buckets.setdefault(c.label, []).append(c.text)

    analysis_items = [
        c.text
        for c in classified
        if c.section
        in (SectionKind.REQUIREMENTS, SectionKind.UNKNOWN, SectionKind.JOB_OVERVIEW)
    ]
    resp_items = buckets.get(ClassLabel.RESPONSIBILITY, [])
    req_items = buckets.get(ClassLabel.REQUIRED, [])
    pref_items = buckets.get(ClassLabel.PREFERRED, [])
    soft_items = buckets.get(ClassLabel.SOFT_SKILL, [])

    return JDExtraction(
        education=_extract_education(analysis_items),
        years_of_experience=_extract_years(analysis_items),
        salary=(structured.meta.get("salary") or [None])[0],
        location=(structured.meta.get("location") or [None])[0],
        # 职责里出现的技能同样算核心要求（gold 亦如此标注）
        required_skills=_extract_skills(req_items + resp_items),
        preferred_skills=_extract_skills(pref_items),
        responsibilities=list(dict.fromkeys(resp_items)),
        soft_skills=list(dict.fromkeys(soft_items)),
        key_metrics=_extract_metrics(req_items + resp_items),
        core_keywords=extract_keywords(classified),
    )
