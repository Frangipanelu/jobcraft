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

import inspect
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
                "app.tools.db_job_entity.get_job_id_by_analysis",
                lambda *a, **k: 15,
            ),
            patch(
                "app.tools.db_resume_version.create_resume_version",
                lambda **k: {"id": 77},
            ),
            patch(
                "app.tools.db_expression.get_active_expression_content",
                lambda cid, user_id, expr_type="standardized": "激活表达",
            ),
            patch(
                "app.tools.db_expression.increment_active_expression_usage",
                lambda cid, user_id, expr_type="standardized": incremented.append(cid),
            ),
            # T-M6-8：单测不触真实 DB（jd_alignment 快照写入方）
            patch("app.tools.db_experience.insert_card_version", lambda *a, **k: 1),
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
        # T-M6-2：产物写 resume_version，不再 insert submission
        assert result["submission_id"] is None
        assert result["resume_version_id"] == 77

    def test_generate_resume_writes_version_not_submission(self, tmp_path):
        """T-M6-2：save-resume 产物写 resume_version，绝不 insert/update submission。"""
        from app.tools.jobcraft_resume import generate_resume

        created = {}

        def fake_create(**kwargs):
            created.update(kwargs)
            return {"id": 42}

        def forbid_submission(*args, **kwargs):
            raise AssertionError("T-M6-2 后 save-resume 不得写 submission")

        with (
            patch("app.tools.jobcraft_resume.db_tools") as mock_db,
            patch(
                "app.tools.jobcraft_resume.generate_resume_markdown",
                lambda **k: "MD",
            ),
            patch("app.tools.jobcraft_resume.generate_resume_html", lambda **k: "HTML"),
            patch("app.tools.jobcraft_resume.OUTPUT_ROOT", tmp_path),
            patch(
                "app.tools.db_submission.get_submission_by_analysis",
                lambda *a, **k: None,
            ),
            patch("app.tools.db_submission.insert_submission", forbid_submission),
            patch("app.tools.db_submission.update_submission", forbid_submission),
            patch(
                "app.tools.db_job_entity.get_job_id_by_analysis",
                lambda *a, **k: 15,
            ),
            patch("app.tools.db_resume_version.create_resume_version", fake_create),
            # T-M6-8：单测不触真实 DB（jd_alignment 快照写入方）
            patch("app.tools.db_experience.insert_card_version", lambda *a, **k: 1),
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
                "raw_text": "x",
            }
            result = generate_resume(1, [3], user_id=7)

        assert created["job_id"] == 15
        assert created["job_analysis_id"] == 1
        assert created["resume_markdown"] == "MD"
        assert created["user_id"] == 7
        assert result["resume_version_id"] == 42
        assert result["submission_id"] is None

    def test_generate_resume_backfills_job_when_missing(self, tmp_path):
        """T-M6-2：存量岗位无 job 行时按分析懒回填（find_or_create 回链
        analysis+submission，防 FE 地图双行）。"""
        from app.tools.jobcraft_resume import generate_resume

        find_calls = {}
        created = {}

        def fake_find(user_id, position, company=None, **kwargs):
            find_calls.update(kwargs)
            find_calls["user_id"] = user_id
            find_calls["position"] = position
            find_calls["company"] = company
            return 31

        def fake_create(**kwargs):
            created.update(kwargs)
            return {"id": 9}

        with (
            patch("app.tools.jobcraft_resume.db_tools") as mock_db,
            patch(
                "app.tools.jobcraft_resume.generate_resume_markdown",
                lambda **k: "MD",
            ),
            patch("app.tools.jobcraft_resume.generate_resume_html", lambda **k: "HTML"),
            patch("app.tools.jobcraft_resume.OUTPUT_ROOT", tmp_path),
            patch(
                "app.tools.db_submission.get_submission_by_analysis",
                lambda *a, **k: {"id": 8},
            ),
            patch(
                "app.tools.db_job_entity.get_job_id_by_analysis",
                lambda *a, **k: None,
            ),
            patch("app.tools.db_job_entity.find_or_create_job", fake_find),
            patch("app.tools.db_resume_version.create_resume_version", fake_create),
            # T-M6-8：单测不触真实 DB（jd_alignment 快照写入方）
            patch("app.tools.db_experience.insert_card_version", lambda *a, **k: 1),
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
                "raw_text": "x",
            }
            result = generate_resume(1, [3], user_id=7)

        assert find_calls["job_analysis_id"] == 1
        assert find_calls["submission_id"] == 8
        assert find_calls["position"] == "P"
        assert find_calls["company"] == "C"
        assert created["job_id"] == 31
        assert result["resume_version_id"] == 9

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
            # T-M6-8 评审修复：版本落库链 + 快照写入全 patch，单测不触真实 DB
            patch(
                "app.tools.db_job_entity.get_job_id_by_analysis",
                lambda *a, **k: 15,
            ),
            patch(
                "app.tools.db_resume_version.create_resume_version",
                lambda **k: {"id": 42},
            ),
            patch("app.tools.db_experience.insert_card_version", lambda *a, **k: 1),
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
            # T-M6-8 评审修复：版本落库链 + 快照写入全 patch，单测不触真实 DB
            patch(
                "app.tools.db_job_entity.get_job_id_by_analysis",
                lambda *a, **k: 15,
            ),
            patch(
                "app.tools.db_resume_version.create_resume_version",
                lambda **k: {"id": 42},
            ),
            patch("app.tools.db_experience.insert_card_version", lambda *a, **k: 1),
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
            # T-M6-8 评审修复：版本落库链 + 快照写入全 patch，单测不触真实 DB
            patch(
                "app.tools.db_job_entity.get_job_id_by_analysis",
                lambda *a, **k: 15,
            ),
            patch(
                "app.tools.db_resume_version.create_resume_version",
                lambda **k: {"id": 42},
            ),
            patch("app.tools.db_experience.insert_card_version", lambda *a, **k: 1),
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

    # --------------------------------------------------------
    # T-M6-8：save-resume 写 jd_alignment 卡版本快照（写入方）
    # --------------------------------------------------------

    @staticmethod
    def _run_generate(tmp_path, cards, create_version, **kwargs):
        """搭 generate_resume 的全量 patch 环境并执行（单测不触真实 DB）。

        :param cards: {card_id: 卡 dict}，get_card 按 id 返回副本
        :param create_version: create_resume_version 替身（可抛异常走失败路径）
        :param kwargs: card_versions / insert_side_effect / job_id
        :return: (generate_resume 结果, insert_card_version mock)
        """
        from contextlib import ExitStack

        from app.tools.jobcraft_resume import generate_resume

        card_versions = kwargs.get("card_versions")
        job_id = kwargs.get("job_id", 15)
        insert_mock = MagicMock(return_value=1)
        if kwargs.get("insert_side_effect") is not None:
            insert_mock.side_effect = kwargs["insert_side_effect"]

        def fake_card(cid, user_id=None):
            return dict(cards[cid])

        with ExitStack() as stack:
            mock_db = stack.enter_context(patch("app.tools.jobcraft_resume.db_tools"))
            stack.enter_context(
                patch(
                    "app.tools.jobcraft_resume.generate_resume_markdown",
                    lambda **k: "MD",
                )
            )
            stack.enter_context(
                patch(
                    "app.tools.jobcraft_resume.generate_resume_html",
                    lambda **k: "HTML",
                )
            )
            stack.enter_context(
                patch("app.tools.jobcraft_resume.OUTPUT_ROOT", tmp_path)
            )
            stack.enter_context(
                patch(
                    "app.tools.db_submission.get_submission_by_analysis",
                    lambda *a, **k: None,
                )
            )
            stack.enter_context(
                patch(
                    "app.tools.db_job_entity.get_job_id_by_analysis",
                    lambda *a, **k: job_id,
                )
            )
            stack.enter_context(
                patch(
                    "app.tools.db_resume_version.create_resume_version", create_version
                )
            )
            stack.enter_context(
                patch(
                    "app.tools.db_expression.get_active_expression_content",
                    lambda cid, user_id, expr_type="standardized": None,
                )
            )
            stack.enter_context(
                patch("app.tools.db_experience.insert_card_version", insert_mock)
            )

            mock_db.get_job_analysis.return_value = {
                "user_id": 7,
                "company": "C",
                "position": "P",
                "jd_text": "JD",
            }
            mock_db.get_card.side_effect = fake_card
            result = generate_resume(
                1, list(cards), card_versions=card_versions, user_id=7
            )
        return result, insert_mock

    @staticmethod
    def _snapshot_card(cid, raw_text):
        """构造一张最小可用的入选经历卡。"""
        return {
            "id": cid,
            "is_active": True,
            "title": f"卡{cid}",
            "tags": [f"t{cid}"],
            "raw_text": raw_text,
        }

    def test_generate_resume_writes_jd_alignment_snapshots(self, tmp_path):
        """T-M6-8：每张入选卡写一条 jd_alignment 快照，字段与 FE 消费端对齐。"""
        cards = {
            1: self._snapshot_card(1, "原始一"),
            2: self._snapshot_card(2, "原始二"),
        }

        result, insert_mock = self._run_generate(
            tmp_path,
            cards,
            lambda **k: {"id": 42},
            card_versions={1: "编辑终稿"},
        )

        assert result["resume_version_id"] == 42
        assert insert_mock.call_count == 2

        first = insert_mock.call_args_list[0][0][0]
        assert first["card_id"] == 1
        assert first["version_type"] == "jd_alignment"
        assert first["source_type"] == "resume_version"
        assert first["source_id"] == 42
        assert first["title"] == "卡1"
        assert first["tags"] == ["t1"]
        # 命中编辑终稿：card_versions 优先于渲染链
        assert first["raw_text"] == "编辑终稿"

        second = insert_mock.call_args_list[1][0][0]
        assert second["card_id"] == 2
        assert second["source_id"] == 42
        assert second["version_type"] == "jd_alignment"
        # 未编辑：走 card_render 渲染链回退到 raw_text
        assert second["raw_text"] == "原始二"

    def test_jd_alignment_note_reuses_version_name_or_fallback(self, tmp_path):
        """T-M6-8：note 复用简历版本名；无版本名按 matrix 兜底 方向-公司-年/月/日。"""
        import re

        cards = {3: self._snapshot_card(3, "x")}

        _, insert_fallback = self._run_generate(tmp_path, cards, lambda **k: {"id": 1})
        note = insert_fallback.call_args[0][0]["note"]
        assert re.fullmatch(r"P-C-\d{4}/\d{1,2}/\d{1,2}", note), note

        _, insert_named = self._run_generate(
            tmp_path, cards, lambda **k: {"id": 2, "version_name": "我的命名"}
        )
        assert insert_named.call_args[0][0]["note"] == "我的命名"

    def test_jd_alignment_snapshot_failure_is_tolerated(self, tmp_path):
        """T-M6-8：快照写失败只记日志，版本 id 仍返回、generate_resume 不抛。"""
        cards = {3: self._snapshot_card(3, "x")}

        result, insert_mock = self._run_generate(
            tmp_path,
            cards,
            lambda **k: {"id": 42},
            insert_side_effect=Exception("DB 写入失败"),
        )

        assert insert_mock.call_count == 1
        assert result["resume_version_id"] == 42

    def test_jd_alignment_skipped_when_version_create_fails(self, tmp_path):
        """T-M6-8：resume_version 落库失败 → resume_version_id=None → 不写快照。"""
        cards = {3: self._snapshot_card(3, "x")}

        def fail_create(**kwargs):
            raise RuntimeError("版本落库失败")

        result, insert_mock = self._run_generate(tmp_path, cards, fail_create)

        assert result["resume_version_id"] is None
        insert_mock.assert_not_called()

    def test_jd_alignment_per_card_failure_does_not_skip_next(self, tmp_path):
        """T-M6-8 评审修复：第 1 卡写失败只记日志，第 2 卡仍照常写入。"""
        cards = {
            1: self._snapshot_card(1, "原始一"),
            2: self._snapshot_card(2, "原始二"),
        }

        def flaky_insert(data):
            if data["card_id"] == 1:
                raise Exception("第 1 卡写失败")
            return 1

        result, insert_mock = self._run_generate(
            tmp_path,
            cards,
            lambda **k: {"id": 42},
            insert_side_effect=flaky_insert,
        )

        assert result["resume_version_id"] == 42
        assert insert_mock.call_count == 2
        assert insert_mock.call_args_list[1][0][0]["card_id"] == 2
        assert insert_mock.call_args_list[1][0][0]["raw_text"] == "原始二"

    def test_create_resume_version_gets_version_name_suggestion(self, tmp_path):
        """T-M6-8 评审修复：版本落库带 matrix 建议名 方向-公司-日期，
        note 复用该名后与 FE 简历列表展示一致。"""
        import re

        cards = {3: self._snapshot_card(3, "x")}
        created = {}

        def fake_create(**kwargs):
            created.update(kwargs)
            return {"id": 42}

        self._run_generate(tmp_path, cards, fake_create)

        assert re.fullmatch(r"P-C-\d{4}/\d{1,2}/\d{1,2}", created["version_name"])

    def test_jd_alignment_card_without_tags_is_tolerated(self, tmp_path):
        """T-M6-8：tags 缺省的卡 → 快照 tags=None，写入不炸。"""
        card = self._snapshot_card(3, "无标签卡")
        card.pop("tags")

        result, insert_mock = self._run_generate(
            tmp_path, {3: card}, lambda **k: {"id": 42}
        )

        assert result["resume_version_id"] == 42
        payload = insert_mock.call_args[0][0]
        assert payload["card_id"] == 3
        assert payload["tags"] is None
        assert payload["raw_text"] == "无标签卡"


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
                    include_domains=None,
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
                    include_domains=None,
                )

    def test_internet_search_include_domains_passthrough(self):
        """T-P7-2：include_domains 透传 tavily_client.search + monitor 上报。"""
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
                patch.object(mod, "monitor") as mock_monitor,
            ):
                mod.internet_search.invoke(
                    {
                        "query": "字节跳动 官网",
                        "include_domains": ["bytedance.com", "example.org"],
                    }
                )
                mock_client.search.assert_called_once_with(
                    query="字节跳动 官网",
                    topic="general",
                    max_results=5,
                    include_raw_content=False,
                    include_domains=["bytedance.com", "example.org"],
                )
                reported = mock_monitor.report_tool.call_args.kwargs["args"]
                assert reported["include_domains"] == [
                    "bytedance.com",
                    "example.org",
                ]

    def test_internet_search_monitor_truncates_include_domains(self):
        """质量审查 Minor-7：超长 include_domains 上报截前 10 + …(+n) 尾标，
        tavily_client 收到的仍是完整白名单。"""
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": []}
        domains = [f"site{i}.example.com" for i in range(15)]

        with (
            patch("tavily.TavilyClient", return_value=mock_client),
            patch.dict("os.environ", {"TAVILY_API_KEY": "fake-key"}),
        ):
            import importlib
            import app.tools.tavily_tool as mod

            importlib.reload(mod)
            with (
                patch.object(mod, "tavily_client", mock_client),
                patch.object(mod, "monitor") as mock_monitor,
            ):
                mod.internet_search.invoke({"query": "q", "include_domains": domains})
                reported = mock_monitor.report_tool.call_args.kwargs["args"]
                assert reported["include_domains"] == domains[:10] + ["…(+5)"]
                assert mock_client.search.call_args.kwargs["include_domains"] == domains


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


