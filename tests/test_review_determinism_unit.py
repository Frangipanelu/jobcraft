"""T-EVAL-3 feedback 确定性治理单测。

S4 基线发现：复盘链四 agent 均未显式 temperature（默认 ~0.7）导致同输入
L1 漂移（rev_real_04 四采样 0.77~1.00）；router 少返回分类时该题被静默
置空 feedback。本文件锁定三件套修复：

1. 复盘链四 agent 默认 temperature=0（类常量，BaseAgent 默认仍 None）
2. Router 分类覆盖保证（selected 全集必进 tech/soft 桶，缺口记 warning）
3. AI 缓存 key 纳入 temperature（防旧温度缓存串结果）
"""

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------- temperature=0 默认 ----------


def test_router_passes_temperature_zero(monkeypatch):
    from app.agents.router_agent import RouterAgent

    captured = {}

    def _fake_invoke(model, schema, prompt, **kwargs):
        captured.update(kwargs)
        return schema(classified=[])

    monkeypatch.setattr("app.agents.base_agent.invoke_structured", _fake_invoke)
    RouterAgent().run({"selected_qa_pairs": []})
    assert captured.get("temperature") == 0.0


def test_tech_analyzer_passes_temperature_zero(monkeypatch):
    from app.agents.tech_analyzer import TechAnalyzer

    captured = {}

    def _fake_invoke(model, schema, prompt, **kwargs):
        captured.update(kwargs)
        return schema(analyses=[])

    monkeypatch.setattr("app.agents.tech_analyzer.llm_call", _fake_invoke)
    TechAnalyzer().run(
        {"classified": {"tech": [1], "soft": []}, "selected_qa_pairs": []}
    )
    assert captured.get("temperature") == 0.0


def test_soft_analyzer_passes_temperature_zero(monkeypatch):
    from app.agents.soft_analyzer import SoftAnalyzer

    captured = {}

    def _fake_invoke(model, schema, prompt, **kwargs):
        captured.update(kwargs)
        return schema(analyses=[])

    monkeypatch.setattr("app.agents.soft_analyzer.llm_call", _fake_invoke)
    SoftAnalyzer().run(
        {"classified": {"tech": [], "soft": [1]}, "selected_qa_pairs": []}
    )
    assert captured.get("temperature") == 0.0


def test_gate_passes_temperature_zero(monkeypatch):
    from app.agents.gate_agent import GateAgent

    captured = {}

    def _fake_invoke(model, schema, prompt, **kwargs):
        captured.update(kwargs)
        return schema(issues=[], overall_quality="high")

    monkeypatch.setattr("app.agents.gate_agent.invoke_structured", _fake_invoke)
    GateAgent().run(
        {
            "tech_results": [{"sequence": 1, "score": 80, "dimension": "D1"}],
            "soft_results": [],
        }
    )
    assert captured.get("temperature") == 0.0


def test_base_agent_default_temperature_unchanged(monkeypatch):
    """非复盘链 agent 默认 temperature 保持 None（不改变既有行为）。"""
    from app.agents.base_agent import BaseAgent

    class _DummyOut(__import__("pydantic").BaseModel):
        value: int = 1

    class _Dummy(BaseAgent):
        def _get_output_schema(self):
            return _DummyOut

        def _build_prompt(self, state):
            return "dummy"

    captured = {}

    def _fake_invoke(model, schema, prompt, **kwargs):
        captured.update(kwargs)
        return schema()

    monkeypatch.setattr("app.agents.base_agent.invoke_structured", _fake_invoke)
    _Dummy().run({})
    assert captured.get("temperature") is None


# ---------- Router 分类覆盖保证 ----------


def test_router_fills_unclassified_sequences(monkeypatch):
    from app.agents.router_agent import RouterAgent

    fake = {"classified": [{"sequence": 1, "category": "tech"}]}

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(**fake)

    monkeypatch.setattr("app.agents.base_agent.invoke_structured", _fake_invoke)
    out = RouterAgent().run(
        {
            "selected_qa_pairs": [
                {"sequence": 1, "question_text": "技术题"},
                {"sequence": 2, "question_text": "漏分类题A"},
                {"sequence": 3, "question_text": "漏分类题B"},
            ]
        }
    )
    assert out["classified"]["tech"] == [1]
    assert sorted(out["classified"]["soft"]) == [2, 3]


def test_router_full_coverage_unchanged(monkeypatch):
    from app.agents.router_agent import RouterAgent

    fake = {
        "classified": [
            {"sequence": 1, "category": "tech"},
            {"sequence": 2, "category": "soft"},
        ]
    }

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(**fake)

    monkeypatch.setattr("app.agents.base_agent.invoke_structured", _fake_invoke)
    out = RouterAgent().run(
        {
            "selected_qa_pairs": [
                {"sequence": 1, "question_text": "技术题"},
                {"sequence": 2, "question_text": "行为题"},
            ]
        }
    )
    assert out["classified"] == {"tech": [1], "soft": [2]}


