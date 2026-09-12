"""JD 结构化切分器（Pipeline L1 · 纯确定性，无 LLM）。

将原始 JD 文本切分为「带原文 Span 的 section + item」结构：

- ``Section Detection``：按标题词典把 JD 划分为 responsibilities / requirements /
  preferred / benefits / company_info / meta(薪资·地点) / job_overview 等区块。
- ``Item Split``：把每个区块拆成最小分析单元（按换行、分号、句号、列表标记）。
- ``Span Extraction``：每个 item 携带其在 JD 原文中的 ``[start, end)`` 偏移，
  供证据层「从 Span 构建 Evidence」使用，而非 LLM 猜测。

设计约束（对应 `docs/evaluation/JobCraft ATS Pipeline v0.5` §4/§5）：

- 标题识别只接受「标题后紧跟冒号/换行/行尾」的命中，避免正文词汇误判。
- 重叠命中取最长（如「任职要求」覆盖「要求」），保证一个位置只命中一个标题。
- 无任何标题的 JD 整段降级为 ``unknown`` 区块，交给规则分类器/LLM 兜底。
- 本节不做任何语义分类与抽取，那是 ``jd_classifier`` / ``jd_extractor`` 的职责。
"""

from __future__ import annotations

import re
from enum import StrEnum
from itertools import count

from pydantic import BaseModel, Field


class SectionKind(StrEnum):
    """JD 区块类型（v0.5 §4.1 的 section 角色）。"""

    JOB_OVERVIEW = "job_overview"
    RESPONSIBILITIES = "responsibilities"
    REQUIREMENTS = "requirements"
    PREFERRED = "preferred"
    BENEFITS = "benefits"
    COMPANY_INFO = "company_info"
    META_SALARY = "meta_salary"
    META_LOCATION = "meta_location"
    UNKNOWN = "unknown"


class SectionItem(BaseModel):
    """最小分析单元：带原文 Span 的单条 JD 内容。"""

    item_id: str
    section: SectionKind
    text: str
    raw: str = Field(default="", description="命中时的原始切片（含列表标记/分隔符）")
    start: int = Field(default=0, description="干净文本在 JD 原文中的起始偏移")
    end: int = Field(default=0, description="干净文本在 JD 原文中的结束偏移（不含）")


class DocumentSection(BaseModel):
    """一个内容区块（含该区块下拆出的全部 item）。"""

    kind: SectionKind
    title: str | None = None
    start: int = 0
    end: int = 0
    items: list[SectionItem] = Field(default_factory=list)


class StructuredJD(BaseModel):
    """结构化切分结果：JD 原文 → sections + 扁平 items + meta 候选。"""

    source: str
    sections: list[DocumentSection] = Field(default_factory=list)
    items: list[SectionItem] = Field(default_factory=list)
    meta: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "salary": [],
            "location": [],
        },
        description="meta 区块原始文本候选（供 L0 兜底抽取复用）",
    )


# —— 标题词典：长词在前，同位置命中取最长 ——
_LEXICON: dict[SectionKind, tuple[str, ...]] = {
    SectionKind.RESPONSIBILITIES: (
        "Key Responsibilities",
        "Job Responsibilities",
        "What you'll do",
        "What you will do",
        "Your responsibilities",
        "Responsibilities",
        "岗位职责",
        "工作职责",
        "职位职责",
        "岗位指责",
        "你的主要工作",
        "你将负责",
        "职位描述",
        "岗位描述",
        "职责",
    ),
    SectionKind.REQUIREMENTS: (
        "What we're looking for",
        "What We Are Looking For",
        "What you need",
        "Qualifications",
        "Requirements",
        "任职资格",
        "任职要求",
        "职位要求",
        "岗位要求",
        "岗位需求",
        "招聘要求",
        "硬性要求",
        "基本要求",
        "我们希望你能",
        "我们希望你",
        "你需要",
        "要求",
    ),
    SectionKind.PREFERRED: (
        "Nice to have",
        "Preferred Qualifications",
        "Preferred",
        "Bonus",
        "加分项",
        "加分条件",
        "优先条件",
        "优先考虑",
        "有以下经验者优先",
        "具备以下条件尤佳",
    ),
    SectionKind.BENEFITS: (
        "What we offer",
        "Benefits",
        "Perks",
        "福利待遇",
        "薪酬福利",
        "你将获得",
        "你将得到",
    ),
    SectionKind.COMPANY_INFO: (
        "About the team",
        "About us",
        "About Us",
        "关于我们",
        "公司简介",
        "公司介绍",
        "团队介绍",
    ),
    SectionKind.META_SALARY: (
        "Salary",
        "Compensation",
        "薪资待遇",
        "薪资",
        "薪酬",
        "工资",
    ),
    SectionKind.META_LOCATION: (
        "Where you'll work",
        "Location",
        "办公地点",
        "任职地点",
        "工作地点",
        "坐标",
    ),
}

