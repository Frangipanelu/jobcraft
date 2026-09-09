"""
Experience Matching Evaluation 单元测试（无 LLM 依赖，仅 Keyword 与指标计算）。

覆盖：策略生成器（strategies.py）、生成 CLI（generate.py）、
远端 model-agnostic 评估器（run_matching_eval.py）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.datasets import load_cases
from evaluation.fusion import (
    FUSION_MODES,
    fused_score,
    generate_fused,
    local_scores_for_case,
    max_score,
)
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


# ---------- fusion ----------


def test_fused_score_weighted():
    assert fused_score(40.0, 60.0, 0.4, 0.6) == 52.0
    assert fused_score(40.0, 60.0, 0.2, 0.8) == 56.0


def test_fused_score_weights_sum_to_one():
    for mode, local_w, llm_w in FUSION_MODES.values():
        if mode == "max":
            continue
        assert round(local_w + llm_w, 2) == 1.0


def test_max_score_takes_larger():
    assert max_score(30.0, 70.0) == 70.0
    assert max_score(90.0, 70.0) == 90.0


def test_local_scores_for_case_deterministic():
    local_a = local_scores_for_case(_CASE)
    local_b = local_scores_for_case(_CASE)
    assert local_a == local_b
    assert "e1" in local_a and "e2" in local_a
    assert 0.0 <= local_a["e1"] <= 100.0


def test_generate_fused_modes():
    llm_pred = {
        "case_id": "test_001",
        "predictions": [
            {"experience_id": "e1", "label": "high", "score": 50.0},
            {"experience_id": "e2", "label": "irrelevant", "score": 20.0},
        ],
    }
    for mode in FUSION_MODES:
        preds = generate_fused(llm_pred, _CASE, mode)
        assert len(preds) == 2
        for p in preds:
            assert {"experience_id", "label", "score"} == set(p)
            assert 0.0 <= p["score"] <= 100.0


def test_generate_fused_invalid_mode():
    import pytest

    with pytest.raises(ValueError):
        generate_fused({}, _CASE, "unknown")


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


# ---------- v0.2 Chinese benchmark ----------


def test_chinese_dataset_schema_and_mix():
    from evaluation.run_chinese_eval import DATASET_DIFFICULTY_MIX
    from evaluation.datasets import DEFAULT_DATASET

    chinese_path = DEFAULT_DATASET.parent / "chinese_cases.jsonl"
    assert chinese_path.exists()
    cases = load_gold(chinese_path)
    assert len(cases) == 10
    counts: dict[str, int] = {}
    for case in cases:
        assert case["case_id"].startswith("cn_")
        assert case.get("difficulty") in DATASET_DIFFICULTY_MIX
        assert set(case["gold"]["relevance"]) == set(case["gold"]["score"])
        assert set(case["gold"]["relevance"]) == {e["id"] for e in case["experiences"]}
        assert len(case["gold"]["ranking"]) == len(case["experiences"])
        counts[case["difficulty"]] = counts.get(case["difficulty"], 0) + 1
    assert counts == DATASET_DIFFICULTY_MIX


def test_estimate_cost_zero_when_no_tokens():
    from evaluation.run_chinese_eval import estimate_cost

    assert estimate_cost(0, 0) == 0.0


def test_estimate_cost_scales_with_tokens():
    from evaluation.run_chinese_eval import estimate_cost

    # 1M input @ $0.06 + 1M output @ $0.40 = $0.46
    assert estimate_cost(1_000_000, 1_000_000, 0.06, 0.40) == 0.46


def test_usage_collector_counts_non_cached_only():
    from evaluation.run_chinese_eval import UsageCollector

    c = UsageCollector()
    c(
        {
            "feature": "llm_score_match",
            "duration_s": 1.5,
            "from_cache": 0,
            "prompt_tokens": 1000,
            "completion_tokens": 150,
            "total_tokens": 1150,
        }
    )
    c(
        {
            "feature": "llm_score_match",
            "duration_s": 0.0,
            "from_cache": 1,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        }
    )
    snap = c.snapshot()
    assert snap["llm_calls"] == 1
    assert snap["llm_calls_cached"] == 1
    assert snap["total_tokens"] == 1150
    assert snap["estimated_cost_usd"] > 0


def test_produce_hybrid_deterministic():
    from evaluation.datasets import DEFAULT_DATASET
    from evaluation.run_chinese_eval import produce_hybrid

    gold = load_gold(DEFAULT_DATASET)
    llm_preds_static = [
        {
            "case_id": c["case_id"],
            "predictions": [
                {"experience_id": e["id"], "label": "high", "score": 85.0}
                for e in c["experiences"]
            ],
        }
        for c in gold
    ]
    a1 = produce_hybrid(gold, llm_preds_static, "hybrid_a")
    a2 = produce_hybrid(gold, llm_preds_static, "hybrid_a")
    assert a1 == a2
    assert len(a1) == len(gold)
