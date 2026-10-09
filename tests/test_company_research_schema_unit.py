"""
公司调研 schema 单元测试（T-P7-1：6 维 aspect 内层结构化）。

覆盖：
- CompanyResearchInfo 六键默认空列表 / 旧自由字段已删除
- ResearchItem 逐条字段校验（content 空拒、非法 source_type/sufficiency 拒、默认值）
- 每维 max_length=5
- prompt 版本化：v1 仍可加载、v2 可加载且含关键约束子串
"""

import pytest
from pydantic import ValidationError

from app.core.prompts import load_prompt
from app.schemas.jobcraft import CompanyResearchInfo, ResearchItem

_ASPECTS = ("overview", "business", "ecosystem", "team", "recent", "reputation")


def _item(**kwargs) -> dict:
    """构造一条合法 ResearchItem 的 dict。"""
    base = {"content": "字节跳动 2012 年成立于北京"}
    base.update(kwargs)
    return base


class TestCompanyResearchInfoShape:
    def test_six_aspect_keys_default_empty(self):
        """六键固定且默认空列表（LLM 漏填不炸，无据维=空列表）。"""
        info = CompanyResearchInfo()
        for key in _ASPECTS:
            assert getattr(info, key) == []

    def test_legacy_free_fields_removed(self):
        """D3：basic/funding/news/sources 等旧自由字段不得保留。"""
        dumped = CompanyResearchInfo().model_dump()
        for legacy in ("basic", "funding", "industry", "news", "sources"):
            assert legacy not in dumped
        # business/team 是新旧同名键，但形态从自由 dict 变为条目列表
        assert dumped["business"] == []
        assert dumped["team"] == []

    @pytest.mark.parametrize("aspect", _ASPECTS)
    def test_max_length_five_per_aspect(self, aspect):
        """矩阵输出约束：每维 ≤5 条，第 6 条校验拒绝。"""
        five = [_item(content=f"条目 {i}") for i in range(5)]
        ok = CompanyResearchInfo(**{aspect: five})
        assert len(getattr(ok, aspect)) == 5

        six = five + [_item(content="第 6 条")]
        with pytest.raises(ValidationError):
            CompanyResearchInfo(**{aspect: six})

    def test_partial_fill_keeps_other_defaults(self):
        """只填 business 维（必产），其余维保持默认空列表。"""
        info = CompanyResearchInfo(business=[_item(content="主营 AI 招聘 SaaS")])
        assert len(info.business) == 1
        assert info.overview == [] and info.reputation == []


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
            ResearchItem(content="")

    def test_missing_content_rejected(self):
        with pytest.raises(ValidationError):
            ResearchItem(source_url="https://example.com")

    @pytest.mark.parametrize("bad", ["来源不明", "official", "OFFICIAL", ""])
    def test_invalid_source_type_rejected(self, bad):
        with pytest.raises(ValidationError):
            ResearchItem(content="x", source_type=bad)

    @pytest.mark.parametrize("bad", ["ok", "high", ""])
    def test_invalid_sufficiency_rejected(self, bad):
        with pytest.raises(ValidationError):
            ResearchItem(content="x", sufficiency=bad)

    def test_defaults_do_not_fabricate_source(self):
        """漏填不炸，且 source_type 默认取最保守的 AI推断（不冒充官方来源）。"""
        item = ResearchItem(content="推断条目")
        assert item.source_type == "AI推断"
        assert item.sufficiency == "partial"
        assert item.source_url == ""
        assert item.date == ""

    def test_ai_inference_item_needs_no_url(self):
        item = ResearchItem(content="公司处于上升期（推断）", source_type="AI推断")
        assert item.source_url == ""


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
        """v2 输出契约与 6 条硬约束子串（关键约束被测试钉住）。"""
        text = load_prompt(
            "interview",
            "company_research",
            version=2,
            company="X",
            search_data="Y",
        )
        # 6 键结构
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
