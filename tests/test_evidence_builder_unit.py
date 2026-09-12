"""evidence_builder 单测（app/pipeline/evidence_builder.py）。

验证 v0.5 §十一/§十二：Evidence 从 Span 构建（EXACT by construction）、
关系分级（EXACT/CONTAINED/PARAPHRASE/INFERRED/UNSUPPORTED）、
以及 Relation → ACCEPT/REVIEW/REJECT 三档折算。
"""

from __future__ import annotations

from app.pipeline.evidence_builder import (
    EvidenceRelation,
    build_source_evidence,
    grade_entity,
    grade_relation,
    to_verdict,
)
from app.pipeline.jd_classifier import (
    ClassLabel,
    ClassifiedItem,
    classify_jd,
)
from app.pipeline.jd_structurer import SectionKind, structure_jd


def _classified_item(text: str, label: ClassLabel) -> ClassifiedItem:
    return ClassifiedItem(
        item_id="t_001",
        section=SectionKind.REQUIREMENTS,
        text=text,
        start=0,
        end=len(text),
        label=label,
        confidence=1.0,
        rule="test",
    )


def test_relation_exact():
    assert grade_relation("Python", "Python") is EvidenceRelation.EXACT


def test_relation_contained():
    assert grade_relation("Python", "熟悉 Python 开发") is EvidenceRelation.CONTAINED


def test_relation_paraphrase():
    assert grade_relation("Redis 缓存", "缓存 Redis") is EvidenceRelation.PARAPHRASE


def test_relation_inferred():
    assert (
        grade_relation("同时处理多任务", "多任务处理能力") is EvidenceRelation.INFERRED
    )


def test_relation_unsupported():
    assert grade_relation("Python", "Java") is EvidenceRelation.UNSUPPORTED


def test_verdict_mapping():
    assert to_verdict(EvidenceRelation.EXACT) == "accept"
    assert to_verdict(EvidenceRelation.CONTAINED) == "accept"
    assert to_verdict(EvidenceRelation.PARAPHRASE) == "review"
    assert to_verdict(EvidenceRelation.INFERRED) == "review"
    assert to_verdict(EvidenceRelation.UNSUPPORTED) == "reject"


def test_build_source_evidence_maps_field():
    classified = [
        _classified_item("精通 Python", ClassLabel.REQUIRED),
        _classified_item("有责任心，抗压能力强", ClassLabel.SOFT_SKILL),
    ]
    evidence = build_source_evidence(classified)
    assert [e.field for e in evidence] == ["required_skills", "soft_skills"]
    for e, c in zip(evidence, classified):
        assert e.relation is EvidenceRelation.EXACT
        assert e.text == c.text
        assert e.item_id == c.item_id


def test_build_source_evidence_spans_integration():
    jd = "要求：精通Python；具备良好的沟通能力。"
    doc = structure_jd(jd)
    evidence = build_source_evidence(classify_jd(doc))
    assert len(evidence) == 2
    for e in evidence:
        assert jd[e.start : e.end] == e.text, e.item_id
        assert e.relation is EvidenceRelation.EXACT


def test_grade_entity_picks_best_span():
    spans = ["负责核心服务设计", "熟悉 Python 与 Redis"]
    best = grade_entity("Redis", spans)
    assert best.relation is EvidenceRelation.CONTAINED
    assert best.verdict == "accept"
    assert best.span == "熟悉 Python 与 Redis"

    worst = grade_entity("Java", spans)
    assert worst.relation is EvidenceRelation.UNSUPPORTED
    assert worst.verdict == "reject"
