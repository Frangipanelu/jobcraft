"""
get_card_render_text 统一消费入口单元测试（§32 Consumer Chain）

优先级：版本链 → 结构化 STAR → raw_text → content → summary → title；
markdown 模式输出简历正文格式，纯文本模式供关键词匹配 / LLM 提示词。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.card_render import get_card_render_text


def _card(**overrides):
    card = {
        "id": 1,
        "title": "标题",
        "raw_text": "",
        "content": "",
        "summary": "",
        "tags": ["Python", "后端"],
        "ai_structured": None,
    }
    card.update(overrides)
    return card


def _star_card():
    return _card(
        ai_structured={
            "summary": "总结",
            "achievements": [
                {
                    "title": "重构",
                    "situation": "背景A",
                    "action": {
                        "main": "行动B",
                        "difficulty": "困难C",
                        "resolution": "解决D",
                    },
                    "result": "结果E",
                }
            ],
        }
    )


# ---------- 版本链 ----------


def test_version_has_highest_priority():
    card = _star_card()
    assert get_card_render_text(card, versions={1: "终稿"}) == "终稿"


# ---------- 结构化 STAR ----------


def test_markdown_renders_star_sections():
    text = get_card_render_text(_star_card(), markdown=True)
    assert "### 重构" in text
    assert "**背景**：背景A" in text
    assert "**行动**：行动B" in text
    assert "**困难**：困难C" in text
    assert "**解决**：解决D" in text
    assert "**结果**：结果E" in text


def test_plain_renders_star_without_labels():
    text = get_card_render_text(_star_card())
    assert "背景A" in text
    assert "行动B" in text
    assert "结果E" in text
    assert "**背景**" not in text
    assert "###" not in text


def test_plain_star_allows_keyword_substring_match():
    text = get_card_render_text(_star_card(), include_tags=True)
    assert "背景A" in text
    assert "Python" in text


def test_empty_achievements_falls_through_to_fallback():
    card = _card(ai_structured={"achievements": []}, raw_text="原始文本")
    assert get_card_render_text(card, markdown=True) == "原始文本"


# ---------- 回退链 ----------


def test_fallback_raw_text():
    card = _card(raw_text="原始文本内容")
    assert get_card_render_text(card) == "原始文本内容"


def test_fallback_content():
    card = _card(content="内容字段")
    assert get_card_render_text(card) == "内容字段"


def test_fallback_summary():
    card = _card(summary="小结字段")
    assert get_card_render_text(card) == "小结字段"


def test_fallback_title():
    card = _card()
    assert get_card_render_text(card) == "标题"


def test_include_tags_appends_markdown_fallback():
    card = _card(raw_text="原始")
    assert get_card_render_text(card, include_tags=True) == "原始 Python 后端"


def test_no_tags_no_text_returns_empty():
    card = _card(tags=[], title="")
    assert get_card_render_text(card) == ""
