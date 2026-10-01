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
 10. db_raw_jd.py — RawJD 不可变快照（P4-2）
"""

import json
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
        from app.tools.card_render import get_card_render_text

        card = {"id": 10, "raw_text": "raw", "content": "c", "summary": "s"}
        versions = {10: "version text"}
        assert get_card_render_text(card, versions) == "version text"

    def test_card_text_falls_back_to_raw_text(self):
        from app.tools.card_render import get_card_render_text

        card = {"id": 2, "raw_text": "raw text", "content": "", "summary": ""}
        assert get_card_render_text(card, {}) == "raw text"

    def test_card_text_falls_back_to_content(self):
        from app.tools.card_render import get_card_render_text

        card = {"id": 3, "raw_text": "", "content": "content field", "summary": ""}
        assert get_card_render_text(card, {}) == "content field"

    def test_card_text_falls_back_to_summary(self):
        from app.tools.card_render import get_card_render_text

        card = {"id": 4, "raw_text": "", "content": "", "summary": "summary text"}
        assert get_card_render_text(card, {}) == "summary text"

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
        # v2 字段映射（elevator_pitch 非空 + card_ids 整数约束）已随加载生效
        assert "elevator_pitch" in prompt
        assert "禁止填卡片标题" in prompt

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

    def test_generate_resume_attaches_active_expression(self, tmp_path):
        """P2C-01：简历消费链应将激活表达附加到经验卡供渲染优先使用。"""
        from app.tools.jobcraft_resume import generate_resume

        captured_md = {}
        captured_html = {}
        incremented = []

        def fake_md(**kwargs):
            captured_md["cards"] = kwargs["cards"]
            return "resume-md"

        def fake_html(**kwargs):
            captured_html["cards"] = kwargs["cards"]
            return "resume-html"

        with (
            patch("app.tools.jobcraft_resume.db_tools") as mock_db,
            patch("app.tools.jobcraft_resume.generate_resume_markdown", fake_md),
            patch("app.tools.jobcraft_resume.generate_resume_html", fake_html),
            patch("app.tools.jobcraft_resume.OUTPUT_ROOT", tmp_path),
            patch(
                "app.tools.db_submission.get_submission_by_analysis",
                lambda *a, **k: None,
            ),
            patch("app.tools.db_submission.insert_submission", lambda *a, **k: 99),
            patch(
                "app.tools.db_expression.get_active_expression_content",
                lambda cid, user_id, expr_type="standardized": "激活表达",
            ),
            patch(
                "app.tools.db_expression.increment_active_expression_usage",
                lambda cid, user_id, expr_type="standardized": incremented.append(cid),
            ),
        ):
            mock_db.get_job_analysis.return_value = {
                "user_id": 7,
                "company": "C",
                "position": "P",
                "jd_text": "JD",
            }
            mock_db.get_card.return_value = {
                "id": 3,
                "is_active": True,
                "raw_text": "原始",
            }
            result = generate_resume(1, [3], user_id=7)

        assert captured_md["cards"][0]["id"] == 3
        assert captured_md["cards"][0]["active_expression"] == "激活表达"
        assert captured_html["cards"][0]["active_expression"] == "激活表达"
        assert incremented == [3]
        assert result["submission_id"] == 99

    def test_generate_resume_passes_ats_profile_to_generators(self, tmp_path):
        """BE-ATS-01：ats_profile 应解析后传入 md/html 生成器（原硬编码 None）。"""
        from app.schemas.jobcraft import ATSProfile
        from app.tools.jobcraft_resume import generate_resume

        captured_md = {}
        captured_html = {}

        def fake_md(**kwargs):
            captured_md["ats"] = kwargs["ats"]
            return "resume-md"

        def fake_html(**kwargs):
            captured_html["ats"] = kwargs["ats"]
            return "resume-html"

        with (
            patch("app.tools.jobcraft_resume.db_tools") as mock_db,
            patch("app.tools.jobcraft_resume.generate_resume_markdown", fake_md),
            patch("app.tools.jobcraft_resume.generate_resume_html", fake_html),
            patch("app.tools.jobcraft_resume.OUTPUT_ROOT", tmp_path),
            patch(
                "app.tools.db_submission.get_submission_by_analysis",
                lambda *a, **k: None,
            ),
            patch("app.tools.db_submission.insert_submission", lambda *a, **k: 99),
        ):
            mock_db.get_job_analysis.return_value = {
                "user_id": 7,
                "company": "C",
                "position": "P",
                "jd_text": "JD",
                "ats_profile": {
                    "job_title": "后端工程师",
                    "required_skills": ["Python", "MySQL"],
                    "preferred_skills": ["Redis", "K8s", "Go", "Rust"],
                },
            }
            mock_db.get_card.return_value = {
                "id": 3,
                "is_active": True,
                "raw_text": "x",
            }
            generate_resume(1, [3], user_id=7)

        assert isinstance(captured_md["ats"], ATSProfile)
        assert captured_md["ats"].required_skills == ["Python", "MySQL"]
        assert captured_md["ats"].preferred_skills[:3] == ["Redis", "K8s", "Go"]
        assert captured_html["ats"] is captured_md["ats"]

    def test_generate_resume_renders_core_skills_section(self, tmp_path):
        """真实渲染路径：核心能力块应出现于 md 与 html（原恒跳过）。"""
        from app.tools.jobcraft_resume import generate_resume

        with (
            patch("app.tools.jobcraft_resume.db_tools") as mock_db,
            patch("app.tools.jobcraft_resume.OUTPUT_ROOT", tmp_path),
            patch(
                "app.tools.db_submission.get_submission_by_analysis",
                lambda *a, **k: None,
            ),
            patch("app.tools.db_submission.insert_submission", lambda *a, **k: 99),
            patch(
                "app.tools.db_expression.get_active_expression_content",
                lambda cid, user_id, expr_type="standardized": None,
            ),
        ):
            mock_db.get_job_analysis.return_value = {
                "user_id": 7,
                "company": "C",
                "position": "P",
                "jd_text": "JD",
                "ats_profile": {
                    "required_skills": ["Python", "MySQL"],
                    "preferred_skills": ["Redis"],
                },
            }
            mock_db.get_card.return_value = {
                "id": 3,
                "is_active": True,
                "raw_text": "原始文本",
            }
            result = generate_resume(1, [3], user_id=7)

        assert "## 核心能力" in result["resume_markdown"]
        assert "Python、MySQL、Redis" in result["resume_markdown"]
        assert "核心能力" in result["resume_html"]
        assert "Python" in result["resume_html"]

    def test_generate_resume_invalid_ats_profile_skips_section(self, tmp_path):
        """ats_profile 损坏时降级跳过核心能力块，生成流程不失败。"""
        from app.tools.jobcraft_resume import generate_resume

        with (
            patch("app.tools.jobcraft_resume.db_tools") as mock_db,
            patch("app.tools.jobcraft_resume.OUTPUT_ROOT", tmp_path),
            patch(
                "app.tools.db_submission.get_submission_by_analysis",
                lambda *a, **k: None,
            ),
            patch("app.tools.db_submission.insert_submission", lambda *a, **k: 99),
            patch(
                "app.tools.db_expression.get_active_expression_content",
                lambda cid, user_id, expr_type="standardized": None,
            ),
        ):
            mock_db.get_job_analysis.return_value = {
                "user_id": 7,
                "company": "C",
                "position": "P",
                "jd_text": "JD",
                "ats_profile": {"required_skills": "not-a-list"},
            }
            mock_db.get_card.return_value = {
                "id": 3,
                "is_active": True,
                "raw_text": "原始文本",
            }
            result = generate_resume(1, [3], user_id=7)

        assert "## 核心能力" not in result["resume_markdown"]
        assert result["resume_markdown"]


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
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": [{"title": "test"}]}

        with (
            patch("tavily.TavilyClient", return_value=mock_client),
            patch.dict("os.environ", {"TAVILY_API_KEY": "fake-key"}),
        ):
            import importlib
            import app.tools.tavily_tool as mod

            importlib.reload(mod)
            with (
                patch.object(mod, "tavily_client", mock_client),
                patch.object(mod, "monitor"),
            ):
                result = mod.internet_search.invoke(
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
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": []}

        with (
            patch("tavily.TavilyClient", return_value=mock_client),
            patch.dict("os.environ", {"TAVILY_API_KEY": "fake-key"}),
        ):
            import importlib
            import app.tools.tavily_tool as mod

            importlib.reload(mod)
            with (
                patch.object(mod, "tavily_client", mock_client),
                patch.object(mod, "monitor"),
            ):
                mod.internet_search.invoke({"query": "AI"})
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

    def test_row_to_card_aggregates_star_slots(self):
        from app.tools.db_experience import _row_to_card

        row = {
            "id": 1,
            "user_id": 1,
            "title": "T",
            "raw_text": "raw",
            "tags": "[]",
            "ai_structured": json.dumps(
                {
                    "summary": "s",
                    "achievements": [
                        {
                            "title": "a1",
                            "situation": "st",
                            "action": {
                                "main": "行动1",
                                "difficulty": "d",
                                "resolution": "r",
                            },
                            "result": "结果1",
                        },
                        {
                            "title": "a2",
                            "situation": "st",
                            "action": {"main": "行动2"},
                            "result": "",
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            "summary": "summary text",
            "content": None,
            "company": None,
            "role": None,
            "period": None,
            "background": "背景",
            "problem": "问题",
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
        assert card["background"] == "背景"
        assert card["problem"] == "问题"
        assert card["actions"] == ["行动1", "行动2"]
        assert card["results"] == ["结果1"]

    def test_merge_star_slots_builds_achievements(self):
        from app.tools.db_experience import _merge_star_slots

        cache = _merge_star_slots(
            None,
            actions=["行动A", "行动B"],
            results=["结果A", "结果B"],
        )
        assert len(cache["achievements"]) == 2
        assert cache["achievements"][0]["action"]["main"] == "行动A"
        assert cache["achievements"][0]["result"] == "结果A"
        assert cache["achievements"][1]["action"]["difficulty"] == ""

    def test_merge_star_slots_preserves_existing_fields(self):
        from app.tools.db_experience import _merge_star_slots

        existing = {
            "summary": "old summary",
            "achievements": [
                {
                    "title": "标题保留",
                    "situation": "场景保留",
                    "action": {
                        "main": "旧行动",
                        "difficulty": "旧难度",
                        "resolution": "旧解法",
                    },
                    "result": "旧结果",
                }
            ],
        }
        cache = _merge_star_slots(existing, actions=["新行动"], results=None)
        assert cache["summary"] == "old summary"
        assert cache["achievements"][0]["title"] == "标题保留"
        assert cache["achievements"][0]["situation"] == "场景保留"
        assert cache["achievements"][0]["action"]["main"] == "新行动"
        assert cache["achievements"][0]["action"]["difficulty"] == "旧难度"
        assert cache["achievements"][0]["result"] == "旧结果"

    def test_merge_star_slots_asymmetric_preserves_other_slot(self):
        from app.tools.db_experience import _merge_star_slots

        cache = _merge_star_slots(None, actions=["行动1"], results=["结果1", "结果2"])
        assert len(cache["achievements"]) == 2
        assert cache["achievements"][0]["action"]["main"] == "行动1"
        assert cache["achievements"][0]["result"] == "结果1"
        assert cache["achievements"][1]["action"]["main"] == ""
        assert cache["achievements"][1]["result"] == "结果2"

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

        with patch("app.tools.db_conn.connect", return_value=mock_conn):
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

        with patch("app.tools.db_conn.connect", return_value=mock_conn):
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
        mock_cursor.fetchall.return_value = []
        mock_conn = _make_mock_conn(mock_cursor)

        with patch("app.tools.db_conn.connect", return_value=mock_conn):
            assert delete_job_analysis(999) is False

    def test_get_job_analysis_restores_p4_1_artifacts(self):
        """P4-1：读取路径还原 ats_profile / suggestions / per_card_scores /
        match_level / analysis_version 五列。"""
        from app.tools.db_job import get_job_analysis

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "user_id": 1,
            "company": "TestCo",
            "position": "Engineer",
            "jd_text": "JD text",
            "jd_requirements": "{}",
            "match_score": 85.5,
            "match_level": "值得投递",
            "analysis_version": "v1",
            "ats_profile": '{"job_title": "Engineer"}',
            "suggestions": '[{"type": "rewrite", "message": "补充 Go"}]',
            "per_card_scores": '[{"card_id": 1, "score": 85}]',
            "gap_analysis": "[]",
            "dimension_requirements": "[]",
            "created_at": SimpleNamespace(isoformat=lambda: "2024-01-01T00:00:00"),
        }
        mock_cursor.fetchall.return_value = []
        mock_conn = _make_mock_conn(mock_cursor)

        with patch("app.tools.db_conn.connect", return_value=mock_conn):
            result = get_job_analysis(1)
        assert result is not None
        assert result["ats_profile"] == {"job_title": "Engineer"}
        assert result["suggestions"] == [{"type": "rewrite", "message": "补充 Go"}]
        assert result["per_card_scores"] == [{"card_id": 1, "score": 85}]
        assert result["match_level"] == "值得投递"
        assert result["analysis_version"] == "v1"

    def test_get_job_analysis_tolerates_missing_p4_1_columns(self):
        """P4-1：未迁移库（旧行无五列）读取时回落空值，不抛错。"""
        from app.tools.db_job import get_job_analysis

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "user_id": 1,
            "company": "TestCo",
            "position": "Engineer",
            "jd_text": "JD text",
            "jd_requirements": "{}",
            "match_score": 85.5,
            "gap_analysis": "[]",
            "dimension_requirements": "[]",
            "created_at": SimpleNamespace(isoformat=lambda: "2024-01-01T00:00:00"),
        }
        mock_cursor.fetchall.return_value = []
        mock_conn = _make_mock_conn(mock_cursor)

        with patch("app.tools.db_conn.connect", return_value=mock_conn):
            result = get_job_analysis(1)
        assert result is not None
        assert result["ats_profile"] == {}
        assert result["suggestions"] == []
        assert result["per_card_scores"] == []
        assert result["match_level"] is None
        assert result["analysis_version"] is None

    def test_insert_job_analysis_writes_p4_1_columns(self):
        """P4-1：insert 携带五列并按 JSON 序列化落库参数。"""
        from app.tools.db_job import insert_job_analysis

        with (
            patch("app.tools.db_job._ensure_job_analysis_columns"),
            patch("app.tools.db_job.execute_lastrowid", return_value=5) as mock_insert,
            patch("app.tools.db_job._attach_job_entity", return_value=None),
        ):
            job_id = insert_job_analysis(
                {
                    "user_id": 1,
                    "company": "TestCo",
                    "position": "Engineer",
                    "jd_text": "JD",
                    "ats_profile": {"job_title": "Engineer"},
                    "suggestions": [{"type": "rewrite", "message": "补充 Go"}],
                    "per_card_scores": [{"card_id": 1, "score": 85}],
                    "match_level": "值得投递",
                    "analysis_version": "v1",
                }
            )
        assert job_id == 5
        sql, params = mock_insert.call_args[0]
        for col in (
            "ats_profile",
            "suggestions",
            "per_card_scores",
            "match_level",
            "analysis_version",
        ):
            assert col in sql
        assert json.loads(params[8]) == {"job_title": "Engineer"}
        assert json.loads(params[9]) == [{"type": "rewrite", "message": "补充 Go"}]
        assert json.loads(params[10]) == [{"card_id": 1, "score": 85}]
        assert params[11] == "值得投递"
        assert params[12] == "v1"

    def test_insert_job_analysis_attaches_job_entity(self):
        """P4-4a：insert 后 find-or-create Job 并回填 job_analysis.job_id。"""
        from app.tools.db_job import insert_job_analysis

        with (
            patch("app.tools.db_job._ensure_job_analysis_columns"),
            patch("app.tools.db_job.execute_lastrowid", return_value=5),
            patch("app.tools.db_job._attach_job_entity", return_value=9) as mock_attach,
        ):
            assert (
                insert_job_analysis(
                    {"user_id": 1, "company": "Co", "position": "Eng", "jd_text": "JD"}
                )
                == 5
            )
        mock_attach.assert_called_once()

    def test_attach_job_entity_degrades_on_error(self):
        """P4-4a：岗位归属异常不阻断分析落库（返回 None）。"""
        from app.tools.db_job import _attach_job_entity

        with patch(
            "app.tools.db_job_entity.find_or_create_job", side_effect=Exception("无表")
        ):
            assert _attach_job_entity({"user_id": 1, "position": "Eng"}, 5) is None


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

        with patch("app.tools.db_conn.connect", return_value=mock_conn):
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
            "delivered": 0,
            "created_at": SimpleNamespace(isoformat=lambda: "2024-01-01"),
            "updated_at": SimpleNamespace(isoformat=lambda: "2024-01-02"),
        }
        mock_cursor.fetchall.return_value = []
        mock_conn = _make_mock_conn(mock_cursor)

        with patch("app.tools.db_conn.connect", return_value=mock_conn):
            result = get_submission(1)
            assert result is not None
            assert result["position"] == "Backend Eng"
            assert result["card_version_ids"] == [1, 2]
            assert result["is_manual"] is False
            assert result["delivered"] is False

    def test_get_submission_returns_delivered_true(self):
        from app.tools.db_submission import get_submission

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": 2,
            "user_id": 1,
            "job_analysis_id": None,
            "position": "PM",
            "company": "X",
            "jd_text": "",
            "resume_markdown": "",
            "resume_file_path": None,
            "card_version_ids": "[]",
            "status": "APPLIED",
            "notes": "",
            "is_manual": 0,
            "delivered": 1,
            "created_at": SimpleNamespace(isoformat=lambda: "2024-01-01"),
            "updated_at": SimpleNamespace(isoformat=lambda: "2024-01-02"),
        }
        mock_cursor.fetchall.return_value = []
        mock_conn = _make_mock_conn(mock_cursor)

        with patch("app.tools.db_conn.connect", return_value=mock_conn):
            result = get_submission(2)
            assert result is not None
            assert result["delivered"] is True

    def test_update_submission_empty_returns_false(self):
        from app.tools.db_submission import update_submission

        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)

        with patch("app.tools.db_conn.connect", return_value=mock_conn):
            result = update_submission(1, {})
            assert result is False

    def test_update_submission_ignores_jd_text(self):
        """P4-2：db 层兜底——误传 jd_text 也不生成 UPDATE（快照不可覆写）。"""
        from app.tools.db_submission import update_submission

        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)

        with patch("app.tools.db_conn.connect", return_value=mock_conn):
            assert update_submission(1, {"jd_text": "改写后的 JD"}) is False
        executed = [c[0][0].strip().upper() for c in mock_cursor.execute.call_args_list]
        assert executed, "应至少执行一次 schema 检查"
        assert not any(s.startswith("UPDATE RESUME_SUBMISSION") for s in executed)

    def test_update_submission_syncs_job_status(self):
        """P4-4a：状态更新成功后同步 Job 实体状态（CLOSED → PREPARED）。"""
        from app.tools.db_submission import update_submission

        with (
            patch("app.tools.db_submission._ensure_resume_submission_table"),
            patch("app.tools.db_submission.execute", return_value=1),
            patch(
                "app.tools.db_submission._sync_job_entity", return_value=12
            ) as mock_sync,
        ):
            assert update_submission(1, {"status": "PREPARED"}) is True
        mock_sync.assert_called_once_with(1, {"status": "PREPARED"})

    def test_sync_job_entity_derives_status_from_delivered_only(self):
        """P4-4a：仅翻转 delivered 时按存量状态推导岗位状态（P11-a 语义）。"""
        from app.tools.db_submission import _sync_job_entity

        with (
            patch(
                "app.tools.db_submission.query_one",
                return_value={"status": "APPLIED"},
            ),
            patch(
                "app.tools.db_job_entity.sync_submission_job", return_value=12
            ) as mock_sync,
        ):
            assert _sync_job_entity(1, {"delivered": 1}) == 12
        mock_sync.assert_called_once_with(1, status="APPLIED", job_analysis_id=None)

    def test_sync_job_entity_ignores_unrelated_updates(self):
        """P4-4a：notes 等无关字段不触发岗位同步。"""
        from app.tools.db_submission import _sync_job_entity

        with patch("app.tools.db_job_entity.sync_submission_job") as mock_sync:
            assert _sync_job_entity(1, {"notes": "备注"}) is None
        mock_sync.assert_not_called()

    def test_sync_job_entity_degrades_on_error(self):
        """P4-4a：岗位同步异常不阻断投递记录更新。"""
        from app.tools.db_submission import _sync_job_entity

        with patch(
            "app.tools.db_job_entity.sync_submission_job", side_effect=Exception("无表")
        ):
            assert _sync_job_entity(1, {"status": "APPLIED"}) is None

    def test_get_submission_projects_legacy_applied_to_prepared(self):
        """P11-a：存量 `APPLIED + delivered=0` 读取时投影为「待投递」。"""
        from app.tools.db_submission import get_submission

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "user_id": 1,
            "job_analysis_id": None,
            "position": "PM",
            "company": "X",
            "jd_text": "",
            "resume_markdown": "",
            "resume_file_path": None,
            "card_version_ids": "[]",
            "status": "APPLIED",
            "notes": "",
            "is_manual": 0,
            "delivered": 0,
            "created_at": SimpleNamespace(isoformat=lambda: "2024-01-01"),
            "updated_at": SimpleNamespace(isoformat=lambda: "2024-01-02"),
        }
        mock_cursor.fetchall.return_value = []
        mock_conn = _make_mock_conn(mock_cursor)

        with patch("app.tools.db_conn.connect", return_value=mock_conn):
            result = get_submission(1)
        assert result is not None
        assert result["status"] == "PREPARED"
        assert result["delivered"] is False

    def test_insert_submission_defaults_to_prepared(self):
        """P11-a：创建投递记录默认「待投递」（创建 ≠ 投递）。"""
        from app.tools.db_submission import insert_submission

        with (
            patch("app.tools.db_conn.connect"),
            patch(
                "app.tools.db_submission.execute_lastrowid", return_value=1
            ) as mock_insert,
            patch(
                "app.tools.db_submission._attach_job_entity", return_value=3
            ) as mock_attach,
        ):
            insert_submission({"position": "PM"})
        params = mock_insert.call_args[0][1]
        assert params[8] == "PREPARED"
        # P4-4a：创建后 find-or-create 岗位并挂上投递记录
        mock_attach.assert_called_once()

    def test_get_submission_returns_job_id(self):
        """P4-4a：单条读取暴露岗位实体 id（LEFT JOIN job）。"""
        from app.tools.db_submission import get_submission

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "user_id": 1,
            "job_analysis_id": 7,
            "position": "PM",
            "company": "X",
            "jd_text": "",
            "resume_markdown": "",
            "resume_file_path": None,
            "card_version_ids": "[]",
            "status": "PREPARED",
            "job_id": 12,
            "notes": "",
            "is_manual": 0,
            "delivered": 0,
            "created_at": SimpleNamespace(isoformat=lambda: "2024-01-01"),
            "updated_at": SimpleNamespace(isoformat=lambda: "2024-01-02"),
        }
        mock_cursor.fetchall.return_value = []
        mock_conn = _make_mock_conn(mock_cursor)

        with patch("app.tools.db_conn.connect", return_value=mock_conn):
            result = get_submission(1)
        assert result is not None
        assert result["job_id"] == 12
        executed = [c[0][0] for c in mock_cursor.execute.call_args_list]
        assert any("LEFT JOIN job" in sql for sql in executed)

    def test_get_submission_falls_back_when_job_table_missing(self):
        """P4-4a：旧库无 job 表时 JOIN 失败回落原查询，不阻断读取。"""
        from app.tools.db_submission import get_submission

        row = {
            "id": 1,
            "user_id": 1,
            "job_analysis_id": None,
            "position": "PM",
            "company": "X",
            "jd_text": "",
            "resume_markdown": "",
            "resume_file_path": None,
            "card_version_ids": "[]",
            "status": "PREPARED",
            "notes": "",
            "is_manual": 0,
            "delivered": 0,
            "created_at": SimpleNamespace(isoformat=lambda: "2024-01-01"),
            "updated_at": SimpleNamespace(isoformat=lambda: "2024-01-02"),
        }
        calls: list = []

        def fake_query_one(sql, params):
            calls.append(sql)
            if "LEFT JOIN job" in sql:
                raise Exception("Table 'job' doesn't exist")
            return row

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = _make_mock_conn(mock_cursor)
        with (
            patch("app.tools.db_conn.connect", return_value=mock_conn),
            patch("app.tools.db_submission.query_one", side_effect=fake_query_one),
        ):
            result = get_submission(1)
        assert result is not None
        assert result["job_id"] is None
        assert len(calls) == 2


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

        with patch("app.tools.db_conn.connect", return_value=mock_conn):
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

        with patch("app.tools.db_conn.connect", return_value=mock_conn):
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

        with patch("app.tools.db_conn.connect", return_value=mock_conn):
            result = get_interview_record(999)
            assert result is None

    def test_list_interview_records_empty(self):
        from app.tools.db_interview import list_interview_records

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None
        mock_conn = _make_mock_conn(mock_cursor)

        with patch("app.tools.db_conn.connect", return_value=mock_conn):
            result = list_interview_records()
            assert result == []


class TestExperiencePolish:
    def test_polish_goes_through_invoke_structured(self, monkeypatch, tmp_path):
        """polish_experience 必须走 llm_json 统一出口（审计/缓存/观测）。"""
        import app.tools.experience_polish as ep

        captured = {}

        def fake_invoke(model, schema, prompt, **kwargs):
            captured.update(
                schema=schema.__name__,
                debug_label=kwargs.get("debug_label"),
                has_prompt="润色" in prompt,
            )
            assert "某公司" in prompt and "工程师" in prompt and "原始经历" in prompt
            return schema(polished_text="润色之后的量化描述。")

        monkeypatch.setattr(ep, "invoke_structured", fake_invoke)

        out = ep.polish_experience("原始经历", company="某公司", role="工程师")
        assert out == "润色之后的量化描述。"
        assert captured["schema"] == "PolishOutput"
        assert captured["debug_label"] == "experience_polish"
        assert captured["has_prompt"]

    def test_polish_uses_json_structured_prompt_v2(self, monkeypatch):
        """polish 必须使用 v2 JSON 指示（v1 的纯文本输出指示与 invoke_structured 期望不符）。"""
        import app.tools.experience_polish as ep

        captured = {}

        def fake_invoke(model, schema, prompt, **kwargs):
            captured["prompt"] = prompt
            return schema(polished_text=".")

        monkeypatch.setattr(ep, "invoke_structured", fake_invoke)

        ep.polish_experience("原始经历", company="某公司", role="工程师")

        assert "polished_text" in captured["prompt"]
        assert "JSON" in captured["prompt"]
        # v1 的"直接输出润色后的经历文本"纯文本指示不应再出现
        assert "直接输出润色后的经历文本" not in captured["prompt"]

    def test_polish_raises_on_empty_output(self, monkeypatch, tmp_path):
        import app.tools.experience_polish as ep

        def fake_invoke_blank(model, schema, prompt, **kwargs):
            return schema(polished_text="   ")

        monkeypatch.setattr(ep, "invoke_structured", fake_invoke_blank)

        with pytest.raises(RuntimeError, match="润色返回内容为空"):
            ep.polish_experience("原始经历")

    def test_polish_raises_on_llm_failure(self, monkeypatch, tmp_path):
        import app.tools.experience_polish as ep

        def fake_invoke_fail(model, schema, prompt, **kwargs):
            raise RuntimeError("LLM 不可用")

        monkeypatch.setattr(ep, "invoke_structured", fake_invoke_fail)

        with pytest.raises(RuntimeError, match="LLM 不可用"):
            ep.polish_experience("原始经历")


class TestExpressionGenerate:
    def test_generate_goes_through_invoke_structured(self, monkeypatch):
        """generate_standardized_expression 必须走 llm_json 统一出口（审计/缓存/观测）。"""
        import app.tools.expression_generate as eg

        captured = {}

        def fake_invoke(model, schema, prompt, **kwargs):
            captured.update(
                schema=schema.__name__,
                debug_label=kwargs.get("debug_label"),
                has_prompt="标准化表达" in prompt,
            )
            assert "某公司" in prompt and "工程师" in prompt and "原始经历" in prompt
            return schema(content="负责构建推荐系统，提升了 CTR。")

        monkeypatch.setattr(eg, "invoke_structured", fake_invoke)

        out = eg.generate_standardized_expression(
            "负责构建推荐系统，提升了 CTR 30%。",
            company="某公司",
            role="工程师",
        )
        assert out == "负责构建推荐系统，提升了 CTR。"
        assert captured["schema"] == "StandardizedExpressionOutput"
        assert captured["debug_label"] == "expression_standardized"
        assert captured["has_prompt"]

    def test_generate_uses_standardized_prompt_v1(self, monkeypatch):
        """生成必须使用 expression_standardized v1（中性化 + 输出 content）。"""
        import app.tools.expression_generate as eg

        captured = {}

        def fake_invoke(model, schema, prompt, **kwargs):
            captured["prompt"] = prompt
            return schema(content=".")

        monkeypatch.setattr(eg, "invoke_structured", fake_invoke)
        eg.generate_standardized_expression("这是一段足够长的原始经历内容")
        assert "content" in captured["prompt"]
        assert "标准化表达" in captured["prompt"]

    def test_generate_raises_on_empty_input(self, monkeypatch):
        import app.tools.expression_generate as eg

        with pytest.raises(ValueError, match="不能为空"):
            eg.generate_standardized_expression("   ")

        with pytest.raises(ValueError, match="过短"):
            eg.generate_standardized_expression("短")

    def test_generate_raises_on_empty_output(self, monkeypatch):
        import app.tools.expression_generate as eg

        def fake_invoke_blank(model, schema, prompt, **kwargs):
            return schema(content="   ")

        monkeypatch.setattr(eg, "invoke_structured", fake_invoke_blank)

        with pytest.raises(RuntimeError, match="返回内容为空"):
            eg.generate_standardized_expression("这是一段足够长的原始经历内容")

    def test_generate_raises_on_llm_failure(self, monkeypatch):
        import app.tools.expression_generate as eg

        def fake_invoke_fail(model, schema, prompt, **kwargs):
            raise RuntimeError("LLM 不可用")

        monkeypatch.setattr(eg, "invoke_structured", fake_invoke_fail)

        with pytest.raises(RuntimeError, match="LLM 不可用"):
            eg.generate_standardized_expression("这是一段足够长的原始经历内容")


# ============================================================
# 10. db_raw_jd.py — RawJD 不可变快照（P4-2）
# ============================================================


class TestDbRawJd:
    def test_insert_skips_empty_jd_text(self):
        """P4-2：空 JD 原文不产生空快照。"""
        from app.tools import db_raw_jd

        with (
            patch("app.tools.db_raw_jd._ensure_raw_jd_table"),
            patch("app.tools.db_raw_jd.execute_lastrowid") as mock_insert,
        ):
            assert db_raw_jd.insert_raw_jd("   ") == 0
        mock_insert.assert_not_called()

    def test_insert_writes_snapshot_fields(self):
        """P4-2：快照落 user/job_analysis/source/原文四要素。"""
        from app.tools import db_raw_jd

        with (
            patch("app.tools.db_raw_jd._ensure_raw_jd_table"),
            patch(
                "app.tools.db_raw_jd.execute_lastrowid", return_value=9
            ) as mock_insert,
        ):
            rid = db_raw_jd.insert_raw_jd(
                "  岗位 JD 原文  ", user_id=3, job_analysis_id=7, source="split_jd"
            )
        assert rid == 9
        sql, params = mock_insert.call_args[0]
        assert "INSERT INTO raw_jd" in sql
        assert params == (3, 7, "split_jd", "岗位 JD 原文")

    def test_insert_falls_back_on_unknown_source(self):
        """P4-2：非法 source 回落 job_analysis，避免脏值入列。"""
        from app.tools import db_raw_jd

        with (
            patch("app.tools.db_raw_jd._ensure_raw_jd_table"),
            patch(
                "app.tools.db_raw_jd.execute_lastrowid", return_value=1
            ) as mock_insert,
        ):
            db_raw_jd.insert_raw_jd("JD", source="unknown-source")
        assert mock_insert.call_args[0][1][2] == "job_analysis"

    def test_module_exposes_no_mutation_api(self):
        """P4-2：快照只增不改，模块不提供 update/delete 写路径。"""
        from app.tools import db_raw_jd

        assert not hasattr(db_raw_jd, "update_raw_jd")
        assert not hasattr(db_raw_jd, "delete_raw_jd")

    def test_get_returns_none_when_not_found(self):
        from app.tools import db_raw_jd

        with (
            patch("app.tools.db_raw_jd._ensure_raw_jd_table"),
            patch("app.tools.db_raw_jd.query_one", return_value=None),
        ):
            assert db_raw_jd.get_raw_jd(999, user_id=1) is None

    def test_get_maps_row_fields(self):
        from app.tools import db_raw_jd

        row = {
            "id": 4,
            "user_id": 1,
            "job_analysis_id": 7,
            "source": "job_analysis",
            "jd_text": "JD 原文",
            "created_at": SimpleNamespace(isoformat=lambda: "2024-01-01T00:00:00"),
        }
        with (
            patch("app.tools.db_raw_jd._ensure_raw_jd_table"),
            patch("app.tools.db_raw_jd.query_one", return_value=row) as mock_query,
        ):
            result = db_raw_jd.get_raw_jd(4, user_id=1)
        assert result is not None
        assert result["jd_text"] == "JD 原文"
        assert result["source"] == "job_analysis"
        assert result["job_analysis_id"] == 7
        assert "AND user_id=%s" in mock_query.call_args[0][0]

    def test_list_filters_by_job_analysis(self):
        from app.tools import db_raw_jd

        with (
            patch("app.tools.db_raw_jd._ensure_raw_jd_table"),
            patch("app.tools.db_raw_jd.query_all", return_value=[]) as mock_query,
        ):
            assert db_raw_jd.list_raw_jds(1, job_analysis_id=7) == []
        sql, params = mock_query.call_args[0]
        assert "AND job_analysis_id=%s" in sql
        assert params == (1, 7)


# ============================================================
# 11. db_job_entity.py — Job 实体（岗位聚合根，P4-4a）
# ============================================================


class TestDbJobEntity:
    def test_find_or_create_skips_empty_position(self):
        """P4-4a：岗位名为空不落库（无法定位岗位）。"""
        from app.tools import db_job_entity

        with (
            patch("app.tools.db_job_entity._ensure_job_table"),
            patch("app.tools.db_job_entity.execute_lastrowid") as mock_insert,
        ):
            assert db_job_entity.find_or_create_job(1, "  ", "字节") is None
        mock_insert.assert_not_called()

    def test_find_or_create_reuses_existing_job(self):
        """P4-4a：同 (user, company, position) 复用岗位并回填关联。"""
        from app.tools import db_job_entity

        with (
            patch("app.tools.db_job_entity._ensure_job_table"),
            patch(
                "app.tools.db_job_entity.query_one", return_value={"id": 12}
            ) as mock_query,
            patch("app.tools.db_job_entity.link_job") as mock_link,
        ):
            job_id = db_job_entity.find_or_create_job(
                1, " 后端 ", " 字节 ", job_analysis_id=7, submission_id=3
            )
        assert job_id == 12
        assert mock_query.call_args[0][1] == (1, "字节", "后端")
        mock_link.assert_called_once_with(
            12, job_analysis_id=7, submission_id=3, raw_jd_id=None
        )

    def test_find_or_create_creates_with_associations(self):
        """P4-4a：岗位不存在则创建并带上分析/投递/快照关联。"""
        from app.tools import db_job_entity

        with (
            patch("app.tools.db_job_entity._ensure_job_table"),
            patch("app.tools.db_job_entity.query_one", return_value=None),
            patch(
                "app.tools.db_job_entity.execute_lastrowid", return_value=21
            ) as mock_insert,
        ):
            job_id = db_job_entity.find_or_create_job(
                1, "后端", "字节", job_analysis_id=7, submission_id=3, raw_jd_id=2
            )
        assert job_id == 21
        sql, params = mock_insert.call_args[0]
        assert "INSERT INTO job" in sql
        assert params == (1, "字节", "后端", 7, 3, 2)

    def test_find_or_create_skips_backfill_when_no_associations(self):
        """P4-4a：复用既有岗位且无关联信息时不发 UPDATE。"""
        from app.tools import db_job_entity

        with (
            patch("app.tools.db_job_entity._ensure_job_table"),
            patch("app.tools.db_job_entity.query_one", return_value={"id": 5}),
            patch("app.tools.db_job_entity.link_job") as mock_link,
        ):
            assert db_job_entity.find_or_create_job(1, "后端", "字节") == 5
        mock_link.assert_not_called()

    def test_link_job_only_sets_provided_fields(self):
        from app.tools import db_job_entity

        with (
            patch("app.tools.db_job_entity._ensure_job_table"),
            patch("app.tools.db_job_entity.execute", return_value=1) as mock_exec,
        ):
            assert db_job_entity.link_job(5, submission_id=9) is True
        sql, params = mock_exec.call_args[0]
        assert "submission_id=%s" in sql
        assert "job_analysis_id" not in sql
        assert params == (9, 5)

    def test_link_job_without_fields_returns_false(self):
        from app.tools import db_job_entity

        with patch("app.tools.db_job_entity._ensure_job_table"):
            assert db_job_entity.link_job(5) is False

    def test_link_raw_jd_by_analysis(self):
        """P4-4a：按分析记录回链 RawJD 快照（不需先查岗位 id）。"""
        from app.tools import db_job_entity

        with (
            patch("app.tools.db_job_entity._ensure_job_table"),
            patch("app.tools.db_job_entity.execute", return_value=1) as mock_exec,
        ):
            assert db_job_entity.link_raw_jd_by_analysis(7, 2) is True
        sql, params = mock_exec.call_args[0]
        assert "raw_jd_id=%s" in sql
        assert "job_analysis_id=%s" in sql
        assert params == (2, 7)

    def test_sync_submission_job_updates_status(self):
        """P4-4a：投递状态变更后同步 Job 状态与分析归属。"""
        from app.tools import db_job_entity

        with (
            patch("app.tools.db_job_entity._ensure_job_table"),
            patch(
                "app.tools.db_job_entity.query_one", return_value={"id": 12}
            ) as mock_query,
            patch("app.tools.db_job_entity.link_job") as mock_link,
            patch("app.tools.db_job_entity.execute", return_value=1) as mock_exec,
        ):
            assert (
                db_job_entity.sync_submission_job(
                    3, status="APPLIED", job_analysis_id=7
                )
                == 12
            )
        assert mock_query.call_args[0][1] == (3,)
        mock_link.assert_called_once_with(12, job_analysis_id=7)
        sql, params = mock_exec.call_args[0]
        assert "status=%s" in sql
        assert params == ("APPLIED", 12)

    def test_sync_submission_job_noop_without_fields(self):
        from app.tools import db_job_entity

        with patch("app.tools.db_job_entity._ensure_job_table"):
            assert db_job_entity.sync_submission_job(3) is None

    def test_sync_submission_job_missing_job_returns_none(self):
        """P4-4a：投递记录尚未建岗时不报错（返回 None）。"""
        from app.tools import db_job_entity

        with (
            patch("app.tools.db_job_entity._ensure_job_table"),
            patch("app.tools.db_job_entity.query_one", return_value=None),
        ):
            assert db_job_entity.sync_submission_job(3, status="APPLIED") is None

    def test_set_job_analysis_job_id_degrades_on_error(self):
        """P4-4a：旧库无 job_id 列时不抛错（降级 False）。"""
        from app.tools import db_job_entity

        with patch(
            "app.tools.db_job_entity.execute", side_effect=Exception("列不存在")
        ):
            assert db_job_entity.set_job_analysis_job_id(7, 5) is False

    def test_get_job_by_submission(self):
        from app.tools import db_job_entity

        row = {
            "id": 12,
            "user_id": 1,
            "company": "字节",
            "position": "后端",
            "raw_jd_id": 2,
            "job_analysis_id": 7,
            "submission_id": 3,
            "status": "PREPARED",
            "is_active": 1,
            "created_at": SimpleNamespace(isoformat=lambda: "2024-01-01"),
            "updated_at": SimpleNamespace(isoformat=lambda: "2024-01-02"),
        }
        with (
            patch("app.tools.db_job_entity._ensure_job_table"),
            patch("app.tools.db_job_entity.query_one", return_value=row),
        ):
            result = db_job_entity.get_job_by_submission(3, user_id=1)
        assert result is not None
        assert result["id"] == 12
        assert result["submission_id"] == 3
        assert result["is_active"] is True

    def test_list_jobs_filters_owner_and_active(self):
        from app.tools import db_job_entity

        with (
            patch("app.tools.db_job_entity._ensure_job_table"),
            patch("app.tools.db_job_entity.query_all", return_value=[]) as mock_query,
        ):
            assert db_job_entity.list_jobs(1) == []
        sql, params = mock_query.call_args[0]
        assert "user_id=%s AND is_active=1" in sql
        assert params == (1,)


class TestUpdateInterviewQaPairFields:
    """BE-QT-01：QA 对字段级更新（问题表 upsert）的白名单与 SQL 组装"""

    @staticmethod
    def _patch(monkeypatch, execute_result=1):
        """替换 ensure 与 execute，返回 SQL 调用记录列表"""
        from app.tools import db_interview

        calls = []
        monkeypatch.setattr(
            db_interview, "_ensure_interview_qa_pairs_table", lambda: None
        )
        monkeypatch.setattr(
            db_interview,
            "execute",
            lambda sql, params: (calls.append((sql, params)), execute_result)[1],
        )
        return calls

    def test_whitelist_fields_builds_parameterized_update(self, monkeypatch):
        from app.tools import db_interview

        calls = self._patch(monkeypatch, execute_result=1)
        assert (
            db_interview.update_interview_qa_pair_fields(
                9, {"intent": "考察项目", "dimension": "D1 技术深度", "level": "L4"}
            )
            is True
        )
        sql, params = calls[0]
        assert sql == (
            "UPDATE interview_qa_pairs "
            "SET intent=%s, dimension=%s, level=%s WHERE id=%s"
        )
        assert params == ("考察项目", "D1 技术深度", "L4", 9)

    def test_rejects_analysis_fields(self, monkeypatch):
        from app.tools import db_interview

        calls = self._patch(monkeypatch)
        with pytest.raises(ValueError, match="不允许更新"):
            db_interview.update_interview_qa_pair_fields(
                9, {"score": 100, "intent": "x"}
            )
        assert calls == [], "白名单外字段不得触达 SQL"

    def test_empty_fields_is_noop(self, monkeypatch):
        from app.tools import db_interview

        calls = self._patch(monkeypatch)
        assert db_interview.update_interview_qa_pair_fields(9, {}) is False
        assert calls == []

    def test_missing_row_returns_false(self, monkeypatch):
        from app.tools import db_interview

        self._patch(monkeypatch, execute_result=0)
        assert (
            db_interview.update_interview_qa_pair_fields(404, {"intent": ""}) is False
        )
