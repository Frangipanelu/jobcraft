"""规则标签池（零 LLM，EXPERIENCE_SPEC §26/§29/§55）。

职责：从经历 raw_text 中按「关键词 + 同义词」匹配出扁平标签，作为
``recommend_tags`` 的规则先行路径（无候选时 API 才走 LLM 兜底）。

词典（代码内 JSON，无新表，§29）：
- 技术栈：``app/pipeline/data/technical_skills.json``
- 能力维度：``app/pipeline/data/soft_skills.json``
- 业务领域 / 行业：``app/pipeline/data/business_fields.json``（带同义词）

原则：
- 零 LLM、无状态、确定性：相同输入 → 相同输出。
- 只返回「原文中出现」的标签（关键词命中即来自原文，不编造）。
- 扁平标签，不分类不层级不加 #。
"""

import json
from pathlib import Path
from typing import Dict, List

_DATA_DIR = Path(__file__).resolve().parent.parent / "pipeline" / "data"

# 业务领域（tag + keywords 同义词）
_BUSINESS_FIELDS: List[Dict[str, object]] = json.loads(
    (_DATA_DIR / "business_fields.json").read_text(encoding="utf-8")
)["business_fields"]

# 技术栈 / 能力维度（flat 字符串列表，自身即关键词）
_TECHNICAL_SKILLS: List[str] = json.loads(
    (_DATA_DIR / "technical_skills.json").read_text(encoding="utf-8")
)["technical_skills"]

_SOFT_SKILLS: List[str] = json.loads(
    (_DATA_DIR / "soft_skills.json").read_text(encoding="utf-8")
)["soft_skills"]

MAX_TAGS = 8


def _normalize_ascii(term: str) -> str:
    """ASCII 关键词归一化：小写，仅文本匹配用（不用于输出标签原文）。"""
    return term.lower().strip()


def recommend_tags_from_pool(raw_text: str) -> List[str]:
    """从词典中匹配原文出现的标签（关键词 + 同义词，去重，上限 MAX_TAGS）。

    :param raw_text: 经历原文
    :return: 扁平标签列表（按词典顺序：技术栈 → 业务领域 → 能力维度）
    """
    if not raw_text or not raw_text.strip():
        return []

    text_lower = raw_text.lower()
    tags: List[str] = []
    seen: set = set()

    # 技术栈（flat）
    for term in _TECHNICAL_SKILLS:
        if len(tags) >= MAX_TAGS:
            break
        term_lower = _normalize_ascii(term)
        if term_lower and term_lower in text_lower and term not in seen:
            seen.add(term)
            tags.append(term)

    # 业务领域 / 行业（tag + keywords）
    for entry in _BUSINESS_FIELDS:
        if len(tags) >= MAX_TAGS:
            break
        tag = str(entry["tag"])
        keywords = entry["keywords"]
        if not isinstance(keywords, list):
            continue
        matched = any(
            _normalize_ascii(str(kw)) and _normalize_ascii(str(kw)) in text_lower
            for kw in keywords
        )
        if matched and tag not in seen:
            seen.add(tag)
            tags.append(tag)

    # 能力维度（flat）
    for term in _SOFT_SKILLS:
        if len(tags) >= MAX_TAGS:
            break
        term_lower = _normalize_ascii(term)
        if term_lower and term_lower in text_lower and term not in seen:
            seen.add(term)
            tags.append(term)

    return tags