def test_router_empty_llm_output_covers_all_to_soft(monkeypatch):
    """LLM 返回空分类时全部 selected 进 soft 桶（不静默丢题）。"""
    from app.agents.router_agent import RouterAgent

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(classified=[])

    monkeypatch.setattr("app.agents.base_agent.invoke_structured", _fake_invoke)
    out = RouterAgent().run(
        {
            "selected_qa_pairs": [
                {"sequence": 1, "question_text": "题1"},
                {"sequence": 2, "question_text": "题2"},
            ]
        }
    )
    assert sorted(out["classified"]["soft"]) == [1, 2]
    assert out["classified"]["tech"] == []


def test_router_missing_coverage_logs_warning(monkeypatch, caplog):
    import logging

    from app.agents.router_agent import RouterAgent

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(classified=[{"sequence": 1, "category": "tech"}])

    monkeypatch.setattr("app.agents.base_agent.invoke_structured", _fake_invoke)
    with caplog.at_level(logging.WARNING, logger="app.agents.router_agent"):
        RouterAgent().run(
            {
                "selected_qa_pairs": [
                    {"sequence": 1, "question_text": "题1"},
                    {"sequence": 2, "question_text": "题2"},
                ]
            }
        )
    assert any("未覆盖" in r.message for r in caplog.records)


# ---------- analyzer 覆盖缺口告警（不造假） ----------


def _tech_state(seqs):
    return {
        "classified": {"tech": list(seqs), "soft": []},
        "selected_qa_pairs": [
            {
                "sequence": s,
                "question_text": f"技术问题{s}",
                "my_answer": "回答",
                "start_time": "0:10",
            }
            for s in seqs
        ],
    }


def test_tech_analyzer_warns_on_missing_and_does_not_fabricate(monkeypatch, caplog):
    import logging

    from app.agents.tech_analyzer import TechAnalyzer

    fake = {
        "analyses": [
            {
                "sequence": 1,
                "dimension": "D1",
                "level": "L3",
                "intent": "意图",
                "expected_answer": "答案",
                "score": 80,
                "feedback": ["反馈"],
                "suggestions": ["建议"],
            }
        ]
    }

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(**fake)

    monkeypatch.setattr("app.agents.tech_analyzer.llm_call", _fake_invoke)
    with caplog.at_level(logging.WARNING, logger="app.agents.tech_analyzer"):
        out = TechAnalyzer().run(_tech_state([1, 2]))
    assert [a["sequence"] for a in out["tech_results"]] == [1]
    assert any("未产出" in r.message for r in caplog.records)


def test_tech_analyzer_full_coverage_no_warning(monkeypatch, caplog):
    import logging

    from app.agents.tech_analyzer import TechAnalyzer

    fake = {
        "analyses": [
            {
                "sequence": s,
                "dimension": "D1",
                "level": "L3",
                "intent": "意图",
                "expected_answer": "答案",
                "score": 80,
                "feedback": ["反馈"],
                "suggestions": ["建议"],
            }
            for s in (1, 2)
        ]
    }

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(**fake)

    monkeypatch.setattr("app.agents.tech_analyzer.llm_call", _fake_invoke)
    with caplog.at_level(logging.WARNING, logger="app.agents.tech_analyzer"):
        out = TechAnalyzer().run(_tech_state([1, 2]))
    assert len(out["tech_results"]) == 2
    assert not [r for r in caplog.records if "未产出" in r.message]


# ---------- 缓存 key 纳入 temperature ----------


def test_cache_key_includes_temperature(monkeypatch):
    from app.tools import ai_cache, db_ai, llm_json

    class _FakeModel:
        model_name = "glm-test"

    class _SampleOut(__import__("pydantic").BaseModel):
        title: str = "x"

    keys = []
    monkeypatch.setattr(ai_cache, "cache_get", lambda key: keys.append(key) and None)
    monkeypatch.setattr(ai_cache, "cache_set", lambda key, value: None)
    monkeypatch.setattr(db_ai, "create_ai_task", lambda **k: 1)
    monkeypatch.setattr(db_ai, "complete_ai_task", lambda **k: None)
    monkeypatch.setattr(
        llm_json,
        "_invoke_with_bind_tools",
        lambda *a, **k: (_SampleOut(), object()),
    )

    llm_json.invoke_structured(_FakeModel(), _SampleOut, "hello", temperature=0.0)
    llm_json.invoke_structured(_FakeModel(), _SampleOut, "hello")

    assert "t0.0" in keys[0]
    assert "tNone" not in keys[1]
    assert keys[0] != keys[1]


def test_cache_key_different_temperatures_differ(monkeypatch):
    from app.tools import ai_cache

    k_none = ai_cache.build_cache_key("f", "m", "h" * 64)
    k_zero = ai_cache.build_cache_key("f", "m", "h" * 64, temperature=0.0)
    k_half = ai_cache.build_cache_key("f", "m", "h" * 64, temperature=0.7)

    assert k_none == "ai:f:m:" + "h" * 64
    assert len({k_none, k_zero, k_half}) == 3
