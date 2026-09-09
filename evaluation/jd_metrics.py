"""
JD Extraction Evaluation — 纯函数评测模块（无 LLM 依赖，可直接单测）.

目标：评估 `JdAtsAgent`（JD 原文 → ATSProfile）是否正确抽取岗位要求，
重点不是"写得好不好"，而是"抽得准不准"。

维度（对齐 ATSProfile 字段）：
- required_skills  → Required Skills     Precision / Recall / F1
- responsibilities → Responsibilities    Precision / Recall / F1
- culture_keywords → Keywords            Precision / Recall / F1
- preferred_skills → Soft/Preferred Skills  Precision / Recall / F1
- dimension_requirements → Dimension Accuracy（D1-D8 level 命中率）
- salary / location   → Exact Match
- subtext_decoded     → Hidden Requirements（人工复核，脚本仅输出待审清单）

字符串匹配策略：归一化（小写 + 去标点空格，保留 CJK/字母数字）+ bigram Dice，
并允许"一方包含另一方"视为命中，以容忍 中文/英文 术语变体（如 REST API vs RESTful API）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

# D1-D8 维度编码，供 dimension accuracy 统计
DIMENSIONS = [f"D{i}" for i in range(1, 9)]

# 参与 token 匹配的四个列表字段
LIST_FIELDS = [
    ("required_skills", "required_skills"),
    ("responsibilities", "responsibilities"),
    ("culture_keywords", "culture_keywords"),
    ("preferred_skills", "preferred_skills"),
]

# 标量精确匹配字段
SCALAR_FIELDS = ["salary", "location"]


def normalize(text: str) -> str:
    """归一化：小写、去标点与空白，保留中英文与数字。

    :param text: 原始文本
    :return: 归一化后的紧凑字符串
    """
    if not text:
        return ""
    return re.sub(r"[^\w\u4e00-\u9fa5]", "", text, flags=re.UNICODE).lower()


def _dice(a: str, b: str) -> float:
    """计算两个字符串的 bigram Dice 系数。

    :param a: 归一化字符串
    :param b: 归一化字符串
    :return: [0,1] 相似度；任一侧无 bigram 时返回 1（单字符按包含关系判定）
    """
    if a == b:
        return 1.0
    big = lambda s: {s[i : i + 2] for i in range(len(s) - 1)}  # noqa: E731
    ba, bb = big(a), big(b)
    if not ba or not bb:
        return 1.0 if (a in b or b in a) else 0.0
    return 2 * len(ba & bb) / (len(ba) + len(bb))


def items_match(a: str, b: str, *, threshold: float = 0.6) -> bool:
    """判断两条文本是否视为同一抽取实体。

    :param a: 文本 A
    :param b: 文本 B
    :param threshold: Dice 命中阈值
    :return: True 表示匹配
    """
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # 单边包含（多词 vs 单段，或中文 vs 英文子串）
    if len(na) >= 4 and na in nb:
        return True
    if len(nb) >= 4 and nb in na:
        return True
    return _dice(na, nb) >= threshold


def match_lists(
    pred: Sequence[str], gold: Sequence[str], *, threshold: float = 0.6
) -> Tuple[int, int, int]:
    """贪婪配对统计 tp / fp / fn。

    :param pred: 预测列表
    :param gold: 人工标注列表
    :param threshold: 单个匹配的 Dice 阈值
    :return: (tp, fp, fn)
    """
    tp = 0
    used = [False] * len(gold)
    for p in pred:
        for i, g in enumerate(gold):
            if not used[i] and items_match(p, g, threshold=threshold):
                used[i] = True
                tp += 1
                break
    fp = len(pred) - tp
    fn = len(gold) - tp
    return tp, fp, fn


def prf(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    """由 tp/fp/fn 计算 Precision / Recall / F1。

    :param tp: 真正例
    :param fp: 假正例
    :param fn: 假负例
    :return: (precision, recall, f1)
    """
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def aggregate_prf(triplets: Iterable[Tuple[int, int, int]]) -> Dict[str, float]:
    """聚合多条 case 的 (tp,fp,fn) → micro Precision/Recall/F1。

    :param triplets: 每组 (tp,fp,fn)
    :return: {"precision","recall","f1"}
    """
    tp = fp = fn = 0
    for t, f_p, f_n in triplets:
        tp += t
        fp += f_p
        fn += f_n
    p, r, f = prf(tp, fp, fn)
    return {"precision": p, "recall": r, "f1": f}


def dimension_accuracy(
    gold_dims: Dict[str, int], pred_reqs: Sequence[Dict[str, Any]]
) -> Tuple[float, Dict[str, bool]]:
    """计算 D1-D8 维度 level 命中率。

    :param gold_dims: {D1-D8: gold level 1-5}
    :param pred_reqs: ATSProfile.dimension_requirements 列表 [{"dimension","level",...}]
    :return: (accuracy, per_dim 命中字典 {D1: bool})
    """
    pred_map: Dict[str, int] = {}
    for req in pred_reqs:
        d = str(req.get("dimension", "")).strip().upper()
        if d in DIMENSIONS and d not in pred_map:
            pred_map[d] = int(req.get("level") or 0)
    hits: Dict[str, bool] = {}
    for d in DIMENSIONS:
        if d in gold_dims and d in pred_map:
            hits[d] = pred_map[d] == int(gold_dims[d])
        else:
            hits[d] = False
    correct = sum(1 for v in hits.values() if v)
    return (correct / len(DIMENSIONS), hits)


def exact_match_shape(gold: str, pred: Any, *, allow_contain: bool = True) -> bool:
    """标量字段（salary/location）精确匹配。

    :param gold: 人工标注值
    :param pred: 模型抽取值（可能是 None）
    :param allow_contain: 允许单边包含（JD 常写多城市）
    :return: True 表示命中
    """
    if not pred:
        return False
    ng, np_ = normalize(gold), normalize(str(pred))
    if not ng or not np_:
        return False
    if ng == np_:
        return True
    if allow_contain and (ng in np_ or np_ in ng):
        return True
    return False


def hidden_requirements_review(
    gold_subtexts: Sequence[Dict[str, Any]],
    pred_subtexts: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Hidden Requirements — 供人工复核的输出。

    自动计算：gold 表面要求被预测覆盖的比例（surface coverage）与预测潜台词有效条数；
    逐条映射留给人审。返回 {surface_coverage, pred_count, pairs: [...]}。

    键名兼容：ATSProfile 输出用 surface_requirement/hidden_meaning，
    人工标注数据集用 surface/hidden，二者均接受。
    """
    gold_surfaces = [
        str(s.get("surface_requirement") or s.get("surface") or "").strip()
        for s in gold_subtexts
    ]
    gold_surfaces = [g for g in gold_surfaces if g]
    covered = 0
    for g in gold_surfaces:
        if any(
            items_match(g, p.get("surface_requirement") or p.get("surface") or "")
            for p in pred_subtexts
        ):
            covered += 1
    coverage = covered / len(gold_surfaces) if gold_surfaces else 0.0
    return {
        "surface_coverage": coverage,
        "pred_count": len(pred_subtexts),
        "gold_count": len(gold_surfaces),
        "pairs": [
            {
                "gold_surface": g,
                "matched_pred": next(
                    (
                        p
                        for p in pred_subtexts
                        if items_match(
                            g, p.get("surface_requirement") or p.get("surface") or ""
                        )
                    ),
                    None,
                ),
            }
            for g in gold_surfaces
        ],
    }