class TestGetCardsSummary:
    """T-M1-2：GET /cards 内嵌摘要的 DAO（版本数 + 表达计数 + 降级）。"""

    @pytest.fixture
    def exp_db(self, monkeypatch):
        import app.tools.db_experience as m

        holder = {
            "version_rows": [],
            "expr_rows": [],
            "expr_error": None,
            "calls": [],
        }

        def _query_all(sql, params=None):
            holder["calls"].append((sql, params))
            if "FROM expression" in sql:
                if holder["expr_error"] is not None:
                    raise holder["expr_error"]
                return holder["expr_rows"]
            return holder["version_rows"]

        monkeypatch.setattr(m, "query_all", _query_all)
        monkeypatch.setattr(m, "_ensure_card_versions_table", lambda: None)
        return holder

    def test_empty_ids_returns_empty_without_query(self, exp_db):
        from app.tools.db_experience import get_cards_summary

        assert get_cards_summary(1, []) == {}
        assert exp_db["calls"] == []

    def test_aggregates_counts_with_zero_defaults(self, exp_db):
        from app.tools.db_experience import get_cards_summary

        exp_db["version_rows"] = [(7, 4)]
        exp_db["expr_rows"] = [(7, 3, 1)]
        summary = get_cards_summary(1, [7, 8])
        assert summary[7] == {
            "version_count": 4,
            "expression_summary": {"active": 1, "total": 3},
        }
        assert summary[8] == {
            "version_count": 0,
            "expression_summary": {"active": 0, "total": 0},
        }

    def test_version_query_filters_ownership(self, exp_db):
        from app.tools.db_experience import get_cards_summary

        get_cards_summary(9, [7])
        sql, params = exp_db["calls"][0]
        assert "JOIN experience_card" in sql
        assert "c.user_id = %s" in sql
        assert params[0] == 9

    def test_version_query_excludes_jd_alignment(self, exp_db):
        """FE-JDVER-01：version_count 只排除显式 jd_alignment，NULL 类型照算"""
        from app.tools.db_experience import get_cards_summary

        get_cards_summary(1, [7])
        sql, _ = exp_db["calls"][0]
        # <> 会误伤 NULL 行，必须写成 OR 形式（IS NULL OR <> 'jd_alignment'）
        assert "(v.version_type IS NULL OR v.version_type <> 'jd_alignment')" in sql
        assert "GROUP BY v.card_id" in sql

    def test_expression_table_missing_degrades_to_zero(self, exp_db):
        """expression 表缺失（未迁移库 errno 1146）→ 按 0 计，不抛错"""
        from app.tools.db_experience import get_cards_summary

        class _Err(Exception):
            errno = 1146

        exp_db["version_rows"] = [(7, 2)]
        exp_db["expr_error"] = _Err("Table 'expression' doesn't exist")
        summary = get_cards_summary(1, [7])
        assert summary[7] == {
            "version_count": 2,
            "expression_summary": {"active": 0, "total": 0},
        }

    def test_expression_other_error_propagates(self, exp_db):
        from app.tools.db_experience import get_cards_summary

        class _Err(Exception):
            errno = 1054

        exp_db["expr_error"] = _Err("Unknown column")
        with pytest.raises(Exception, match="Unknown column"):
            get_cards_summary(1, [7])


