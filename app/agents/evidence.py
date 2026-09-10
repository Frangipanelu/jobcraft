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
import re

_EDU_PATTERNS = (
    re.compile(r"统招|全日制|专升本"),
    re.compile(
        r"(本科|硕士|博士|专科|大专|研究生)(?:及以上|及以下|或以上|以上|学位|学历)?"
    ),
    re.compile(r"学历|学位"),
    re.compile(r"相关专业|专业背景|对口专业"),
    re.compile(r"应届(?:生)?毕业|高校应届"),
)

_YEARS_RE = re.compile(
    r"(\d+|[一二三四五六七八九十两])\s*年\s*(以上|及以上|左右|起)?"
    r"[^，。；、]{0,14}?(经验|经历)"
)

# 本体归位扫描的列表字段（学历/年限只可能混入技能类字段）
_ONTOLOGY_FIELDS = ("required_skills", "preferred_skills")

# —— Responsibilities 独立判定（Issue：P0，Skill↔Responsibility 边界混淆）——
# 能力表述动词（capability 开头 → Skill）
_CAPABILITY_VERBS = (
    "熟悉", "精通", "掌握", "熟练", "了解", "具备", "拥有", "理解",
    "深入理解", "熟悉并使用", "能熟练",
)
# 动作/职责表述动词（action 开头 → Responsibility）
_ACTION_VERBS = (
    "负责", "主导", "参与", "设计", "开发", "搭建", "构建", "维护", "优化",
    "推动", "制定", "跟进", "协调", "管理", "落地", "执行", "支持", "把控",
    "交付", "保障", "评估", "调研", "分析", "梳理", "沉淀", "培训", "指导",
    "监督", "验收", "重构", "建设", "实施", "规划", "推进",
)


def classify_sentence_role(sentence: str) -> str:
    """独立判定一句话属于 Responsibility 还是 Skill（确定性词表，无 LLM）。

    规则（Issue 3 独立判定要件）：
    - 以能力动词开头（熟悉/精通/掌握…）→ ``skill``
    - 以动作动词开头（负责/主导/设计…）→ ``responsibility``
    - 其余（无动词的名词/工具/领域短语）→ ``ambiguous``

    仅"动词开头"是高精度判据：名词短语双向都有歧义（"MySQL 调优"既可能
    是职责态也可能是能力态），不做确定性搬移。``ambiguous`` 由
    `reclassify_claims` 原位保留。

    :param sentence: 待分类句子
    :return: "responsibility" | "skill" | "ambiguous"
    """
    head = sentence.strip()[:6]
    for v in _CAPABILITY_VERBS:
        if head.startswith(v):
            return "skill"
    for v in _ACTION_VERBS:
        if head.startswith(v):
            return "responsibility"
    return "ambiguous"


def reclassify_claims(ats: Dict[str, Any]) -> Dict[str, Any]:
    """按独立判定规则纠正 responsibilities ↔ required_skills 的错位（确定性）。

    模型倾向把能力句（"熟悉Docker"）写进 responsibilities，把动作句
    （"负责系统性能优化"）写进 required_skills（E3 MISCLASSIFIED 的头号来源）。
    仅搬移动词开头的高置信条目：能力动词开头 → required_skills；动作动词开头
    → responsibilities；无动词名词短语（ambiguous）原位保留。不新增/删除条目。

    :param ats: ATSProfile dict
    :return: 搬移后的新 dict
    """
    result = dict(ats)
    skills_to_res: List[str] = []
    res_kept: List[str] = []
    for x in ats.get("responsibilities") or []:
        if classify_sentence_role(str(x)) == "skill":
            skills_to_res.append(str(x))
        else:
            res_kept.append(str(x))
    res_to_skills: List[str] = []
    skill_kept: List[str] = []
    for x in ats.get("required_skills") or []:
        if classify_sentence_role(str(x)) == "responsibility":
            res_to_skills.append(str(x))
        else:
            skill_kept.append(str(x))
    result["responsibilities"] = res_kept + res_to_skills
    result["required_skills"] = skill_kept + skills_to_res
    return result

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


