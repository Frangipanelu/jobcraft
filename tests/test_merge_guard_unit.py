"""merge_ats 守卫逻辑单测（app/agents/jd_ats_agent.py）。

验证 v4 分层收窄的确定性合并约束：
- LLM 歧义裁决只作用于 L1 未定论（UNKNOWN）条目，不覆盖 L1 已确定性归类结果；
- 纯格式/薪资 stub（markdown 标题行、全粗体薪资）不构成需求，LLM 裁决不收编。
"""

from __future__ import annotations

from app.agents.jd_ats_agent import merge_ats
from app.pipeline.jd_classifier import ClassLabel, classify_jd
from app.pipeline.jd_extractor import extract_jd
from app.pipeline.jd_structurer import structure_jd
from app.schemas.jobcraft import AtsInference


def _build(jd_text: str):
    s = structure_jd(jd_text)
    c = classify_jd(s)
    e = extract_jd(s, c)
    return c, e


def test_llm_decision_does_not_override_l1_resolved():
    jd = "职位描述\n岗位要求：\n1）熟悉 Python。"
    c, e = _build(jd)
    req_id = next(item.item_id for item in c if item.label is ClassLabel.REQUIRED)
    inf = AtsInference(
        job_title="X",
        ambiguous=[{"item_id": req_id, "label": "preferred", "reason": "试"}],
    )
    ats = merge_ats(e, c, inf, jd)
    assert "Python" in ats.required_skills


def test_llm_decision_stub_text_ignored():
    # markdown 标题行 stub：L1 UNKNOWN，但不应被 LLM 裁决收编进 required
    jd = "##Al Builder - 产品\n岗位要求：\n1）熟悉 Python。"
    c, e = _build(jd)
    stub_id = next(item.item_id for item in c if item.section.value == "job_overview")
    inf = AtsInference(
        job_title="X",
        ambiguous=[{"item_id": stub_id, "label": "required", "reason": "试"}],
    )
    ats = merge_ats(e, c, inf, jd)
    assert "##Al Builder - 产品" not in ats.required_skills


def test_llm_decision_salary_stub_ignored():
    jd = "欣旺达**生产经理****17-22k**\n岗位要求：\n1）熟悉 Python。"
    c, e = _build(jd)
    stub_id = next(item.item_id for item in c if item.section.value == "job_overview")
    inf = AtsInference(
        job_title="X",
        ambiguous=[{"item_id": stub_id, "label": "required", "reason": "试"}],
    )
    ats = merge_ats(e, c, inf, jd)
    assert not any("17-22k" in s for s in ats.required_skills)


def test_llm_decision_genuine_unknown_applied():
    # 公司介绍区无动词名词短语：L1 UNKNOWN 且非 stub → LLM 裁决有效
    jd = "职位描述\n岗位要求：\n1）熟悉 Python。\n公司介绍\n弹性工作制"
    c, e = _build(jd)
    unk_id = next(item.item_id for item in c if item.label is ClassLabel.UNKNOWN)
    inf = AtsInference(
        job_title="X",
        ambiguous=[{"item_id": unk_id, "label": "responsibility", "reason": "试"}],
    )
    ats = merge_ats(e, c, inf, jd)
    assert "弹性工作制" in ats.responsibilities
