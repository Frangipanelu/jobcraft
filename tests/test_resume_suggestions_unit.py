"""FE-RESUME-02：简历 AI 建议存储契约单测。

覆盖三处：PATCH /api/jobcraft/submission 的 resume_suggestions Schema 校验、
db_submission.update_submission 的 JSON 序列化、get_submission 行映射回退。
DB / LLM 均 mock，不依赖真实 MySQL。
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.server import app
from app.auth import create_access_token

_TEST_TOKEN = create_access_token({"user_id": 1, "username": "unittest"})
_AUTH = {"Authorization": f"Bearer {_TEST_TOKEN}"}

client = TestClient(app, raise_server_exceptions=False)

VALID_SUGGESTION = {
    "id": "sg_ab12cd34",
    "type": "keyword",
    "title": "补充 JD 关键词",
    "original_text": "主导重构与缓存策略",
    "suggested_text": "主导首屏性能重构与多级缓存策略（命中 JD「性能优化」）",
    "reason": "缺失岗位关键词，量化口径不明",
    "item_index": 0,
    "bullet_index": 1,
    "status": "pending",
}


# ============================================================
# PATCH 端点 Schema 校验
# ============================================================


class TestPatchResumeSuggestions:
    def test_valid_list_forwarded(self):
        captured = {}

        def fake_update(submission_id, updates, user_id=None):
            captured.update(updates)
            return True

        with (
            patch("app.api.submission.db_tools.update_submission", fake_update),
            patch("app.api.submission.db_tools.get_submission", lambda *a: None),
        ):
            resp = client.patch(
                "/api/jobcraft/submission/1",
                json={"resume_suggestions": [VALID_SUGGESTION]},
                headers=_AUTH,
            )
        assert resp.status_code == 200
        assert captured.get("resume_suggestions") == [VALID_SUGGESTION]

    def test_empty_list_clears(self):
        captured = {}

        def fake_update(submission_id, updates, user_id=None):
            captured.update(updates)
            return True

        with (
            patch("app.api.submission.db_tools.update_submission", fake_update),
            patch("app.api.submission.db_tools.get_submission", lambda *a: None),
        ):
            resp = client.patch(
                "/api/jobcraft/submission/1",
                json={"resume_suggestions": []},
                headers=_AUTH,
            )
        assert resp.status_code == 200
        assert captured.get("resume_suggestions") == []

    def test_invalid_type_rejected(self):
        bad = {**VALID_SUGGESTION, "type": "nonsense"}
        resp = client.patch(
            "/api/jobcraft/submission/1",
            json={"resume_suggestions": [bad]},
            headers=_AUTH,
        )
        assert resp.status_code == 422

    def test_invalid_status_rejected(self):
        bad = {**VALID_SUGGESTION, "status": "archived"}
        resp = client.patch(
            "/api/jobcraft/submission/1",
            json={"resume_suggestions": [bad]},
            headers=_AUTH,
        )
        assert resp.status_code == 422

    def test_missing_id_rejected(self):
        bad = {k: v for k, v in VALID_SUGGESTION.items() if k != "id"}
        resp = client.patch(
            "/api/jobcraft/submission/1",
            json={"resume_suggestions": [bad]},
            headers=_AUTH,
        )
        assert resp.status_code == 422

    def test_over_limit_rejected(self):
        many = [{**VALID_SUGGESTION, "id": f"sg_{i:04d}"} for i in range(51)]
        resp = client.patch(
            "/api/jobcraft/submission/1",
            json={"resume_suggestions": many},
            headers=_AUTH,
        )
        assert resp.status_code == 422


# ============================================================
# DAO 序列化
# ============================================================


class TestUpdateSubmissionDao:
    def test_serializes_resume_suggestions_json(self):
        from app.tools.db_submission import update_submission

        with (
            patch("app.tools.db_submission._ensure_resume_submission_table"),
            patch("app.tools.db_submission.execute", return_value=1) as ex,
            patch("app.tools.db_submission._sync_job_entity"),
        ):
            ok = update_submission(1, {"resume_suggestions": [VALID_SUGGESTION]})
        assert ok is True
        sql, params = ex.call_args[0]
        assert "resume_suggestions=%s" in sql
        payload = next(p for p in params if isinstance(p, str) and "sg_ab12cd34" in p)
        assert json.loads(payload) == [VALID_SUGGESTION]

    def test_empty_list_still_issued(self):
        from app.tools.db_submission import update_submission

        with (
            patch("app.tools.db_submission._ensure_resume_submission_table"),
            patch("app.tools.db_submission.execute", return_value=1) as ex,
            patch("app.tools.db_submission._sync_job_entity"),
        ):
            ok = update_submission(1, {"resume_suggestions": []})
        assert ok is True
        sql, params = ex.call_args[0]
        assert "resume_suggestions=%s" in sql
        assert "[]" in params


# ============================================================
# get_submission 行映射（旧库行无该列时回退 []）
# ============================================================


def _make_row(with_suggestions: bool):
    row = {
        "id": 1,
        "user_id": 1,
        "job_analysis_id": None,
        "position": "AI 产品经理",
        "company": "字节跳动",
        "jd_text": "",
        "resume_markdown": "# 张三\n\n## 工作经历\n",
        "resume_file_path": None,
        "card_version_ids": "[]",
        "status": "PREPARED",
        "notes": "",
        "is_manual": 0,
        "delivered": 0,
        "job_id": None,
        "created_at": None,
        "updated_at": None,
    }
    if with_suggestions:
        row["resume_suggestions"] = json.dumps([VALID_SUGGESTION], ensure_ascii=False)
    return row


class TestGetSubmissionSuggestions:
    def test_maps_stored_suggestions(self):
        from app.tools.db_submission import get_submission

        with (
            patch("app.tools.db_submission._ensure_resume_submission_table"),
            patch("app.tools.db_submission.query_one", return_value=_make_row(True)),
        ):
            result = get_submission(1)
        assert result["resume_suggestions"] == [VALID_SUGGESTION]

    def test_missing_column_falls_back_to_empty(self):
        from app.tools.db_submission import get_submission

        with (
            patch("app.tools.db_submission._ensure_resume_submission_table"),
            patch("app.tools.db_submission.query_one", return_value=_make_row(False)),
        ):
            result = get_submission(1)
        assert result["resume_suggestions"] == []