class TestSearchCardsDirection:
    """T-M3-4 search_cards/count_search_cards 方向结构化过滤（mock DB）。"""

    @pytest.fixture
    def exp_db(self, monkeypatch):
        import app.tools.db_experience as m

        holder = {"rows": [], "scalar": 0, "calls": []}

        def _query_all(sql, params=None):
            holder["calls"].append((sql, params))
            return holder["rows"]

        def _query_scalar(sql, params=None):
            holder["calls"].append((sql, params))
            return holder["scalar"]

        monkeypatch.setattr(m, "query_all", _query_all)
        monkeypatch.setattr(m, "query_scalar", _query_scalar)
        monkeypatch.setattr(m, "_ensure_experience_card_columns", lambda: None)
        return holder

    def test_direction_only_has_exists_and_no_like(self, exp_db):
        from app.tools.db_experience import search_cards

        out = search_cards(1, "", direction_id=3)
        assert out == []
        sql, params = exp_db["calls"][-1]
        assert "EXISTS (SELECT 1 FROM expression e" in sql
        assert "e.direction_id=%s" in sql
        assert "LIKE" not in sql
        assert params == (1, 1, 3, 20, 0)

    def test_direction_and_query_param_order(self, exp_db):
        from app.tools.db_experience import search_cards

        search_cards(1, "python", direction_id=3, offset=5, limit=10)
        sql, params = exp_db["calls"][-1]
        assert "EXISTS" in sql
        assert "(title LIKE %s OR company LIKE %s" in sql
        # user_id / EXISTS(user_id, direction_id) / LIKE×4 / tags JSON / limit / offset
        assert params == (
            1,
            1,
            3,
            "%python%",
            "%python%",
            "%python%",
            "%python%",
            json.dumps("python", ensure_ascii=False),
            10,
            5,
        )

    def test_keyword_only_regression_no_exists(self, exp_db):
        """原关键词契约回归：不带 direction_id 时不出现 EXISTS，LIKE 参数齐备。"""
        from app.tools.db_experience import search_cards, count_search_cards

        search_cards(1, "python")
        sql, params = exp_db["calls"][-1]
        assert "EXISTS" not in sql
        assert sql.count("LIKE") == 4
        assert params[0] == 1
        assert params[-1] == 0  # offset

        exp_db["scalar"] = 2
        assert count_search_cards(1, "python") == 2
        sql, params = exp_db["calls"][-1]
        assert "EXISTS" not in sql

    def test_empty_query_without_direction_returns_all(self, exp_db):
        """API 层保证二者至少其一；DAO 层空查询+无方向 = 全量（无 LIKE）。"""
        from app.tools.db_experience import search_cards

        search_cards(1, "")
        sql, params = exp_db["calls"][-1]
        assert "LIKE" not in sql
        assert "EXISTS" not in sql
        assert params == (1, 20, 0)

    def test_count_with_direction(self, exp_db):
        from app.tools.db_experience import count_search_cards

        exp_db["scalar"] = 5
        assert count_search_cards(1, "", direction_id=3) == 5
        sql, params = exp_db["calls"][-1]
        assert "SELECT COUNT(*) FROM experience_card" in sql
        assert "e.direction_id=%s" in sql
        assert params == (1, 1, 3)

    def test_is_active_predicate_precedes_exists(self, exp_db):
        """默认 include_inactive=False：is_active=1 条件先于 EXISTS 拼接。"""
        from app.tools.db_experience import search_cards

        search_cards(1, "", direction_id=3)
        sql, params = exp_db["calls"][-1]
        assert "is_active=1" in sql
        assert sql.index("is_active=1") < sql.index("EXISTS")
        assert params == (1, 1, 3, 20, 0)


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
            # T-M4-2：详情附改写任务清单（mock fetchall 空 → 降级 []）
            assert result["capability_gaps"] == []

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

    def test_get_job_analysis_attaches_jd_classification(self):
        """T-M4-4：详情附方向分类（grouped 命中 → dict，携带方向名）。"""
        from app.tools.db_job import get_job_analysis

        classification = {
            "id": 9,
            "job_analysis_id": 1,
            "direction_id": 3,
            "direction_name": "电商零售",
            "direction_code": "DIR-1",
            "industry": "电商",
        }
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "user_id": 7,
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

        with (
            patch("app.tools.db_conn.connect", return_value=mock_conn),
            patch(
                "app.tools.db_jd_classification.list_jd_classifications_grouped",
                return_value={1: classification},
            ) as mock_grouped,
        ):
            result = get_job_analysis(1, user_id=7)
        assert result is not None
        assert result["jd_classification"] == classification
        mock_grouped.assert_called_once_with([1], user_id=7)

    def test_get_job_analysis_missing_classification_is_none(self):
        """T-M4-4：无分类行 / 缺表（grouped 降级空映射）→ jd_classification=None。"""
        from app.tools.db_job import get_job_analysis

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "user_id": 7,
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

        with (
            patch("app.tools.db_conn.connect", return_value=mock_conn),
            patch(
                "app.tools.db_jd_classification.list_jd_classifications_grouped",
                return_value={},
            ),
        ):
            result = get_job_analysis(1, user_id=7)
        assert result is not None
        assert result["jd_classification"] is None

    @staticmethod
    def _analysis_row():
        """list_job_analyses 单行（列名与 SELECT 一致）。"""
        return {
            "id": 55,
            "user_id": 7,
            "company": "Co",
            "position": "Eng",
            "jd_text": "JD",
            "jd_requirements": "{}",
            "match_score": 80,
            "match_level": None,
            "analysis_version": None,
            "job_id": None,
            "ats_profile": None,
            "suggestions": None,
            "per_card_scores": None,
            "gap_analysis": "[]",
            "dimension_requirements": "[]",
            "created_at": SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
        }

    def test_list_job_analyses_attaches_jd_classification(self):
        """T-M4-4：列表批量附方向分类（按行 id 命中，user_id 透传 DAO）。"""
        from app.tools import db_job

        classification = {"id": 9, "job_analysis_id": 55, "direction_name": "电商零售"}
        with (
            patch("app.tools.db_job._ensure_job_analysis_columns"),
            patch("app.tools.db_job.query_all", return_value=[self._analysis_row()]),
            patch(
                "app.tools.db_capability_gap.list_capability_gaps_grouped",
                return_value={},
            ),
            patch(
                "app.tools.db_jd_classification.list_jd_classifications_grouped",
                return_value={55: classification},
            ) as mock_grouped,
        ):
            out = db_job.list_job_analyses(7, limit=100)
        assert len(out) == 1
        assert out[0]["capability_gaps"] == []
        assert out[0]["jd_classification"] == classification
        mock_grouped.assert_called_once_with([55], user_id=7)

    def test_list_job_analyses_missing_classification_degrades_none(self):
        """T-M4-4：分类缺表/未命中 → 每行 jd_classification=None，不抛错。"""
        from app.tools import db_job

        with (
            patch("app.tools.db_job._ensure_job_analysis_columns"),
            patch("app.tools.db_job.query_all", return_value=[self._analysis_row()]),
            patch(
                "app.tools.db_capability_gap.list_capability_gaps_grouped",
                return_value={},
            ),
            patch(
                "app.tools.db_jd_classification.list_jd_classifications_grouped",
                return_value={},
            ),
        ):
            out = db_job.list_job_analyses(7)
        assert out[0]["jd_classification"] is None


# ============================================================
# 7b. db_capability_gap.py — T-M4-2 改写任务清单落库
# ============================================================


