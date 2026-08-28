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

from app.api.server import app

client = TestClient(app, raise_server_exceptions=False)


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

    def test_cards_missing_user_id_uses_default(self, monkeypatch):
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
        assert body["code"] == 500


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


class TestExperienceExport:
    """GET /api/jobcraft/experience/export"""

    def test_export_no_cards_returns_404(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.experience.db_tools.list_cards", lambda *a, **kw: []
        )
        resp = client.get("/api/jobcraft/experience/export?format=json")
        assert resp.status_code == 404

    def test_export_json_format(self, monkeypatch):
        fake = [{"id": 1, "company": "A", "role": "B"}]
        monkeypatch.setattr(
            "app.api.experience.db_tools.list_cards", lambda *a, **kw: fake
        )
        resp = client.get("/api/jobcraft/experience/export?format=json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "json"
        assert data["count"] == 1

    def test_export_csv_format(self, monkeypatch):
        fake = [
            {
                "id": 1,
                "company": "A",
                "role": "B",
                "period": "",
                "title": "T",
                "tags": [],
                "is_active": True,
                "created_at": "",
            }
        ]
        monkeypatch.setattr(
            "app.api.experience.db_tools.list_cards", lambda *a, **kw: fake
        )
        resp = client.get("/api/jobcraft/experience/export?format=csv")
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "csv"
        assert "content" in data

    def test_export_unsupported_format_returns_400(self, monkeypatch):
        fake = [{"id": 1}]
        monkeypatch.setattr(
            "app.api.experience.db_tools.list_cards", lambda *a, **kw: fake
        )
        resp = client.get("/api/jobcraft/experience/export?format=xml")
        assert resp.status_code == 400


class TestExperienceBatch:
    """POST /api/jobcraft/experience/cards/batch"""

    def test_batch_missing_action_returns_400(self):
        resp = client.post(
            "/api/jobcraft/experience/cards/batch",
            json={"card_ids": [1]},
        )
        assert resp.status_code == 400

    def test_batch_missing_card_ids_returns_400(self):
        resp = client.post(
            "/api/jobcraft/experience/cards/batch",
            json={"action": "archive", "card_ids": []},
        )
        assert resp.status_code == 400

    def test_batch_archive_success(self, monkeypatch):
        monkeypatch.setattr("app.api.experience.db_tools.update_card", lambda *a: True)
        resp = client.post(
            "/api/jobcraft/experience/cards/batch",
            json={"action": "archive", "card_ids": [1, 2]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "archive"
        assert data["success_count"] == 2
        assert data["failed_count"] == 0

    def test_batch_unsupported_action_returns_400(self):
        resp = client.post(
            "/api/jobcraft/experience/cards/batch",
            json={"action": "unknown_op", "card_ids": [1]},
        )
        assert resp.status_code == 400

    def test_batch_tag_missing_tags_returns_400(self):
        resp = client.post(
            "/api/jobcraft/experience/cards/batch",
            json={"action": "tag", "card_ids": [1], "params": {"tags": []}},
        )
        assert resp.status_code == 400


class TestExperienceVersions:
    """GET /api/jobcraft/experience/cards/{card_id}/versions"""

    def test_versions_card_not_found_returns_404(self, monkeypatch):
        monkeypatch.setattr("app.api.experience.db_tools.get_card", lambda *a: None)
        resp = client.get("/api/jobcraft/experience/cards/999/versions")
        assert resp.status_code == 404

    def test_versions_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.experience.db_tools.get_card", lambda *a: {"id": 1}
        )
        monkeypatch.setattr(
            "app.api.experience.db_tools.get_card_versions_by_card_id",
            lambda *a: [{"version_id": 10}],
        )
        resp = client.get("/api/jobcraft/experience/cards/1/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["card_id"] == 1


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
        monkeypatch.setattr("app.api.experience.db_tools.update_card", lambda *a: False)
        resp = client.patch(
            "/api/jobcraft/experience/cards/999", json={"title": "updated"}
        )
        assert resp.status_code == 404

    def test_update_normal(self, monkeypatch):
        monkeypatch.setattr("app.api.experience.db_tools.update_card", lambda *a: True)
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
        assert "公司名" in resp.json()["msg"]

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
        assert "JD" in resp.json()["msg"]

    def test_analyze_empty_card_ids_returns_400(self):
        resp = client.post(
            "/api/jobcraft/job/analyze",
            json={"company": "C", "position": "P", "jd_text": "J", "card_ids": []},
        )
        assert resp.status_code == 400
        assert "经历卡" in resp.json()["msg"]

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
        assert "invalid input" in resp.json()["msg"]


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


class TestStep1AtsRecommend:
    """POST /api/jobcraft/job/step1-ats-recommend"""

    def test_step1_missing_jd_text_returns_400(self):
        resp = client.post(
            "/api/jobcraft/job/step1-ats-recommend",
            json={"company": "C", "position": "P", "jd_text": ""},
        )
        assert resp.status_code == 400

    def test_step1_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.job_analysis.db_tools.list_cards", lambda *a, **kw: []
        )
        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.run_step1_workflow",
            lambda **kw: {"ats": {"job_title": "SWE"}, "recommended_cards": []},
        )
        monkeypatch.setattr(
            "app.api.job_analysis.db_tools.insert_job_analysis", lambda *a: 1
        )
        resp = client.post(
            "/api/jobcraft/job/step1-ats-recommend",
            json={"company": "C", "position": "P", "jd_text": "JD text"},
        )
        assert resp.status_code == 200
        assert resp.json()["job_analysis_id"] == 1


class TestStep2GapPolish:
    """POST /api/jobcraft/job/step2-gap-polish"""

    def test_step2_empty_card_ids_returns_400(self):
        resp = client.post(
            "/api/jobcraft/job/step2-gap-polish",
            json={"job_analysis_id": 1, "card_ids": []},
        )
        assert resp.status_code == 400

    def test_step2_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.run_step2_workflow",
            lambda *a: {"gap_analysis": "none"},
        )
        resp = client.post(
            "/api/jobcraft/job/step2-gap-polish",
            json={"job_analysis_id": 1, "card_ids": [1]},
        )
        assert resp.status_code == 200
        assert resp.json()["gap_analysis"] == "none"


