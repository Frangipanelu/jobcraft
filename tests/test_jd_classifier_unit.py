"""jd_classifier 规则分类单测（app/pipeline/jd_classifier.py）。

验证 v0.5 §六-§九 的分类语义：Section + Trigger + Verb + Context 联合判定，
UNKNOWN 不硬猜。全部确定性路径，无 LLM。
"""

from __future__ import annotations

from app.pipeline.jd_classifier import ClassLabel, classify_item, classify_jd
from app.pipeline.jd_structurer import SectionItem, SectionKind, structure_jd


def _item(text: str, section: SectionKind = SectionKind.REQUIREMENTS) -> SectionItem:
    return SectionItem(
        item_id="t_001", section=section, text=text, start=0, end=len(text)
    )


def _label(text: str, section: SectionKind = SectionKind.REQUIREMENTS) -> ClassLabel:
    return classify_item(_item(text, section)).label


def test_capability_verb_is_required():
    assert _label("熟悉 Python") is ClassLabel.REQUIRED
    assert _label("精通 Python、FastAPI") is ClassLabel.REQUIRED
    assert _label("熟练使用 MySQL、Redis") is ClassLabel.REQUIRED


def test_context_noun_is_required():
    assert _label("具有 AI 产品经验") is ClassLabel.REQUIRED
    assert _label("MySQL、Redis") is ClassLabel.REQUIRED


def test_soft_skill_by_trait_context():
    assert _label("具备良好的沟通能力") is ClassLabel.SOFT_SKILL
    assert _label("具备较强的业务理解能力") is ClassLabel.SOFT_SKILL
    assert _label("执行力强") is ClassLabel.SOFT_SKILL
    assert _label("责任心强") is ClassLabel.SOFT_SKILL
    assert _label("沟通能力较强，具备团队协作精神") is ClassLabel.SOFT_SKILL


def test_soft_skill_phrase():
    assert _label("有责任心") is ClassLabel.SOFT_SKILL
    assert _label("具备较强的执行力") is ClassLabel.SOFT_SKILL


def test_preferred_by_marker():
    assert _label("有 AI Agent 项目经验优先") is ClassLabel.PREFERRED
    assert _label("熟悉 Flink 是加分项。") is ClassLabel.PREFERRED
    assert _label("熟悉 Docker 优先") is ClassLabel.PREFERRED


def test_preferred_by_section():
    assert _label("熟悉Docker", SectionKind.PREFERRED) is ClassLabel.PREFERRED


def test_edu_years_gate_is_required():
    assert _label("本科及以上学历") is ClassLabel.REQUIRED
    assert _label("统招本科，计算机相关专业") is ClassLabel.REQUIRED
    assert _label("3年以上经验") is ClassLabel.REQUIRED


def test_action_verb_is_responsibility():
    assert _label("负责核心服务设计") is ClassLabel.RESPONSIBILITY
    assert _label("推动跨团队落地") is ClassLabel.RESPONSIBILITY


def test_responsibility_section_default():
    r = classify_item(_item("参与技术方案评审并输出文档", SectionKind.RESPONSIBILITIES))
    assert r.label is ClassLabel.RESPONSIBILITY
    assert r.rule == "verb:action"


def test_responsibility_section_ambiguous_default():
    r = classify_item(_item("日常接口设计", SectionKind.RESPONSIBILITIES))
    assert r.label is ClassLabel.RESPONSIBILITY
    assert r.confidence == 0.9


def test_unknown_not_guessed():
    assert _label("对标行业一流水平", SectionKind.UNKNOWN) is ClassLabel.UNKNOWN
    assert _label("公司成立于2015年", SectionKind.COMPANY_INFO) is ClassLabel.UNKNOWN


def test_hard_skill_not_soft_when_object_is_code_standard():
    # 单元测试习惯属于硬性工程要求，不误判为软实力
    r = classify_item(_item("具备良好的代码规范意识与单元测试习惯"))
    assert r.label is ClassLabel.REQUIRED


def test_english_soft_skill():
    assert _label("Strong ownership mindset") is ClassLabel.SOFT_SKILL


def test_span_preserved():
    jd = "要求：掌握Python；有责任心。"
    doc = structure_jd(jd)
    classified = classify_jd(doc)
    assert len(classified) == 2
    for c in classified:
        assert jd[c.start : c.end] == c.text, c.item_id
    assert classified[0].label is ClassLabel.REQUIRED
    assert classified[1].label is ClassLabel.SOFT_SKILL


def test_classify_jd_integration():
    jd = (
        "职责：负责核心服务的设计与开发；保障线上稳定性。"
        "要求：本科及以上学历；精通Python；具备良好的沟通能力；有Kafka经验优先。"
    )
    doc = structure_jd(jd)
    classified = classify_jd(doc)
    labels = {c.label for c in classified}
    assert ClassLabel.RESPONSIBILITY in labels
    assert ClassLabel.REQUIRED in labels
    assert ClassLabel.SOFT_SKILL in labels
    assert ClassLabel.PREFERRED in labels
