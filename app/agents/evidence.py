"""确定性证据校验器（Prompt C evidence-first 的后处理）。

职责：LLM 输出 ATSProfile 后，用 `evidence_items` 反向校验每个字段值是否有
JD 原文证据支撑，**无证据的值一律丢弃**（确定性、无 LLM 调用）。

作用：把"先证据、后画像"落成可复核的硬约束，直接压低 E2 Hallucinated 类错误；
同时暴露"无证据即判缺失"的 Recall 代价，供评测对照。

匹配规则（与评测 normalize 语义近似，轻量实现避免 app→evaluation 依赖）：
- 归一化后相等 → 支撑
- 单边包含（长度 >= 4）→ 支撑
- 兜底 bigram Dice >= 0.6 → 支撑
"""

from typing import Any, Dict, List, Sequence

_EV_SUPPORTED_FIELDS = {
    "required_skills",
    "preferred_skills",
    "responsibilities",
    "culture_keywords",
    "key_metrics",
    "dimension_d1",
    "dimension_d2",
    "dimension_d3",
    "dimension_d4",
    "dimension_d5",
    "dimension_d6",
    "dimension_d7",
    "dimension_d8",
    "salary",
    "location",
    "subtext",
}

# 直接按 evidence_items 过滤的列表字段
_LIST_FIELDS = [
    "required_skills",
    "preferred_skills",
    "responsibilities",
    "culture_keywords",
    "key_metrics",
]


def _get(item: Any, key: str, default: str = "") -> str:
    """兼容 EvidenceItem(pydantic) 与 dict 两种输入。"""
    if isinstance(item, dict):
        return str(item.get(key) or default)
    return str(getattr(item, key, default) or default)


def normalize(text: str) -> str:
    """归一化：小写、去标点空白，保留中英文与数字。"""
    if not text:
        return ""
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _dice(a: str, b: str) -> float:
    """bigram Dice 系数。"""
    a, b = normalize(a), normalize(b)
    if a == b:
        return 1.0
    ba = {a[i : i + 2] for i in range(len(a) - 1)}
    bb = {b[i : i + 2] for i in range(len(b) - 1)}
    if not ba or not bb:
        return 1.0 if (a in b or b in a) else 0.0
    return 2 * len(ba & bb) / (len(ba) + len(bb))


def values_match(a: str, b: str, *, threshold: float = 0.6) -> bool:
    """判断两个文本是否为同一实体（证据支撑判定）。"""
    if not a or not b:
        return False
    na, nb = normalize(a), normalize(b)
    if na == nb:
        return True
    if len(na) >= 4 and na in nb:
        return True
    if len(nb) >= 4 and nb in na:
        return True
    return _dice(na, nb) >= threshold


def _evidence_by_field(
    evidence_items: Sequence[Any],
) -> Dict[str, List[Dict[str, str]]]:
    """按 field 组织证据 {span, derived} 列表。"""
    out: Dict[str, List[Dict[str, str]]] = {}
    for item in evidence_items:
        field = _get(item, "field").strip().lower()
        if field not in _EV_SUPPORTED_FIELDS:
            continue
        out.setdefault(field, []).append(
            {"span": _get(item, "span"), "derived": _get(item, "derived")}
        )
    return out


def _evidenced_by_derived(value: str, evidence_list: Sequence[Dict[str, str]]) -> bool:
    """字段值是否被任一证据的 derived 支撑。"""
    return any(values_match(value, ev["derived"]) for ev in evidence_list)


def _evidenced_by_span(value: str, evidence_list: Sequence[Dict[str, str]]) -> bool:
    """字段值是否被任一证据的 span（原文）支撑。"""
    return any(values_match(value, ev["span"]) for ev in evidence_list)


def reconcile_evidence(ats: Dict[str, Any]) -> Dict[str, Any]:
    """按证据过滤 ATSProfile，丢弃无证据支撑的字段值。

    列表字段：只能保留有证据支撑的条目。
    标量字段（salary/location）：值有证据支撑则保留；值缺失/不符时，若证据
    恰好只有唯一取值，则用证据 derived 回填（结果可复核）；多条互不一致才置空。
    维度：level 必须被其一 dimension_Dx 证据支撑。

    :param ats: ATSProfile dict（含 evidence_items）
    :return: 过滤后的副本；evidence_items 原样保留
    """
    result = dict(ats)
    evidence_items = list(ats.get("evidence_items") or [])
    evidence = _evidence_by_field(evidence_items)

    for field in _LIST_FIELDS:
        items = [str(x) for x in (ats.get(field) or [])]
        result[field] = [
            x for x in items if _evidenced_by_derived(x, evidence.get(field, []))
        ]

    if "dimension_requirements" in ats:
        kept_dim = []
        for req in ats.get("dimension_requirements") or []:
            d = _get(req, "dimension").strip().upper()
            dim_evidence = evidence.get(f"dimension_{d.lower()}", [])
            level = _get(req, "level")
            if dim_evidence and _evidenced_by_derived(level, dim_evidence):
                kept_dim.append(req)
        result["dimension_requirements"] = kept_dim

    for field in ("salary", "location"):
        ev_derived = [e["derived"] for e in evidence.get(field, [])]
        if not ev_derived:
            result[field] = None
            continue
        value = ats.get(field)
        if value is not None and _evidenced_by_derived(
            str(value), evidence.get(field, [])
        ):
            result[field] = str(value)
            continue
        # 值缺失或与证据不符：若证据恰为单一且明确的取值，则用证据回填（结果仍可复核）。
        distinct = list(dict.fromkeys(ev_derived))
        if len(distinct) == 1:
            result[field] = distinct[0]
            continue
        # 多条互不一致 → 无法确定，置空
        result[field] = None

    sub_items = []
    for item in ats.get("subtext_decoded") or []:
        surface = _get(item, "surface_requirement")
        hidden = _get(item, "hidden_meaning")
        sub_ok = any(
            values_match(surface, ev["span"])
            or values_match(hidden, ev["span"])
            or values_match(hidden, ev["derived"])
            for ev in evidence.get("subtext", [])
        )
        if sub_ok:
            sub_items.append(item)
    result["subtext_decoded"] = sub_items

    return result


def coverage_stats(ats: Dict[str, Any]) -> Dict[str, Any]:
    """统计证据覆盖情况（供评测/报告展示）。

    :param ats: ATSProfile dict（含 evidence_items）
    :return: {"evidence_total", "sourced_fields", "dropped_values"}
    """
    evidence_items = list(ats.get("evidence_items") or [])
    evidence = _evidence_by_field(evidence_items)
    recon = reconcile_evidence(ats)
    dropped = 0
    for field in _LIST_FIELDS:
        dropped += len(list(ats.get(field) or [])) - len(list(recon.get(field) or []))
    return {
        "evidence_total": len(evidence_items),
        "sourced_fields": sorted(evidence.keys()),
        "dropped_values": dropped,
    }
