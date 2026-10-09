"""
公司调研 schema 单元测试（T-P7-1：wire 统一包 aspects 层 + 来源铁律强制）。

覆盖：
- CompanyResearchInfo 顶层唯一 aspects 键（wire == model_dump）/ 旧自由字段已删除
- CompanyResearchAspects 六键默认空列表（LLM 漏填不炸，无据维=空列表）
- ResearchItem 逐条字段校验（content 空拒、非法 source_type/sufficiency 拒、
  非 AI推断必须带 source_url 的铁律 validator）
- 每维 max_length=5
- 共享契约 fixture（tests/fixtures/company_research_payload.json）双向一致
- prompt 版本化：v1 仍可加载、v2 可加载且含嵌套契约与关键约束子串
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.prompts import load_prompt
from app.schemas.jobcraft import (
    CompanyResearchAspects,
    CompanyResearchInfo,
    ResearchItem,
)

_ASPECTS = ("overview", "business", "ecosystem", "team", "recent", "reputation")

_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "company_research_payload.json"
)


def _load_fixture() -> dict:
    """读取共享公司调研契约 fixture（BE/FE 同一份）。"""
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _item(**kwargs) -> dict:
    """构造一条合法 ResearchItem 的 dict（默认带来源 URL）。"""
    base = {
        "content": "字节跳动 2012 年成立于北京",
        "source_url": "https://example.com/about",
    }
    base.update(kwargs)
    return base


class TestCompanyResearchWireShape:
    def test_model_dump_top_level_is_exactly_aspects(self):
        """wire 契约：model_dump() 顶层键恰为 {"aspects"}（spec 复审 Critical）。"""
        assert set(CompanyResearchInfo().model_dump().keys()) == {"aspects"}

    def test_six_aspect_keys_default_empty(self):
        """六键固定且默认空列表（LLM 漏填不炸，无据维=空列表）。"""
        for key in _ASPECTS:
            assert getattr(CompanyResearchInfo().aspects, key) == []
            assert getattr(CompanyResearchAspects(), key) == []

    def test_legacy_free_fields_removed(self):
        """D3：basic/funding/news/sources 等旧自由字段不得出现在 wire 上。"""
        dumped = CompanyResearchInfo().model_dump()
        for legacy in ("basic", "funding", "industry", "news", "sources"):
            assert legacy not in dumped
        # business/team 是新旧同名键，但只存在于 aspects 内且形态为条目列表
        assert dumped["aspects"]["business"] == []
        assert dumped["aspects"]["team"] == []
        assert "basic" not in dumped["aspects"]

    @pytest.mark.parametrize("aspect", _ASPECTS)
    def test_max_length_five_per_aspect(self, aspect):
        """矩阵输出约束：每维 ≤5 条，第 6 条校验拒绝。"""
        five = [_item(content=f"条目 {i}") for i in range(5)]
        ok = CompanyResearchInfo(aspects={aspect: five})
        assert len(getattr(ok.aspects, aspect)) == 5

        six = five + [_item(content="第 6 条")]
        with pytest.raises(ValidationError):
            CompanyResearchInfo(aspects={aspect: six})

    def test_partial_fill_keeps_other_defaults(self):
        """只填 business 维（必产），其余维保持默认空列表。"""
        info = CompanyResearchInfo(
            aspects={"business": [_item(content="主营 AI 招聘 SaaS")]}
        )
        assert len(info.aspects.business) == 1
        assert info.aspects.overview == [] and info.aspects.reputation == []


class TestSharedContractFixture:
    def test_fixture_parses_and_round_trips(self):
        """共享 fixture（BE/FE 同一份）：解析通过且 model_dump 与 fixture 语义一致。"""
        fixture = _load_fixture()
        info = CompanyResearchInfo(**fixture)
        dumped = info.model_dump()
        assert set(dumped.keys()) == set(fixture.keys()) == {"aspects"}
        assert (
            set(dumped["aspects"].keys())
            == set(fixture["aspects"].keys())
            == set(_ASPECTS)
        )
        # fixture 条目字段完整 → 逐条 round-trip 相等（契约断即测试红）
        assert dumped == fixture

    def test_fixture_covers_all_source_types(self):
        """fixture 覆盖四种 source_type（含 AI推断无 URL 的合法形态）。"""
        items = [
            item for items in _load_fixture()["aspects"].values() for item in items
        ]
        assert {i["source_type"] for i in items} == {"官方", "新闻", "社交", "AI推断"}
        assert {i["sufficiency"] for i in items} >= {"full", "partial", "insufficient"}


class TestResearchItem:
    def test_valid_item_parses(self):
        item = ResearchItem(
            content="公司 2012 年成立",
            source_url="https://example.com",
            date="2026-01-15",
            source_type="官方",
            sufficiency="full",
        )
        assert item.source_type == "官方"
        assert item.sufficiency == "full"

    def test_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            ResearchItem(content="", source_url="https://example.com")

    def test_missing_content_rejected(self):
        with pytest.raises(ValidationError):
            ResearchItem(source_url="https://example.com")

    @pytest.mark.parametrize("bad", ["来源不明", "official", "OFFICIAL", ""])
    def test_invalid_source_type_rejected(self, bad):
        with pytest.raises(ValidationError):
            ResearchItem(content="x", source_url="https://example.com", source_type=bad)

    @pytest.mark.parametrize("bad", ["ok", "high", ""])
    def test_invalid_sufficiency_rejected(self, bad):
        with pytest.raises(ValidationError):
            ResearchItem(content="x", source_url="https://example.com", sufficiency=bad)

    @pytest.mark.parametrize("source_type", ["官方", "新闻", "社交"])
    def test_non_inference_without_url_rejected(self, source_type):
        """铁律 schema 层强制：非 AI推断条目无 source_url → 拒绝。"""
        with pytest.raises(ValidationError):
            ResearchItem(content="x", source_type=source_type, source_url="")

    @pytest.mark.parametrize("source_type", ["官方", "新闻", "社交"])
    def test_non_inference_with_url_accepted(self, source_type):
        item = ResearchItem(
            content="x", source_type=source_type, source_url="https://example.com"
        )
        assert item.source_type == source_type

    def test_inference_without_url_accepted(self):
        """AI推断条目不需要 URL（漏填不炸，且不冒充官方来源）。"""
        item = ResearchItem(content="公司处于上升期（推断）")
        assert item.source_type == "AI推断"
        assert item.sufficiency == "partial"
        assert item.source_url == ""
        assert item.date == ""

    def test_whitespace_url_does_not_pass_validator(self):
        """空白 URL 不算来源。"""
        with pytest.raises(ValidationError):
            ResearchItem(content="x", source_type="官方", source_url="   ")


class TestPromptVersioning:
    def test_v1_prompt_still_loads(self):
        """版本化红线：v1 不动，仍可按旧占位符加载。"""
        rendered = load_prompt(
            "interview", "company_research", company="字节跳动", search_data="<DATA>"
        )
        assert "<DATA>" in rendered
        assert "字节跳动" in rendered
        assert "sources" in rendered

    def test_v2_prompt_loads_with_same_placeholders(self):
        rendered = load_prompt(
            "interview",
            "company_research",
            version=2,
            company="字节跳动",
            search_data="<DATA>",
        )
        assert "<DATA>" in rendered
        assert "字节跳动" in rendered

    def test_v2_prompt_contains_hard_constraints(self):
        """v2 输出契约（嵌套 aspects）与 6 条硬约束子串（关键约束被测试钉住）。"""
        text = load_prompt(
            "interview",
            "company_research",
            version=2,
            company="X",
            search_data="Y",
        )
        # 嵌套 wire 契约：顶层只有 aspects
        assert '"aspects"' in text
        for key in _ASPECTS:
            assert f'"{key}"' in text
        # 条目形状
        assert "source_url" in text
        assert "source_type" in text
        assert "sufficiency" in text
        # 约束条款
        assert "仅基于检索结果" in text
        assert "不许拿旧知识编" in text
        assert "每维 ≤5 条" in text
        assert "面试桌上" in text
        assert "YYYY-MM-DD" in text
        assert "拿下面试" in text
        assert '"官方"' in text and '"新闻"' in text and '"社交"' in text
        assert '"AI推断"' in text
        assert "空列表" in text
        # 铁律与 validator 兼容：非 AI推断必须带 URL，否则校验拒绝
        assert "必须给出 source_url" in text
        assert "校验拒绝" in text
