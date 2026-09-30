"""FE-RESUME-02：简历 AI 建议生成工具 / 同步端点 / 任务 handler 单测。

LLM 与 DB 全 mock，不依赖真实 MySQL 与模型服务。
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.server import app
from app.auth import create_access_token

_TEST_TOKEN = create_access_token({"user_id": 1, "username": "unittest"})
_AUTH = {"Authorization": f"Bearer {_TEST_TOKEN}"}

client = TestClient(app, raise_server_exceptions=False)

_BULLETS = [
    {"item_index": 0, "bullet_index": 0, "text": "负责推荐系统"},
    {"item_index": 1, "bullet_index": 0, "text": "主导重构与缓存策略"},
]

_VALID_ITEM = {
    "type": "keyword",
    "title": "补充 JD 关键词",
    "original_text": "主导重构与缓存策略",
    "suggested_text": "主导首屏性能重构与多级缓存策略（命中 JD 关键词）",
    "reason": "缺失岗位关键词",
    "item_index": 1,
    "bullet_index": 0,
}


def _make_output(items):
    from app.tools.resume_suggest import ResumeSuggestOutput, ResumeSuggestionItem

    return ResumeSuggestOutput(
        suggestions=[ResumeSuggestionItem(**item) for item in items]
    )


# ============================================================
# 工具：清洗与记录构造
# ============================================================


class TestSuggestResumeEdits:
    def test_valid_item_becomes_pending_record(self):
        from app.tools.resume_suggest import suggest_resume_edits

        with patch(
            "app.tools.resume_suggest.invoke_structured",
            return_value=_make_output([_VALID_ITEM]),
        ):
            records = suggest_resume_edits(_BULLETS, jd_text="JD 原文")

        assert len(records) == 1
        rec = records[0]
        assert rec["id"].startswith("sg_") and len(rec["id"]) == 11
        assert rec["status"] == "pending"
        assert rec["original_text"] == "主导重构与缓存策略"
        assert rec["suggested_text"].startswith("主导首屏性能重构")
        assert rec["item_index"] == 1 and rec["bullet_index"] == 0

    def test_out_of_range_index_dropped(self):
        from app.tools.resume_suggest import suggest_resume_edits

        bad = {**_VALID_ITEM, "item_index": 9, "bullet_index": 9}
        with patch(
            "app.tools.resume_suggest.invoke_structured",
            return_value=_make_output([bad, _VALID_ITEM]),
        ):
            records = suggest_resume_edits(_BULLETS)
        assert len(records) == 1
        assert records[0]["item_index"] == 1

    def test_original_text_mismatch_dropped(self):
        from app.tools.resume_suggest import suggest_resume_edits

        hallucinated = {**_VALID_ITEM, "original_text": "完全不同的原文"}
        with patch(
            "app.tools.resume_suggest.invoke_structured",
            return_value=_make_output([hallucinated]),
        ):
            records = suggest_resume_edits(_BULLETS)
        assert records == []

    def test_empty_suggested_dropped(self):
        from app.tools.resume_suggest import suggest_resume_edits

        empty = {**_VALID_ITEM, "suggested_text": "   "}
        with patch(
            "app.tools.resume_suggest.invoke_structured",
            return_value=_make_output([empty]),
        ):
            assert suggest_resume_edits(_BULLETS) == []

    def test_capped_at_12(self):
        from app.tools.resume_suggest import suggest_resume_edits

        items = [
            {**_VALID_ITEM, "original_text": "负责推荐系统", "item_index": 0}
            for _ in range(15)
        ]
        with patch(
            "app.tools.resume_suggest.invoke_structured",
            return_value=_make_output(items),
        ):
            records = suggest_resume_edits(_BULLETS)
        assert len(records) == 12

    def test_empty_bullets_raises(self):
        from app.tools.resume_suggest import suggest_resume_edits

        with pytest.raises(ValueError):
            suggest_resume_edits([])


# ============================================================
# 工具：岗位上下文装配（JD 分析产物）
# ============================================================


class TestLoadSuggestContext:
    def test_merges_analysis_products(self):
        from app.tools.resume_suggest import load_suggest_context

        fake_analysis = {
            "jd_text": "JD 原文",
            "ats_profile": {"job_title": "AI 产品经理"},
            "gap_items": ["缺量化指标"],
        }
        with patch("app.tools.db_job.get_job_analysis", return_value=fake_analysis):
            ctx = load_suggest_context(
                {"job_analysis_id": 5, "jd_text": "旧文本"}, user_id=1
            )
        assert ctx["jd_text"] == "JD 原文"
        assert ctx["ats"]["job_title"] == "AI 产品经理"
        assert ctx["gap_items"] == ["缺量化指标"]

    def test_falls_back_to_submission_jd(self):
        from app.tools.resume_suggest import load_suggest_context

        with patch("app.tools.db_job.get_job_analysis", return_value=None):
            ctx = load_suggest_context(
                {"job_analysis_id": 5, "jd_text": "提交时保存的 JD"}, user_id=1
            )
        assert ctx["jd_text"] == "提交时保存的 JD"
        assert ctx["ats"] == {}

    def test_analysis_error_degrades(self):
        from app.tools.resume_suggest import load_suggest_context

        with patch(
            "app.tools.db_job.get_job_analysis", side_effect=RuntimeError("db down")
        ):
            ctx = load_suggest_context({"job_analysis_id": 5, "jd_text": ""}, user_id=1)
        assert ctx["jd_text"] == ""


# ============================================================
# 同步端点
# ============================================================


class TestResumeSuggestEndpoint:
    def test_404_without_ownership(self):
        with patch("app.api.submission.db_tools.get_submission", return_value=None):
            resp = client.post(
                "/api/jobcraft/submission/999/resume-suggest",
                json={"bullets": [{"item_index": 0, "bullet_index": 0, "text": "x"}]},
                headers=_AUTH,
            )
        assert resp.status_code == 404

    def test_400_empty_bullets(self):
        fake_submission = {"id": 1, "job_analysis_id": None, "jd_text": ""}
        with patch(
            "app.api.submission.db_tools.get_submission", return_value=fake_submission
        ):
            resp = client.post(
                "/api/jobcraft/submission/1/resume-suggest",
                json={"bullets": []},
                headers=_AUTH,
            )
        assert resp.status_code == 400

    def test_success_returns_suggestions(self):
        fake_submission = {"id": 1, "job_analysis_id": None, "jd_text": ""}
        fake_record = {"id": "sg_1", "status": "pending"}
        with (
            patch(
                "app.api.submission.db_tools.get_submission",
                return_value=fake_submission,
            ),
            patch(
                "app.tools.resume_suggest.load_suggest_context",
                return_value={"jd_text": "", "ats": {}, "gap_items": []},
            ),
            patch(
                "app.tools.resume_suggest.suggest_resume_edits",
                return_value=[fake_record],
            ) as fake_suggest,
        ):
            resp = client.post(
                "/api/jobcraft/submission/1/resume-suggest",
                json={"bullets": [{"item_index": 0, "bullet_index": 0, "text": "x"}]},
                headers=_AUTH,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["suggestions"] == [fake_record]
        passed_bullets = fake_suggest.call_args[0][0]
        assert passed_bullets == [{"item_index": 0, "bullet_index": 0, "text": "x"}]

    def test_llm_failure_returns_502(self):
        fake_submission = {"id": 1, "job_analysis_id": None, "jd_text": ""}
        with (
            patch(
                "app.api.submission.db_tools.get_submission",
                return_value=fake_submission,
            ),
            patch(
                "app.tools.resume_suggest.load_suggest_context",
                return_value={"jd_text": "", "ats": {}, "gap_items": []},
            ),
            patch(
                "app.tools.resume_suggest.suggest_resume_edits",
                side_effect=RuntimeError("llm down"),
            ),
        ):
            resp = client.post(
                "/api/jobcraft/submission/1/resume-suggest",
                json={"bullets": [{"item_index": 0, "bullet_index": 0, "text": "x"}]},
                headers=_AUTH,
            )
        assert resp.status_code == 502


# ============================================================
# 任务 handler
# ============================================================


class _FakeTaskManager:
    """不依赖真实 Redis 的 task manager 替身。"""

    def __init__(self):
        self.status_updates = []

    def update_task_status(self, task_id, status, result=None, error=None):
        self.status_updates.append(
            {"task_id": task_id, "status": status, "result": result, "error": error}
        )


class TestExecuteResumeSuggest:
    def test_registered(self):
        from app.tasks.handlers import TASK_REGISTRY, TASK_TYPE_RESUME_SUGGEST

        assert TASK_TYPE_RESUME_SUGGEST in TASK_REGISTRY

    def test_success_completes_with_result(self, monkeypatch):
        fake_mgr = _FakeTaskManager()
        monkeypatch.setattr("app.tasks.handlers.get_task_manager", lambda: fake_mgr)
        monkeypatch.setattr(
            "app.tools.db_submission.get_submission",
            lambda sid, uid: {"id": sid, "job_analysis_id": None, "jd_text": ""},
        )
        monkeypatch.setattr(
            "app.tools.resume_suggest.load_suggest_context",
            lambda sub, uid=None: {"jd_text": "", "ats": {}, "gap_items": []},
        )
        monkeypatch.setattr(
            "app.tools.resume_suggest.suggest_resume_edits",
            lambda bullets, **kw: [{"id": "sg_x", "status": "pending"}],
        )

        from app.tasks.handlers import execute_resume_suggest

        result = execute_resume_suggest(
            {"task_id": "t-1", "user_id": 1, "submission_id": 3, "bullets": _BULLETS}
        )
        assert result == {"suggestions": [{"id": "sg_x", "status": "pending"}]}
        statuses = [u["status"].value for u in fake_mgr.status_updates]
        assert "running" in statuses and "completed" in statuses

    def test_missing_submission_fails(self, monkeypatch):
        fake_mgr = _FakeTaskManager()
        monkeypatch.setattr("app.tasks.handlers.get_task_manager", lambda: fake_mgr)
        monkeypatch.setattr(
            "app.tools.db_submission.get_submission", lambda sid, uid: None
        )

        from app.tasks.handlers import execute_resume_suggest

        with pytest.raises(ValueError):
            execute_resume_suggest(
                {
                    "task_id": "t-2",
                    "user_id": 1,
                    "submission_id": 999,
                    "bullets": _BULLETS,
                }
            )
        errors = [u for u in fake_mgr.status_updates if u["error"]]
        assert errors, "失败时必须写入 FAILED 状态"

    def test_missing_params_raises_before_running(self):
        from app.tasks.handlers import execute_resume_suggest

        with pytest.raises(ValueError):
            execute_resume_suggest({"task_id": "t-3", "user_id": 1})
