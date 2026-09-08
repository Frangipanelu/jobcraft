"""
Experience Matching Evaluation 单元测试（无 LLM 依赖，仅 Keyword 与指标计算）。

覆盖：策略生成器（strategies.py）、生成 CLI（generate.py）、
远端 model-agnostic 评估器（run_matching_eval.py）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.datasets import load_cases
from evaluation.generate import generate, load_gold
from evaluation.run_matching_eval import evaluate, macro_f1, ndcg_at_k
from evaluation.strategies import (
    HybridStrategy,
    KeywordStrategy,
    get_strategy,
    score_to_relevance,
)

_CASE = {
    "case_id": "test_001",
    "job": {
        "title": "Backend Engineer",
        "requirements": ["Python", "Redis"],
        "responsibilities": ["build backend services"],
    },
    "experiences": [
        {
            "id": "e1",
            "title": "Backend Service",
            "raw_text": "Built Python FastAPI services and Redis caching.",
        },
        {
            "id": "e2",
            "title": "Frontend Dashboard",
            "raw_text": "Built a React dashboard with TypeScript.",
        },
    ],
    "gold": {
        "relevance": {"e1": "high", "e2": "irrelevant"},
        "score": {"e1": 90, "e2": 10},
        "ranking": ["e1", "e2"],
    },
}


# ---------- score_to_relevance ----------


def test_score_to_relevance_thresholds():
    assert score_to_relevance(85) == "high"
    assert score_to_relevance(60) == "medium"
    assert score_to_relevance(50) == "low"
    assert score_to_relevance(30) == "irrelevant"


# ---------- KeywordStrategy ----------


def test_keyword_high_match():
    case = {
        "job": {
            "title": "Backend Engineer",
            "requirements": ["Python", "Redis"],
        },
        "experiences": [
            {
                "id": "e1",
                "title": "Backend",
                "raw_text": "负责 python 服务开发与 redis 缓存优化",
            }
        ],
    }
    preds = KeywordStrategy().predict_case(case)
    assert len(preds) == 1
    assert preds[0]["experience_id"] == "e1"
    assert preds[0]["score"] >= 80
    assert preds[0]["label"] == "high"


def test_keyword_irrelevant():
    case = {
        "job": {
            "title": "后端",
            "requirements": ["量化交易", "c++"],
        },
        "experiences": [
            {
                "id": "e1",
                "title": "前端",
                "raw_text": "负责前端页面开发",
            }
        ],
    }
    preds = KeywordStrategy().predict_case(case)
    assert preds[0]["label"] == "irrelevant"
    assert preds[0]["score"] < 40


def test_keyword_returns_all_experiences():
    preds = KeywordStrategy().predict_case(_CASE)
    ids = {p["experience_id"] for p in preds}
    assert ids == {"e1", "e2"}


# ---------- get_strategy ----------


def test_get_strategy_valid():
    assert isinstance(get_strategy("keyword"), KeywordStrategy)
    assert isinstance(get_strategy("hybrid"), HybridStrategy)


def test_get_strategy_invalid():
    import pytest

    with pytest.raises(ValueError):
        get_strategy("unknown")


# ---------- generate ----------


def test_generate_output_format():
    preds = generate("keyword", [_CASE])
    assert len(preds) == 1
    assert preds[0]["case_id"] == "test_001"
    assert len(preds[0]["predictions"]) == 2
    for p in preds[0]["predictions"]:
        assert {"experience_id", "label", "score"} == set(p)


def test_load_gold(tmp_path):
    p = tmp_path / "cases.jsonl"
    p.write_text('{"case_id":"match_001"}\n{"case_id":"match_002"}\n', encoding="utf-8")
    cases = load_gold(p)
    assert len(cases) == 2
    assert cases[0]["case_id"] == "match_001"


# ---------- ndcg_at_k ----------


def test_ndcg_at_k_perfect():
    gold_labels = {"e1": "high", "e2": "medium", "e3": "low"}
    assert ndcg_at_k(["e1", "e2", "e3"], ["e1", "e2", "e3"], gold_labels, 3) == 1.0


def test_ndcg_at_k_worst_is_below_one():
    gold_labels = {"e1": "high", "e2": "medium", "e3": "low"}
    val = ndcg_at_k(["e3", "e2", "e1"], ["e1", "e2", "e3"], gold_labels, 3)
    assert 0.0 <= val < 1.0


def test_ndcg_at_k_missing_ideal_is_zero():
    assert ndcg_at_k(["e1"], ["e2"], {"e1": "high", "e2": "high"}, 3) == 0.0


# ---------- macro_f1 ----------


def test_macro_f1_perfect():
    assert macro_f1(["high", "low"], ["high", "low"]) == 1.0


def test_macro_f1_imperfect():
    val = macro_f1(["high", "low"], ["low", "high"])
    assert 0.0 <= val < 1.0


# ---------- evaluate ----------


def test_evaluate_perfect_match():
    gold = [_CASE]
    prediction = {
        "case_id": "test_001",
        "predictions": [
            {"experience_id": "e1", "label": "high", "score": 90},
            {"experience_id": "e2", "label": "irrelevant", "score": 10},
        ],
    }
    result = evaluate(gold, [prediction])
    assert result["accuracy"] == 1.0
    assert result["macro_f1"] == 1.0
    assert result["precision_relevant"] == 1.0
    assert result["recall_relevant"] == 1.0
    assert result["score_mae"] == 0.0
    assert result["ndcg_at_3"] == 1.0
    assert result["cases_evaluated"] == 1.0


def test_evaluate_wrong_all():
    gold = [_CASE]
    prediction = {
        "case_id": "test_001",
        "predictions": [
            {"experience_id": "e1", "label": "irrelevant", "score": 10},
            {"experience_id": "e2", "label": "high", "score": 90},
        ],
    }
    result = evaluate(gold, [prediction])
    assert result["accuracy"] == 0.0
    assert result["precision_relevant"] == 0.0
    assert result["recall_relevant"] == 0.0


# ---------- dataset ----------


def test_dataset_loadable_and_schema_valid():
    cases = load_cases()
    assert len(cases) > 0
    for case in cases:
        assert case["case_id"].startswith("match_")
        assert set(case["gold"]["relevance"]) == set(case["gold"]["score"])
        assert set(case["gold"]["relevance"]) == {e["id"] for e in case["experiences"]}
        for exp_id, label in case["gold"]["relevance"].items():
            assert label in ("high", "medium", "low", "irrelevant")
            assert 0 <= case["gold"]["score"][exp_id] <= 100
