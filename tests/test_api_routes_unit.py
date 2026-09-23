"""
API 路由模块单元测试

覆盖 5 个路由模块的参数校验、正常路径、错误处理和边界 case。
所有 db_tools / workflow 调用均被 mock，不依赖真实 DB 或 LLM。
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import create_access_token
from app.api.server import app

_TEST_TOKEN = create_access_token({"user_id": 1, "username": "unittest"})
_AUTH_HEADERS = {"Authorization": f"Bearer {_TEST_TOKEN}"}


class _AuthedClient:
    """为每个请求自动携带认证头，保持既有测试调用方式不变。"""

    def __init__(self, inner):
        self.inner = inner

    def _with_headers(self, kwargs):
        headers = kwargs.pop("headers", {})
        merged = dict(_AUTH_HEADERS)
        merged.update(headers)
        kwargs["headers"] = merged
        return kwargs

    def get(self, url, **kwargs):
        return self.inner.get(url, **self._with_headers(kwargs))

    def post(self, url, **kwargs):
        return self.inner.post(url, **self._with_headers(kwargs))

    def patch(self, url, **kwargs):
        return self.inner.patch(url, **self._with_headers(kwargs))

    def delete(self, url, **kwargs):
        return self.inner.delete(url, **self._with_headers(kwargs))


client = _AuthedClient(TestClient(app, raise_server_exceptions=False))


# ============================================================
# Helper: 非空 raw_text 用于跳过长度校验
# ============================================================

LONG_RAW_TEXT = "这是一段用于测试的面试记录文本，包含足够多的字符以通过长度校验。" * 3
RESUME_TEXT = "这是一段用于测试的简历内容，包含足够多的字符以通过内容校验，需要大于五十个字符才能通过校验。"


# ============================================================
# 1. experience.py — 经历卡路由
# ============================================================


class TestExperienceCards:
    """GET /api/jobcraft/experience/cards"""

    def test_cards_without_user_id_param_succeeds(self, monkeypatch):
        """身份来自 JWT，不再需要客户端传 user_id"""
        monkeypatch.setattr("app.api.experience.db_tools.count_cards", lambda *a: 0)
        monkeypatch.setattr(
            "app.api.experience.db_tools.list_cards_paginated", lambda *a: []
        )
        resp = client.get("/api/jobcraft/experience/cards")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_cards_normal_pagination(self, monkeypatch):
        fake_cards = [{"id": i, "title": f"card_{i}"} for i in range(1, 4)]
        monkeypatch.setattr("app.api.experience.db_tools.count_cards", lambda *a: 3)
        monkeypatch.setattr(
            "app.api.experience.db_tools.list_cards_paginated", lambda *a: fake_cards
        )
        resp = client.get("/api/jobcraft/experience/cards?page=1&page_size=20")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_cards_invalid_page_clamps_to_1(self, monkeypatch):
        monkeypatch.setattr("app.api.experience.db_tools.count_cards", lambda *a: 0)
        monkeypatch.setattr(
            "app.api.experience.db_tools.list_cards_paginated", lambda *a: []
        )
        resp = client.get("/api/jobcraft/experience/cards?page=0")
        assert resp.status_code == 200
        assert resp.json()["page"] == 1

    def test_cards_page_size_exceeds_max_clamps(self, monkeypatch):
        monkeypatch.setattr("app.api.experience.db_tools.count_cards", lambda *a: 0)
        monkeypatch.setattr(
            "app.api.experience.db_tools.list_cards_paginated", lambda *a: []
        )
        resp = client.get("/api/jobcraft/experience/cards?page_size=999")
        assert resp.status_code == 200
        assert resp.json()["page_size"] == 100

    def test_cards_db_error_returns_500(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.experience.db_tools.count_cards",
            lambda *a: (_ for _ in ()).throw(Exception("db down")),
        )
        resp = client.get("/api/jobcraft/experience/cards")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"]["code"] == "INTERNAL_ERROR"


class TestExperienceSearch:
    """GET /api/jobcraft/experience/cards/search"""

    def test_search_missing_q_returns_400(self, monkeypatch):
        resp = client.get("/api/jobcraft/experience/cards/search?q=")
        assert resp.status_code == 400

    def test_search_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.experience.db_tools.count_search_cards", lambda *a: 1
        )
        monkeypatch.setattr(
            "app.api.experience.db_tools.search_cards",
            lambda *a: [{"id": 1, "title": "match"}],
        )
        resp = client.get("/api/jobcraft/experience/cards/search?q=python")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["query"] == "python"


class TestExperienceCreate:
    """POST /api/jobcraft/experience/cards"""

    def test_create_missing_required_field_returns_422(self):
        resp = client.post("/api/jobcraft/experience/cards", json={"user_id": 1})
        assert resp.status_code == 422

    def test_create_normal(self, monkeypatch):
        monkeypatch.setattr("app.api.experience.db_tools.insert_card", lambda *a: 10)
        monkeypatch.setattr(
            "app.api.experience.db_tools.get_card",
            lambda *a: {"id": 10, "title": "新卡", "raw_text": "内容"},
        )
        resp = client.post(
            "/api/jobcraft/experience/cards",
            json={"title": "新卡", "raw_text": "内容"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 10
        assert data["title"] == "新卡"


class TestExperienceUpdate:
    """PATCH /api/jobcraft/experience/cards/{card_id}"""

    def test_update_card_not_found_returns_404(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.experience.db_tools.update_card", lambda *a, **k: False
        )
        resp = client.patch(
            "/api/jobcraft/experience/cards/999", json={"title": "updated"}
        )
        assert resp.status_code == 404

    def test_update_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.experience.db_tools.update_card", lambda *a, **k: True
        )
        monkeypatch.setattr(
            "app.api.experience.db_tools.get_card",
            lambda *a: {"id": 1, "title": "updated"},
        )
        resp = client.patch(
            "/api/jobcraft/experience/cards/1", json={"title": "updated"}
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "updated"


class TestExperienceDelete:
    """DELETE /api/jobcraft/experience/cards/{card_id}"""

    def test_delete_card_not_found_returns_404(self, monkeypatch):
        monkeypatch.setattr("app.api.experience.db_tools.delete_card", lambda *a: False)
        resp = client.delete("/api/jobcraft/experience/cards/999")
        assert resp.status_code == 404

    def test_delete_normal(self, monkeypatch):
        monkeypatch.setattr("app.api.experience.db_tools.delete_card", lambda *a: True)
        resp = client.delete("/api/jobcraft/experience/cards/1")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True


class TestExperienceStructure:
    """POST /api/jobcraft/experience/cards/{card_id}/structure"""

    def test_structure_card_not_found_returns_404(self, monkeypatch):
        monkeypatch.setattr("app.api.experience.db_tools.get_card", lambda *a: None)
        resp = client.post(
            "/api/jobcraft/experience/cards/999/structure", json={"user_id": 1}
        )
        assert resp.status_code == 404

    def test_structure_short_text_returns_400(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.experience.db_tools.get_card",
            lambda *a: {"id": 1, "raw_text": "短"},
        )
        resp = client.post(
            "/api/jobcraft/experience/cards/1/structure", json={"user_id": 1}
        )
        assert resp.status_code == 400

    def test_structure_workflow_returns_none_returns_500(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.experience.db_tools.get_card",
            lambda *a: {"id": 1, "raw_text": LONG_RAW_TEXT},
        )
        monkeypatch.setattr("app.api.experience.db_tools.update_card", lambda *a: True)
        monkeypatch.setattr(
            "app.workflows.extract_flow.run_extract_structured_workflow",
            lambda *a: None,
        )
        resp = client.post(
            "/api/jobcraft/experience/cards/1/structure", json={"user_id": 1}
        )
        assert resp.status_code == 500


class TestExperienceRecommendTags:
    """POST /api/jobcraft/experience/cards/{card_id}/recommend-tags"""

    def test_recommend_tags_card_not_found_returns_404(self, monkeypatch):
        monkeypatch.setattr("app.api.experience.db_tools.get_card", lambda *a: None)
        resp = client.post("/api/jobcraft/experience/cards/999/recommend-tags")
        assert resp.status_code == 404

    def test_recommend_tags_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.experience.db_tools.get_card",
            lambda *a: {"id": 1, "raw_text": LONG_RAW_TEXT},
        )
        monkeypatch.setattr(
            "app.workflows.extract_flow.run_recommend_tags_workflow",
            lambda *a: ["Python", "FastAPI"],
        )
        resp = client.post("/api/jobcraft/experience/cards/1/recommend-tags")
        assert resp.status_code == 200
        assert resp.json()["tags"] == ["Python", "FastAPI"]


class TestExperienceBackfill:
    """POST /api/jobcraft/experience/cards/backfill"""

    def test_backfill_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.workflows.extract_flow.run_backfill_workflow",
            lambda *a: {"processed": 3},
        )
        resp = client.post(
            "/api/jobcraft/experience/cards/backfill",
            json={"user_id": 1, "min_chars": 100},
        )
        assert resp.status_code == 200
        assert resp.json()["processed"] == 3

    def test_backfill_workflow_error_returns_500(self, monkeypatch):
        def raise_err(*a, **kw):
            raise Exception("boom")

        monkeypatch.setattr(
            "app.workflows.extract_flow.run_backfill_workflow", raise_err
        )
        resp = client.post(
            "/api/jobcraft/experience/cards/backfill", json={"user_id": 1}
        )
        assert resp.status_code == 500


class TestBaseResume:
    """底座简历历史版本 CRUD"""

    def _mock_db(self, monkeypatch):
        """把 db_base_resume 的函数替换为可控假实现。"""
        from app.tools import db_base_resume as mod

        store = {
            "rows": [],
            "seq": 1,
        }

        def _fake_create(data):
            rec = {
                "id": store["seq"],
                "user_id": data["user_id"],
                "name": data.get("name", "上传简历"),
                "file_size": data.get("file_size", ""),
                "format": data.get("format", "docx"),
                "parsed_count": data.get("parsed_count", 0),
                "tags": data.get("tags") or [],
                "is_default": bool(data.get("is_default", False)),
                "created_at": "2026-09-14T00:00:00",
                "updated_at": "2026-09-14T00:00:00",
            }
            store["seq"] += 1
            store["rows"].append(rec)
            return rec["id"]

        def _fake_list(user_id):
            return [r for r in store["rows"] if r["user_id"] == user_id]

        def _fake_get(resume_id, user_id=None):
            for r in store["rows"]:
                if r["id"] == resume_id and (
                    user_id is None or r["user_id"] == user_id
                ):
                    return r
            return None

        def _fake_delete(resume_id, user_id=None):
            for i, r in enumerate(store["rows"]):
                if r["id"] == resume_id and (
                    user_id is None or r["user_id"] == user_id
                ):
                    store["rows"].pop(i)
                    return True
            return False

        def _fake_set_default(resume_id, user_id):
            for r in store["rows"]:
                r["is_default"] = r["user_id"] == user_id and r["id"] == resume_id
            return any(
                r["id"] == resume_id and r["user_id"] == user_id for r in store["rows"]
            )

        monkeypatch.setattr(mod, "create_base_resume", _fake_create)
        monkeypatch.setattr(mod, "list_base_resumes", _fake_list)
        monkeypatch.setattr(mod, "get_base_resume", _fake_get)
        monkeypatch.setattr(mod, "delete_base_resume", _fake_delete)
        monkeypatch.setattr(mod, "set_default_base_resume", _fake_set_default)
        return store

    def test_create_first_is_default(self, monkeypatch):
        store = self._mock_db(monkeypatch)
        resp = client.post(
            "/api/jobcraft/experience/base-resumes",
            json={
                "name": "resume_a.pdf",
                "file_size": "1.2 MB",
                "parsed_count": 3,
                "format": "pdf",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["is_default"] is True
        assert data["parsed_count"] == 3
        assert len(store["rows"]) == 1

    def test_create_second_not_default(self, monkeypatch):
        store = self._mock_db(monkeypatch)
        client.post(
            "/api/jobcraft/experience/base-resumes",
            json={"name": "a.pdf", "format": "pdf"},
        )
        client.post(
            "/api/jobcraft/experience/base-resumes",
            json={"name": "b.docx", "format": "docx"},
        )
        row2 = store["rows"][1]
        assert row2["is_default"] is False
        resp = client.get("/api/jobcraft/experience/base-resumes")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_set_default_flips_ownership(self, monkeypatch):
        store = self._mock_db(monkeypatch)
        client.post(
            "/api/jobcraft/experience/base-resumes",
            json={"name": "a.pdf", "format": "pdf"},
        )
        client.post(
            "/api/jobcraft/experience/base-resumes",
            json={"name": "b.docx", "format": "docx"},
        )
        resp = client.patch("/api/jobcraft/experience/base-resumes/2/default")
        assert resp.status_code == 200
        assert resp.json()["id"] == 2
        assert resp.json()["is_default"] is True
        # 只有 id=2 保持默认
        defaults = [r for r in store["rows"] if r["is_default"]]
        assert [r["id"] for r in defaults] == [2]

    def test_set_default_missing_returns_404(self, monkeypatch):
        self._mock_db(monkeypatch)
        resp = client.patch("/api/jobcraft/experience/base-resumes/99/default")
        assert resp.status_code == 404

    def test_delete_normal(self, monkeypatch):
        store = self._mock_db(monkeypatch)
        client.post(
            "/api/jobcraft/experience/base-resumes",
            json={"name": "a.pdf", "format": "pdf"},
        )
        resp = client.delete("/api/jobcraft/experience/base-resumes/1")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert len(store["rows"]) == 0

    def test_delete_missing_returns_404(self, monkeypatch):
        self._mock_db(monkeypatch)
        resp = client.delete("/api/jobcraft/experience/base-resumes/99")
        assert resp.status_code == 404


class TestExperienceExpressions:
    """GET /api/jobcraft/experience/cards/{card_id}/expressions（EXP-P2-02 §8.1）"""

    def _mock_card(self, monkeypatch, card_id=10):
        monkeypatch.setattr(
            "app.api.experience.db_tools.get_card", lambda *a, **k: {"id": card_id}
        )

    def test_list_normal(self, monkeypatch):
        self._mock_card(monkeypatch, 10)
        monkeypatch.setattr(
            "app.tools.db_expression.EXPRESSION_TYPES",
            ("standardized", "direction", "job_specific"),
        )
        monkeypatch.setattr(
            "app.tools.db_expression.get_expressions_by_experience",
            lambda *a, **k: [
                {
                    "id": 1,
                    "user_id": 7,
                    "experience_id": 10,
                    "direction_id": None,
                    "job_id": None,
                    "type": "standardized",
                    "content": "内容",
                    "version": 3,
                    "validation_level": 0,
                    "usage_count": 0,
                    "source_refs": [],
                    "status": "active",
                    "created_at": None,
                    "updated_at": None,
                }
            ],
        )
        resp = client.get("/api/jobcraft/experience/cards/10/expressions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["experience_id"] == 10
        assert len(data["items"]) == 1
        assert data["items"][0]["version"] == 3

    def test_list_card_not_found_returns_404(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.experience.db_tools.get_card", lambda *a, **k: None
        )
        resp = client.get("/api/jobcraft/experience/cards/999/expressions")
        assert resp.status_code == 404

    def test_list_invalid_type_returns_400(self, monkeypatch):
        self._mock_card(monkeypatch)
        monkeypatch.setattr(
            "app.tools.db_expression.EXPRESSION_TYPES",
            ("standardized", "direction", "job_specific"),
        )
        resp = client.get("/api/jobcraft/experience/cards/10/expressions?type=bogus")
        assert resp.status_code == 400

    def test_list_with_filters(self, monkeypatch):
        self._mock_card(monkeypatch)
        captured = {}

        monkeypatch.setattr(
            "app.tools.db_expression.EXPRESSION_TYPES",
            ("standardized", "direction", "job_specific"),
        )

        def fake_list(card_id, user, t=None, d=None, j=None):
            captured["card_id"] = card_id
            captured["type"] = t
            captured["direction_id"] = d
            captured["job_id"] = j
            return []

        monkeypatch.setattr(
            "app.tools.db_expression.get_expressions_by_experience", fake_list
        )
        resp = client.get(
            "/api/jobcraft/experience/cards/10/expressions?type=direction&direction_id=3"
        )
        assert resp.status_code == 200
        assert captured["card_id"] == 10
        assert captured["type"] == "direction"
        assert captured["direction_id"] == 3

    def test_list_db_error_returns_500(self, monkeypatch):
        self._mock_card(monkeypatch)

        def boom(*a, **k):
            raise Exception("db down")

        monkeypatch.setattr(
            "app.tools.db_expression.get_expressions_by_experience", boom
        )
        resp = client.get("/api/jobcraft/experience/cards/10/expressions")
        assert resp.status_code == 500


class TestExpressionCreate:
    """POST /api/jobcraft/experience/expressions（EXP-P2-02 §8.2）"""

    def test_create_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.experience.db_tools.get_card", lambda *a, **k: {"id": 10}
        )
        monkeypatch.setattr(
            "app.tools.db_expression.create_expression", lambda *a, **k: 5
        )
        monkeypatch.setattr(
            "app.tools.db_expression.get_expression",
            lambda *a, **k: {
                "id": 5,
                "user_id": 7,
                "experience_id": 10,
                "direction_id": None,
                "job_id": None,
                "type": "standardized",
                "content": "新表达",
                "version": 1,
                "validation_level": 0,
                "usage_count": 0,
                "source_refs": [],
                "status": "candidate",
                "created_at": None,
                "updated_at": None,
            },
        )
        resp = client.post(
            "/api/jobcraft/experience/expressions",
            json={"experience_id": 10, "type": "standardized", "content": "新表达"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 5
        assert data["status"] == "candidate"

    def test_create_card_not_found_returns_404(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.experience.db_tools.get_card", lambda *a, **k: None
        )
        resp = client.post(
            "/api/jobcraft/experience/expressions",
            json={"experience_id": 999, "type": "standardized", "content": "x"},
        )
        assert resp.status_code == 404

    def test_create_empty_content_returns_400(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.experience.db_tools.get_card", lambda *a, **k: {"id": 10}
        )
        resp = client.post(
            "/api/jobcraft/experience/expressions",
            json={"experience_id": 10, "type": "standardized", "content": "  "},
        )
        assert resp.status_code == 400

    def test_create_missing_required_returns_422(self):
        resp = client.post(
            "/api/jobcraft/experience/expressions",
            json={"type": "standardized", "content": "x"},
        )
        assert resp.status_code == 422

    def test_create_db_error_returns_500(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.experience.db_tools.get_card", lambda *a, **k: {"id": 10}
        )

        def boom(**k):
            raise Exception("db down")

        monkeypatch.setattr("app.tools.db_expression.create_expression", boom)
        resp = client.post(
            "/api/jobcraft/experience/expressions",
            json={"experience_id": 10, "type": "standardized", "content": "x"},
        )
        assert resp.status_code == 500


# ============================================================
# 2. job_analysis.py — 岗位分析路由
# ============================================================


class TestJobAnalyze:
    """POST /api/jobcraft/job/analyze"""

    def test_analyze_missing_company_returns_400(self):
        resp = client.post(
            "/api/jobcraft/job/analyze",
            json={"position": "P", "jd_text": "J", "card_ids": [1]},
        )
        assert resp.status_code == 400
        assert "公司名" in resp.json()["error"]["message"]

    def test_analyze_missing_position_returns_422(self):
        resp = client.post(
            "/api/jobcraft/job/analyze",
            json={"company": "C", "jd_text": "J", "card_ids": [1]},
        )
        assert resp.status_code == 422

    def test_analyze_missing_jd_text_returns_400(self):
        resp = client.post(
            "/api/jobcraft/job/analyze",
            json={"company": "C", "position": "P", "card_ids": [1], "jd_text": ""},
        )
        assert resp.status_code == 400
        assert "JD" in resp.json()["error"]["message"]

    def test_analyze_empty_card_ids_returns_400(self):
        resp = client.post(
            "/api/jobcraft/job/analyze",
            json={"company": "C", "position": "P", "jd_text": "J", "card_ids": []},
        )
        assert resp.status_code == 400
        assert "经历卡" in resp.json()["error"]["message"]

    def test_analyze_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.job_analysis.run_job_analysis_workflow",
            lambda **kw: {"job_analysis_id": 1, "match_score": 80},
        )
        resp = client.post(
            "/api/jobcraft/job/analyze",
            json={
                "company": "Google",
                "position": "SWE",
                "jd_text": "JD text here",
                "card_ids": [1],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["match_score"] == 80

    def test_analyze_workflow_value_error_returns_400(self, monkeypatch):
        def raise_val(*a, **kw):
            raise ValueError("invalid input")

        monkeypatch.setattr("app.api.job_analysis.run_job_analysis_workflow", raise_val)
        resp = client.post(
            "/api/jobcraft/job/analyze",
            json={
                "company": "C",
                "position": "P",
                "jd_text": "J",
                "card_ids": [1],
            },
        )
        assert resp.status_code == 400
        assert "invalid input" in resp.json()["error"]["message"]


class TestJobList:
    """GET /api/jobcraft/job/analyses"""

    def test_list_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.job_analysis.db_tools.list_job_analyses",
            lambda *a: [{"id": 1}],
        )
        resp = client.get("/api/jobcraft/job/analyses")
        assert resp.status_code == 200
        assert len(resp.json()["analyses"]) == 1


class TestJobGet:
    """GET /api/jobcraft/job/analyze/{job_id}"""

    def test_get_not_found_returns_404(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.job_analysis.db_tools.get_job_analysis", lambda *a: None
        )
        resp = client.get("/api/jobcraft/job/analyze/999")
        assert resp.status_code == 404

    def test_get_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.job_analysis.db_tools.get_job_analysis",
            lambda *a: {"id": 1, "company": "C"},
        )
        resp = client.get("/api/jobcraft/job/analyze/1")
        assert resp.status_code == 200
        assert resp.json()["company"] == "C"


class TestJobDelete:
    """DELETE /api/jobcraft/job/analyze/{job_id}"""

    def test_delete_not_found_returns_404(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.job_analysis.db_tools.delete_job_analysis", lambda *a: False
        )
        resp = client.delete("/api/jobcraft/job/analyze/999")
        assert resp.status_code == 404

    def test_delete_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.job_analysis.db_tools.delete_job_analysis", lambda *a: True
        )
        resp = client.delete("/api/jobcraft/job/analyze/1")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestSplitJd:
    """POST /api/jobcraft/job/split-jd"""

    def test_split_jd_missing_text_returns_400(self):
        resp = client.post("/api/jobcraft/job/split-jd", json={"jd_text": ""})
        assert resp.status_code == 400

    def test_split_jd_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.run_structured_ats_split",
            lambda *a: {"duties": ["负责开发"], "requirements": []},
        )
        resp = client.post(
            "/api/jobcraft/job/split-jd",
            json={"jd_text": "岗位职责：负责开发"},
        )
        assert resp.status_code == 200
        assert resp.json()["duties"] == ["负责开发"]


class TestStructuredAnalyzeAts:
    """POST /api/jobcraft/job/analyze-ats-structured"""

    def test_structured_empty_returns_400(self):
        resp = client.post(
            "/api/jobcraft/job/analyze-ats-structured",
            json={"duties": [], "requirements": []},
        )
        assert resp.status_code == 400

    def test_structured_invalid_tag_returns_400(self):
        resp = client.post(
            "/api/jobcraft/job/analyze-ats-structured",
            json={
                "duties": ["负责开发"],
                "requirements": [{"text": "熟悉 Python", "tag": "bad"}],
            },
        )
        assert resp.status_code == 400

    def test_structured_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.run_structured_ats_workflow",
            lambda **kw: {
                "ats_profile": {"job_title": "后端", "required_skills": ["Python"]},
                "raw": {},
                "company": "C",
                "position": "后端",
            },
        )
        resp = client.post(
            "/api/jobcraft/job/analyze-ats-structured",
            json={
                "company": "字节跳动",
                "position": "后端工程师",
                "duties": ["负责交易系统"],
                "requirements": [
                    {"text": "3年以上经验", "tag": "hard"},
                    {"text": "熟悉 Python", "tag": "required"},
                    {"text": "高并发经验者优先", "tag": "preferred"},
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ats_profile"]["required_skills"] == ["Python"]


class TestSaveResume:
    """POST /api/jobcraft/job/save-resume"""

    def test_save_resume_empty_card_ids_returns_400(self):
        resp = client.post(
            "/api/jobcraft/job/save-resume",
            json={"job_analysis_id": 1, "selected_card_ids": []},
        )
        assert resp.status_code == 400

    def test_save_resume_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.job_analysis.jobcraft_resume.generate_resume",
            lambda **kw: {"resume_md": "# Resume"},
        )
        resp = client.post(
            "/api/jobcraft/job/save-resume",
            json={"job_analysis_id": 1, "selected_card_ids": [1]},
        )
        assert resp.status_code == 200
        assert "resume_md" in resp.json()


class TestResumeDownload:
    """GET /api/jobcraft/job/resume/download"""

    def test_download_invalid_path(self):
        resp = client.get("/api/jobcraft/job/resume/download?path=../etc/passwd")
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"
        assert resp.json()["error"]["message"]

    def test_download_nonexistent_file(self, monkeypatch):
        from app.api.server import output_dir

        missing = (output_dir / "__no_such_file__.md").resolve()
        resp = client.get(f"/api/jobcraft/job/resume/download?path={missing}")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"
        assert resp.json()["error"]["message"]


# ============================================================
# 3. submission.py — 投递记录路由
# ============================================================


class TestSubmissionCreate:
    """POST /api/jobcraft/submission"""

    def test_create_missing_position_returns_422(self):
        resp = client.post(
            "/api/jobcraft/submission",
            json={"company": "C"},
        )
        assert resp.status_code == 422

    def test_create_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.submission.db_tools.insert_submission", lambda *a: 1
        )
        monkeypatch.setattr(
            "app.api.submission.db_tools.get_submission",
            lambda *a: {"id": 1, "position": "P", "status": "APPLIED"},
        )
        resp = client.post(
            "/api/jobcraft/submission",
            json={"position": "SWE", "company": "G"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == 1
        assert resp.json()["status"] == "APPLIED"


class TestSubmissionGet:
    """GET /api/jobcraft/submission/{submission_id}"""

    def test_get_not_found_returns_404(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.submission.db_tools.get_submission", lambda *a: None
        )
        resp = client.get("/api/jobcraft/submission/999")
        assert resp.status_code == 404

    def test_get_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.submission.db_tools.get_submission",
            lambda *a: {"id": 1, "position": "P"},
        )
        resp = client.get("/api/jobcraft/submission/1")
        assert resp.status_code == 200
        assert resp.json()["position"] == "P"


class TestSubmissionUpdate:
    """PATCH /api/jobcraft/submission/{submission_id}"""

    def test_update_not_found_returns_404(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.submission.db_tools.update_submission", lambda *a: False
        )
        monkeypatch.setattr(
            "app.api.submission.db_tools.get_submission", lambda *a: None
        )
        resp = client.patch("/api/jobcraft/submission/999", json={"status": "INVITED"})
        assert resp.status_code == 404

    def test_update_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.submission.db_tools.update_submission", lambda *a: True
        )
        monkeypatch.setattr(
            "app.api.submission.db_tools.get_submission",
            lambda *a: {"id": 1, "status": "APPLIED"},
        )
        resp = client.patch("/api/jobcraft/submission/1", json={"status": "INVITED"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPLIED"

    def test_update_invalid_status_returns_400(self, monkeypatch):
        resp = client.patch("/api/jobcraft/submission/1", json={"status": "面试中"})
        assert resp.status_code == 400

    def test_update_illegal_transition_returns_400(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.submission.db_tools.update_submission", lambda *a: True
        )
        monkeypatch.setattr(
            "app.api.submission.db_tools.get_submission",
            lambda *a: {"id": 1, "status": "APPLIED"},
        )
        resp = client.patch("/api/jobcraft/submission/1", json={"status": "OFFER"})
        assert resp.status_code == 400
        assert "非法状态流转" in resp.json()["error"]["message"]

    def test_update_delivered_flag(self, monkeypatch):
        """P0-1：用户手动确认已投递 → delivered 标志透传到 db_tools.update_submission。"""
        updates_captured = {}

        def fake_update(submission_id, updates, user_id=None):
            updates_captured["updates"] = updates
            return True

        monkeypatch.setattr(
            "app.api.submission.db_tools.update_submission", fake_update
        )
        monkeypatch.setattr(
            "app.api.submission.db_tools.get_submission",
            lambda *a: {"id": 1, "status": "APPLIED", "delivered": True},
        )
        resp = client.patch("/api/jobcraft/submission/1", json={"delivered": True})
        assert resp.status_code == 200
        assert updates_captured["updates"]["delivered"] is True
        assert resp.json()["delivered"] is True

    def test_update_delivered_flag_false(self, monkeypatch):
        """取消已投递：delivered=false 不能被过滤掉（布尔值应保留）。"""
        updates_captured = {}

        def fake_update(submission_id, updates, user_id=None):
            updates_captured["updates"] = updates
            return True

        monkeypatch.setattr(
            "app.api.submission.db_tools.update_submission", fake_update
        )
        monkeypatch.setattr(
            "app.api.submission.db_tools.get_submission",
            lambda *a: {"id": 1, "status": "APPLIED", "delivered": False},
        )
        resp = client.patch("/api/jobcraft/submission/1", json={"delivered": False})
        assert resp.status_code == 200
        assert updates_captured["updates"]["delivered"] is False
        assert resp.json()["delivered"] is False


class TestSubmissionDelete:
    """DELETE /api/jobcraft/submission/{submission_id}"""

    def test_delete_not_found_returns_500(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.submission.db_tools.delete_submission", lambda *a: False
        )
        resp = client.delete("/api/jobcraft/submission/999")
        assert resp.status_code == 500
        assert "投递记录不存在" in resp.json()["error"]["message"]

    def test_delete_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.submission.db_tools.delete_submission", lambda *a: True
        )
        resp = client.delete("/api/jobcraft/submission/1")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True


class TestDashboard:
    """GET /api/jobcraft/dashboard"""

    def test_dashboard_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.submission.db_tools.get_dashboard",
            lambda *a: {"total": 5, "interviews": 2},
        )
        resp = client.get("/api/jobcraft/dashboard?user_id=1")
        assert resp.status_code == 200
        assert resp.json()["submissions"]["total"] == 5

    def test_dashboard_db_error_returns_500(self, monkeypatch):
        def raise_err(*a, **kw):
            raise Exception("db down")

        monkeypatch.setattr("app.api.submission.db_tools.get_dashboard", raise_err)
        resp = client.get("/api/jobcraft/dashboard")
        assert resp.status_code == 500


# ============================================================
# 4. interview_prep.py — 面试准备路由
# ============================================================


class TestInterviewPrep:
    """POST /api/jobcraft/job/{job_id}/interview-prep"""

    def test_prep_empty_card_ids_and_no_saved_returns_400(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.interview_prep.db_tools.get_selected_card_ids_by_job",
            lambda *a: [],
        )
        resp = client.post(
            "/api/jobcraft/job/1/interview-prep",
            json={"card_ids": [], "round_type": "技术面"},
        )
        assert resp.status_code == 400
        assert "经历卡" in resp.json()["error"]["message"]

    def test_prep_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.interview_prep.db_tools.get_selected_card_ids_by_job",
            lambda *a: [1],
        )
        monkeypatch.setattr(
            "app.api.interview_prep.db_tools.get_job_analysis",
            lambda *a: {"company": "C"},
        )
        monkeypatch.setattr(
            "app.api.interview_prep.db_tools.list_submissions", lambda *a: []
        )
        monkeypatch.setattr(
            "app.workflows.interview_prep_flow.run_interview_prep_workflow",
            lambda **kw: {"elevator_pitch": "Hi", "dimension_questions": []},
        )
        resp = client.post(
            "/api/jobcraft/job/1/interview-prep",
            json={"card_ids": [1], "round_type": "技术面"},
        )
        assert resp.status_code == 200
        assert resp.json()["elevator_pitch"] == "Hi"

    def test_prep_workflow_value_error_returns_400(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.interview_prep.db_tools.get_selected_card_ids_by_job",
            lambda *a: [1],
        )
        monkeypatch.setattr(
            "app.api.interview_prep.db_tools.get_job_analysis", lambda *a: None
        )
        monkeypatch.setattr(
            "app.api.interview_prep.db_tools.list_submissions", lambda *a: []
        )

        def raise_val(*a, **kw):
            raise ValueError("missing data")

        monkeypatch.setattr(
            "app.workflows.interview_prep_flow.run_interview_prep_workflow", raise_val
        )
        resp = client.post(
            "/api/jobcraft/job/1/interview-prep",
            json={"card_ids": [1], "round_type": "技术面"},
        )
        assert resp.status_code == 400
        assert "missing data" in resp.json()["error"]["message"]


class TestGetInterviewPrep:
    """GET /api/jobcraft/job/{job_id}/interview-prep"""

    def test_get_prep_not_found_returns_404(self, monkeypatch):
        monkeypatch.setattr(
            "app.tools.interview_pre.get_interview_prep",
            lambda *a: None,
        )
        resp = client.get("/api/jobcraft/job/1/interview-prep")
        assert resp.status_code == 404

    def test_get_prep_normal(self, monkeypatch):
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"job_analysis_id": 1}
        monkeypatch.setattr(
            "app.tools.interview_pre.get_interview_prep",
            lambda *a: mock_result,
        )
        resp = client.get("/api/jobcraft/job/1/interview-prep")
        assert resp.status_code == 200
        assert resp.json()["job_analysis_id"] == 1


# ============================================================
# 5. interview_review.py — 面试复盘路由
# ============================================================


class TestInterviewReviewCreate:
    """POST /api/jobcraft/interview-review"""

    def test_create_empty_raw_text_returns_400(self):
        resp = client.post(
            "/api/jobcraft/interview-review",
            json={"raw_text": ""},
        )
        assert resp.status_code == 400
        assert "不能为空" in resp.json()["error"]["message"]

    def test_create_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.tools.interview_review.create_interview_record",
            lambda **kw: 1,
        )
        monkeypatch.setattr(
            "app.tools.interview_review._parse_dialogue",
            lambda *a: [{"speaker": "I", "role": "interviewer", "text": "Q1"}],
        )
        monkeypatch.setattr(
            "app.workflows.question_table_flow.run_question_table_workflow",
            lambda *a, **kw: [{"question": "Q1"}],
        )
        resp = client.post(
            "/api/jobcraft/interview-review",
            json={
                "raw_text": LONG_RAW_TEXT,
                "title": "面试记录",
                "position": "SWE",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "parsed"
        assert data["qa_pair_count"] == 1
        assert data["speaker_count"] == 1

    def test_create_workflow_value_error_returns_400(self, monkeypatch):
        monkeypatch.setattr(
            "app.tools.interview_review.create_interview_record",
            lambda **kw: 1,
        )
        monkeypatch.setattr(
            "app.tools.interview_review._parse_dialogue",
            lambda *a: [],
        )

        def raise_val(*a, **kw):
            raise ValueError("parse error")

        monkeypatch.setattr(
            "app.workflows.question_table_flow.run_question_table_workflow", raise_val
        )
        resp = client.post(
            "/api/jobcraft/interview-review",
            json={"raw_text": LONG_RAW_TEXT},
        )
        assert resp.status_code == 400


class TestInterviewReviewList:
    """GET /api/jobcraft/interview-review"""

    def test_list_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.interview_review.db_tools.list_interview_records",
            lambda *a, **kw: [{"id": 1}],
        )
        resp = client.get("/api/jobcraft/interview-review")
        assert resp.status_code == 200
        assert len(resp.json()["records"]) == 1

    def test_list_db_error_returns_500(self, monkeypatch):
        def raise_err(*a, **kw):
            raise Exception("db error")

        monkeypatch.setattr(
            "app.api.interview_review.db_tools.list_interview_records", raise_err
        )
        resp = client.get("/api/jobcraft/interview-review")
        assert resp.status_code == 500


class TestInterviewReviewDetail:
    """GET /api/jobcraft/interview-review/{record_id}"""

    def test_detail_not_found_returns_404(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.interview_review.db_tools.get_interview_record", lambda *a: None
        )
        resp = client.get("/api/jobcraft/interview-review/999")
        assert resp.status_code == 404

    def test_detail_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.interview_review.db_tools.get_interview_record",
            lambda *a: {"id": 1, "title": "面试"},
        )
        monkeypatch.setattr(
            "app.api.interview_review.db_tools.list_interview_qa_pairs",
            lambda *a: [{"question": "Q1"}],
        )
        resp = client.get("/api/jobcraft/interview-review/1")
        assert resp.status_code == 200
        assert resp.json()["record"]["title"] == "面试"
        assert len(resp.json()["qa_pairs"]) == 1


class TestInterviewReviewDelete:
    """DELETE /api/jobcraft/interview-review/{record_id}"""

    def test_delete_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.interview_review.db_tools.delete_interview_record",
            lambda *a: None,
        )
        resp = client.delete("/api/jobcraft/interview-review/1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"


class TestInterviewReviewQuestionTable:
    """POST /api/jobcraft/interview-review/{record_id}/question-table"""

    def test_question_table_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.workflows.question_table_flow.run_question_table_workflow",
            lambda **kw: [{"question": "Q1", "dimension": "D1"}],
        )
        resp = client.post(
            "/api/jobcraft/interview-review/1/question-table",
            json={"user_id": 1},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "question_table"
        assert len(resp.json()["questions"]) == 1


class TestInterviewReviewAnalyze:
    """POST /api/jobcraft/interview-review/{record_id}/analyze"""

    def test_analyze_empty_sequences_returns_400(self):
        resp = client.post(
            "/api/jobcraft/interview-review/1/analyze",
            json={"selected_sequences": []},
        )
        assert resp.status_code == 400
        assert "至少选择" in resp.json()["error"]["message"]

    def test_analyze_too_many_sequences_returns_400(self):
        resp = client.post(
            "/api/jobcraft/interview-review/1/analyze",
            json={"selected_sequences": list(range(1, 10))},
        )
        assert resp.status_code == 400
        assert "最多" in resp.json()["error"]["message"]

    def test_analyze_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.workflows.interview_review_flow.run_interview_review_workflow",
            lambda **kw: {"overall_score": 75, "summary": "good"},
        )
        resp = client.post(
            "/api/jobcraft/interview-review/1/analyze",
            json={"selected_sequences": [1, 2]},
        )
        assert resp.status_code == 200
        assert resp.json()["overall_score"] == 75


class TestInterviewReviewParsePreview:
    """POST /api/jobcraft/interview-review/parse-preview"""

    def test_parse_preview_empty_text_returns_400(self):
        resp = client.post(
            "/api/jobcraft/interview-review/parse-preview",
            data={"raw_text": ""},
        )
        assert resp.status_code == 400

    def test_parse_preview_short_text_returns_400(self):
        resp = client.post(
            "/api/jobcraft/interview-review/parse-preview",
            data={"raw_text": "太短了"},
        )
        assert resp.status_code == 400

    def test_parse_preview_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.tools.interview_review._parse_dialogue",
            lambda *a: [
                {"speaker": "I", "role": "interviewer", "text": "Q1"},
                {"speaker": "C", "role": "candidate", "text": "A1"},
            ],
        )
        monkeypatch.setattr(
            "app.tools.interview_review._build_qa_pairs",
            lambda *a: [{"question": "Q1", "answer": "A1"}],
        )
        resp = client.post(
            "/api/jobcraft/interview-review/parse-preview",
            data={"raw_text": LONG_RAW_TEXT},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["qa_pair_count"] == 1
        assert data["speaker_count"] == 2


class TestInterviewReviewUpload:
    """POST /api/jobcraft/interview-review/upload"""

    def test_upload_missing_position_returns_400(self):
        import io

        resp = client.post(
            "/api/jobcraft/interview-review/upload",
            files={"file": ("test.txt", io.BytesIO(b"content"), "text/plain")},
            data={"position": ""},
        )
        assert resp.status_code == 400
        assert "岗位名称" in resp.json()["error"]["message"]

    def test_upload_unsupported_ext_returns_400(self):
        import io

        resp = client.post(
            "/api/jobcraft/interview-review/upload",
            files={
                "file": ("test.exe", io.BytesIO(b"content"), "application/octet-stream")
            },
            data={"position": "SWE"},
        )
        assert resp.status_code == 400
        assert "不支持" in resp.json()["error"]["message"]
