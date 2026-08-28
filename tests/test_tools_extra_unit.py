"""
Tools 额外单元测试

覆盖 9 个尚未有完整测试的 Tools 模块：
  1. interview_pre.py  — 纯函数测试 (_card_text, _build_interview_prompt)
  2. jobcraft_resume.py — _sanitize_filename, generate_resume error paths
  3. upload_file_read_tool.py — _read_pdf (mock pypdf/pdfplumber)
  4. tavily_tool.py — internet_search (mock TavilyClient)
  5. db_tools.py — _parse_json, get_db_config, _jc_config
  6. db_experience.py — _row_to_card, _looks_like_full_resume, _rebuild_entry_text
  7. db_job.py — mock DB 测试 get_job_analysis
  8. db_submission.py — mock DB 测试 get_submission
  9. db_interview.py — mock DB 测试 get_interview_prep_by_job
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.db_tools import _parse_json


# ============================================================
# 1. interview_pre.py — 纯函数
# ============================================================


class TestInterviewPre:
    def test_card_text_prefers_card_versions(self):
        from app.tools.interview_pre import _card_text

        card = {"id": 10, "raw_text": "raw", "content": "c", "summary": "s"}
        versions = {10: "version text"}
        assert _card_text(card, versions) == "version text"

    def test_card_text_falls_back_to_raw_text(self):
        from app.tools.interview_pre import _card_text

        card = {"id": 2, "raw_text": "raw text", "content": "", "summary": ""}
        assert _card_text(card, {}) == "raw text"

    def test_card_text_falls_back_to_content(self):
        from app.tools.interview_pre import _card_text

        card = {"id": 3, "raw_text": "", "content": "content field", "summary": ""}
        assert _card_text(card, {}) == "content field"

    def test_card_text_falls_back_to_summary(self):
        from app.tools.interview_pre import _card_text

        card = {"id": 4, "raw_text": "", "content": "", "summary": "summary text"}
        assert _card_text(card, {}) == "summary text"

    def test_build_interview_prompt_contains_key_sections(self):
        from app.tools.interview_pre import _build_interview_prompt

        prompt = _build_interview_prompt(
            round_type="tech",
            position="backend engineer",
            company="TestCo",
            jd_text="requires Python",
            cards=[
                {
                    "id": 1,
                    "title": "Project A",
                    "summary": "did XX",
                    "tags": ["Python"],
                    "raw_text": "project details",
                }
            ],
            dimension_requirements=[
                {"dimension": "D1", "level": 4, "evidence": "needs depth"}
            ],
        )
        assert "backend engineer" in prompt
        assert "TestCo" in prompt
        assert "tech" in prompt
        assert "Project A" in prompt
        assert "D1" in prompt
        assert "InterviewPrepResult" in prompt

    def test_build_interview_prompt_with_company_research(self):
        from app.tools.interview_pre import _build_interview_prompt

        prompt = _build_interview_prompt(
            round_type="tech",
            position="eng",
            company="CoA",
            jd_text="JD",
            cards=[],
            dimension_requirements=[],
            company_research={"info": {"name": "CoA", "business": "AI"}},
        )
        assert "CoA" in prompt
        assert "AI" in prompt

    def test_build_interview_prompt_with_resume(self):
        from app.tools.interview_pre import _build_interview_prompt

        prompt = _build_interview_prompt(
            round_type="tech",
            position="eng",
            company="CoA",
            jd_text="JD",
            cards=[],
            dimension_requirements=[],
            resume_markdown="## Resume\nJohn Doe",
        )
        assert "resume" in prompt.lower()

    def test_build_interview_prompt_with_previous_review(self):
        from app.tools.interview_pre import _build_interview_prompt

        prompt = _build_interview_prompt(
            round_type="round2",
            position="eng",
            company="CoA",
            jd_text="JD",
            cards=[],
            dimension_requirements=[],
            previous_review_summary="tech round went well",
        )
        assert "tech round went well" in prompt

    def test_build_interview_prompt_second_round(self):
        from app.tools.interview_pre import _build_interview_prompt

        prompt = _build_interview_prompt(
            round_type="round2",
            position="eng",
            company="CoA",
            jd_text="JD",
            cards=[],
            dimension_requirements=[],
        )
        assert "round2" in prompt

    def test_dimension_descriptions_complete(self):
        from app.tools.interview_pre import DIMENSION_DESCRIPTIONS

        assert len(DIMENSION_DESCRIPTIONS) == 8
        for key in [f"D{i}" for i in range(1, 9)]:
            assert key in DIMENSION_DESCRIPTIONS


# ============================================================
# 2. jobcraft_resume.py — _sanitize_filename + error paths
# ============================================================


class TestJobcraftResume:
    def test_sanitize_filename_normal(self):
        from app.tools.jobcraft_resume import _sanitize_filename

        assert _sanitize_filename("ByteDance") == "ByteDance"

    def test_sanitize_filename_strips_special_chars(self):
        from app.tools.jobcraft_resume import _sanitize_filename

        result = _sanitize_filename("hello@world.com!")
        assert "@" not in result
        assert "!" not in result

    def test_sanitize_filename_truncates_at_40(self):
        from app.tools.jobcraft_resume import _sanitize_filename

        long_name = "A" * 60
        assert len(_sanitize_filename(long_name)) <= 40

    def test_sanitize_filename_empty_string(self):
        from app.tools.jobcraft_resume import _sanitize_filename

        assert _sanitize_filename("") == ""

    def test_generate_resume_raises_on_missing_analysis(self):
        from app.tools.jobcraft_resume import generate_resume

        with patch("app.tools.jobcraft_resume.db_tools") as mock_db:
            mock_db.get_job_analysis.return_value = None
            with pytest.raises(ValueError):
                generate_resume(999, [1])

    def test_generate_resume_raises_on_no_active_cards(self):
        from app.tools.jobcraft_resume import generate_resume

        with patch("app.tools.jobcraft_resume.db_tools") as mock_db:
            mock_db.get_job_analysis.return_value = {
                "user_id": 1,
                "company": "C",
                "position": "P",
                "jd_text": "JD",
            }
            mock_db.get_card.return_value = {"is_active": False}
            with pytest.raises(ValueError):
                generate_resume(1, [1])


# ============================================================
# 3. upload_file_read_tool.py — _read_pdf
# ============================================================


class TestUploadFileRead:
    def test_read_pdf_pypdf_success(self, tmp_path):
        from app.tools.upload_file_read_tool import _read_pdf

        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"fake")

        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "PDF text extracted"
        mock_reader.pages = [mock_page]

        with patch("app.tools.upload_file_read_tool.pypdf") as mock_pypdf:
            mock_pypdf.PdfReader.return_value = mock_reader
            text, err = _read_pdf(fake_pdf)
            assert text == "PDF text extracted"
            assert err == ""

    def test_read_pdf_pypdf_empty_falls_to_pdfplumber(self, tmp_path):
        from app.tools.upload_file_read_tool import _read_pdf

        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"fake")

        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_reader.pages = [mock_page]

        mock_pdfplumber_page = MagicMock()
        mock_pdfplumber_page.extract_text.return_value = "pdfplumber result"

        mock_pdfplumber_ctx = MagicMock()
        mock_pdfplumber_ctx.pages = [mock_pdfplumber_page]

        with (
            patch("app.tools.upload_file_read_tool.pypdf") as mock_pypdf,
            patch("app.tools.upload_file_read_tool.pdfplumber") as mock_pdfplumber,
        ):
            mock_pypdf.PdfReader.return_value = mock_reader
            mock_pdfplumber.open.return_value.__enter__ = MagicMock(
                return_value=mock_pdfplumber_ctx
            )
            mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)
            text, err = _read_pdf(fake_pdf)
            assert text == "pdfplumber result"
            assert err == ""

    def test_read_pdf_all_fail_returns_error(self, tmp_path):
        from app.tools.upload_file_read_tool import _read_pdf

        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"fake")

        with (
            patch("app.tools.upload_file_read_tool.pypdf", None),
            patch("app.tools.upload_file_read_tool.pdfplumber", None),
        ):
            text, err = _read_pdf(fake_pdf)
            assert text == ""
            assert "test.pdf" in err

    def test_min_useful_chars_constant(self):
        from app.tools.upload_file_read_tool import MIN_USEFUL_CHARS

        assert MIN_USEFUL_CHARS == 50

    def test_tool_error_prefix(self):
        from app.tools.upload_file_read_tool import _TOOL_ERROR_PREFIX

        assert _TOOL_ERROR_PREFIX == "__TOOL_ERROR__:"


# ============================================================
# 4. tavily_tool.py — internet_search
# ============================================================


class TestTavilyTool:
    def test_internet_search_calls_tavily_client(self):
        from app.tools.tavily_tool import internet_search

        mock_client = MagicMock()
        mock_client.search.return_value = {"results": [{"title": "test"}]}

        with (
            patch("app.tools.tavily_tool.tavily_client", mock_client),
            patch("app.tools.tavily_tool.monitor"),
        ):
            result = internet_search.invoke(
                {"query": "test query", "topic": "general", "max_results": 3}
            )
            mock_client.search.assert_called_once_with(
                query="test query",
                topic="general",
                max_results=3,
                include_raw_content=False,
            )
            assert result == {"results": [{"title": "test"}]}

    def test_internet_search_default_params(self):
        from app.tools.tavily_tool import internet_search

        mock_client = MagicMock()
        mock_client.search.return_value = {"results": []}

        with (
            patch("app.tools.tavily_tool.tavily_client", mock_client),
            patch("app.tools.tavily_tool.monitor"),
        ):
            internet_search.invoke({"query": "AI"})
            mock_client.search.assert_called_once_with(
                query="AI",
                topic="general",
                max_results=5,
                include_raw_content=False,
            )


# ============================================================
# 5. db_tools.py — _parse_json, get_db_config, _jc_config
# ============================================================


class TestDbTools:
    def test_parse_json_none(self):
        assert _parse_json(None) is None

    def test_parse_json_empty_string(self):
        assert _parse_json("") is None

    def test_parse_json_dict_passthrough(self):
        d = {"key": "value"}
        assert _parse_json(d) == d

    def test_parse_json_list_passthrough(self):
        lst = [1, 2, 3]
        assert _parse_json(lst) == lst

    def test_parse_json_valid_string(self):
        assert _parse_json('{"a": 1}') == {"a": 1}

    def test_parse_json_invalid_string_returns_original(self):
        assert _parse_json("not json") == "not json"

    def test_get_db_config_reads_env(self, monkeypatch):
        from app.tools.db_tools import get_db_config

        monkeypatch.setenv("MYSQL_HOST", "db.example.com")
        monkeypatch.setenv("MYSQL_PORT", "3307")
        monkeypatch.setenv("MYSQL_USER", "testuser")
        monkeypatch.setenv("MYSQL_PASSWORD", "testpass")
        monkeypatch.setenv("MYSQL_DATABASE", "testdb")

        config = get_db_config()
        assert config["host"] == "db.example.com"
        assert config["port"] == 3307
        assert config["user"] == "testuser"
        assert config["password"] == "testpass"
        assert config["database"] == "testdb"
        assert config["charset"] == "utf8mb4"

    def test_get_db_config_raises_on_missing_required(self, monkeypatch):
        from app.tools.db_tools import get_db_config

        monkeypatch.delenv("MYSQL_USER", raising=False)
        monkeypatch.delenv("MYSQL_PASSWORD", raising=False)
        monkeypatch.delenv("MYSQL_DATABASE", raising=False)

        with pytest.raises(ValueError):
            get_db_config()

    def test_get_db_config_applies_overrides(self, monkeypatch):
        from app.tools.db_tools import get_db_config

        monkeypatch.setenv("MYSQL_USER", "u")
        monkeypatch.setenv("MYSQL_PASSWORD", "p")
        monkeypatch.setenv("MYSQL_DATABASE", "db")

        config = get_db_config({"database": "override_db", "port": 3308})
        assert config["database"] == "override_db"
        assert config["port"] == 3308

    def test_jc_config_sets_jobcraft_database(self, monkeypatch):
        from app.tools.db_tools import _jc_config

        monkeypatch.setenv("MYSQL_USER", "u")
        monkeypatch.setenv("MYSQL_PASSWORD", "p")
        monkeypatch.setenv("MYSQL_DATABASE", "db")

        config = _jc_config()
        assert config["database"] == "jobcraft"


# ============================================================
# 6. db_experience.py — 纯函数测试
# ============================================================


class TestDbExperience:
    def test_row_to_card_basic(self):
        from app.tools.db_experience import _row_to_card

        row = {
            "id": 1,
            "user_id": 1,
            "title": "Test Card",
            "raw_text": "raw text",
            "tags": '["tag1"]',
            "ai_structured": None,
            "summary": "summary",
            "content": "content",
            "company": "CompanyA",
            "role": "Engineer",
            "period": "2020-2022",
            "background": "bg",
            "problem": "problem",
            "solution": "solution",
            "execution": "exec",
            "result": "result",
            "dimensions": "[]",
            "source": "manual",
            "card_type": "work",
            "version": 1,
            "is_active": 1,
            "created_at": None,
            "updated_at": None,
        }
        card = _row_to_card(row)
        assert card["id"] == 1
        assert card["title"] == "Test Card"
        assert card["raw_text"] == "raw text"
        assert card["tags"] == ["tag1"]
        assert card["company"] == "CompanyA"
        assert card["is_active"] is True

    def test_row_to_card_empty(self):
        from app.tools.db_experience import _row_to_card

        assert _row_to_card({}) == {}
        assert _row_to_card(None) is None

    def test_row_to_card_fallback_raw_text(self):
        from app.tools.db_experience import _row_to_card

        row = {
            "id": 1,
            "user_id": 1,
            "title": "T",
            "raw_text": None,
            "tags": "[]",
            "ai_structured": None,
            "summary": "summary text",
            "content": None,
            "company": None,
            "role": None,
            "period": None,
            "background": "",
            "problem": "",
            "solution": "",
            "execution": "",
            "result": "",
            "dimensions": "[]",
            "source": "manual",
            "card_type": "work",
            "version": 1,
            "is_active": 1,
            "created_at": None,
            "updated_at": None,
        }
        card = _row_to_card(row)
        assert card["raw_text"] == "summary text"

    def test_looks_like_full_resume_false_for_short_text(self):
        from app.tools.db_experience import _looks_like_full_resume

        assert _looks_like_full_resume("") is False
        assert _looks_like_full_resume("short") is False

    def test_looks_like_full_resume_true_for_multiple_ranges(self):
        from app.tools.db_experience import _looks_like_full_resume

        # Two separate date ranges trigger the >= 2 range detection
        text = (
            "2019年3月 - 2020年12月 负责A项目核心开发和维护，协调前后端团队完成上线\n"
            "2021年1月 - 2022年6月 负责B项目架构设计和团队协作，推动技术选型落地\n"
            "一些其他内容填充，确保文本长度达到一百字的最低要求确保测试能够正确运行通过"
        )
        assert len(text) >= 100
        assert _looks_like_full_resume(text) is True

    def test_looks_like_full_resume_true_for_resume_markers(self):
        from app.tools.db_experience import _looks_like_full_resume

        # >= 2 resume section markers triggers detection
        text = (
            "个人简历，包含工作经历和项目经历两个主要章节，用于测试自动检测功能\n"
            "工作经历：在A公司负责XX项目的核心开发工作，涉及前后端架构设计\n"
            "项目经历：完成YY项目的架构设计和开发工作，推动技术选型和落地\n"
            "一些内容填充，确保文本长度达到一百字的最低要求来确保测试能够正确运行"
        )
        assert len(text) >= 100
        assert _looks_like_full_resume(text) is True

    def test_looks_like_full_resume_true_for_entry_headers(self):
        from app.tools.db_experience import _looks_like_full_resume

        # >= 2 entry headers like "#### 经历1：xxx" triggers detection
        text = (
            "#### 经历1：A公司 - 高级工程师\n"
            "负责核心模块开发和维护工作，推动架构升级和技术选型落地\n"
            "#### 经历2：B公司 - 技术负责人\n"
            "负责架构设计和团队协作管理，推动技术选型和团队建设落地\n"
            "内容填充确保达到字符数要求，并且确保测试能够正确运行通过"
        )
        assert len(text) >= 100
        assert _looks_like_full_resume(text) is True

    def test_rebuild_entry_text_basic(self):
        from app.tools.db_experience import _rebuild_entry_text

        entry = {
            "company": "ByteDance",
            "role": "PM",
            "period": "2020-2022",
            "summary": "led recommendation system",
            "achievements": [
                {
                    "title": "redesigned strategy",
                    "action": {"main": "led"},
                    "result": "CTR+12%",
                }
            ],
        }
        text = _rebuild_entry_text(entry)
        assert "ByteDance" in text
        assert "PM" in text
        assert "led recommendation system" in text
        assert "redesigned strategy" in text
        assert "CTR+12%" in text

    def test_rebuild_entry_text_minimal(self):
        from app.tools.db_experience import _rebuild_entry_text

        entry = {"company": "CompanyA"}
        text = _rebuild_entry_text(entry)
        assert "CompanyA" in text

    def test_rebuild_entry_text_empty(self):
        from app.tools.db_experience import _rebuild_entry_text

        text = _rebuild_entry_text({})
        assert text == ""


# ============================================================
# Helper: create mock connection for DB tests
# ============================================================


def _make_mock_conn(mock_cursor):
    """Create a mock connection that works with `with connect(**config) as conn:` and
    `with conn.cursor(...) as cur:` patterns."""
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    # conn.cursor(...) must return an object whose __enter__ returns the cursor
    cursor_obj = MagicMock()
    cursor_obj.__enter__ = MagicMock(return_value=mock_cursor)
    cursor_obj.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = cursor_obj
    return mock_conn


# ============================================================
# 7. db_job.py — mock DB
# ============================================================


class TestDbJob:
    def test_get_job_analysis_returns_none_when_not_found(self):
        from app.tools.db_job import get_job_analysis

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []
        mock_conn = _make_mock_conn(mock_cursor)

        with (
            patch("app.tools.db_job._jc_config", return_value={"database": "jc"}),
            patch("app.tools.db_job.connect", return_value=mock_conn),
            patch("app.tools.db_tools.connect", return_value=mock_conn),
        ):
            result = get_job_analysis(999)
            assert result is None

    def test_get_job_analysis_returns_dict(self):
        from app.tools.db_job import get_job_analysis

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "user_id": 1,
            "company": "TestCo",
            "position": "Engineer",
            "jd_text": "JD text",
            "jd_requirements": '{"hard_skills": ["Python"]}',
            "match_score": 85.5,
            "gap_analysis": "[]",
            "dimension_requirements": "[]",
            "created_at": SimpleNamespace(isoformat=lambda: "2024-01-01T00:00:00"),
        }
        mock_cursor.fetchall.return_value = []
        mock_conn = _make_mock_conn(mock_cursor)

        with (
            patch("app.tools.db_job._jc_config", return_value={"database": "jc"}),
            patch("app.tools.db_job.connect", return_value=mock_conn),
            patch("app.tools.db_tools.connect", return_value=mock_conn),
        ):
            result = get_job_analysis(1)
            assert result is not None
            assert result["company"] == "TestCo"
            assert result["position"] == "Engineer"
            assert result["match_score"] == 85.5
            assert result["jd_requirements"] == {"hard_skills": ["Python"]}

    def test_delete_job_analysis_returns_false_when_not_found(self):
        from app.tools.db_job import delete_job_analysis

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_conn = _make_mock_conn(mock_cursor)

        with (
            patch("app.tools.db_job._jc_config", return_value={"database": "jc"}),
            patch("app.tools.db_job.connect", return_value=mock_conn),
        ):
            assert delete_job_analysis(999) is False


# ============================================================
# 8. db_submission.py — mock DB
# ============================================================


class TestDbSubmission:
    def test_get_submission_returns_none_when_not_found(self):
        from app.tools.db_submission import get_submission

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []
        mock_conn = _make_mock_conn(mock_cursor)

        with (
            patch(
                "app.tools.db_submission._jc_config", return_value={"database": "jc"}
            ),
            patch("app.tools.db_submission.connect", return_value=mock_conn),
            patch("app.tools.db_tools.connect", return_value=mock_conn),
        ):
            result = get_submission(999)
            assert result is None

    def test_get_submission_returns_dict(self):
        from app.tools.db_submission import get_submission

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "user_id": 1,
            "job_analysis_id": 10,
            "position": "Backend Eng",
            "company": "TestCo",
            "jd_text": "JD",
            "resume_markdown": "# Resume",
            "resume_file_path": None,
            "card_version_ids": "[1,2]",
            "status": "submitted",
            "notes": "",
            "is_manual": 0,
            "created_at": SimpleNamespace(isoformat=lambda: "2024-01-01"),
            "updated_at": SimpleNamespace(isoformat=lambda: "2024-01-02"),
        }
        mock_cursor.fetchall.return_value = []
        mock_conn = _make_mock_conn(mock_cursor)

        with (
            patch(
                "app.tools.db_submission._jc_config", return_value={"database": "jc"}
            ),
            patch("app.tools.db_submission.connect", return_value=mock_conn),
            patch("app.tools.db_tools.connect", return_value=mock_conn),
        ):
            result = get_submission(1)
            assert result is not None
            assert result["position"] == "Backend Eng"
            assert result["card_version_ids"] == [1, 2]
            assert result["is_manual"] is False

    def test_update_submission_empty_returns_false(self):
        from app.tools.db_submission import update_submission

        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)

        with (
            patch(
                "app.tools.db_submission._jc_config", return_value={"database": "jc"}
            ),
            patch("app.tools.db_submission.connect", return_value=mock_conn),
        ):
            result = update_submission(1, {})
            assert result is False


# ============================================================
# 9. db_interview.py — mock DB
# ============================================================


class TestDbInterview:
    def test_get_interview_prep_by_job_returns_none(self):
        from app.tools.db_interview import get_interview_prep_by_job

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []
        mock_conn = _make_mock_conn(mock_cursor)

        with (
            patch("app.tools.db_interview._jc_config", return_value={"database": "jc"}),
            patch("app.tools.db_interview.connect", return_value=mock_conn),
            patch("app.tools.db_tools.connect", return_value=mock_conn),
        ):
            result = get_interview_prep_by_job(999)
            assert result is None

    def test_get_interview_prep_by_job_returns_dict(self):
        from app.tools.db_interview import get_interview_prep_by_job

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "job_analysis_id": 10,
            "user_id": 1,
            "round_type": "tech",
            "duration": "10-15 min",
            "elevator_pitch": "intro",
            "standard_version_json": "{}",
            "extended_version_json": '{"full_version": "full ver"}',
            "ability_matrix_json": '[{"dimension": "D1", "question": "q1"}]',
            "html_content": "<div>HTML</div>",
            "submission_id": None,
            "created_at": SimpleNamespace(isoformat=lambda: "2024-01-01"),
        }
        mock_cursor.fetchall.return_value = []
        mock_conn = _make_mock_conn(mock_cursor)

        with (
            patch("app.tools.db_interview._jc_config", return_value={"database": "jc"}),
            patch("app.tools.db_interview.connect", return_value=mock_conn),
            patch("app.tools.db_tools.connect", return_value=mock_conn),
        ):
            result = get_interview_prep_by_job(10)
            assert result is not None
            assert result["round_type"] == "tech"
            assert result["extended_version"] == {"full_version": "full ver"}
            assert len(result["ability_matrix"]) == 1

    def test_get_interview_record_returns_none(self):
        from app.tools.db_interview import get_interview_record

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []
        mock_conn = _make_mock_conn(mock_cursor)

        with (
            patch("app.tools.db_interview._jc_config", return_value={"database": "jc"}),
            patch("app.tools.db_interview.connect", return_value=mock_conn),
            patch("app.tools.db_tools.connect", return_value=mock_conn),
        ):
            result = get_interview_record(999)
            assert result is None

    def test_list_interview_records_empty(self):
        from app.tools.db_interview import list_interview_records

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None
        mock_conn = _make_mock_conn(mock_cursor)

        with (
            patch("app.tools.db_interview._jc_config", return_value={"database": "jc"}),
            patch("app.tools.db_interview.connect", return_value=mock_conn),
            patch("app.tools.db_tools.connect", return_value=mock_conn),
        ):
            result = list_interview_records()
            assert result == []