class TestDbCapabilityGap:
    def test_insert_capability_gaps_writes_rows(self):
        """T-M4-2：逐条插入，wire current 映射 DB 列 current_text。"""
        from app.tools.db_capability_gap import insert_capability_gaps

        with patch("app.tools.db_capability_gap.execute", return_value=1) as mock_exec:
            n = insert_capability_gaps(
                42,
                1,
                [
                    {
                        "dimension": "D6",
                        "kind": "rewrite",
                        "status": "weak",
                        "severity": "high",
                        "jd_evidence": "独立完成用户研究",
                        "current": "协助调研",
                        "rewrite_hint": "突出独立主导",
                        "card_id": 3,
                        "note": "备注",
                    },
                    {"dimension": "EXT"},
                ],
            )
        assert n == 2
        sql, params = mock_exec.call_args_list[0][0]
        assert "INSERT INTO capability_gap" in sql
        assert "current_text" in sql
        assert params == (
            42,
            1,
            "D6",
            "rewrite",
            "weak",
            "high",
            "独立完成用户研究",
            "协助调研",
            "突出独立主导",
            3,
            "备注",
        )
        # 第二条缺省字段走 schema 默认
        assert mock_exec.call_args_list[1][0][1][1:] == (
            1,
            "EXT",
            "evidence",
            "missing",
            "medium",
            "",
            "",
            "",
            None,
            "",
        )

    def test_insert_capability_gaps_missing_table_raises(self):
        """缺表（errno 1146）翻译为 ValueError 提示先迁移（collate 降级告警）。"""
        from mysql.connector import Error as MySQLError

        from app.tools.db_capability_gap import insert_capability_gaps

        err = MySQLError("Table 'capability_gap' doesn't exist")
        err.errno = 1146
        with (
            patch("app.tools.db_capability_gap.execute", side_effect=err),
            pytest.raises(ValueError, match="migrations.runner"),
        ):
            insert_capability_gaps(42, 1, [{"dimension": "D6"}])

    def test_list_capability_gaps_grouped_empty_ids_skips_query(self):
        from app.tools.db_capability_gap import list_capability_gaps_grouped

        with patch("app.tools.db_capability_gap.query_all") as mock_q:
            assert list_capability_gaps_grouped([]) == {}
        mock_q.assert_not_called()

    def test_list_capability_gaps_grouped_maps_wire_fields(self):
        """DB 行 → wire：current_text 映射回 current，缺省字段兜底。"""
        from app.tools.db_capability_gap import list_capability_gaps_grouped

        rows = [
            {
                "id": 7,
                "job_analysis_id": 42,
                "dimension": "D6",
                "kind": "evidence",
                "status": "missing",
                "severity": "high",
                "jd_evidence": "独立完成用户研究",
                "current_text": "协助调研",
                "rewrite_hint": "突出独立主导",
                "card_id": None,
                "note": None,
            }
        ]
        with patch("app.tools.db_capability_gap.query_all", return_value=rows):
            grouped = list_capability_gaps_grouped([42])
        assert grouped[42][0]["current"] == "协助调研"
        assert grouped[42][0]["note"] == ""
        assert grouped[42][0]["card_id"] is None

    def test_list_capability_gaps_grouped_degrades_on_missing_table(self):
        from mysql.connector import Error as MySQLError

        from app.tools.db_capability_gap import list_capability_gaps_grouped

        err = MySQLError("Table missing")
        err.errno = 1146
        with patch("app.tools.db_capability_gap.query_all", side_effect=err):
            assert list_capability_gaps_grouped([42]) == {}

    def test_list_capability_gaps_single_returns_list(self):
        from app.tools.db_capability_gap import list_capability_gaps

        rows = [
            {
                "id": 1,
                "job_analysis_id": 42,
                "dimension": "EXT",
                "current_text": "",
            }
        ]
        with patch("app.tools.db_capability_gap.query_all", return_value=rows):
            gaps = list_capability_gaps(42)
        assert len(gaps) == 1
        assert gaps[0]["dimension"] == "EXT"

    def test_count_gaps_by_dimension_maps_and_sorts(self):
        """T-M3-6：按维度计数——聚合行映射 + count 降序交由 SQL，此处透传。"""
        from app.tools.db_capability_gap import count_gaps_by_dimension

        rows = [
            {"dimension": "D6", "c": 5},
            {"dimension": "D3", "c": 3},
            {"dimension": None, "c": 1},
        ]
        with patch(
            "app.tools.db_capability_gap.query_all", return_value=rows
        ) as mock_q:
            out = count_gaps_by_dimension(7)
        assert out == [
            {"dimension": "D6", "count": 5},
            {"dimension": "D3", "count": 3},
            {"dimension": "EXT", "count": 1},
        ], "NULL 维度兜底 EXT"
        sql, params = mock_q.call_args[0]
        assert "GROUP BY dimension" in sql
        assert "user_id=%s" in sql
        assert params == (7,)

    def test_count_gaps_by_dimension_missing_table_degrades_empty(self):
        from mysql.connector import Error as MySQLError

        from app.tools.db_capability_gap import count_gaps_by_dimension

        err = MySQLError("Table missing")
        err.errno = 1146
        with patch("app.tools.db_capability_gap.query_all", side_effect=err):
            assert count_gaps_by_dimension(7) == []

    def test_count_gaps_by_dimension_other_error_reraises(self):
        from mysql.connector import Error as MySQLError

        from app.tools.db_capability_gap import count_gaps_by_dimension

        err = MySQLError("Lost connection")
        err.errno = 2003
        with (
            patch("app.tools.db_capability_gap.query_all", side_effect=err),
            pytest.raises(MySQLError),
        ):
            count_gaps_by_dimension(7)


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

    def test_insert_submission_never_relies_on_db_default(self):
        """BE-DRIFT-01：INSERT 恒显式带 status 列（三处 DDL DEFAULT 不参与写入），
        无法识别的 status 回落 PREPARED 而非透传。"""
        from app.schemas.submission_status import SUBMISSION_STATUS_CN, SubmissionStatus
        from app.tools.db_submission import insert_submission

        with (
            patch("app.tools.db_conn.connect"),
            patch(
                "app.tools.db_submission.execute_lastrowid", return_value=1
            ) as mock_insert,
            patch("app.tools.db_submission._attach_job_entity", return_value=3),
        ):
            insert_submission({"position": "PM"})
            insert_submission({"position": "PM", "status": "已投递"})
            insert_submission({"position": "PM", "status": "不存在的状态"})
        sql = mock_insert.call_args_list[0][0][0]
        assert "status" in sql.split("VALUES")[0]
        valid = {s.value for s in SubmissionStatus} | set(SUBMISSION_STATUS_CN)
        for call in mock_insert.call_args_list:
            assert call[0][1][8] in valid
        # 缺省 → PREPARED；旧中文归一化；垃圾值不透传
        assert mock_insert.call_args_list[0][0][1][8] == "PREPARED"
        assert mock_insert.call_args_list[1][0][1][8] == "APPLIED"
        assert mock_insert.call_args_list[2][0][1][8] == "PREPARED"

    def test_status_default_drift_documented_and_isolated(self):
        """BE-DRIFT-01：三处 DDL DEFAULT 差异锁定为已知决策（AGENTS §4.4 不改列）。
        若任一处被改动，本测试失败提醒重新评估迁移方案。"""
        root = Path(__file__).resolve().parent.parent
        v0001 = (root / "migrations" / "versions" / "V0001__baseline.sql").read_text(
            encoding="utf-8"
        )
        baseline = (root / "docker" / "mysql" / "jobcraft.sql").read_text(
            encoding="utf-8"
        )
        ensure_sql = inspect.getsource(
            sys.modules["app.tools.db_submission"]._ensure_resume_submission_table
        )
        assert "DEFAULT 'APPLIED'" in v0001
        assert "DEFAULT '已投递'" in baseline
        assert "DEFAULT 'PREPARED'" in ensure_sql

    def test_get_submission_by_analysis_projects_effective_status(self):
        """BE-DRIFT-01：按分析查投递也走 effective_status 投影（存量
        APPLIED+delivered=0 → PREPARED），不透传裸存量值。"""
        from app.tools.db_submission import get_submission_by_analysis

        row = {
            "id": 9,
            "user_id": 1,
            "job_analysis_id": 7,
            "position": "PM",
            "company": "X",
            "jd_text": "",
            "resume_markdown": "",
            "resume_file_path": "",
            "card_version_ids": "[]",
            "status": "APPLIED",
            "notes": "",
            "is_manual": 0,
            "delivered": 0,
            "created_at": SimpleNamespace(isoformat=lambda: "2024-01-01"),
            "updated_at": SimpleNamespace(isoformat=lambda: "2024-01-02"),
        }
        with (
            patch("app.tools.db_submission.is_schema_ready", return_value=True),
            patch("app.tools.db_submission.query_one", return_value=row),
        ):
            out = get_submission_by_analysis(7, user_id=1)
        assert out is not None
        assert out["status"] == "PREPARED"

        row["delivered"] = 1
        with (
            patch("app.tools.db_submission.is_schema_ready", return_value=True),
            patch("app.tools.db_submission.query_one", return_value=row),
        ):
            out = get_submission_by_analysis(7, user_id=1)
        assert out["status"] == "APPLIED"

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

    def test_get_submission_exposes_resume_version_id(self):
        """T-M6-7：读取投递带出归档版本 id；旧库缺列行为 None 不炸。"""
        from app.tools.db_submission import get_submission, get_submission_by_analysis

        base = {
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
            "notes": "",
            "is_manual": 0,
            "delivered": 0,
            "created_at": SimpleNamespace(isoformat=lambda: "2024-01-01"),
            "updated_at": SimpleNamespace(isoformat=lambda: "2024-01-02"),
        }
        # 有归档 → 透出版本 id
        row = dict(base, resume_version_id=33)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = row
        mock_cursor.fetchall.return_value = []
        with patch(
            "app.tools.db_conn.connect", return_value=_make_mock_conn(mock_cursor)
        ):
            assert get_submission(1)["resume_version_id"] == 33

        # 未迁移旧行缺列 → None 不炸（单条读取）
        with patch(
            "app.tools.db_conn.connect", return_value=_make_mock_conn(mock_cursor)
        ):
            mock_cursor.fetchone.return_value = dict(base)
            assert get_submission(1)["resume_version_id"] is None

        # 未迁移旧行缺列 → None 不炸（按分析读取）
        with (
            patch("app.tools.db_submission.is_schema_ready", return_value=True),
            patch("app.tools.db_submission.query_one", return_value=dict(base)),
        ):
            out = get_submission_by_analysis(7, user_id=1)
        assert out is not None
        assert out["resume_version_id"] is None

    def test_archive_selected_version_idempotent_when_archived(self):
        """T-M6-7：已归档幂等——返回现值，不发起 UPDATE（不覆写）。"""
        from app.tools import db_submission

        with (
            patch(
                "app.tools.db_submission.get_submission",
                return_value={
                    "id": 1,
                    "job_analysis_id": 10,
                    "resume_version_id": 42,
                },
            ),
            patch("app.tools.db_submission.execute") as mock_exec,
        ):
            assert db_submission.archive_selected_version(1, 1) == 42
        mock_exec.assert_not_called()

    def test_archive_selected_version_skips_without_analysis(self):
        """T-M6-7：无分析归属（job 实体回查也无）→ 跳过返回 None。"""
        from app.tools import db_submission

        with (
            patch(
                "app.tools.db_submission.get_submission",
                return_value={
                    "id": 1,
                    "job_analysis_id": None,
                    "resume_version_id": None,
                },
            ),
            patch(
                "app.tools.db_job_entity.get_job_by_submission", return_value=None
            ) as mock_job,
            patch("app.tools.db_submission.execute") as mock_exec,
        ):
            assert db_submission.archive_selected_version(1, 1) is None
        mock_job.assert_called_once_with(1, 1)
        mock_exec.assert_not_called()

    def test_archive_selected_version_skips_without_version(self):
        """T-M6-7：该分析下无可归档版本 → 跳过返回 None，不 UPDATE。"""
        from app.tools import db_submission

        with (
            patch(
                "app.tools.db_submission.get_submission",
                return_value={
                    "id": 1,
                    "job_analysis_id": 10,
                    "resume_version_id": None,
                },
            ),
            patch(
                "app.tools.db_resume_version.get_selected_resume_version",
                return_value=None,
            ) as mock_sel,
            patch("app.tools.db_submission.execute") as mock_exec,
        ):
            assert db_submission.archive_selected_version(1, 1) is None
        mock_sel.assert_called_once_with(1, 10)
        mock_exec.assert_not_called()

    def test_archive_selected_version_writes_snapshot(self):
        """T-M6-7：成功路径——单条 UPDATE 拷贝正文并写版本 id，返回版本 id。"""
        from app.tools import db_submission

        with (
            patch(
                "app.tools.db_submission.get_submission",
                return_value={
                    "id": 1,
                    "job_analysis_id": 10,
                    "resume_version_id": None,
                },
            ),
            patch(
                "app.tools.db_resume_version.get_selected_resume_version",
                return_value={"id": 77, "resume_markdown": "# 快照"},
            ) as mock_sel,
            patch("app.tools.db_submission.execute", return_value=1) as mock_exec,
        ):
            assert db_submission.archive_selected_version(1, 1) == 77
        mock_sel.assert_called_once_with(1, 10)
        sql, params = mock_exec.call_args[0]
        assert "UPDATE resume_submission" in sql
        assert "resume_markdown=%s" in sql
        assert "resume_version_id=%s" in sql
        assert "is_active=1" in sql
        # 评审修复：原子幂等守卫——条件写，首次投递优先，绝不覆写
        assert "resume_version_id IS NULL" in sql
        assert params == ("# 快照", 77, 1, 1)

    def test_archive_rowcount_zero_rereads_existing_version(self):
        """T-M6-7 评审：UPDATE rowcount=0（并发已抢先归档）→ 回读返回既有版本 id。"""
        from app.tools import db_submission

        first = {"id": 1, "job_analysis_id": 10, "resume_version_id": None}
        winner = {"id": 1, "job_analysis_id": 10, "resume_version_id": 55}
        with (
            patch(
                "app.tools.db_submission.get_submission",
                side_effect=[first, winner],
            ),
            patch(
                "app.tools.db_resume_version.get_selected_resume_version",
                return_value={"id": 77, "resume_markdown": "# 新"},
            ),
            patch("app.tools.db_submission.execute", return_value=0) as mock_exec,
        ):
            assert db_submission.archive_selected_version(1, 1) == 55
        sql, _ = mock_exec.call_args[0]
        assert "resume_version_id IS NULL" in sql

    def test_archive_rowcount_zero_and_row_gone_returns_none(self):
        """T-M6-7 评审：rowcount=0 且回读无行 → logger.info 后返回 None。"""
        from app.tools import db_submission

        first = {"id": 1, "job_analysis_id": 10, "resume_version_id": None}
        with (
            patch(
                "app.tools.db_submission.get_submission",
                side_effect=[first, None],
            ),
            patch(
                "app.tools.db_resume_version.get_selected_resume_version",
                return_value={"id": 77, "resume_markdown": "# 新"},
            ),
            patch("app.tools.db_submission.execute", return_value=0),
        ):
            assert db_submission.archive_selected_version(1, 1) is None

    def test_archive_skips_empty_markdown_write(self):
        """T-M6-7 评审：版本正文为 NULL/空 → 不写 resume_markdown（不清空投递既有正文），仍写版本 id。"""
        from app.tools import db_submission

        with (
            patch(
                "app.tools.db_submission.get_submission",
                return_value={
                    "id": 1,
                    "job_analysis_id": 10,
                    "resume_version_id": None,
                },
            ),
            patch(
                "app.tools.db_resume_version.get_selected_resume_version",
                return_value={"id": 77, "resume_markdown": None},
            ),
            patch("app.tools.db_submission.execute", return_value=1) as mock_exec,
        ):
            assert db_submission.archive_selected_version(1, 1) == 77
        sql, params = mock_exec.call_args[0]
        assert "resume_version_id=%s" in sql
        assert "resume_markdown" not in sql
        assert params == (77, 1, 1)

    def test_archive_selected_version_resolves_analysis_via_job(self):
        """T-M6-7：submission 无 analysis → 经 job 实体回查后归档。"""
        from app.tools import db_submission

        with (
            patch(
                "app.tools.db_submission.get_submission",
                return_value={
                    "id": 1,
                    "job_analysis_id": None,
                    "resume_version_id": None,
                },
            ),
            patch(
                "app.tools.db_job_entity.get_job_by_submission",
                return_value={"id": 3, "job_analysis_id": 55},
            ) as mock_job,
            patch(
                "app.tools.db_resume_version.get_selected_resume_version",
                return_value={"id": 9, "resume_markdown": "# V"},
            ) as mock_sel,
            patch("app.tools.db_submission.execute", return_value=1),
        ):
            assert db_submission.archive_selected_version(1, 1) == 9
        mock_job.assert_called_once_with(1, 1)
        mock_sel.assert_called_once_with(1, 55)

    def test_archive_selected_version_denied_for_other_user(self):
        """T-M6-7：越权（get_submission None）→ 返回 None，不查版本不 UPDATE。"""
        from app.tools import db_submission

        with (
            patch("app.tools.db_submission.get_submission", return_value=None),
            patch(
                "app.tools.db_resume_version.get_selected_resume_version"
            ) as mock_sel,
            patch("app.tools.db_submission.execute") as mock_exec,
        ):
            assert db_submission.archive_selected_version(404, 2) is None
        mock_sel.assert_not_called()
        mock_exec.assert_not_called()


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

    def test_get_interview_prep_ref_hit(self):
        from app.tools.db_interview import get_interview_prep_ref

        with (
            patch("app.tools.db_interview.is_schema_ready", return_value=True),
            patch(
                "app.tools.db_interview.query_one",
                return_value={"id": 7, "job_analysis_id": 12},
            ) as mock_q,
        ):
            result = get_interview_prep_ref(7, 1)
        assert result == {"id": 7, "job_analysis_id": 12}
        assert "user_id=%s" in mock_q.call_args[0][0]

    def test_get_interview_prep_ref_not_owned(self):
        from app.tools.db_interview import get_interview_prep_ref

        with (
            patch("app.tools.db_interview.is_schema_ready", return_value=True),
            patch("app.tools.db_interview.query_one", return_value=None),
        ):
            assert get_interview_prep_ref(999, 1) is None

    def test_update_interview_prep_company_research_writes_json_and_at(self):
        from app.tools.db_interview import update_interview_prep_company_research

        with (
            patch("app.tools.db_interview.is_schema_ready", return_value=True),
            patch("app.tools.db_interview.query_one", return_value={"id": 7}),
            patch("app.tools.db_interview.execute", return_value=1) as mock_exec,
        ):
            ok = update_interview_prep_company_research(7, 1, {"basic": {"name": "X"}})
        assert ok is True
        sql, params = mock_exec.call_args[0]
        assert "company_research_json=%s" in sql
        assert "company_research_at=NOW()" in sql
        assert '"basic"' in params[0] or '"name"' in params[0]

    def test_update_interview_prep_company_research_not_owned(self):
        from app.tools.db_interview import update_interview_prep_company_research

        with (
            patch("app.tools.db_interview.is_schema_ready", return_value=True),
            patch("app.tools.db_interview.query_one", return_value=None),
            patch("app.tools.db_interview.execute", return_value=1) as mock_exec,
        ):
            ok = update_interview_prep_company_research(999, 1, {})
        assert ok is False
        mock_exec.assert_not_called()

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

    def test_update_job_updates_provided_fields_only(self):
        """T-M5-1：update_job 仅更新传入字段，归属校验先行"""
        from app.tools import db_job_entity

        current = {"id": 5, "user_id": 1, "position": "PM", "status": "PREPARED"}
        updated = {"id": 5, "user_id": 1, "position": "PM", "status": "APPLIED"}
        with (
            patch("app.tools.db_job_entity._ensure_job_table"),
            patch(
                "app.tools.db_job_entity.get_job",
                side_effect=[current, updated],
            ),
            patch("app.tools.db_job_entity.execute", return_value=1) as mock_exec,
        ):
            result = db_job_entity.update_job(5, user_id=1, status="APPLIED")
        assert result == updated
        sql, params = mock_exec.call_args[0]
        assert "status=%s" in sql
        assert "company=%s" not in sql and "position=%s" not in sql
        assert params == ("APPLIED", 5)

    def test_update_job_missing_returns_none(self):
        from app.tools import db_job_entity

        with (
            patch("app.tools.db_job_entity._ensure_job_table"),
            patch("app.tools.db_job_entity.get_job", return_value=None),
            patch("app.tools.db_job_entity.execute") as mock_exec,
        ):
            assert db_job_entity.update_job(404, user_id=1, company="X") is None
        mock_exec.assert_not_called()

    def test_update_job_empty_position_raises(self):
        from app.tools import db_job_entity

        with (
            patch("app.tools.db_job_entity._ensure_job_table"),
            patch(
                "app.tools.db_job_entity.get_job",
                return_value={"id": 5, "position": "PM"},
            ),
        ):
            try:
                db_job_entity.update_job(5, position="   ")
            except ValueError as e:
                assert "岗位名称不能为空" in str(e)
            else:
                raise AssertionError("空 position 应抛 ValueError")

    def test_update_job_without_fields_is_read_only(self):
        from app.tools import db_job_entity

        current = {"id": 5, "position": "PM"}
        with (
            patch("app.tools.db_job_entity._ensure_job_table"),
            patch("app.tools.db_job_entity.get_job", side_effect=[current, current]),
            patch("app.tools.db_job_entity.execute") as mock_exec,
        ):
            assert db_job_entity.update_job(5, user_id=1) == current
        mock_exec.assert_not_called()

    def test_update_job_deactivate_sets_inactive(self):
        """Q2：删除 = is_active=0（停用，不物理删除）"""
        from app.tools import db_job_entity

        current = {"id": 5, "is_active": True}
        updated = {"id": 5, "is_active": False}
        with (
            patch("app.tools.db_job_entity._ensure_job_table"),
            patch(
                "app.tools.db_job_entity.get_job",
                side_effect=[current, updated],
            ),
            patch("app.tools.db_job_entity.execute", return_value=1) as mock_exec,
        ):
            assert db_job_entity.update_job(5, user_id=1, is_active=False) == updated
        sql, params = mock_exec.call_args[0]
        assert "is_active=%s" in sql
        assert params == (0, 5)


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