# 技能/动作动词：残留中出现则视为"技能+本体"混合条目，不动
_SKILL_VERBS = (
    "熟悉",
    "掌握",
    "精通",
    "负责",
    "开发",
    "设计",
    "维护",
    "使用",
    "搭建",
    "熟练",
    "编写",
    "调优",
)
# 年限短语的"方向词"残渣（归位后应清空）
_ROLE_DIRECTION_RE = re.compile(
    r"(相关|后端|前端|全栈|软件|设计|算法|测试|运维|架构|大数据|数据|工作|从业|项目|开发)+"
)
# 学历/年限短语的尾缀残渣（整体归位后应清空）
_CLAIM_TRAILER_RE = re.compile(
    "(优先|加分项|加分|及以上|及以下|或以上|以上|左右|等|之类)+$"
)
_CLAIM_CONNECTOR_RE = re.compile(r"[\s，。；、·（）：:；()/]+")


def _claim_remainder(text: str, patterns: Sequence[re.Pattern]) -> str:
    """去掉文本中被 patterns 命中的片段，返回剩余内容（归一化）。

    :param text: 待检条目
    :param patterns: 本体类短语（学历/年限）正则
    :return: 移除命中片段及尾缀残渣后归一化的剩余文本；空表示"整条都是本体短语"
    """
    out = text
    for pat in patterns:
        out = pat.sub("", out)
    out = _CLAIM_TRAILER_RE.sub("", _CLAIM_CONNECTOR_RE.sub("", out))
    return normalize(out)


def _is_education_claim(item: str) -> bool:
    """判断条目是否为学历/专业门槛短语（可整条归位 education）。

    先要求至少命中一个学历关键词（避免"前端架构"这类 4 字技能误判），
    再允许"计算机""数学"等短学科主语残留（≤ 4 字且无技能动词）。
    """
    if not any(p.search(item) for p in _EDU_PATTERNS):
        return False
    residue = _claim_remainder(item, _EDU_PATTERNS)
    if not residue:
        return True
    return len(residue) <= 4 and not any(v in residue for v in _SKILL_VERBS)


def _is_years_claim(item: str) -> bool:
    """判断条目是否为工作年限门槛短语（可整条归位 years_of_experience）。"""
    m = _YEARS_RE.search(item)
    if not m:
        return False
    out = item[: m.start()] + item[m.end() :]
    out = _CLAIM_TRAILER_RE.sub("", _CLAIM_CONNECTOR_RE.sub("", out))
    residue = _ROLE_DIRECTION_RE.sub("", normalize(out))
    return not residue


def _merge_free_text(existing: Any, claims: List[str]) -> str:
    """合并自由文本字段（education/years_of_experience），逗号分隔并去重。"""
    parts: List[str] = []
    if existing:
        parts.append(str(existing))
    seen = set()
    for claim in claims:
        if claim not in seen:
            seen.add(claim)
            parts.append(claim)
    return "；".join(parts) if parts else str(existing or "")


def split_ontology_claims(ats: Dict[str, Any]) -> Dict[str, Any]:
    """确定性本体归位：把混入技能字段的学历/年限门槛移回 ATSProfile 自有字段。

    背景：v3 精简 prompt 丢失 education / years_of_experience 归因指令后，模型把
    "统招本科及以上学历""3年以上后端开发经验""计算机相关专业"等门槛短语塞进
    required_skills / preferred_skills（本体错误，非幻觉）。

    规则（无 LLM，纯正则，保守优先）：
    - 条目整体为学历/专业短语（去除命中片段后无剩余）→ 移入 ``education``
    - 条目整体为"N年以上XX经验"短语 → 移入 ``years_of_experience``
    - 混合短语（如"熟悉Java，统招本科以上"）保持原位，交由 prompt 修复
    - 不修改 evidence_items；返回副本

    :param ats: ATSProfile dict
    :return: 归位后的新 dict（education / years_of_experience 合并 FreeText）
    """
    result = dict(ats)
    seen_edu: List[str] = []
    seen_years: List[str] = []

    for field in _ONTOLOGY_FIELDS:
        items = [str(x) for x in (ats.get(field) or [])]
        kept = []
        for x in items:
            if _is_education_claim(x):
                if x not in seen_edu:
                    seen_edu.append(x)
                continue
            if _is_years_claim(x):
                if x not in seen_years:
                    seen_years.append(x)
                continue
            kept.append(x)
        result[field] = kept

    if seen_edu:
        result["education"] = _merge_free_text(ats.get("education"), seen_edu)
    if seen_years:
        result["years_of_experience"] = _merge_free_text(
            ats.get("years_of_experience"), seen_years
        )
    return result


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
