"""Surface L1 契约锁定测试（T-EVAL-2 C1）。

锁定被评输出 schema 的关键约束，防止未来改动静默放宽导致 L1 漏检：
- InterviewPrepLLMOutput：关键字段 ``min_length=1``（JSON schema required 且禁空）
- CompanyResearchInfo：``extra="forbid"``（顶层只允许 aspects 键）
- ResearchItem：非 AI推断条目必须绑定 source_url（model_validator）
- ReviewedQuestion / InterviewReviewResult：score / overall_score 的 ge/le 边界
- JudgeScore：四维 0-10 边界
- check_review_l1 / check_prep_l1：L1 规则行为

测试只读 import app.schemas，不触发 LLM、不访问 DB。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.jobcraft import (
    CompanyResearchInfo,
    InterviewPrepLLMOutput,
    InterviewReviewResult,
    InterviewPrepResult,
    ResearchItem,
    ReviewedQuestion,
)
from evaluation.surface_schemas import (
    JudgeScore,
    check_prep_l1,
    check_review_l1,
    summarize_l1,
)


# ---- InterviewPrepLLMOutput 契约 ----


class TestInterviewPrepLLMOutputContract:
    """InterviewPrepLLMOutput 关键字段 min_length 锁定。"""

    def _base_ok(self) -> dict:
        return {
            "job_analysis_id": 1,
            "elevator_pitch": "你好，我是张三。",
            "dimension_questions": [
                {
                    "dimension": "D1",
                    "question": "介绍一下你的项目",
                    "answer_points": ["背景", "行动"],
                }
            ],
            "full_version": "完整逐字稿内容",
            "html_content": "<p>你好</p>",
        }

    def test_valid_passes(self):
        obj = InterviewPrepLLMOutput(**self._base_ok())
        assert obj.elevator_pitch

    def test_empty_elevator_pitch_rejected(self):
        d = self._base_ok()
        d["elevator_pitch"] = ""
        with pytest.raises(ValidationError):
            InterviewPrepLLMOutput(**d)

    def test_empty_full_version_rejected(self):
        d = self._base_ok()
        d["full_version"] = ""
        with pytest.raises(ValidationError):
            InterviewPrepLLMOutput(**d)

    def test_empty_html_content_rejected(self):
        d = self._base_ok()
        d["html_content"] = ""
        with pytest.raises(ValidationError):
            InterviewPrepLLMOutput(**d)

    def test_empty_dimension_questions_rejected(self):
        d = self._base_ok()
        d["dimension_questions"] = []
        with pytest.raises(ValidationError):
            InterviewPrepLLMOutput(**d)

    def test_json_schema_required_fields(self):
        """JSON schema 中四个关键字段必须在 required 且有 minLength=1。"""
        schema = InterviewPrepLLMOutput.model_json_schema()
        required = schema.get("required", [])
        for field in (
            "elevator_pitch",
            "dimension_questions",
            "full_version",
            "html_content",
        ):
            assert field in required, f"{field} 必须在 required 中"

        props = schema.get("properties", {})
        for field in ("elevator_pitch", "full_version", "html_content"):
            assert props[field].get("minLength") == 1, f"{field} minLength 必须为 1"
        assert props["dimension_questions"].get("minItems") == 1, (
            "dimension_questions minItems 必须为 1"
        )

    def test_parent_defaults_optional(self):
        """InterviewPrepResult（落库契约）关键字段仍带默认值，不强制必填。"""
        schema = InterviewPrepResult.model_json_schema()
        required = schema.get("required", [])
        assert "elevator_pitch" not in required


# ---- CompanyResearchInfo 契约 ----


class TestCompanyResearchInfoContract:
    """CompanyResearchInfo extra=forbid 与 ResearchItem 来源绑定锁定。"""

    def test_extra_top_level_key_rejected(self):
        """顶层出现 aspects 之外的键必须被拒（防 LLM 平铺输出）。"""
        with pytest.raises(ValidationError):
            CompanyResearchInfo(aspects={}, overview=[])

    def test_valid_empty_aspects_passes(self):
        obj = CompanyResearchInfo()
        assert obj.aspects is not None

    def test_research_item_non_inference_requires_url(self):
        """source_type != AI推断 时 source_url 不能为空。"""
        with pytest.raises(ValidationError):
            ResearchItem(content="某新闻", source_type="新闻", source_url="")

    def test_research_item_inference_allows_empty_url(self):
        obj = ResearchItem(content="某推断", source_type="AI推断", source_url="")
        assert obj.source_type == "AI推断"

    def test_research_item_content_min_length(self):
        with pytest.raises(ValidationError):
            ResearchItem(content="", source_type="AI推断", source_url="")


# ---- ReviewedQuestion / InterviewReviewResult 契约 ----


class TestReviewSchemaContract:
    """复盘输出 score / overall_score 边界锁定。"""

    def test_score_bounds(self):
        q = ReviewedQuestion(question_text="Q", score=0)
        assert q.score == 0
        q2 = ReviewedQuestion(question_text="Q", score=100)
        assert q2.score == 100
        with pytest.raises(ValidationError):
            ReviewedQuestion(question_text="Q", score=101)
        with pytest.raises(ValidationError):
            ReviewedQuestion(question_text="Q", score=-1)

    def test_overall_score_bounds(self):
        r = InterviewReviewResult(record_id=1, overall_score=0)
        assert r.overall_score == 0
        r2 = InterviewReviewResult(record_id=1, overall_score=100)
        assert r2.overall_score == 100
        with pytest.raises(ValidationError):
            InterviewReviewResult(record_id=1, overall_score=101)


# ---- JudgeScore 契约 ----


class TestJudgeScoreContract:
    """L2 裁判输出 schema 边界锁定。"""

    def _base(self) -> dict:
        return {
            "accuracy": 8,
            "completeness": 7,
            "actionability": 9,
            "safety": 10,
            "strengths": ["亮点1"],
            "weaknesses": ["不足1"],
            "overall": 8,
            "rationale": "总体良好",
        }

    def test_valid(self):
        obj = JudgeScore(**self._base())
        assert obj.overall == 8

    def test_out_of_range_rejected(self):
        d = self._base()
        d["accuracy"] = 11
        with pytest.raises(ValidationError):
            JudgeScore(**d)

    def test_negative_rejected(self):
        d = self._base()
        d["safety"] = -1
        with pytest.raises(ValidationError):
            JudgeScore(**d)

    def test_json_schema_bounds(self):
        schema = JudgeScore.model_json_schema()
        props = schema.get("properties", {})
        for field in ("accuracy", "completeness", "actionability", "safety", "overall"):
            assert props[field].get("minimum") == 0
            assert props[field].get("maximum") == 10


# ---- L1 检查函数行为 ----


class TestCheckReviewL1:
    """check_review_l1 规则行为。"""

    def _ok_result(self) -> dict:
        return {
            "record_id": 1,
            "overall_score": 75,
            "summary": "总体尚可",
            "strengths": ["D1 良好"],
            "weaknesses": ["D7 待提升"],
            "action_items": ["多练表达"],
            "questions": [
                {
                    "sequence": 1,
                    "question_text": "介绍一下 Redis 分布式锁",
                    "dimension": "D1",
                    "level": "L3",
                    "score": 80,
                    "feedback": ["原理讲清楚了"],
                    "suggestions": ["补充 RedLock 争议"],
                }
            ],
        }

    def test_all_pass(self):
        findings = check_review_l1("c1", self._ok_result())
        assert all(f.passed for f in findings), [f for f in findings if not f.passed]

    def test_schema_invalid(self):
        findings = check_review_l1("c1", {"record_id": 1, "overall_score": 200})
        assert any(f.check == "schema_valid" and not f.passed for f in findings)

    def test_empty_questions_flagged(self):
        d = self._ok_result()
        d["questions"] = []
        findings = check_review_l1("c1", d)
        assert any(f.check == "question_coverage" and not f.passed for f in findings)

    def test_bad_dimension_flagged(self):
        d = self._ok_result()
        d["questions"][0]["dimension"] = "D99"
        findings = check_review_l1("c1", d)
        assert any("dimension_format" in f.check and not f.passed for f in findings)

    def test_summarize(self):
        findings = check_review_l1("c1", self._ok_result())
        summary = summarize_l1(findings)
        assert summary["failed"] == 0
        assert summary["pass_rate"] == 1.0


class TestCheckPrepL1:
    """check_prep_l1 规则行为。"""

    def _ok_result(self) -> dict:
        return {
            "job_analysis_id": 1,
            "elevator_pitch": "你好，我是张三。",
            "dimension_questions": [
                {"dimension": "D1", "question": "Q", "answer_points": ["a"]}
            ],
            "full_version": "完整逐字稿",
            "html_content": "<p>hi</p>",
        }

    def test_all_pass(self):
        findings = check_prep_l1("c1", self._ok_result())
        assert all(f.passed for f in findings), [f for f in findings if not f.passed]

    def test_schema_invalid_empty_pitch(self):
        d = self._ok_result()
        d["elevator_pitch"] = ""
        findings = check_prep_l1("c1", d)
        assert any(f.check == "schema_valid" and not f.passed for f in findings)

    def test_empty_answer_points_flagged(self):
        d = self._ok_result()
        d["dimension_questions"][0]["answer_points"] = []
        findings = check_prep_l1("c1", d)
        assert any("answer_points" in f.check and not f.passed for f in findings)

    def test_bad_dimension_flagged(self):
        d = self._ok_result()
        d["dimension_questions"][0]["dimension"] = "X"
        findings = check_prep_l1("c1", d)
        assert any("dimension_format" in f.check and not f.passed for f in findings)
