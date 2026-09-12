"""
Agent 节点 Mock 单测（无真实 LLM 调用）

通过 monkeypatch 替换各 agent 模块内的 invoke_structured，
验证 agent 的输入→输出转换逻辑与容错分支。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------- ExtractStructuredAgent ----------


def test_extract_structured_empty_input(monkeypatch):
    from app.agents.extract_agent import ExtractStructuredAgent

    def _fail(*args, **kwargs):
        raise AssertionError("空输入不应触发 LLM 调用")

    monkeypatch.setattr("app.agents.extract_agent.invoke_structured", _fail)
    out = ExtractStructuredAgent().run({"raw_text": ""})
    assert out["cache"] is None


def test_extract_structured_with_mock_llm(monkeypatch):
    from app.agents.extract_agent import ExtractStructuredAgent

    fake = {
        "summary": "负责推荐系统",
        "achievements": [
            {
                "title": "重构召回",
                "situation": "召回精度不足",
                "action": {"main": "引入向量召回", "difficulty": "", "resolution": ""},
                "result": "点击率提升 20%",
            }
        ],
    }

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(**fake)

    monkeypatch.setattr("app.agents.extract_agent.invoke_structured", _fake_invoke)
    out = ExtractStructuredAgent().run({"raw_text": "我负责推荐系统"})
    assert out["cache"]["summary"] == "负责推荐系统"
    assert out["cache"]["achievements"][0]["result"] == "点击率提升 20%"


def test_extract_structured_empty_achievements_returns_none(monkeypatch):
    from app.agents.extract_agent import ExtractStructuredAgent

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(summary="", achievements=[])

    monkeypatch.setattr("app.agents.extract_agent.invoke_structured", _fake_invoke)
    out = ExtractStructuredAgent().run({"raw_text": "无成果的经历"})
    assert out["cache"] is None


# ---------- ParseResumeEntriesAgent ----------


def test_parse_resume_entries_empty_input(monkeypatch):
    from app.agents.extract_agent import ParseResumeEntriesAgent

    def _fail(*args, **kwargs):
        raise AssertionError("空输入不应触发 LLM 调用")

    monkeypatch.setattr("app.agents.extract_agent.invoke_structured", _fail)
    out = ParseResumeEntriesAgent().run({"resume_text": ""})
    assert out["entries"] == []


def test_parse_resume_entries_with_mock_llm(monkeypatch):
    from app.agents.extract_agent import ParseResumeEntriesAgent

    fake = {
        "entries": [
            {
                "company": "字节跳动",
                "role": "高级后端工程师",
                "period": "2019.03 - 2021.06",
                "title": "推荐系统架构",
                "summary": "负责推荐系统架构",
                "achievements": [
                    {
                        "title": "重构召回策略",
                        "situation": "召回精度不足",
                        "action": {
                            "main": "引入向量召回",
                            "difficulty": "",
                            "resolution": "",
                        },
                        "result": "点击率提升 20%",
                    }
                ],
            }
        ]
    }

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(**fake)

    monkeypatch.setattr("app.agents.extract_agent.invoke_structured", _fake_invoke)
    out = ParseResumeEntriesAgent().run({"resume_text": "简历文本"})
    assert len(out["entries"]) == 1
    assert out["entries"][0]["company"] == "字节跳动"


# ---------- RecommendTagsAgent ----------


def test_recommend_tags_empty_input(monkeypatch):
    from app.agents.extract_agent import RecommendTagsAgent

    def _fail(*args, **kwargs):
        raise AssertionError("空输入不应触发 LLM 调用")

    monkeypatch.setattr("app.agents.extract_agent.invoke_structured", _fail)
    out = RecommendTagsAgent().run({"raw_text": ""})
    assert out["tags"] == []


def test_recommend_tags_with_mock_llm(monkeypatch):
    from app.agents.extract_agent import RecommendTagsAgent

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(tags=["python", "推荐系统", "后端"])

    monkeypatch.setattr("app.agents.extract_agent.invoke_structured", _fake_invoke)
    out = RecommendTagsAgent().run({"raw_text": "负责推荐系统开发"})
    assert out["tags"] == ["python", "推荐系统", "后端"]


# ---------- JdAtsAgent ----------


def test_jd_ats_agent_empty_input_raises():
    from app.agents.jd_ats_agent import JdAtsAgent

    with pytest.raises(ValueError):
        JdAtsAgent().run({"jd_text": ""})


def test_jd_ats_agent_with_mock_llm(monkeypatch):
    from app.agents.jd_ats_agent import JdAtsAgent

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(
            job_title="高级后端工程师",
            required_skills=["python", "redis"],
            preferred_skills=["go"],
            responsibilities=["设计高可用系统"],
        )

    monkeypatch.setattr("app.agents.jd_ats_agent.invoke_structured", _fake_invoke)
    out = JdAtsAgent().run({"jd_text": "JD 文本"})
    assert out["ats"]["job_title"] == "高级后端工程师"
    assert "python" in out["ats"]["required_skills"]


def test_jd_ats_agent_v3_mock_llm(monkeypatch):
    from app.agents.jd_ats_agent import JdAtsAgent

    def _fake_invoke(model, schema, prompt, **kwargs):
        assert "evidence-first" in prompt
        return schema(
            job_title="高级后端工程师",
            required_skills=["python", "go"],
            evidence_items=[
                {
                    "id": 1,
                    "field": "required_skills",
                    "span": "精通 Python",
                    "derived": "python",
                }
            ],
        )

    monkeypatch.setattr("app.agents.jd_ats_agent.invoke_structured", _fake_invoke)
    out = JdAtsAgent().run({"jd_text": "JD 文本", "prompt_version": "v3"})
    assert "raw" in out
    # 证据校验：go 无证据支撑 → 被丢弃
    assert out["ats"]["required_skills"] == ["python"]
    assert out["raw"]["required_skills"] == ["python", "go"]


def test_jd_ats_agent_v3_prompt_version_default_v1(monkeypatch):
    from app.agents.jd_ats_agent import _build_ats_prompt

    p1 = _build_ats_prompt("JD", version="v1")
    p3 = _build_ats_prompt("JD", version="v3")
    assert "evidence-first" not in p1
    assert "evidence-first" in p3


def test_jd_ats_agent_v2_prompt_explicit_rules(monkeypatch):
    from app.agents.jd_ats_agent import JdAtsAgent, _build_ats_prompt

    p2 = _build_ats_prompt("JD", version="v2")
    # Prompt B 显式规则：禁止编造 / 技能归属 / 缩写归一
    assert "禁止编造" in p2
    assert "preferred_skills" in p2
    assert "缩写归一" in p2

    def _fake_invoke(model, schema, prompt, **kwargs):
        assert "硬性规则" in prompt
        return schema(
            job_title="后端工程师",
            required_skills=["Python"],
            responsibilities=["服务开发"],
        )

    monkeypatch.setattr("app.agents.jd_ats_agent.invoke_structured", _fake_invoke)
    out = JdAtsAgent().run({"jd_text": "JD 文本", "prompt_version": "v2"})
    # v2 与 v1 输出契约一致：仅 ats，无 raw
    assert "raw" not in out
    assert out["ats"]["required_skills"] == ["Python"]


# ---------- JdAtsAgent v4（分层收窄） ----------


def test_jd_ats_v4_merges_pipeline_and_inference(monkeypatch):
    from app.agents.jd_ats_agent import JdAtsAgent

    captured = {}

    def _fake_invoke(model, schema, prompt, **kwargs):
        from app.schemas.jobcraft import AtsInference

        assert schema is AtsInference
        captured["prompt"] = prompt
        return AtsInference(
            job_title="后端工程师",
            culture_keywords=["代码规范"],
            dimension_requirements=[{"dimension": "D1", "level": 4, "evidence": "熟悉 Python"}],
            subtext_decoded=[
                {
                    "surface_requirement": "能抗压",
                    "hidden_meaning": "节奏快",
                    "key_ability": "执行力",
                    "how_to_prove": "高压交付案例",
                    "confidence": 0.7,
                }
            ],
        )

    monkeypatch.setattr("app.agents.jd_ats_agent.invoke_structured", _fake_invoke)
    jd = "职位描述\n岗位职责：\n1）负责交易系统后端开发\n岗位要求：\n1）熟悉 Python、Redis\n2）具备良好的沟通能力"
    out = JdAtsAgent().run({"jd_text": jd, "prompt_version": "v4"})

    assert out["raw"]["culture_keywords"] == ["代码规范"]
    ats = out["ats"]
    assert ats["job_title"] == "后端工程师"
    # L1 算法产出的技能被保留（LLM 未返回技能字段也不丢失）
    assert {"Python", "Redis"} <= set(ats["required_skills"])
    assert ats["culture_keywords"] == ["代码规范"]
    assert ats["soft_skills"]
    assert ats["dimension_requirements"][0]["dimension"] == "D1"
    assert ats["subtext_decoded"][0]["key_ability"] == "执行力"
    assert ats["core_keywords"]
    assert ats["evidence_items"]
    # prompt 只包含结构化摘要，不含"重复抽取技能"指令
    assert "needs_review" in captured["prompt"]


def test_jd_ats_v4_ambiguous_decision_relabels_item(monkeypatch):
    from app.agents.jd_ats_agent import JdAtsAgent

    def _fake_invoke(model, schema, prompt, **kwargs):
        from app.schemas.jobcraft import AtsInference

        # 找出 needs_review 中真实存在的 item_id
        import json
        import re

        m = re.search(r"```json\n(.*?)\n```", prompt, re.S)
        summary = json.loads(m.group(1))
        ids = summary["needs_review"]
        decisions = (
            [{"item_id": ids[0], "label": "required", "reason": "实为硬性要求"}]
            if ids
            else []
        )
        return AtsInference(job_title="X", ambiguous=decisions)

    monkeypatch.setattr("app.agents.jd_ats_agent.invoke_structured", _fake_invoke)
    out = JdAtsAgent().run(
        {"jd_text": "职位描述\n岗位要求：\n1）有良好的编码习惯与自我驱动能力", "prompt_version": "v4"}
    )
    assert "ats" in out


def test_jd_ats_v4_prompt_is_narrowed():
    from app.agents.jd_ats_agent import _build_v4_prompt
    from app.pipeline.jd_classifier import classify_jd
    from app.pipeline.jd_extractor import extract_jd
    from app.pipeline.jd_structurer import structure_jd

    jd = "职位描述\n岗位职责：\n1）负责系统开发\n岗位要求：\n1）熟悉 Python"
    s = structure_jd(jd)
    c = classify_jd(s)
    e = extract_jd(s, c)
    prompt = _build_v4_prompt(jd, s, c, e)
    assert "只负责算法无法可靠完成" in prompt
    assert "structured_summary" not in prompt  # 占位符已填充
    assert "禁止**重复输出 required_skills" in prompt or "禁止" in prompt


# ---------- AtsRecommendAgent ----------


def test_ats_recommend_agent_merges_ats_and_cards(monkeypatch):
    from app.agents.ats_recommend_agent import AtsRecommendAgent

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(
            ats={"job_title": "后端工程师", "required_skills": ["python"]},
            recommended_cards=[{"card_id": 1, "score": 90, "reason": "高度匹配"}],
        )

    monkeypatch.setattr(
        "app.agents.ats_recommend_agent.invoke_structured", _fake_invoke
    )
    out = AtsRecommendAgent().run(
        {
            "jd_text": "JD",
            "cards": [{"id": 1, "title": "后端开发", "raw_text": "python"}],
        }
    )
    assert out["ats"]["job_title"] == "后端工程师"
    assert out["recommended_cards"][0]["card_id"] == 1
    assert out["recommended_cards"][0]["score"] == 90


# ---------- QuestionTableAgent ----------


def test_question_table_agent_empty_qa_returns_empty_with_mock(monkeypatch):
    from app.agents.question_table_agent import QuestionTableAgent

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(questions=[])

    monkeypatch.setattr(
        "app.agents.question_table_agent.invoke_structured", _fake_invoke
    )
    out = QuestionTableAgent().run({"qa_pairs": []})
    assert out["intent_by_seq"] == {}


def test_question_table_agent_with_mock_llm(monkeypatch):
    from app.agents.question_table_agent import QuestionTableAgent

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(
            questions=[
                {
                    "sequence": 1,
                    "intent": "考察项目深度",
                    "dimension": "D3 问题拆解",
                    "level": "L4",
                }
            ]
        )

    monkeypatch.setattr(
        "app.agents.question_table_agent.invoke_structured", _fake_invoke
    )
    out = QuestionTableAgent().run(
        {
            "company": "字节",
            "position": "后端",
            "round_type": "技术面",
            "qa_pairs": [{"sequence": 1, "question_text": "聊聊你的项目"}],
            "jd_text": "",
        }
    )
    assert out["intent_by_seq"][1]["dimension"] == "D3 问题拆解"


# ---------- InterviewPrepAgent ----------


def test_interview_prep_agent_empty_prompt():
    from app.agents.interview_prep_agent import InterviewPrepAgent

    with pytest.raises(ValueError):
        InterviewPrepAgent().run({"prompt": ""})


def test_interview_prep_agent_with_mock_llm(monkeypatch):
    from app.agents.interview_prep_agent import InterviewPrepAgent

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(
            job_analysis_id=1,
            round_type="技术面",
            elevator_pitch="我是候选人",
            dimension_questions=[
                {"dimension": "D1", "question": "谈谈项目", "card_ids": [1]}
            ],
        )

    monkeypatch.setattr(
        "app.agents.interview_prep_agent.invoke_structured", _fake_invoke
    )
    out = InterviewPrepAgent().run({"prompt": "请生成逐字稿"})
    assert out["prep_result"]["elevator_pitch"] == "我是候选人"
    assert out["prep_result"]["dimension_questions"][0]["dimension"] == "D1"