class TestInterviewRecordSessionColumns:
    """T-M7-4：interview_records 场次骨架列的 DAO 落库与更新约束"""

    def test_insert_passes_session_columns(self, monkeypatch):
        from datetime import datetime as _dt

        from app.tools import db_interview

        captured = {}
        monkeypatch.setattr(
            db_interview, "_ensure_interview_records_table", lambda: None
        )
        monkeypatch.setattr(
            "app.tools.db_submission._ensure_interview_submission_columns",
            lambda: None,
        )

        def fake_lastrowid(sql, params):
            captured.update(sql=sql, params=params)
            return 901

        monkeypatch.setattr(db_interview, "execute_lastrowid", fake_lastrowid)
        occurred = _dt(2026, 9, 20, 10, 0)
        rid = db_interview.insert_interview_record(
            {
                "user_id": 1,
                "company": "字节跳动",
                "position": "AI 产品经理",
                "round_type": "tech",
                "status": "planned",
                "round_seq": 1,
                "occurred_at": occurred,
                "interviewer": "张三",
                "format": "video",
                "resume_version_id": 3,
            }
        )
        assert rid == 901
        for col in (
            "round_seq",
            "occurred_at",
            "interviewer",
            "format",
            "resume_version_id",
        ):
            assert col in captured["sql"], f"INSERT 缺列 {col}"
        params = captured["params"]
        # 列序：… status(idx9), submission_id(10), round_label(11),
        # round_seq(12), occurred_at(13), interviewer(14), format(15), resume_version_id(16)
        assert params[9] == "planned"
        assert params[12:17] == (1, occurred, "张三", "video", 3)

    def test_update_owned_builds_parameterized_sql(self, monkeypatch):
        from app.tools import db_interview

        calls = []
        monkeypatch.setattr(
            db_interview, "_ensure_interview_records_table", lambda: None
        )
        monkeypatch.setattr(db_interview, "query_one", lambda *a: {"id": 9})
        monkeypatch.setattr(
            db_interview,
            "execute",
            lambda sql, params: (calls.append((sql, params)), 1)[1],
        )
        ok = db_interview.update_interview_record_session(
            9, 1, {"round_seq": 2, "interviewer": "李四"}
        )
        assert ok is True
        sql, params = calls[0]
        assert sql == (
            "UPDATE interview_records SET round_seq=%s, interviewer=%s "
            "WHERE id=%s AND user_id=%s"
        )
        assert params == (2, "李四", 9, 1)

    def test_update_not_owned_skips_sql(self, monkeypatch):
        from app.tools import db_interview

        calls = []
        monkeypatch.setattr(
            db_interview, "_ensure_interview_records_table", lambda: None
        )
        monkeypatch.setattr(db_interview, "query_one", lambda *a: None)
        monkeypatch.setattr(
            db_interview,
            "execute",
            lambda sql, params: (calls.append((sql, params)), 1)[1],
        )
        assert (
            db_interview.update_interview_record_session(999, 1, {"round_seq": 2})
            is False
        )
        assert calls == [], "越权不得触达 UPDATE"

    def test_update_rejects_non_whitelist_fields(self, monkeypatch):
        from app.tools import db_interview

        calls = []
        monkeypatch.setattr(
            db_interview, "_ensure_interview_records_table", lambda: None
        )
        monkeypatch.setattr(db_interview, "query_one", lambda *a: {"id": 9})
        monkeypatch.setattr(
            db_interview,
            "execute",
            lambda sql, params: (calls.append((sql, params)), 1)[1],
        )
        with pytest.raises(ValueError, match="不允许更新"):
            db_interview.update_interview_record_session(9, 1, {"analysis": {}})
        assert calls == [], "白名单外字段不得触达 SQL"

    def test_update_empty_fields_is_noop(self, monkeypatch):
        from app.tools import db_interview

        queried = []
        monkeypatch.setattr(
            db_interview,
            "query_one",
            lambda *a: (queried.append(a), {"id": 9})[1],
        )
        assert db_interview.update_interview_record_session(9, 1, {}) is True
        assert queried == [], "空 fields 直接幂等返回，不查归属"


