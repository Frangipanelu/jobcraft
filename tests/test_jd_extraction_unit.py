"""JD Extraction 评测纯函数单测（evaluation/jd_metrics.py）。"""

from __future__ import annotations

from evaluation.jd_metrics import (
    DIMENSIONS,
    aggregate_cases,
    dimension_accuracy,
    evaluate_case,
    exact_match_shape,
    hidden_requirements_review,
    items_match,
    match_lists,
    normalize,
    prf,
)


def test_normalize():
    assert normalize("REST API") == "restapi"
    assert normalize("25-40K·14薪") == "2540k14薪"
    assert normalize("  Python ") == "python"
    assert normalize("") == ""


def test_items_match_exact_and_variant():
    assert items_match("Python", "python")
    assert items_match("REST API", "RESTful API")  # Dice 高相似


def test_items_match_substring():
    assert items_match("数据可视化", "数据可视化工具")  # 多词 vs 单段包含
    assert items_match("PowerBI", "数据可视化") is not True


def test_items_match_abbrev():
    # 缩写（K8s vs Kubernetes）不做模糊匹配，属未命中
    assert items_match("Kubernetes", "K8s") is not True


def test_match_lists():
    tp, fp, fn = match_lists(
        ["Python", "Redis", "Golang"], ["Python", "redis", "MySQL"]
    )
    assert tp == 2
    assert fp == 1
    assert fn == 1


def test_prf():
    p, r, f = prf(6, 4, 2)
    assert round(p, 4) == 0.6
    assert round(r, 4) == 0.75
    assert round(f, 4) == 0.6667


def test_dimension_accuracy_full_hits():
    gold = {"D1": 4, "D2": 3, "D3": 4, "D4": 4, "D5": 4, "D6": 3, "D7": 3, "D8": 3}
    pred = [
        {"dimension": f"D{i}", "level": gold[f"D{i}"], "evidence": "x"}
        for i in range(1, 9)
    ]
    acc, hits = dimension_accuracy(gold, pred)
    assert acc == 1.0
    assert all(hits.values())


def test_dimension_accuracy_partial():
    gold = {"D1": 4, "D2": 3}
    pred = [{"dimension": "d1", "level": 4, "evidence": "x"}]
    acc, hits = dimension_accuracy(gold, pred)
    assert hits["D1"] is True
    assert hits["D2"] is False  # 缺失维度视为未命中
    assert acc == 0.125  # 1/8：只有 D1 命中，分母固定为 8 个维度


def test_exact_match_shape():
    assert exact_match_shape("北京", "北京", allow_contain=True)
    assert exact_match_shape("北京", "北京·上海", allow_contain=True)
    assert exact_match_shape("北京", "上海", allow_contain=True) is False
    assert exact_match_shape("25-40K·14薪", "25-40K·14薪", allow_contain=False)
    assert exact_match_shape("15-25K", "", allow_contain=False) is False


def test_hidden_requirements_review():
    gold = [
        {"surface_requirement": "熟悉分布式缓存", "hidden_meaning": "需要高并发经验"},
        {"surface_requirement": "具备良好设计能力", "hidden_meaning": "方案落地能力强"},
    ]
    pred = [
        {
            "surface_requirement": "熟悉分布式缓存与消息队列",
            "hidden_meaning": "要求高并发设计经验",
            "key_ability": "系统设计",
            "how_to_prove": "github",
        }
    ]
    review = hidden_requirements_review(gold, pred)
    assert review["gold_count"] == 2
    assert review["pred_count"] == 1
    assert review["pairs"][0]["matched_pred"] is not None  # 第一条被覆盖
    assert review["pairs"][1]["matched_pred"] is None  # 第二条未命中


def test_evaluate_case_end_to_end():
    ats = {
        "required_skills": ["Python", "Redis", "Golang"],
        "preferred_skills": ["Kubernetes", "Docker"],
        "responsibilities": ["后端开发", "性能优化"],
        "culture_keywords": ["数据驱动"],
        "salary": "25-40K·14薪",
        "location": "北京",
        "dimension_requirements": [
            {"dimension": "D1", "level": 4, "evidence": "精通 Python"},
            {"dimension": "D2", "level": 5, "evidence": ""},
        ],
        "subtext_decoded": [],
    }
    gold = {
        "required_skills": ["Python", "redis", "MySQL"],
        "preferred_skills": ["Docker", "kubernetes"],
        "responsibilities": ["后端开发", "性能优化"],
        "culture_keywords": ["数据驱动"],
        "salary": "25-40K·14薪",
        "location": "北京",
        "dimensions": {
            "D1": 4,
            "D2": 5,
            "D3": 4,
            "D4": 4,
            "D5": 4,
            "D6": 3,
            "D7": 3,
            "D8": 3,
        },
        "subtext": [],
    }
    result = evaluate_case(ats, gold)
    assert result["required_skills"]["precision"] == 2 / 3
    assert result["required_skills"]["recall"] == 2 / 3
    assert result["preferred_skills"]["f1"] == 1.0
    assert result["culture_keywords"]["f1"] == 1.0
    assert result["salary"] is True
    assert result["location"] is True
    assert result["dimension_hits"]["D1"] is True
    assert result["dimension_hits"]["D2"] is True
    assert result["dimension_hits"]["D3"] is False
    assert DIMENSIONS == [f"D{i}" for i in range(1, 9)]


def _dummy_case(**overrides) -> dict:
    """构造一个完整的 evaluate_case 结果 dict（含全部 LIST_FIELDS）。"""
    case = {
        "required_skills": {
            "tp": 2,
            "fp": 0,
            "fn": 0,
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
        },
        "responsibilities": {
            "tp": 2,
            "fp": 0,
            "fn": 0,
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
        },
        "culture_keywords": {
            "tp": 2,
            "fp": 0,
            "fn": 0,
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
        },
        "preferred_skills": {
            "tp": 2,
            "fp": 0,
            "fn": 0,
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
        },
        "dimension_accuracy": 0.9,
        "dimension_hits": {d: True for d in DIMENSIONS},
        "salary": True,
        "location": True,
        "hidden": {
            "surface_coverage": 1.0,
            "pred_count": 1,
            "gold_count": 1,
            "pairs": [],
        },
    }
    case.update(overrides)
    return case


def test_aggregate_prf():
    agg = aggregate_cases([_dummy_case(), _dummy_case()])
    assert round(agg["required_skills"]["precision"], 4) == 1.0  # 4/4
    assert round(agg["required_skills"]["recall"], 4) == 1.0  # 4/4
    assert round(agg["required_skills"]["f1"], 4) == 1.0


def test_aggregate_cases():
    agg = aggregate_cases([_dummy_case(), _dummy_case()])
    assert agg["cases"] == 2
    assert agg["required_skills"]["f1"] == 1.0
    assert agg["dimension_accuracy"] == 0.9  # 平均各 case 的精度
    assert agg["salary"] == (2, 2)