class TestSaveCardVersion:
    """POST /api/jobcraft/job/save-card-version"""

    def test_save_version_empty_raw_text_returns_400(self):
        resp = client.post(
            "/api/jobcraft/job/save-card-version",
            json={"card_id": 1, "source_id": 1, "raw_text": ""},
        )
        assert resp.status_code == 400

    def test_save_version_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.job_analysis.db_tools.insert_card_version", lambda *a: 10
        )
        resp = client.post(
            "/api/jobcraft/job/save-card-version",
            json={
                "card_id": 1,
                "source_id": 1,
                "raw_text": "polished text",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["version_id"] == 10
        assert resp.json()["status"] == "saved"


class TestAnalyzeAts:
    """POST /api/jobcraft/job/analyze-ats"""

    def test_ats_missing_jd_returns_400(self):
        resp = client.post(
            "/api/jobcraft/job/analyze-ats",
            json={"jd_text": ""},
        )
        assert resp.status_code == 400

    def test_ats_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.run_analyze_ats_workflow",
            lambda *a: {"job_title": "SWE"},
        )
        resp = client.post(
            "/api/jobcraft/job/analyze-ats",
            json={"jd_text": "some JD"},
        )
        assert resp.status_code == 200
        assert resp.json()["ats_profile"]["job_title"] == "SWE"


class TestJobResumePreview:
    """POST /api/jobcraft/job/{job_id}/resume-preview"""

    def test_preview_not_found_returns_404(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.job_analysis.db_tools.get_job_analysis", lambda *a: None
        )
        resp = client.post("/api/jobcraft/job/999/resume-preview", json={})
        assert resp.status_code == 404

    def test_preview_no_cards_returns_400(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.job_analysis.db_tools.get_job_analysis",
            lambda *a: {"id": 1, "selected_card_ids": []},
        )
        monkeypatch.setattr("app.api.job_analysis.db_tools.get_card", lambda *a: None)
        resp = client.post(
            "/api/jobcraft/job/1/resume-preview",
            json={"selected_card_ids": []},
        )
        assert resp.status_code == 400


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
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_download_nonexistent_file(self, monkeypatch):
        resp = client.get(
            "/api/jobcraft/job/resume/download?path=D:\\nonexistent\\file.md"
        )
        assert resp.status_code == 200
        assert "error" in resp.json()


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
            lambda *a: {"id": 1, "position": "P", "status": "已投递"},
        )
        resp = client.post(
            "/api/jobcraft/submission",
            json={"position": "SWE", "company": "G"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == 1
        assert resp.json()["status"] == "已投递"


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
        resp = client.patch("/api/jobcraft/submission/999", json={"status": "面试中"})
        assert resp.status_code == 404

    def test_update_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.submission.db_tools.update_submission", lambda *a: True
        )
        monkeypatch.setattr(
            "app.api.submission.db_tools.get_submission",
            lambda *a: {"id": 1, "status": "面试中"},
        )
        resp = client.patch("/api/jobcraft/submission/1", json={"status": "面试中"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "面试中"


class TestSubmissionDelete:
    """DELETE /api/jobcraft/submission/{submission_id}"""

    def test_delete_not_found_returns_500(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.submission.db_tools.delete_submission", lambda *a: False
        )
        resp = client.delete("/api/jobcraft/submission/999")
        assert resp.status_code == 500
        assert "投递记录不存在" in resp.json()["msg"]

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
        assert "经历卡" in resp.json()["msg"]

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
        assert "missing data" in resp.json()["msg"]


class TestSelectedCards:
    """GET /api/jobcraft/job/{job_id}/selected-cards"""

    def test_selected_cards_normal(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.interview_prep.db_tools.get_selected_card_ids_by_job",
            lambda *a: [1, 2, 3],
        )
        resp = client.get("/api/jobcraft/job/1/selected-cards")
        assert resp.status_code == 200
        assert resp.json()["card_ids"] == [1, 2, 3]


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
        assert "不能为空" in resp.json()["msg"]

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
        assert "至少选择" in resp.json()["msg"]

    def test_analyze_too_many_sequences_returns_400(self):
        resp = client.post(
            "/api/jobcraft/interview-review/1/analyze",
            json={"selected_sequences": list(range(1, 10))},
        )
        assert resp.status_code == 400
        assert "最多" in resp.json()["msg"]

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
        assert "岗位名称" in resp.json()["msg"]

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
        assert "不支持" in resp.json()["msg"]