def evaluate_case(ats: Dict[str, Any], gold: Dict[str, Any]) -> Dict[str, Any]:
    """对单个 case 计算全部维度的评测结果。

    :param ats: ATSProfile dict（模型输出）
    :param gold: gold 标注 dict
    :return: 该 case 的指标字典 {field: {precision,recall,f1}, dimension_accuracy, ...}
    """
    result: Dict[str, Any] = {}
    for field, attr in LIST_FIELDS:
        pred_items = [str(x) for x in (ats.get(attr) or [])]
        gold_items = [str(x) for x in (gold.get(attr) or [])]
        tp, fp, fn = match_lists(pred_items, gold_items)
        p, r, f = prf(tp, fp, fn)
        result[field] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": p,
            "recall": r,
            "f1": f,
        }

    gold_dims = {k: int(v) for k, v in (gold.get("dimensions") or {}).items()}
    acc, hits = dimension_accuracy(gold_dims, ats.get("dimension_requirements") or [])
    result["dimension_accuracy"] = acc
    result["dimension_hits"] = hits

    for field in SCALAR_FIELDS:
        result[field] = exact_match_shape(str(gold.get(field) or ""), ats.get(field))

    result["hidden"] = hidden_requirements_review(
        gold.get("subtext") or [], ats.get("subtext_decoded") or []
    )
    return result


