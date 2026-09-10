"""确定性证据校验器（Prompt C evidence-first 的后处理，软校验版）。

职责：LLM 输出 ATSProfile 后，用 `evidence_items` 反向校验每个字段值是否有
JD 原文证据支撑，按三档决定去留（确定性、无 LLM 调用）：

- ``ACCEPT``：强支持（归一化相等 / 单边包含 / Dice >= 0.6）→ 保留。
- ``REVIEW``：弱支持（0.4 <= Dice < 0.6，语义相近但非同一实体）→ **保留并标注**
  （软校验：不再"无强证据即删"，避免把 paraphrase 当成幻觉误杀；标注后交由
  `trusted_view` 从信任口径剥离，单列为人工复审队列，不进入 Critical 统计）。
- ``REJECT``：无支撑（Dice < 0.4）→ 丢弃（真正的幻觉/编造）。

兼容性：`reconcile_evidence` 仍返回完整列表字段（ACCEPT+REVIEW 合并），并新增
``review_flagged: {field: [item, ...]}`` 标注 REVIEW 档字段值；评测/下游信任口径
用 `trusted_view(ats)` 剥离 REVIEW 项再计算指标，避免弱支撑项污染 Critical。

作用：把"先证据、后画像"落成可复核的硬约束：压 E2 Hallucinated 的同时，
避免 E1 Missing 暴增（旧版无证据即丢是过滤器，本版是有三态的判错器）。

维度处理（回归直接模型输出 + 证据约束）：只要存在对应 dimension_Dx 证据
即保留该维度 level，不再要求 derived 与 level 字符串精确一致——level 是
推断值而非 JD 原文实体，精确匹配要求既不现实也无意义。

匹配规则（与评测 normalize 语义近似，轻量实现避免 app→evaluation 依赖）：
- 归一化后相等 → ACCEPT
- 单边包含（长度 >= 4）→ ACCEPT
- 兜底 bigram Dice >= 0.6 → ACCEPT；>= 0.4 → REVIEW；否则 REJECT
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

# 三态校验阈值
_ACCEPT_THRESHOLD = 0.6
_REVIEW_THRESHOLD = 0.4

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


def _match_level(value: str, evidence_list: Sequence[Dict[str, str]]) -> float:
    """值与证据集的最佳匹配分数：等价/包含视为 1.0，否则取最大 Dice。"""
    if not value or not evidence_list:
        return 0.0
    best = 0.0
    for ev in evidence_list:
        if values_match(value, ev["derived"]) or values_match(value, ev["span"]):
            return 1.0
        best = max(
            best,
            _dice(value, ev["derived"]),
            _dice(value, ev["span"]),
        )
    return best


def validate_list_item(value: str, evidence_list: Sequence[Dict[str, str]]) -> str:
    """判定单个列表值的三态：ACCEPT / REVIEW / REJECT。

    :param value: 字段值
    :param evidence_list: 该字段的证据 {span, derived} 列表
    :return: "ACCEPT"（强支持）/ "REVIEW"（弱支持）/ "REJECT"（无支撑）
    """
    score = _match_level(value, evidence_list)
    if score >= _ACCEPT_THRESHOLD:
        return "ACCEPT"
    if score >= _REVIEW_THRESHOLD:
        return "REVIEW"
    return "REJECT"


def reconcile_evidence(ats: Dict[str, Any]) -> Dict[str, Any]:
    """按证据软校验 ATSProfile，只 REJECT 无证据支撑的值，REVIEW/ACCEPT 保留。

    列表字段：ACCEPT 与 REVIEW 都保留（REVIEW 写入 ``review_flagged`` 标注），
    仅 REJECT 丢弃（弱相似不再误删）。
    标量字段（salary/location）：值有证据支撑则保留；值缺失/不符时，若证据
    恰好只有唯一取值，则用证据 derived 回填（结果可复核）；多条互不一致才置空。
    维度：只要存在对应 dimension_Dx 证据即保留（level 为推断值，不做字符串匹配）。

    :param ats: ATSProfile dict（含 evidence_items）
    :return: 过滤后的副本 + ``review_flagged``（field → REVIEW 项列表）；
             evidence_items 原样保留
    """
    result = dict(ats)
    evidence_items = list(ats.get("evidence_items") or [])
    evidence = _evidence_by_field(evidence_items)
    review_flagged: Dict[str, List[str]] = {}

    for field in _LIST_FIELDS:
        items = [str(x) for x in (ats.get(field) or [])]
        kept, flagged = [], []
        for x in items:
            tier = validate_list_item(x, evidence.get(field, []))
            if tier == "REJECT":
                continue
            kept.append(x)
            if tier == "REVIEW":
                flagged.append(x)
        result[field] = kept
        if flagged:
            review_flagged[field] = flagged

    result["review_flagged"] = review_flagged

    if "dimension_requirements" in ats:
        kept_dim = []
        for req in ats.get("dimension_requirements") or []:
            d = _get(req, "dimension").strip().upper()
            dim_evidence = evidence.get(f"dimension_{d.lower()}", [])
            # 有证据即保留（level 为从证据推断的值，不做字符串精确匹配）
            if dim_evidence:
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


def trusted_view(ats: Dict[str, Any]) -> Dict[str, Any]:
    """生成信任口径视图：剥离 REVIEW 档标注项，供评测 Critical / 下游可信消费。

    仅去除 ``review_flagged`` 中标注的列表值；ACCEPT 档与标量、维度、subtext
    维持 `reconcile_evidence` 结果不变。防止弱支撑项污染 Critical 统计。

    :param ats: reconcile_evidence 输出（含 review_flagged）
    :return: 不含 REVIEW 项的副本；``review_flagged`` 保留供展示
    """
    result = dict(ats)
    flagged = ats.get("review_flagged") or {}
    for field, items in flagged.items():
        block = {str(x) for x in items}
        result[field] = [x for x in (ats.get(field) or []) if x not in block]
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
