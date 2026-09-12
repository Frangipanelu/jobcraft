"""jd_structurer 纯确定性切分单测（app/pipeline/jd_structurer.py）。

验证 v0.5 §4/§5 的四个能力：Section Detection / Item Split / Span Extraction /
无标题降级。全部为确定性规则路径，不需要 LLM。
"""

from __future__ import annotations

from app.pipeline.jd_structurer import SectionKind, structure_jd


def _kinds(doc) -> list:
    return [s.kind for s in doc.sections]


def test_inline_single_line_jd_sections():
    jd = (
        "职责：负责核心服务设计与开发；保障线上稳定性。"
        "要求：本科及以上学历；3年以上经验，精通Python。"
        "加分项：熟悉Docker。薪资：25-40K，坐标北京。"
    )
    doc = structure_jd(jd)
    kinds = _kinds(doc)
    for expected in (
        SectionKind.RESPONSIBILITIES,
        SectionKind.REQUIREMENTS,
        SectionKind.PREFERRED,
        SectionKind.META_SALARY,
        SectionKind.META_LOCATION,
    ):
        assert expected in kinds, expected
    req = next(s for s in doc.sections if s.kind == SectionKind.REQUIREMENTS)
    texts = [i.text for i in req.items]
    assert any("本科" in t for t in texts)
    assert any("Python" in t for t in texts)


def test_span_offsets_point_at_source():
    jd = "要求：掌握Python；了解SQL。"
    doc = structure_jd(jd)
    assert len(doc.items) == 2
    for item in doc.items:
        assert jd[item.start : item.end] == item.text, item.item_id
    assert doc.items[0].text == "掌握Python"
    assert doc.items[1].text == "了解SQL"


def test_no_heading_falls_back_to_unknown():
    jd = "熟悉Python，有FastAPI开发经验，具备良好的沟通能力。"
    doc = structure_jd(jd)
    assert len(doc.sections) == 1
    assert doc.sections[0].kind is SectionKind.UNKNOWN
    assert len(doc.items) == 1
    assert "Python" in doc.items[0].text


def test_longest_heading_wins():
    jd = "任职要求：精通Python。"
    doc = structure_jd(jd)
    assert _kinds(doc).count(SectionKind.REQUIREMENTS) == 1


def test_mid_sentence_word_not_heading():
    jd = "要求：参与岗位职责梳理并输出文档；负责需求分析。"
    doc = structure_jd(jd)
    kinds = _kinds(doc)
    assert kinds.count(SectionKind.RESPONSIBILITIES) == 0
    assert kinds.count(SectionKind.REQUIREMENTS) == 1


def test_multiline_heading_with_markers():
    jd = (
        "工作职责：\n"
        "1. 负责产品规划；\n"
        "2. 推动跨团队落地。\n"
        "任职要求：\n"
        "- 本科及以上\n"
        "- 3年以上经验\n"
    )
    doc = structure_jd(jd)
    resp = next(s for s in doc.sections if s.kind is SectionKind.RESPONSIBILITIES)
    texts = [i.text for i in resp.items]
    assert "负责产品规划" in texts
    assert "推动跨团队落地" in texts
    for item in doc.items:
        assert jd[item.start : item.end] == item.text, item.item_id


def test_english_heading_case_insensitive():
    jd = (
        "Responsibilities: build the core service; keep it stable. "
        "Requirements: 3+ years of Python. Preferred: Docker."
    )
    doc = structure_jd(jd)
    kinds = _kinds(doc)
    assert SectionKind.RESPONSIBILITIES in kinds
    assert SectionKind.REQUIREMENTS in kinds
    assert SectionKind.PREFERRED in kinds


def test_meta_dict_collected():
    jd = "薪资：25-40K·14薪，坐标北京；工作地点：上海。"
    doc = structure_jd(jd)
    assert any("25-40K" in s for s in doc.meta["salary"])
    assert any("北京" in s for s in doc.meta["location"])
    assert any("上海" in s for s in doc.meta["location"])


def test_leading_overview_section():
    jd = "我们是做 AI 招聘的产品团队，正在寻找一位后端工程师。任职要求：精通Python。"
    doc = structure_jd(jd)
    assert _kinds(doc)[0] is SectionKind.JOB_OVERVIEW