def aggregate_cases(case_results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """汇编多条 case 结果 → 汇总指标。

    :param case_results: evaluate_case 结果列表
    :return: 汇总 dict（各列表字段 micro PRF + dimension accuracy + 标量命中）
    """
    summary: Dict[str, Any] = {}
    for field, _ in LIST_FIELDS:
        summary[field] = aggregate_prf(
            (r[field]["tp"], r[field]["fp"], r[field]["fn"]) for r in case_results
        )
    dim_correct = sum(float(r["dimension_accuracy"]) for r in case_results)
    summary["dimension_accuracy"] = (
        dim_correct / len(case_results) if case_results else 0.0
    )
    for field in SCALAR_FIELDS:
        hits = [r[field] for r in case_results]
        summary[field] = (sum(hits), len(hits))
    summary["cases"] = len(case_results)
    return summary


# ============================================================
# Error Taxonomy (v0.4)
# ============================================================


class ErrorType(Enum):
    """JD Extraction 错误类型枚举。"""

    MISSING = "E1"  # gold 有，pred 没有
    HALLUCINATED = "E2"  # pred 有，gold 没有
    MISCLASSIFIED = "E3"  # 字段间误分类 (required↔preferred, skill↔responsibility)
    GRANULARITY = "E4"  # 粒度不匹配 (一个 gold 拆成多个 pred，或反之)
    SEMANTIC = "E5"  # 语义理解错误
    DIMENSION = "E6"  # D1-D8 level 判断错误
    HIDDEN = "E7"  # 潜台词未识别
    NORMALIZATION = "E8"  # 同义词 / 缩写 / 格式问题


@dataclass
class ErrorRecord:
    """单条错误记录。"""

    error_type: ErrorType
    field: str  # 字段名 (required_skills / dimension_D1 / subtext_decoded / ...)
    pred_item: Optional[str] = None
    gold_item: Optional[str] = None
    detail: str = ""


def match_lists_detail(
    pred: Sequence[str], gold: Sequence[str], *, threshold: float = 0.6
) -> Tuple[list[str], list[str]]:
    """贪心配对，返回 (unmatched_pred, unmatched_gold)。"""
    used_gold = [False] * len(gold)
    unmatched_pred: list[str] = []
    for p in pred:
        found = False
        for i, g in enumerate(gold):
            if not used_gold[i] and items_match(p, g, threshold=threshold):
                used_gold[i] = True
                found = True
                break
        if not found:
            unmatched_pred.append(p)
    unmatched_gold = [g for i, g in enumerate(gold) if not used_gold[i]]
    return unmatched_pred, unmatched_gold


def _is_cross_field_match(
    item: str, current_attr: str, full_case: Dict[str, Any]
) -> bool:
    """检查 item 是否匹配其他字段中的 gold 项。"""
    for _, attr in LIST_FIELDS:
        if attr == current_attr:
            continue
        other_items = [str(x) for x in (full_case.get(attr) or [])]
        if any(items_match(item, o) for o in other_items):
            return True
    return False


def _is_normalization_variant(
    item: str, other_items: Sequence[str], *, threshold: float = 0.4
) -> bool:
    """检查 item 是否是 other_items 中某项的归一化变体 (Dice >= threshold)。"""
    ni = normalize(item)
    for o in other_items:
        no = normalize(o)
        if ni != no and _dice(ni, no) >= threshold:
            return True
    return False


def classify_field_errors(
    pred_items: Sequence[str],
    gold_items: Sequence[str],
    field: str,
    full_pred: Dict[str, Any],
    full_gold: Dict[str, Any],
) -> list[ErrorRecord]:
    """对单个列表字段分类错误 (E1/E2/E3/E8)。"""
    errors: list[ErrorRecord] = []
    unmatched_pred, unmatched_gold = match_lists_detail(pred_items, gold_items)
    current_attr = dict(LIST_FIELDS)[field]

    for fp in unmatched_pred:
        if _is_cross_field_match(fp, current_attr, full_gold):
            errors.append(
                ErrorRecord(
                    ErrorType.MISCLASSIFIED,
                    field,
                    pred_item=fp,
                    detail=f"'{fp}' matched gold in another field",
                )
            )
        elif _is_normalization_variant(fp, gold_items):
            errors.append(
                ErrorRecord(
                    ErrorType.NORMALIZATION,
                    field,
                    pred_item=fp,
                    detail=f"'{fp}' is normalization variant of a gold item",
                )
            )
        else:
            errors.append(
                ErrorRecord(
                    ErrorType.HALLUCINATED,
                    field,
                    pred_item=fp,
                    detail=f"'{fp}' not in any gold field",
                )
            )

    for fn in unmatched_gold:
        if _is_cross_field_match(fn, current_attr, full_pred):
            errors.append(
                ErrorRecord(
                    ErrorType.MISCLASSIFIED,
                    field,
                    gold_item=fn,
                    detail=f"'{fn}' exists in pred but in wrong field",
                )
            )
        elif _is_normalization_variant(fn, pred_items):
            errors.append(
                ErrorRecord(
                    ErrorType.NORMALIZATION,
                    field,
                    gold_item=fn,
                    detail=f"'{fn}' has normalization variant in pred",
                )
            )
        else:
            errors.append(
                ErrorRecord(
                    ErrorType.MISSING,
                    field,
                    gold_item=fn,
                    detail=f"'{fn}' missing from pred",
                )
            )

    # Granularity heuristic: significant count mismatch
    if len(pred_items) > len(gold_items) * 2 and len(gold_items) > 0:
        errors.append(
            ErrorRecord(
                ErrorType.GRANULARITY,
                field,
                detail=f"Potential over-splitting: pred {len(pred_items)} items vs gold {len(gold_items)} items",
            )
        )
    elif len(gold_items) > len(pred_items) * 2 and len(pred_items) > 0:
        errors.append(
            ErrorRecord(
                ErrorType.GRANULARITY,
                field,
                detail=f"Potential under-splitting: gold {len(gold_items)} items vs pred {len(pred_items)} items",
            )
        )

    return errors


def classify_dimension_errors(
    pred: Dict[str, Any], gold: Dict[str, Any]
) -> list[ErrorRecord]:
    """分类维度错误 (E6)。"""
    errors: list[ErrorRecord] = []
    gold_dims = {k: int(v) for k, v in (gold.get("dimensions") or {}).items()}
    pred_map: Dict[str, int] = {}
    for req in pred.get("dimension_requirements") or []:
        d = str(req.get("dimension", "")).strip().upper()
        if d in DIMENSIONS and d not in pred_map:
            pred_map[d] = int(req.get("level") or 0)

    for d in DIMENSIONS:
        field = f"dimension_{d}"
        if d in gold_dims and d in pred_map:
            if pred_map[d] != gold_dims[d]:
                errors.append(
                    ErrorRecord(
                        ErrorType.DIMENSION,
                        field,
                        pred_item=f"level={pred_map[d]}",
                        gold_item=f"level={gold_dims[d]}",
                        detail=f"{d}: predicted {pred_map[d]}, gold {gold_dims[d]}",
                    )
                )
        elif d in gold_dims and d not in pred_map:
            errors.append(
                ErrorRecord(
                    ErrorType.MISSING,
                    field,
                    gold_item=f"level={gold_dims[d]}",
                    detail=f"{d} missing from prediction",
                )
            )
        elif d not in gold_dims and d in pred_map:
            errors.append(
                ErrorRecord(
                    ErrorType.HALLUCINATED,
                    field,
                    pred_item=f"level={pred_map[d]}",
                    detail=f"{d} not in gold",
                )
            )
    return errors


def classify_hidden_errors(
    pred: Dict[str, Any], gold: Dict[str, Any]
) -> list[ErrorRecord]:
    """分类潜台词错误 (E7)。"""
    errors: list[ErrorRecord] = []
    gold_subtexts = gold.get("subtext") or []
    pred_subtexts = pred.get("subtext_decoded") or []

    gold_surfaces = [
        str(s.get("surface_requirement") or s.get("surface") or "").strip()
        for s in gold_subtexts
    ]
    gold_surfaces = [g for g in gold_surfaces if g]

    pred_surfaces = [
        str(p.get("surface_requirement") or p.get("surface") or "").strip()
        for p in pred_subtexts
    ]
    pred_surfaces = [p for p in pred_surfaces if p]

    for surface in gold_surfaces:
        matched = any(
            items_match(surface, p.get("surface_requirement") or p.get("surface") or "")
            for p in pred_subtexts
        )
        if not matched:
            errors.append(
                ErrorRecord(
                    ErrorType.HIDDEN,
                    "subtext_decoded",
                    gold_item=surface,
                    detail=f"Hidden requirement not identified: {surface}",
                )
            )

    for surface in pred_surfaces:
        matched = any(
            items_match(surface, s.get("surface_requirement") or s.get("surface") or "")
            for s in gold_subtexts
        )
        if not matched:
            errors.append(
                ErrorRecord(
                    ErrorType.HALLUCINATED,
                    "subtext_decoded",
                    pred_item=surface,
                    detail=f"Hidden requirement hallucinated: {surface}",
                )
            )
    return errors


def classify_case_errors(
    pred: Dict[str, Any], gold: Dict[str, Any]
) -> list[ErrorRecord]:
    """对单个 case 分类全部错误。"""
    errors: list[ErrorRecord] = []
    for field, attr in LIST_FIELDS:
        pred_items = [str(x) for x in (pred.get(attr) or [])]
        gold_items = [str(x) for x in (gold.get(attr) or [])]
        errors.extend(classify_field_errors(pred_items, gold_items, field, pred, gold))
    errors.extend(classify_dimension_errors(pred, gold))
    errors.extend(classify_hidden_errors(pred, gold))
    return errors


def error_taxonomy_summary(errors: Sequence[ErrorRecord]) -> Dict[str, int]:
    """按错误类型汇总计数。"""
    summary: Dict[str, int] = {e.value: 0 for e in ErrorType}
    for error in errors:
        summary[error.error_type.value] += 1
    return summary


def error_taxonomy_by_field(errors: Sequence[ErrorRecord]) -> Dict[str, Dict[str, int]]:
    """按字段和错误类型汇总计数。"""
    summary: Dict[str, Dict[str, int]] = {}
    for error in errors:
        fld = error.field
        if fld not in summary:
            summary[fld] = {e.value: 0 for e in ErrorType}
        summary[fld][error.error_type.value] += 1
    return summary


# ============================================================
# Field Completeness + Critical Error Rate (v0.4)
# ============================================================


def field_completeness(pred: Dict[str, Any], gold: Dict[str, Any]) -> Dict[str, float]:
    """计算每字段的完整度 (gold 中有多少比例被 pred 填充)。"""
    result: Dict[str, float] = {}
    for field, attr in LIST_FIELDS:
        pred_items = [str(x) for x in (pred.get(attr) or [])]
        gold_items = [str(x) for x in (gold.get(attr) or [])]
        if not gold_items:
            result[field] = 1.0
            continue
        matched = sum(
            1 for g in gold_items if any(items_match(g, p) for p in pred_items)
        )
        result[field] = matched / len(gold_items)
    for field in SCALAR_FIELDS:
        result[field] = (
            1.0
            if exact_match_shape(str(gold.get(field) or ""), pred.get(field))
            else 0.0
        )
    return result


def critical_error_rate(errors: Sequence[ErrorRecord]) -> float:
    """计算关键错误率 (required_skills / preferred_skills 字段的 E3 占比)。

    关键错误: required ↔ preferred 误分类，对求职决策影响最大。
    """
    critical_fields = {"required_skills", "preferred_skills"}
    critical = 0
    total = 0
    for error in errors:
        if error.field in critical_fields:
            total += 1
            if error.error_type == ErrorType.MISCLASSIFIED:
                critical += 1
    return critical / total if total else 0.0
