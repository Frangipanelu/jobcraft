"""
补充单元测试：简历卡片文本选择 / LLM JSON 解析兜底 / 面试文本截断
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.interview_review import _truncate_text
from app.tools.jobcraft_resume_gen import _get_card_text
from app.tools.llm_json import _extract_json


def _card(**overrides):
    card = {
        "id": 1,
        "title": "项目",
        "raw_text": "原始文本内容",
        "ai_structured": None,
    }
    card.update(overrides)
    return card


# ---------- _get_card_text ----------


def test_card_text_prefers_edited_version():
    card = _card()
    text = _get_card_text(card, versions={1: "用户编辑终稿"})
    assert text == "用户编辑终稿"


def test_card_text_uses_ai_structured_achievements():
    card = _card(
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
    text = _get_card_text(card, versions={})
    assert "重构" in text
    assert "背景A" in text
    assert "行动B" in text
    assert "结果E" in text


def test_card_text_falls_back_to_raw_text():
    text = _get_card_text(_card(), versions={})
    assert "原始文本内容" in text


def test_card_text_prefers_version_even_when_ai_structured_exists():
    card = _card(ai_structured={"achievements": []})
    assert _get_card_text(card, versions={1: "终稿"}) == "终稿"


# ---------- _extract_json ----------


def test_extract_json_parses_pure_json():
    assert _extract_json('{"a": 1}') == '{"a": 1}'


def test_extract_json_extracts_from_code_block():
    text = '```json\n{"a": 1}\n```'
    assert _extract_json(text) == '{"a": 1}'


def test_extract_json_finds_first_braced_object():
    text = '前文 {"k": "v"} 后文'
    assert _extract_json(text) == '{"k": "v"}'


def test_extract_json_returns_none_on_invalid():
    assert _extract_json("没有 JSON") is None


# ---------- _truncate_text ----------


def test_truncate_keeps_short_text():
    assert _truncate_text("hello", 100) == "hello"


def test_truncate_cuts_long_text():
    text = "x" * 50
    out = _truncate_text(text, 20)
    # 设计行为：保留前后各半 + 中间省略号（总长 > max_chars 但内容上下文完整）
    assert "已截断" in out
    assert out.startswith("x")
    assert out.endswith("x")
    assert _truncate_text("", 20) == ""