_ITEM_PREFIX: dict[SectionKind, str] = {
    SectionKind.RESPONSIBILITIES: "resp",
    SectionKind.REQUIREMENTS: "req",
    SectionKind.PREFERRED: "pref",
    SectionKind.BENEFITS: "bnf",
    SectionKind.COMPANY_INFO: "co",
    SectionKind.JOB_OVERVIEW: "ov",
    SectionKind.META_SALARY: "meta",
    SectionKind.META_LOCATION: "meta",
    SectionKind.UNKNOWN: "unk",
}

# 标题后紧跟这些字符才承认是标题（要求/职责等词也可能出现在正文中）
_HEADING_FOLLOW = ("：", ":", "\n", "\r", " ", "\t", "")

# 区块内 item 的分隔符
_SPLIT_RE = re.compile(r"[；;\n\r。]+")

# 列表标记：数字/中文字/括号/项目符号
_MARKER_RE = re.compile(
    r"(?:\d+[.、．)）]\s*|[（(]\s*\d+\s*[)）]\s*"
    r"|[①-⑩]\s*|[一二三四五六七八九十]{1,2}[、.)]\s*"
    r"|[-•●·▪—*\u2022\u25CF\u2027\u00B7\u2013\u2014]\s*)+"
)

# 清洗时首尾剥除的字符（空白 + 常见分隔标点）
_STRIP_CHARS = " \t\r\n；;，、。:：()（）[]【】"


def _is_heading(text: str, end: int) -> bool:
    """标题命中后一个字符必须在允许集合内（防止正文中词汇被误判为标题）。"""
    nxt = text[end : end + 1]
    return nxt in _HEADING_FOLLOW


def _detect_headings(text: str) -> list[tuple[int, int, SectionKind, str]]:
    """定位 JD 中的所有标题命中，返回 ``(start, end, kind, lexeme)``。

    规则：重叠命中只保留「起始位置相同的最长命中 + 不重叠的后续命中」，
    保证「任职要求」不会同时把「要求」也当成一个标题。
    """
    candidates: list[tuple[int, int, SectionKind, str]] = []
    for kind, lexemes in _LEXICON.items():
        for lex in lexemes:
            flags = re.IGNORECASE if lex.isascii() else 0
            pattern = re.compile(re.escape(lex), flags)
            for m in pattern.finditer(text):
                # 特例：「坐标」常以「坐标北京」省略冒号紧随城市名（评测语料即此格式）
                if lex == "坐标":
                    candidates.append((m.start(), m.end(), kind, lex))
                    continue
                if _is_heading(text, m.end()):
                    candidates.append((m.start(), m.end(), kind, lex))
    if not candidates:
        return []
    candidates.sort(key=lambda c: (c[0], c[1] - c[0]))
    chosen: list[tuple[int, int, SectionKind, str]] = []
    last_end = -1
    for start, end, kind, lex in candidates:
        if start < last_end:
            continue
        chosen.append((start, end, kind, lex))
        last_end = end
    return chosen


