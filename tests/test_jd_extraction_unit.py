"""JD Extraction 评测纯函数单测（evaluation/jd_metrics.py）。"""

from __future__ import annotations

from evaluation.jd_metrics import (
    DIMENSIONS,
    ErrorRecord,
    ErrorType,
    aggregate_cases,
    classify_case_errors,
    classify_dimension_errors,
    classify_field_errors,
    classify_hidden_errors,
    critical_error_rate,
    dimension_accuracy,
    error_taxonomy_by_field,
    error_taxonomy_summary,
    evaluate_case,
    exact_match_shape,
    field_completeness,
    hidden_requirements_review,
    items_match,
    match_lists,
    match_lists_detail,
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


# ---------------- Error Taxonomy (v0.4) ----------------


def _full_case(
    required=None,
    preferred=None,
    resp=None,
    culture=None,
    dims=None,
    subtext=None,
    salary="",
    location="",
):
    return {
        "required_skills": required or [],
        "preferred_skills": preferred or [],
        "responsibilities": resp or [],
        "culture_keywords": culture or [],
        "dimensions": dims or {f"D{i}": 3 for i in range(1, 9)},
        "subtext": subtext or [],
        "salary": salary,
        "location": location,
    }


def _ats_case(
    required=None,
    preferred=None,
    resp=None,
    culture=None,
    dims=None,
    subtext=None,
    salary=None,
    location=None,
):
    return {
        "required_skills": required or [],
        "preferred_skills": preferred or [],
        "responsibilities": resp or [],
        "culture_keywords": culture or [],
        "dimension_requirements": (
            [{"dimension": d, "level": v} for d, v in (dims or {}).items()]
            if dims
            else []
        ),
        "subtext_decoded": subtext or [],
        "salary": salary,
        "location": location,
    }


def test_match_lists_detail():
    unmatched_pred, unmatched_gold = match_lists_detail(
        ["Python", "Golang"], ["Python", "Redis"]
    )
    assert unmatched_pred == ["Golang"]
    assert unmatched_gold == ["Redis"]


def test_classify_field_errors_missing():
    pred = _ats_case(required=["Python"])
    gold = _full_case(required=["Python", "Redis"])
    errors = classify_field_errors(
        pred["required_skills"], gold["required_skills"], "required_skills", pred, gold
    )
    e1 = [e for e in errors if e.error_type == ErrorType.MISSING]
    assert len(e1) == 1
    assert e1[0].gold_item == "Redis"


def test_classify_field_errors_hallucinated():
    pred = _ats_case(required=["Python", "Golang"])
    gold = _full_case(required=["Python"])
    errors = classify_field_errors(
        pred["required_skills"], gold["required_skills"], "required_skills", pred, gold
    )
    e2 = [e for e in errors if e.error_type == ErrorType.HALLUCINATED]
    assert len(e2) == 1
    assert e2[0].pred_item == "Golang"  # 非跨字段、非变体 → 幻觉


def test_classify_field_errors_misclassified_required_vs_preferred():
    # pred 把 gold.preferred_skills 的内容放进了 required_skills
    pred = _ats_case(required=["Docker"], preferred=[])
    gold = _full_case(required=[], preferred=["Docker"])
    errors = classify_field_errors(
        pred["required_skills"], gold["required_skills"], "required_skills", pred, gold
    )
    e3 = [e for e in errors if e.error_type == ErrorType.MISCLASSIFIED]
    assert len(e3) == 1
    assert e3[0].pred_item == "Docker"  # 跨字段匹配 preferred_skills


def test_classify_field_errors_misclassified_skill_vs_responsibility():
    # pred 把 gold.responsibilities 的内容放进了 required_skills
    pred = _ats_case(required=["性能优化"])
    gold = _full_case(required=[], resp=["性能优化"])
    errors = classify_field_errors(
        pred["required_skills"], gold["required_skills"], "required_skills", pred, gold
    )
    e3 = [e for e in errors if e.error_type == ErrorType.MISCLASSIFIED]
    assert len(e3) == 1


def test_classify_field_errors_normalization():
    # "数据处理与分析" 与 "数据分析与处理" Dice≈0.5 (>0.4 且 <0.6)：
    # items_match 判不中，但归一化变体检测能识别 → E8
    pred = _ats_case(required=["Python", "数据分析与处理"])
    gold = _full_case(required=["Python", "数据处理与分析"])
    errors = classify_field_errors(
        pred["required_skills"], gold["required_skills"], "required_skills", pred, gold
    )
    e8 = [e for e in errors if e.error_type == ErrorType.NORMALIZATION]
    assert len(e8) >= 1


def test_classify_field_errors_abbreviation_requires_lexicon():
    # 缩写（K8s vs Kubernetes）Dice=0，无共享 bigram，自动识别需词表 → 归为 E2 幻觉（诚实标注）
    pred = _ats_case(required=["Python", "K8s"])
    gold = _full_case(required=["Python", "Kubernetes"])
    errors = classify_field_errors(
        pred["required_skills"], gold["required_skills"], "required_skills", pred, gold
    )
    e2 = [e for e in errors if e.error_type == ErrorType.HALLUCINATED]
    assert len(e2) >= 1


def test_classify_field_errors_granularity_oversplit():
    # pred 3 条 vs gold 1 条 → 潜在过度拆分
    pred = _ats_case(required=["Python", "Python 3.12", "Python 高效编码"])
    gold = _full_case(required=["Python"])
    errors = classify_field_errors(
        pred["required_skills"], gold["required_skills"], "required_skills", pred, gold
    )
    e4 = [e for e in errors if e.error_type == ErrorType.GRANULARITY]
    assert len(e4) == 1


def test_classify_dimension_errors_level_mismatch():
    pred = _ats_case(dims={"D1": 4})
    gold = _full_case(dims={"D1": 3})
    errors = classify_dimension_errors(pred, gold)
    e6 = [e for e in errors if e.error_type == ErrorType.DIMENSION]
    assert len(e6) == 1
    assert "D1" in e6[0].field


def test_classify_dimension_errors_missing_dimension():
    pred = _ats_case(dims={})  # 完全没输出维度
    gold = _full_case(dims={"D1": 3, "D2": 4})
    errors = classify_dimension_errors(pred, gold)
    e1 = [e for e in errors if e.error_type == ErrorType.MISSING]
    assert len(e1) == 2  # D1、D2 都被判为缺失


def test_classify_hidden_errors_not_identified():
    pred = _ats_case(subtext=[])
    gold = _full_case(
        subtext=[
            {"surface": "具备良好的业务理解能力", "hidden": "期望从数据中发现业务问题"}
        ]
    )
    errors = classify_hidden_errors(pred, gold)
    e7 = [e for e in errors if e.error_type == ErrorType.HIDDEN]
    assert len(e7) == 1


def test_classify_hidden_errors_hallucinated():
    pred = _ats_case(
        subtext=[
            {"surface_requirement": "熟悉分布式系统", "hidden_meaning": "高并发经验"}
        ]
    )
    gold = _full_case(subtext=[])
    errors = classify_hidden_errors(pred, gold)
    e2 = [e for e in errors if e.error_type == ErrorType.HALLUCINATED]
    assert len(e2) == 1


def test_classify_case_errors_integration():
    pred = _ats_case(
        required=["Python", "Golang"],
        preferred=[],
        dims={"D1": 4},
    )
    gold = _full_case(
        required=["Python", "Redis"],
        preferred=["Golang"],
        dims={"D1": 3},
    )
    errors = classify_case_errors(pred, gold)
    types = {e.error_type.value for e in errors}
    assert "E3" in types  # Golang 被误放进 required
    assert "E6" in types  # D1 等级错


def test_error_taxonomy_summary():
    errors = [
        ErrorRecord(ErrorType.MISSING, "required_skills", gold_item="Redis"),
        ErrorRecord(ErrorType.HALLUCINATED, "required_skills", pred_item="Golang"),
        ErrorRecord(ErrorType.MISCLASSIFIED, "required_skills", pred_item="Docker"),
    ]
    summary = error_taxonomy_summary(errors)
    assert summary["E1"] == 1
    assert summary["E2"] == 1
    assert summary["E3"] == 1
    assert summary["E4"] == 0


def test_error_taxonomy_by_field():
    errors = [
        ErrorRecord(ErrorType.MISSING, "required_skills", gold_item="Redis"),
        ErrorRecord(ErrorType.MISSING, "responsibilities", gold_item="性能优化"),
    ]
    by_field = error_taxonomy_by_field(errors)
    assert by_field["required_skills"]["E1"] == 1
    assert by_field["responsibilities"]["E1"] == 1


# ---------------- Field Completeness + Critical Error Rate (v0.4) ----------------


def test_field_completeness():
    pred = _ats_case(required=["Python"], salary="15-25K")
    gold = _full_case(required=["Python", "Redis"], salary="15-25K")
    fc = field_completeness(pred, gold)
    assert fc["required_skills"] == 0.5  # 2 条 gold，1 条被填充
    assert fc["salary"] == 1.0
    assert fc["location"] == 0.0  # gold 无 location → pred 空 → 0


def test_field_completeness_empty_gold():
    pred = _ats_case(required=["Python"])
    gold = _full_case(required=[])
    fc = field_completeness(pred, gold)
    assert fc["required_skills"] == 1.0  # gold 字段为空 → 视为完整


def test_critical_error_rate_required_preferred_mix():
    errors = [
        ErrorRecord(ErrorType.MISCLASSIFIED, "required_skills", pred_item="Docker"),
        ErrorRecord(ErrorType.MISSING, "required_skills", gold_item="Redis"),
        ErrorRecord(ErrorType.HALLUCINATED, "responsibilities", pred_item="杂项"),
    ]
    assert critical_error_rate(errors) == 0.5  # 2 条 required 字段错误中 1 条是误分类
