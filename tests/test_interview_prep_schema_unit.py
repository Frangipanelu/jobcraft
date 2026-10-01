# -*- coding: utf-8 -*-
"""InterviewPrepResult / DimensionQuestion LLM 输出容错校验器单测。

回归场景：智谱 glm-4.7-flash 实测输出畸形——
- `company_research` 被双重编码为 JSON 字符串（bind_tools 主路径失败根因）
- `card_ids` 填卡片标题而非整数 ID（兜底路径失败根因）
"""

import pytest

from app.schemas.jobcraft import DimensionQuestion, InterviewPrepResult


def _minimal(**overrides):
    payload = {"job_analysis_id": 1, "full_version": "逐字稿"}
    payload.update(overrides)
    return payload


class TestCoerceCardIds:
    def test_plain_ints_passthrough(self):
        q = DimensionQuestion(dimension="技术", question="Q", card_ids=[1, 2, 3])
        assert q.card_ids == [1, 2, 3]

    def test_string_int_coerced(self):
        q = DimensionQuestion(dimension="d", question="q", card_ids=["42"])
        assert q.card_ids == [42]

    def test_card_title_dropped(self):
        """模型把卡片标题填进 card_ids：丢弃而非整体校验失败。"""
        q = DimensionQuestion(
            dimension="d",
            question="q",
            card_ids=["AI推荐策略优化", "8", "背景/任务/行动/结果"],
        )
        assert q.card_ids == [8]

    def test_json_encoded_list_string(self):
        q = DimensionQuestion(dimension="d", question="q", card_ids="[1, 2]")
        assert q.card_ids == [1, 2]

    def test_unparseable_bracket_string_single_value(self):
        q = DimensionQuestion(dimension="d", question="q", card_ids="[oops")
        assert q.card_ids == []

    def test_bool_and_none_and_scalar_ignored(self):
        assert (
            DimensionQuestion(dimension="d", question="q", card_ids=None).card_ids == []
        )
        assert DimensionQuestion(dimension="d", question="q", card_ids=7).card_ids == []
        assert DimensionQuestion(
            dimension="d", question="q", card_ids=[True, "3", False]
        ).card_ids == [3]


class TestCoerceCompanyResearch:
    def test_dict_passthrough(self):
        r = InterviewPrepResult(**_minimal(company_research={"k": 1}))
        assert r.company_research == {"k": 1}

    def test_json_string_decoded(self):
        """bind_tools 主路径失败根因：对象被编码成字符串。"""
        raw = '{"industry_trends": "AI 招聘", "scale": "中型"}'
        r = InterviewPrepResult(**_minimal(company_research=raw))
        assert r.company_research == {"industry_trends": "AI 招聘", "scale": "中型"}

    def test_broken_string_falls_back_to_empty(self):
        r = InterviewPrepResult(**_minimal(company_research="{broken"))
        assert r.company_research == {}

    def test_none_stays_none(self):
        r = InterviewPrepResult(**_minimal(company_research=None))
        assert r.company_research is None

    def test_non_dict_non_string_falls_back_to_empty(self):
        r = InterviewPrepResult(**_minimal(company_research=[1, 2]))
        assert r.company_research == {}


def test_e2e_observed_malformed_payload_validates():
    """真实 e2e 失败载荷（双重编码 + 标题混入）应整体通过校验。"""
    payload = _minimal(
        dimension_questions=[
            {
                "dimension": "技术深度",
                "question": "如何设计推荐系统？",
                "answer_points": ["要点一"],
                "card_ids": ["AI推荐策略优化"],
            },
            {
                "dimension": "工程能力",
                "question": "如何保证稳定性？",
                "answer_points": ["要点"],
                "card_ids": ["12"],
            },
        ],
        company_research='{"industry_trends": "AI、企业成本压力"}',
    )
    result = InterviewPrepResult(**payload)
    assert result.dimension_questions[0].card_ids == []
    assert result.dimension_questions[1].card_ids == [12]
    assert result.company_research == {"industry_trends": "AI、企业成本压力"}


class TestInterviewPrepLLMOutput:
    """LLM 输出契约：关键字段 required + 非空，防模型漏填。"""

    def test_content_fields_are_required_and_non_empty(self):
        from pydantic import ValidationError

        from app.schemas.jobcraft import InterviewPrepLLMOutput

        schema = InterviewPrepLLMOutput.model_json_schema()
        required = set(schema.get("required", []))
        assert {
            "elevator_pitch",
            "dimension_questions",
            "full_version",
            "html_content",
        } <= required

        # 漏填 → 校验错误（e2e 实测：dimension_questions 缺省为 []、pitch 空串）
        with pytest.raises(ValidationError):
            InterviewPrepLLMOutput(job_analysis_id=1)
        with pytest.raises(ValidationError):
            InterviewPrepLLMOutput(
                job_analysis_id=1,
                elevator_pitch="",
                dimension_questions=[],
                full_version="全文",
                html_content="<p>x</p>",
            )

    def test_valid_output_isinstance_parent(self):
        from app.schemas.jobcraft import InterviewPrepLLMOutput

        out = InterviewPrepLLMOutput(
            job_analysis_id=1,
            elevator_pitch="自我介绍",
            dimension_questions=[{"dimension": "D", "question": "Q"}],
            full_version="全文",
            html_content="<p>x</p>",
        )
        assert isinstance(out, InterviewPrepResult)
        # 父类保持宽松默认：落库/API 契约不变
        assert InterviewPrepResult(job_analysis_id=1).dimension_questions == []
