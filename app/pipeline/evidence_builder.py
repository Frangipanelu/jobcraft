"""证据构建器（Pipeline L1 → L3 · 纯确定性，无 LLM）。

v0.5 §十一/§十二 的落地：**Evidence 从 Span 构建，而不是让 LLM 猜测**。

- :class:`SourceEvidence`：每个已分类条目天然成为一条证据——span 即
  ``[start, end)`` 原文切片、field 由分类标签映射、relation 按构建而为
  ``EXACT``（证据即出处，不存在"猜证据"）。
- :func:`grade_relation`：下游实体（skill/metric/…）对一条 span 文本的关系
  分级（EXACT / CONTAINED / PARAPHRASE / INFERRED / UNSUPPORTED）。
- :func:`to_verdict`：把 Relation 折算回既有 ACCEPT / REVIEW / REJECT 三档
  （EXACT/CONTAINED→accept，PARAPHRASE/INFERRED→review，UNSUPPORTED→reject），
  与 ``app.agents.evidence`` 的三态语义保持一致、阈值同源（0.6 / 0.4）。
- 注意：本节不再承担"主要分类器"职责——条目归属判定已由
  ``jd_classifier`` 完成（v0.5 §二十一，规则/算法/LLM 边界前移）。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Sequence

from pydantic import BaseModel

from app.agents.evidence import normalize
from app.pipeline.jd_classifier import ClassLabel, ClassifiedItem


class EvidenceRelation(StrEnum):
    """实体对 span 的支撑关系（v0.5 §十二）。"""

    EXACT = "EXACT"
    CONTAINED = "CONTAINED"
    PARAPHRASE = "PARAPHRASE"
    INFERRED = "INFERRED"
    UNSUPPORTED = "UNSUPPORTED"


class SourceEvidence(BaseModel):
    """一条从 JD 原文 Span 构建的证据。"""

    item_id: str
    field: str
    label: ClassLabel | None = None
    text: str
    start: int
    end: int
    raw: str = ""
    relation: EvidenceRelation = EvidenceRelation.EXACT


class EntityVerdict(BaseModel):
    """一个抽取实体对证据 spans 的最佳关系判定（含 ACCEPT/REVIEW/REJECT）。"""

    entity: str
    relation: EvidenceRelation
    span: str
    verdict: str


# ClassLabel → ATSProfile 列表字段（v0.5 §十四 的 field 映射）
_LABEL_FIELD: dict[ClassLabel, str] = {
    ClassLabel.REQUIRED: "required_skills",
    ClassLabel.PREFERRED: "preferred_skills",
    ClassLabel.RESPONSIBILITY: "responsibilities",
    ClassLabel.SOFT_SKILL: "soft_skills",
    ClassLabel.UNKNOWN: "unknown",
}

# Relation 优先级（高→低），grade_entity 择优
_REL_RANK = {
    EvidenceRelation.EXACT: 4,
    EvidenceRelation.CONTAINED: 3,
    EvidenceRelation.PARAPHRASE: 2,
    EvidenceRelation.INFERRED: 1,
    EvidenceRelation.UNSUPPORTED: 0,
}


def _dice(a: str, b: str) -> float:
    """bigram Dice 系数（与 evidence.values_match 的 0.6/0.4 语义同源）。"""
    if a == b:
        return 1.0
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    ba = {na[i : i + 2] for i in range(len(na) - 1)}
    bb = {nb[i : i + 2] for i in range(len(nb) - 1)}
    if not ba or not bb:
        return 0.0
    return 2 * len(ba & bb) / (len(ba) + len(bb))


def grade_relation(claim: str, span_text: str) -> EvidenceRelation:
    """判定实体 ``claim`` 对原文 ``span_text`` 的支撑关系。

    - 归一化相等 → EXACT；claim 是 span 的子串（长度 >= 4）→ CONTAINED。
    - Dice >= 0.6 → PARAPHRASE（语义等价改写）；>= 0.4 → INFERRED（弱关联）。
    - 其余 → UNSUPPORTED（无支撑，即幻觉候选）。
    """
    if not claim.strip() or not span_text.strip():
        return EvidenceRelation.UNSUPPORTED
    na, ns = normalize(claim), normalize(span_text)
    if na == ns:
        return EvidenceRelation.EXACT
    if na and len(na) >= 4 and na in ns:
        return EvidenceRelation.CONTAINED
    d = _dice(na, ns)
    if d >= 0.6:
        return EvidenceRelation.PARAPHRASE
    if d >= 0.4:
        return EvidenceRelation.INFERRED
    return EvidenceRelation.UNSUPPORTED


def to_verdict(relation: EvidenceRelation) -> str:
    """把 Relation 折算回 ACCEPT/REVIEW/REJECT 三档（与 evidence.py 语义一致）。"""
    if relation in (EvidenceRelation.EXACT, EvidenceRelation.CONTAINED):
        return "accept"
    if relation in (EvidenceRelation.PARAPHRASE, EvidenceRelation.INFERRED):
        return "review"
    return "reject"


def build_source_evidence(
    classified: Sequence[ClassifiedItem],
) -> list[SourceEvidence]:
    """把分类条目固化为带原文 Span 的证据（构建即 EXACT，不猜证据）。

    :param classified: :func:`jd_classifier.classify_jd` 的输出。
    :return: 与输入一一对应的证据列表。
    """
    return [
        SourceEvidence(
            item_id=c.item_id,
            field=_LABEL_FIELD[c.label],
            label=c.label,
            text=c.text,
            start=c.start,
            end=c.end,
            raw=c.text,
            relation=EvidenceRelation.EXACT,
        )
        for c in classified
    ]


def grade_entity(entity: str, spans: Sequence[str]) -> EntityVerdict:
    """在若干 span 中为实体选最佳关系（高优先级者胜，同优先级取首个）。"""
    best: EntityVerdict | None = None
    for span in spans:
        rel = grade_relation(entity, span)
        if best is None or _REL_RANK[rel] > _REL_RANK[best.relation]:
            best = EntityVerdict(
                entity=entity, relation=rel, span=span, verdict=to_verdict(rel)
            )
    assert best is not None
    return best