class TestInterviewRecordFillColumns:
    """T-M8-7：复盘填充（record_id → update 分支）DAO 行为与白名单约束"""

    def test_fill_maps_fields_and_json_encodes_dialogue(self, monkeypatch):
        from app.tools import db_interview

        calls = []
        monkeypatch.setattr(
            db_interview, "_ensure_interview_records_table", lambda: None
        )
        monkeypatch.setattr(db_interview, "query_one", lambda *a: {"id": 9})
        monkeypatch.setattr(
            db_interview,
            "execute",
            lambda sql, params: (calls.append((sql, params)), 1)[1],
        )
        ok = db_interview.update_interview_record_fill(
            9,
            1,
            {
                "title": "字节跳动-AI 产品经理-tech",
                "raw_text": "面试官：你好。",
                "parsed_dialogue": [{"speaker": "面试官", "role": "interviewer"}],
                "status": "parsed",
            },
        )
        assert ok is True
        sql, params = calls[0]
        assert "parsed_dialogue_json=%s" in sql
        assert "analysis" not in sql, "填充不得改写 analysis"
        assert params[0] == "字节跳动-AI 产品经理-tech"
        assert isinstance(params[2], str) and '"interviewer"' in params[2]
        assert params[3:] == ("parsed", 9, 1)

    def test_fill_not_owned_skips_sql(self, monkeypatch):
        from app.tools import db_interview

        calls = []
        monkeypatch.setattr(
            db_interview, "_ensure_interview_records_table", lambda: None
        )
        monkeypatch.setattr(db_interview, "query_one", lambda *a: None)
        monkeypatch.setattr(
            db_interview,
            "execute",
            lambda sql, params: (calls.append((sql, params)), 1)[1],
        )
        assert (
            db_interview.update_interview_record_fill(999, 1, {"raw_text": "x"})
            is False
        )
        assert calls == [], "越权不得触达 UPDATE"

    def test_fill_rejects_non_whitelist_fields(self, monkeypatch):
        from app.tools import db_interview

        calls = []
        monkeypatch.setattr(
            db_interview, "_ensure_interview_records_table", lambda: None
        )
        monkeypatch.setattr(db_interview, "query_one", lambda *a: {"id": 9})
        monkeypatch.setattr(
            db_interview,
            "execute",
            lambda sql, params: (calls.append((sql, params)), 1)[1],
        )
        with pytest.raises(ValueError, match="不允许填充字段"):
            db_interview.update_interview_record_fill(9, 1, {"analysis": {}})
        assert calls == [], "白名单外字段不得触达 SQL"

    def test_fill_record_tool_raises_when_not_owned(self, monkeypatch):
        from app.tools import interview_review

        monkeypatch.setattr(
            interview_review.db_tools,
            "update_interview_record_fill",
            lambda *a, **kw: False,
        )
        with pytest.raises(ValueError, match="无权访问"):
            interview_review.fill_interview_record(
                999,
                1,
                title="",
                company="字节跳动",
                position="AI 产品经理",
                round_type="tech",
                raw_text="面试官：你好，我叫小美。今天来聊下项目经历。",
            )

    def test_fill_record_tool_defaults_title_and_status_parsed(self, monkeypatch):
        from app.tools import interview_review

        captured = {}
        monkeypatch.setattr(
            interview_review.db_tools,
            "update_interview_record_fill",
            lambda rid, uid, fields: (
                captured.update(record_id=rid, user_id=uid, fields=fields) or True
            ),
        )
        interview_review.fill_interview_record(
            9,
            1,
            title="",
            company="字节跳动",
            position="AI 产品经理",
            round_type="tech",
            raw_text="面试官：你好，我叫小美。今天来聊下项目经历。",
            job_analysis_id=12,
        )
        assert captured["record_id"] == 9
        assert captured["fields"]["title"] == "字节跳动-AI 产品经理-tech"
        assert captured["fields"]["status"] == "parsed"
        assert captured["fields"]["job_analysis_id"] == 12
        assert isinstance(captured["fields"]["parsed_dialogue"], list)