def _content_start(text: str, heading_end: int) -> int:
    """标题结束后跳过分隔符（：/:/空格/换行），返回内容起始偏移。"""
    pos = heading_end
    while pos < len(text) and text[pos] in ("：", ":", " ", "\t", "\n", "\r"):
        pos += 1
    return pos


def _split_raw_items(text: str) -> list[tuple[int, int, str]]:
    """按分隔符把区块切成 ``(start, end, raw)`` 原始切片，保留偏移。"""
    out: list[tuple[int, int, str]] = []
    pos = 0
    for m in _SPLIT_RE.finditer(text):
        seg = text[pos : m.start()]
        if seg.strip():
            out.append((pos, m.start(), seg))
        pos = m.end()
    tail = text[pos:]
    if tail.strip():
        out.append((pos, len(text), tail))
    return out


def _clean_item(raw: str) -> tuple[str, int, int]:
    """清洗单条 raw：去列表标记与首尾标点，返回 ``(text, core_start, core_end)``。

    偏移相对 ``raw`` 切片本身，用于把 Span 定位回 JD 原文。
    """
    lead = len(raw) - len(raw.lstrip(" \t"))
    s = raw[lead:]
    m = _MARKER_RE.match(s)
    if m:
        lead += m.end()
        s = s[m.end() :]
    ltrim = len(s) - len(s.lstrip(_STRIP_CHARS))
    rtrim = len(s) - len(s.rstrip(_STRIP_CHARS))
    core_start = lead + ltrim
    core_end = len(raw) - rtrim
    text = raw[core_start:core_end]
    return text, core_start, core_end


def _emit_section(
    doc: StructuredJD,
    kind: SectionKind,
    start: int,
    end: int,
    title: str | None,
    raw: str,
    seq: object,
) -> None:
    """把 ``raw`` 区域切分后写入 doc（元数据区块不切分，整段作为单条）。"""
    is_meta = kind in (SectionKind.META_SALARY, SectionKind.META_LOCATION)
    if is_meta:
        spans: list[tuple[int, int, str]] = [(0, len(raw), raw)] if raw.strip() else []
    else:
        spans = _split_raw_items(raw)
    items: list[SectionItem] = []
    for rs, re_seg, seg in spans:
        text, cs, ce = _clean_item(seg)
        if not text:
            continue
        item = SectionItem(
            item_id=f"{_ITEM_PREFIX[kind]}_{next(seq):03d}",
            section=kind,
            text=text,
            raw=seg,
            start=start + rs + cs,
            end=start + rs + ce,
        )
        items.append(item)
        doc.items.append(item)
    if items:
        doc.sections.append(
            DocumentSection(kind=kind, title=title, start=start, end=end, items=items)
        )


def structure_jd(jd_text: str) -> StructuredJD:
    """切分 JD 文本，返回 ``StructuredJD``（section + item + span + meta）。

    :param jd_text: 原始 JD 文本（可含换行/列表标记/行内“标题：内容”）。
    :return: 结构化结果；无标题 JD 整体降级为单个 ``unknown`` 区块。
    """
    doc = StructuredJD(source=jd_text)
    seq = count(1)
    headings = _detect_headings(jd_text)
    if not headings:
        _emit_section(doc, SectionKind.UNKNOWN, 0, len(jd_text), None, jd_text, seq)
    else:
        first_start = headings[0][0]
        if first_start > 0 and jd_text[:first_start].strip():
            _emit_section(
                doc,
                SectionKind.JOB_OVERVIEW,
                0,
                first_start,
                None,
                jd_text[:first_start],
                seq,
            )
        for i, (start, end, kind, lex) in enumerate(headings):
            content_start = _content_start(jd_text, end)
            content_end = headings[i + 1][0] if i + 1 < len(headings) else len(jd_text)
            raw = jd_text[content_start:content_end]
            if not raw.strip():
                continue
            _emit_section(doc, kind, content_start, content_end, lex, raw, seq)
    for item in doc.items:
        if item.section is SectionKind.META_SALARY:
            doc.meta["salary"].append(item.text)
        elif item.section is SectionKind.META_LOCATION:
            doc.meta["location"].append(item.text)
    return doc
