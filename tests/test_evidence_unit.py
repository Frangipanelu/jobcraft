"""Prompt C evidence-first 确定性证据校验单测（app/agents/evidence.py）。"""

from __future__ import annotations

from app.agents.evidence import (
    coverage_stats,
    normalize,
    reconcile_evidence,
    values_match,
)
from app.schemas.jobcraft import ATSProfile, EvidenceItem, SubtextDecode


def _ats(**overrides) -> dict:
    base = {
        "job_title": "后端开发工程师",
        "required_skills": ["Python", "Redis"],
        "preferred_skills": [],
        "responsibilities": ["后端服务开发"],
        "culture_keywords": [],
        "key_metrics": [],
        "dimension_requirements": [
            {"dimension": "D1", "level": 4, "evidence": ""},
        ],
        "subtext_decoded": [],
        "salary": "25-40K",
        "location": "北京",
        "evidence_items": [],
        "raw_summary": "",
    }
    base.update(overrides)
    return base


def _evidents() -> list:
    return [
        {
            "id": 1,
            "field": "required_skills",
            "span": "精通 Python",
            "derived": "Python",
        },
        {
            "id": 2,
            "field": "required_skills",
            "span": "扎实掌握 MySQL、Redis",
            "derived": "Redis",
        },
        {
            "id": 3,
            "field": "responsibilities",
            "span": "负责后端服务的设计与开发",
            "derived": "后端服务开发",
        },
        {
            "id": 4,
            "field": "dimension_D1",
            "span": "精通 Python，5 年经验",
            "derived": "4",
        },
        {
            "id": 5,
            "field": "salary",
            "span": "薪资：25-40K",
            "derived": "25-40K",
        },
        {
            "id": 6,
            "field": "location",
            "span": "坐标北京",
            "derived": "北京",
        },
        {
            "id": 7,
            "field": "preferred_skills",
            "span": "有 Docker 经验者优先",
            "derived": "Docker",
        },
    ]


def test_normalize():
    assert normalize("REST API") == "restapi"
    assert normalize("25-40K·14薪") == "2540k14薪"
    assert normalize("") == ""


def test_values_match_variants():
    assert values_match("Python", "Python")
    assert values_match("数据可视化", "数据可视化工具")  # 单边包含
    assert values_match("REST API", "RESTful API")  # Dice 高相似
    assert not values_match("Kubernetes", "K8s")  # 缩写不自动识别
    assert not values_match("Python", "Golang")


def test_reconcile_keeps_evidenced_drops_un_evidenced():
    ats = _ats(
        required_skills=["Python", "Redis", "Golang"],  # Golang 无证据 → 丢弃
        evidence_items=_evidents(),
    )
    recon = reconcile_evidence(ats)
    assert recon["required_skills"] == ["Python", "Redis"]
    assert recon["responsibilities"] == ["后端服务开发"]


def test_reconcile_hallucinated_preferred_dropped():
    ats = _ats(
        required_skills=["Python"],
        preferred_skills=["Kubernetes"],  # 无证据
        evidence_items=[_evidents()[0]],
    )
    recon = reconcile_evidence(ats)
    assert recon["preferred_skills"] == []


def test_reconcile_dimensions_only_evidenced():
    ats = _ats(
        dimension_requirements=[
            {"dimension": "D1", "level": 4, "evidence": ""},  # 有 D1 证据
            {"dimension": "D2", "level": 3, "evidence": ""},  # 无 D2 证据 → 丢弃
        ],
        evidence_items=_evidents(),
    )
    recon = reconcile_evidence(ats)
    assert [r["dimension"] for r in recon["dimension_requirements"]] == ["D1"]


def test_reconcile_dimension_level_mismatch_dropped():
    ats = _ats(
        dimension_requirements=[
            {"dimension": "D1", "level": 2, "evidence": ""},  # 证据 derived=4
        ],
        evidence_items=_evidents(),
    )
    recon = reconcile_evidence(ats)
    assert recon["dimension_requirements"] == []


def test_reconcile_scalars_without_evidence_dropped():
    ats = _ats(salary="30-50K", location=None, evidence_items=[])
    recon = reconcile_evidence(ats)
    assert recon["salary"] is None
    assert ats["location"] is None


def test_reconcile_scalars_conflict_overridden_by_single_evidence():
    # 值存在但与唯一证据不一致 → 证据优先覆盖
    ats = _ats(salary="30-50K", location=None, evidence_items=_evidents())
    recon = reconcile_evidence(ats)
    assert recon["salary"] == "25-40K"


def test_reconcile_scalars_filled_from_single_evidence():
    ats = _ats(salary=None, location=None, evidence_items=_evidents())
    recon = reconcile_evidence(ats)
    assert recon["salary"] == "25-40K"
    assert recon["location"] == "北京"


def test_reconcile_scalar_conflicting_evidence_stays_none():
    ev = _evidents()
    ev.append(
        {"id": 9, "field": "salary", "span": "薪资：30-50Kor15薪", "derived": "30-50K"}
    )
    ats = _ats(salary=None, evidence_items=ev)
    recon = reconcile_evidence(ats)
    assert recon["salary"] is None


def test_reconcile_subtext_only_matched():
    ev = _evidents()
    ev.append(
        {
            "id": 8,
            "field": "subtext",
            "span": "具备良好的业务理解能力",
            "derived": "期望从数据中发现业务问题",
        }
    )
    ats = _ats(
        evidence_items=ev,
        subtext_decoded=[
            SubtextDecode(
                surface_requirement="具备良好的业务理解能力",
                hidden_meaning="期望从数据中发现业务问题而非只做取数",
                confidence=0.8,
            ),
            SubtextDecode(
                surface_requirement="责任心强",
                hidden_meaning="能扛住压力",
                confidence=0.4,
            ),
        ],
    )
    recon = reconcile_evidence(ats)
    assert len(recon["subtext_decoded"]) == 1
    kept = recon["subtext_decoded"][0]
    kept_dict = kept.model_dump() if hasattr(kept, "model_dump") else kept
    assert kept_dict["surface_requirement"] == "具备良好的业务理解能力"


def test_reconcile_accepts_pydantic_evidence_items():
    items = [
        EvidenceItem(
            id=1, field="responsibilities", span="负责接口设计", derived="接口设计"
        )
    ]
    ats = _ats(responsibilities=["接口设计", "性能优化"], evidence_items=items)
    recon = reconcile_evidence(ats)
    assert recon["responsibilities"] == ["接口设计"]


def test_reconcile_missing_evidence_drops_everything():
    ats = _ats(required_skills=["Python", "Redis"], evidence_items=[])
    recon = reconcile_evidence(ats)
    assert recon["required_skills"] == []
    assert recon["salary"] is None
    assert recon["dimension_requirements"] == []


def test_coverage_stats():
    ats = _ats(
        required_skills=["Python", "Golang"],
        evidence_items=_evidents(),
    )
    stats = coverage_stats(ats)
    assert stats["evidence_total"] == 7
    assert "required_skills" in stats["sourced_fields"]
    assert stats["dropped_values"] == 1


def test_ats_profile_accepts_evidence_and_confidence():
    profile = ATSProfile(
        job_title="后端",
        evidence_items=[
            EvidenceItem(id=1, field="salary", span="25-40K", derived="25-40K")
        ],
        subtext_decoded=[SubtextDecode(confidence=0.9)],
    )
    assert profile.subtext_decoded[0].model_dump()["confidence"] == 0.9
    assert len(profile.evidence_items) == 1


def test_ats_profile_confidence_default():
    sub = SubtextDecode(surface_requirement="x")
    assert sub.confidence == 0.5