class TestQaPairsAggregateQuery:
    """T-M8-3 聚合题库 DAO：单 JOIN 免 N+1、归属收口、场次上下文映射"""

    ROW = {
        "id": 3,
        "record_id": 55,
        "sequence": 2,
        "speaker": "面试官",
        "start_time": "00:10",
        "content": "讲讲你的项目",
        "is_question": 1,
        "question_text": "讲讲你的项目",
        "dimension": "项目深挖",
        "level": "L2",
        "intent": "验证真实性",
        "expected_answer": "STAR",
        "my_answer": "我做了 RAG 评测",
        "feedback_json": '[{"text":"ok"}]',
        "suggestions_json": None,
        "score": 80,
        "related_card_id": 7,
        "related_card_title": "RAG 项目",
        "record_title": "腾讯-后端-技术面",
        "record_company": "腾讯",
        "record_position": "后端工程师",
        "record_round_type": "技术面",
        "record_job_analysis_id": 12,
    }

    def test_all_records_joins_and_orders(self, monkeypatch):
        from app.tools import db_interview

        captured = {}

        def fake_query_all(sql, params):
            captured.update(sql=sql, params=params)
            return [dict(self.ROW)]

        monkeypatch.setattr(
            db_interview, "_ensure_interview_qa_pairs_table", lambda: None
        )
        monkeypatch.setattr(db_interview, "query_all", fake_query_all)
        rows = db_interview.list_interview_qa_pairs_by_user(1)
        assert captured["params"] == (1,)
        assert "JOIN interview_records r ON r.id = q.record_id" in captured["sql"]
        assert "r.user_id=%s" in captured["sql"]
        assert "ORDER BY r.created_at DESC" in captured["sql"]
        assert rows[0]["record_company"] == "腾讯"
        assert rows[0]["record_job_analysis_id"] == 12
        assert rows[0]["is_question"] is True
        assert rows[0]["feedback"] == [{"text": "ok"}]
        assert rows[0]["suggestions"] == []

    def test_job_filter_appends_param(self, monkeypatch):
        from app.tools import db_interview

        captured = {}
        monkeypatch.setattr(
            db_interview, "_ensure_interview_qa_pairs_table", lambda: None
        )
        monkeypatch.setattr(
            db_interview,
            "query_all",
            lambda sql, params: (captured.update(sql=sql, params=params), [])[1],
        )
        db_interview.list_interview_qa_pairs_by_user(1, job_analysis_id=12)
        assert captured["params"] == (1, 12)
        assert "AND r.job_analysis_id=%s" in captured["sql"]


