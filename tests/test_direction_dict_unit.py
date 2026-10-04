"""方向词典规则匹配单元测试（T-M4-3，零 LLM）。

覆盖：词典结构守卫（防 422 越界）、真词典冒烟、命中/未命中/空文本、
ASCII 大小写归一、合成词典下的计数优先与平手字典序、确定性。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import direction_dict

# JdClassificationPayload 长度上限（越界 → 422，词典侧前置守卫）
_MAX_LEN = {"industry": 100, "product": 200, "scenario": 200, "skills": 500}


class TestDictionaryStructure:
    """词典结构守卫：字段齐全 + 四维不超 payload 上限。"""

    def test_entries_have_name_and_keywords(self):
        assert len(direction_dict._DICTIONARY) >= 10, "词典应有规模化条目"
        for entry in direction_dict._DICTIONARY:
            name = entry.get("name")
            keywords = entry.get("keywords")
            assert isinstance(name, str) and name.strip(), f"缺方向名: {entry}"
            assert isinstance(keywords, list) and keywords, f"{name} 缺 keywords"
            assert all(isinstance(kw, str) and kw.strip() for kw in keywords), (
                f"{name} keywords 须为非空字符串"
            )

    def test_dimensions_within_payload_limits(self):
        for entry in direction_dict._DICTIONARY:
            for dim, max_len in _MAX_LEN.items():
                value = entry.get(dim, "")
                assert isinstance(value, str), f"{entry['name']}.{dim} 须为字符串"
                assert len(value) <= max_len, (
                    f"{entry['name']}.{dim} 长度 {len(value)} 超上限 {max_len}（会 422）"
                )

    def test_dictionary_never_produces_function_or_role(self):
        """Q4 裁决：词典只产 Industry/Product/Scenario/Skills，不产职能/主角色。"""
        assert direction_dict._DIM_FIELDS == (
            "industry",
            "product",
            "scenario",
            "skills",
        )


class TestSuggestRealDictionary:
    """真词典冒烟（确定性，无 I/O）。"""

    def test_cross_border_ecommerce_hits_ecommerce_entry(self):
        hit = direction_dict.suggest_direction("负责跨境电商 GMV 增长与商家运营")
        assert hit["direction_name"] == "电商零售"
        assert hit["industry"] == "电商与零售"
        assert hit["skills"]

    def test_miss_returns_empty(self):
        assert (
            direction_dict.suggest_direction("一段与任何词典条目都无关的描述 xyz") == {}
        )

    def test_empty_or_blank_returns_empty(self):
        assert direction_dict.suggest_direction("") == {}
        assert direction_dict.suggest_direction("   \n\t ") == {}

    def test_ascii_case_insensitive(self):
        assert direction_dict.suggest_direction("Ecommerce platform PM")[
            "direction_name"
        ] == ("电商零售")

    def test_deterministic(self):
        text = "大模型应用产品经理，负责 prompt 设计与模型评测"
        assert direction_dict.suggest_direction(
            text
        ) == direction_dict.suggest_direction(text)


class TestMatchingLogicSynthetic:
    """合成词典下的匹配逻辑（monkeypatch 注入，验证计数/平手/坏数据）。"""

    def test_more_keyword_hits_wins(self, monkeypatch):
        fake = [
            {
                "name": "甲",
                "keywords": ["alpha"],
                "industry": "i1",
                "product": "",
                "scenario": "",
                "skills": "",
            },
            {
                "name": "乙",
                "keywords": ["beta", "gamma"],
                "industry": "i2",
                "product": "",
                "scenario": "",
                "skills": "",
            },
        ]
        monkeypatch.setattr(direction_dict, "_DICTIONARY", fake)
        hit = direction_dict.suggest_direction("alpha beta gamma")
        assert hit["direction_name"] == "乙"
        assert hit["industry"] == "i2"

    def test_tie_prefers_dictionary_order(self, monkeypatch):
        fake = [
            {"name": "先", "keywords": ["x1"], "industry": "a"},
            {"name": "后", "keywords": ["x2"], "industry": "b"},
        ]
        monkeypatch.setattr(direction_dict, "_DICTIONARY", fake)
        assert direction_dict.suggest_direction("x1 x2")["direction_name"] == "先"

    def test_entry_without_keywords_skipped(self, monkeypatch):
        fake = [
            {"name": "坏条目", "keywords": "not-a-list", "industry": "i"},
            {"name": "好条目", "keywords": ["kw"], "industry": "j"},
        ]
        monkeypatch.setattr(direction_dict, "_DICTIONARY", fake)
        assert direction_dict.suggest_direction("kw")["direction_name"] == "好条目"

    def test_zero_hit_returns_empty(self, monkeypatch):
        fake = [{"name": "甲", "keywords": ["alpha"], "industry": "i"}]
        monkeypatch.setattr(direction_dict, "_DICTIONARY", fake)
        assert direction_dict.suggest_direction("omega") == {}
