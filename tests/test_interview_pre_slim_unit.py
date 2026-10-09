"""
prep prompt 公司调研注入瘦身投影单测（T-P7-1 spec 复审 3c）。

新结构（顶层 aspects）注入 prep prompt 前每条只留 content/date/source_type，
URL 不进 prompt；旧结构注入逻辑不动。
"""

import json
from pathlib import Path

from app.tools.interview_pre import _build_interview_prompt, _slim_company_research

_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "company_research_payload.json"
)


def _fixture() -> dict:
    """读取共享公司调研契约 fixture（BE/FE 同一份）。"""
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


class TestSlimCompanyResearch:
    def test_new_structure_projects_only_content_date_source_type(self):
        projected = _slim_company_research(_fixture())
        for items in projected["aspects"].values():
            assert isinstance(items, list)
            for item in items:
                assert set(item.keys()) == {"content", "date", "source_type"}

    def test_projected_contents_and_dates_preserved(self):
        projected = _slim_company_research(_fixture())
        recent = projected["aspects"]["recent"][0]
        assert recent["content"].startswith("发布新一代 AI 编程助手")
        assert recent["date"] == "2026-01-15"
        assert recent["source_type"] == "新闻"

    def test_metadata_keys_outside_aspects_kept(self):
        raw = {**_fixture(), "cached_at": "2026-10-09T00:00:00", "from_cache": False}
        projected = _slim_company_research(raw)
        assert projected["cached_at"] == "2026-10-09T00:00:00"
        assert projected["from_cache"] is False

    def test_legacy_structure_passed_through_unchanged(self):
        legacy = {"basic": {"name": "字节跳动"}, "news": [{"title": "旧新闻"}]}
        assert _slim_company_research(legacy) == legacy


class TestBuildPromptCompanySection:
    def test_prompt_contains_projected_items_without_urls(self):
        prompt = _build_interview_prompt(
            round_type="技术面",
            position="AI 产品经理",
            company="字节跳动",
            jd_text="JD",
            cards=[],
            dimension_requirements=[],
            company_research=_fixture(),
        )
        # 投影后的句子进 prompt
        assert "发布新一代 AI 编程助手" in prompt
        assert "主营抖音、今日头条" in prompt
        # URL / sufficiency 不进 prompt（瘦身投影）
        assert '"source_url"' not in prompt
        assert '"sufficiency"' not in prompt
        # 截断上限仍为 3000（注入段落不无限膨胀）
        assert "公司调研信息" in prompt

    def test_legacy_company_research_still_injected_verbatim(self):
        legacy = {"basic": {"name": "字节跳动", "website": "https://bytedance.com"}}
        prompt = _build_interview_prompt(
            round_type="技术面",
            position="AI 产品经理",
            company="字节跳动",
            jd_text="JD",
            cards=[],
            dimension_requirements=[],
            company_research=legacy,
        )
        assert '"website": "https://bytedance.com"' in prompt