class TestDbResumeVersion:
    """T-M6-1 / M6-Q1-B：resume_version DAO（每岗自增版本、单选设当前、归属校验）"""

    def test_create_assigns_version_no_max_plus_one(self):
        from app.tools import db_resume_version

        with (
            patch("app.tools.db_resume_version._ensure_resume_version_table"),
            patch(
                "app.tools.db_resume_version.query_one",
                return_value={"next_no": 3},
            ),
            patch(
                "app.tools.db_resume_version.execute_lastrowid", return_value=41
            ) as mock_insert,
            patch(
                "app.tools.db_resume_version.get_resume_version",
                return_value={"id": 41, "version_no": 4},
            ),
        ):
            created = db_resume_version.create_resume_version(
                1,
                9,
                version_name="产品-字节-2026/10/02",
                resume_markdown="# 简历",
                job_analysis_id=55,
            )
        assert created["id"] == 41
        sql, params = mock_insert.call_args[0]
        assert "INSERT INTO resume_version" in sql
        # (user_id, job_id, job_analysis_id, direction_id, version_no, version_name, ...)
        assert params[0] == 1
        assert params[1] == 9
        assert params[2] == 55
        assert params[4] == 4
        assert params[5] == "产品-字节-2026/10/02"

    def test_create_without_job_raises(self):
        from app.tools import db_resume_version

        with patch("app.tools.db_resume_version._ensure_resume_version_table"):
            with pytest.raises(ValueError, match="job_id"):
                db_resume_version.create_resume_version(1, None)

    def test_create_serializes_sections_to_json_string(self):
        from app.tools import db_resume_version

        with (
            patch("app.tools.db_resume_version._ensure_resume_version_table"),
            patch("app.tools.db_resume_version.query_one", return_value={"next_no": 0}),
            patch(
                "app.tools.db_resume_version.execute_lastrowid", return_value=2
            ) as mock_insert,
            patch(
                "app.tools.db_resume_version.get_resume_version",
                return_value={"id": 2},
            ),
        ):
            db_resume_version.create_resume_version(
                1, 9, sections=[{"type": "summary", "content": "你好"}]
            )
        params = mock_insert.call_args[0][1]
        assert json.loads(params[6]) == [{"type": "summary", "content": "你好"}]

    def test_get_latest_resume_version_by_analysis(self):
        """T-M6-2：按分析取最新版本（面试准备读简历正文入口），含岗位信息。"""
        from app.tools import db_resume_version

        row = {
            "id": 6,
            "user_id": 1,
            "job_id": None,
            "job_analysis_id": 10,
            "version_no": 2,
            "resume_markdown": "MD",
            "ana_company": "C",
            "ana_position": "P",
        }
        with (
            patch("app.tools.db_resume_version._ensure_resume_version_table"),
            patch("app.tools.db_resume_version.query_one", return_value=row) as mock_q,
        ):
            got = db_resume_version.get_latest_resume_version(1, 10)
        sql, params = mock_q.call_args[0]
        assert "job_analysis_id=%s" in sql
        assert "LIMIT 1" in sql
        assert params == (1, 10)
        assert got["company"] == "C"
        assert got["position"] == "P"
        assert got["job_analysis_id"] == 10

        with (
            patch("app.tools.db_resume_version._ensure_resume_version_table"),
            patch("app.tools.db_resume_version.query_one", return_value=None),
        ):
            assert db_resume_version.get_latest_resume_version(1, 10) is None

    def test_get_selected_resume_version_prefers_single_select(self):
        """T-M6-7：单选优先——selected_for_application=1 按 version_no DESC 取最新。"""
        from app.tools import db_resume_version

        row = {
            "id": 8,
            "user_id": 1,
            "job_analysis_id": 10,
            "version_no": 3,
            "resume_markdown": "# 已选",
            "selected_for_application": 1,
        }
        with (
            patch("app.tools.db_resume_version._ensure_resume_version_table"),
            patch("app.tools.db_resume_version.query_one", return_value=row) as mock_q,
            patch(
                "app.tools.db_resume_version.get_latest_resume_version"
            ) as mock_latest,
        ):
            got = db_resume_version.get_selected_resume_version(1, 10)
        sql, params = mock_q.call_args[0]
        assert "v.user_id=%s" in sql
        assert "v.job_analysis_id=%s" in sql
        assert "selected_for_application=1" in sql
        assert "ORDER BY v.version_no DESC, v.id DESC LIMIT 1" in sql
        assert params == (1, 10)
        assert got["id"] == 8
        assert got["resume_markdown"] == "# 已选"
        mock_latest.assert_not_called()

    def test_get_selected_resume_version_falls_back_to_latest(self):
        """T-M6-7：无单选 → 回落 get_latest_resume_version（单选优先、无单选取最新）。"""
        from app.tools import db_resume_version

        with (
            patch("app.tools.db_resume_version._ensure_resume_version_table"),
            patch("app.tools.db_resume_version.query_one", return_value=None),
            patch(
                "app.tools.db_resume_version.get_latest_resume_version",
                return_value={"id": 5, "version_no": 1},
            ) as mock_latest,
        ):
            got = db_resume_version.get_selected_resume_version(1, 10)
        assert got["id"] == 5
        mock_latest.assert_called_once_with(1, 10)

    def test_get_selected_resume_version_none_when_no_versions(self):
        """T-M6-7：单选与最新均无 → None。"""
        from app.tools import db_resume_version

        with (
            patch("app.tools.db_resume_version._ensure_resume_version_table"),
            patch("app.tools.db_resume_version.query_one", return_value=None),
            patch(
                "app.tools.db_resume_version.get_latest_resume_version",
                return_value=None,
            ),
        ):
            assert db_resume_version.get_selected_resume_version(1, 10) is None

    def test_get_selected_resume_version_scoped_to_owner(self):
        """T-M6-7：越权——WHERE 收口 user_id，他用户选中行不可见 → None。"""
        from app.tools import db_resume_version

        with (
            patch("app.tools.db_resume_version._ensure_resume_version_table"),
            patch("app.tools.db_resume_version.query_one", return_value=None) as mock_q,
            patch(
                "app.tools.db_resume_version.get_latest_resume_version",
                return_value=None,
            ),
        ):
            assert db_resume_version.get_selected_resume_version(2, 10) is None
        sql, params = mock_q.call_args[0]
        assert "v.user_id=%s" in sql
        assert params == (2, 10)

    def test_update_only_provided_fields(self):
        from app.tools import db_resume_version

        with (
            patch("app.tools.db_resume_version._ensure_resume_version_table"),
            patch(
                "app.tools.db_resume_version.get_resume_version",
                return_value={"id": 5, "user_id": 1},
            ),
            patch("app.tools.db_resume_version.execute", return_value=1) as mock_exec,
        ):
            result = db_resume_version.update_resume_version(
                5, user_id=1, resume_markdown="# 新内容"
            )
        assert result == {"id": 5, "user_id": 1}
        sql, params = mock_exec.call_args[0]
        assert "resume_markdown=%s" in sql
        assert "version_name" not in sql
        assert "sections" not in sql
        assert params == ("# 新内容", 5)

    def test_update_without_ownership_returns_none(self):
        from app.tools import db_resume_version

        with (
            patch("app.tools.db_resume_version._ensure_resume_version_table"),
            patch("app.tools.db_resume_version.get_resume_version", return_value=None),
            patch("app.tools.db_resume_version.execute") as mock_exec,
        ):
            assert (
                db_resume_version.update_resume_version(
                    404, user_id=1, version_name="x"
                )
                is None
            )
        mock_exec.assert_not_called()

    def test_delete_requires_ownership(self):
        from app.tools import db_resume_version

        with (
            patch("app.tools.db_resume_version._ensure_resume_version_table"),
            patch("app.tools.db_resume_version.execute", return_value=1) as mock_exec,
        ):
            assert db_resume_version.delete_resume_version(5, user_id=1) is True
        sql, params = mock_exec.call_args[0]
        assert "DELETE FROM resume_version" in sql
        assert "user_id=%s" in sql
        assert params == (5, 1)

    def test_delete_not_owned_returns_false(self):
        from app.tools import db_resume_version

        with (
            patch("app.tools.db_resume_version._ensure_resume_version_table"),
            patch("app.tools.db_resume_version.execute", return_value=0),
        ):
            assert db_resume_version.delete_resume_version(404, user_id=1) is False

    def test_set_current_clears_others_in_single_statement(self):
        """RESUME_SPEC §11 单选：同岗清其他，单条 UPDATE 原子完成。"""
        from app.tools import db_resume_version

        with (
            patch("app.tools.db_resume_version._ensure_resume_version_table"),
            patch(
                "app.tools.db_resume_version.get_resume_version",
                return_value={"id": 7, "job_id": 9, "selected_for_application": True},
            ),
            patch("app.tools.db_resume_version.execute", return_value=3) as mock_exec,
        ):
            result = db_resume_version.set_current_resume_version(7, user_id=1)
        assert result["selected_for_application"] is True
        sql, params = mock_exec.call_args[0]
        assert "IF(id=%s, 1, 0)" in sql
        assert "job_id <=> %s" in sql
        assert params == (7, 1, 9)

    def test_set_current_without_ownership_returns_none(self):
        from app.tools import db_resume_version

        with (
            patch("app.tools.db_resume_version._ensure_resume_version_table"),
            patch("app.tools.db_resume_version.get_resume_version", return_value=None),
            patch("app.tools.db_resume_version.execute") as mock_exec,
        ):
            assert db_resume_version.set_current_resume_version(404, user_id=1) is None
        mock_exec.assert_not_called()

    def test_list_filters_by_job_and_orders_desc(self):
        from app.tools import db_resume_version

        with (
            patch("app.tools.db_resume_version._ensure_resume_version_table"),
            patch("app.tools.db_resume_version.query_all", return_value=[]) as mock_q,
        ):
            assert db_resume_version.list_resume_versions(1, job_id=9) == []
        sql, params = mock_q.call_args[0]
        assert "v.job_id=%s" in sql
        assert "ORDER BY v.version_no DESC" in sql
        # T-M6-2：JOIN job_analysis 带出 FE 地图显示的岗位信息
        assert "LEFT JOIN job_analysis a" in sql
        assert params == (1, 9)

    def test_row_json_columns_parsed(self):
        """JSON 列（str）读出解析为结构，坏数据回退 None。"""
        from app.tools.db_resume_version import _row_to_version

        out = _row_to_version(
            {
                "id": 1,
                "user_id": 1,
                "job_id": 9,
                "direction_id": None,
                "version_no": 2,
                "version_name": "v2",
                "sections": '[{"type": "summary"}]',
                "resume_markdown": "# md",
                "selected_for_application": 1,
                "source_expression_refs": '["expr-1"]',
                "created_at": None,
                "updated_at": None,
            }
        )
        assert out["sections"] == [{"type": "summary"}]
        assert out["source_expression_refs"] == ["expr-1"]
        assert out["selected_for_application"] is True

        bad = _row_to_version(
            {
                "id": 2,
                "user_id": 1,
                "sections": "{broken",
                "source_expression_refs": None,
            }
        )
        assert bad["sections"] is None
        assert bad["source_expression_refs"] is None
