"""
Evaluation v0.3 — JD Extraction Benchmark Runner.

评测目标层（用户指定）：
    JD 原文 → JdAtsAgent → ATSProfile

重点：AI 是否正确抽取岗位要求（而非生成质量）。
维度：Required/Preferred Skills、Responsibilities、Keywords、Dimension、
Salary/Location Exact Match、Hidden Requirements（人工复核）。

用法:
    python -m evaluation.run_jd_eval
    python -m evaluation.run_jd_eval --gold evaluation/datasets/jd_cases.jsonl
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict

from app.agents.jd_ats_agent import JdAtsAgent
from app.tools.llm_json import register_usage_observer
from evaluation.datasets import DEFAULT_DATASET
from evaluation.jd_metrics import (
    LIST_FIELDS,
    ErrorType,
    aggregate_cases,
    classify_case_errors,
    critical_error_rate,
    error_taxonomy_by_field,
    error_taxonomy_summary,
    evaluate_case,
    field_completeness,
)
from evaluation.run_chinese_eval import UsageCollector, estimate_cost

REPORT_PATH = Path(__file__).parent / "reports" / "jd_extraction_report.md"

# 单条 LLM 调用超时（秒）。超过即放弃本轮，留待下次续跑重试，避免卡死整个评测。
_LLM_CALL_TIMEOUT_S = 150.0


def _run_agent_with_timeout(
    jd_text: str, prompt_version: str, timeout_s: float = _LLM_CALL_TIMEOUT_S
) -> Dict[str, Any]:
    """带超时调用 JdAtsAgent（评测专用，防单条 LLM 卡死拖死全量）。

    每次调用使用独立的 ThreadPoolExecutor：超时后放弃该 worker（不再复用），
    避免卡死线程占住共享池导致后续 case 排队。

    :param jd_text: JD 文本
    :param prompt_version: prompt 版本
    :param timeout_s: 超时秒数
    :return: agent.run 结果 dict
    :raises TimeoutError: 调用超过 timeout_s
    """
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(
            _run_agent_with_timeout_impl,
            {"jd_text": jd_text, "prompt_version": prompt_version},
        )
        return future.result(timeout=timeout_s)
    except Exception:
        raise
    finally:
        executor.shutdown(wait=False)


def _run_agent_with_timeout_impl(state: Dict[str, Any]) -> Dict[str, Any]:
    """（内部实现）直接调用 agent，供超时包装执行。"""
    agent = JdAtsAgent()
    return agent.run(state)


def load_gold(path: Path) -> list[dict[str, Any]]:
    """加载 JD gold 数据集（jsonl）。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _is_failed_entry(row: dict[str, Any]) -> bool:
    """判断缓存条目是否为失败兜底（真实输出必有 job_title 等业务字段）。"""
    ats = row.get("ats") or {}
    if not ats:
        return True
    return "job_title" not in ats and "required_skills" not in ats


def _load_existing_preds(pred_file: Path) -> dict[str, dict[str, Any]]:
    """读取已有预测缓存（断点续跑用，同一 case 后者覆盖前者）。"""
    if not pred_file.exists():
        return {}
    by_id: dict[str, dict[str, Any]] = {}
    for line in pred_file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            # 失败兜底条目不使用（保留但续跑时重试）
            if not _is_failed_entry(row):
                by_id[row["case_id"]] = row
    return by_id


def _usage_delta(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """计算两次 snapshot 之间的差值（单 case 的 LLM 调用量）。"""
    keys = (
        "llm_calls",
        "llm_calls_cached",
        "duration_s",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    )
    return {k: round(float(after[k]) - float(before[k]), 4) for k in keys}


def observed_generate_ats(
    gold_cases: list[dict[str, Any]],
    pred_file: Path,
    *,
    prompt_version: str = "v1",
    pace_sec: float = 0.0,
) -> tuple[list[dict[str, Any]], UsageCollector]:
    """用 JdAtsAgent 为每条 JD 生成 ATSProfile，同时采集 usage。

    支持断点续跑：pred_file 中已有的 case 直接复用，避免单 case 失败重来全量。
    每个真实生成的 entry 附带该次调用的 usage，供报告汇总全量成本。

    :param gold_cases: gold case 列表
    :param pred_file: 预测输出 jsonl 路径（兼作续跑缓存）
    :param prompt_version: prompt 版本（"v1" / "v3"）
    :param pace_sec: 每次未命中缓存的 LLM 调用后的强制间隔（防触发账号级 429 限频；默认 0 表示不节流）
    :return: (ats 预测列表, usage snapshot)
    """
    collector = UsageCollector()
    register_usage_observer(collector)
    ats_preds: list[dict[str, Any]] = []
    existing = _load_existing_preds(pred_file)
    for case in gold_cases:
        cached = existing.get(case["case_id"])
        if cached is not None:
            ats_preds.append(cached)
            continue
        before = collector.snapshot()
        try:
            out = _run_agent_with_timeout(case["jd_text"], prompt_version)
            entry = {"case_id": case["case_id"], "ats": out["ats"]}
            if "raw" in out:
                entry["raw"] = out["raw"]
        except Exception as exc:  # noqa: BLE001 - 单 case 失败不中断整体
            print(f"[jd_eval] {case['case_id']} JdAtsAgent 失败: {exc}", flush=True)
            entry = {"case_id": case["case_id"], "ats": {"raw_summary": str(exc)}}
        entry["usage"] = _usage_delta(before, collector.snapshot())
        ats_preds.append(entry)
        with pred_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if pace_sec and cached is None:
            print(f"[jd_eval] 节流 {pace_sec}s（防 429 限频）...", flush=True)
            time.sleep(pace_sec)
    return ats_preds, collector


def _sum_usages(ats_preds: list[dict[str, Any]]) -> Dict[str, Any]:
    """汇总所有预测条目的 usage（含断点续跑的历史行）成一份完整快照。"""
    total = {k: 0.0 for k in ("llm_calls", "llm_calls_cached", "duration_s")}
    total_p = total_com = total_t = 0
    for entry in ats_preds:
        u = entry.get("usage") or {}
        total["llm_calls"] += float(u.get("llm_calls") or 0)
        total["llm_calls_cached"] += float(u.get("llm_calls_cached") or 0)
        total["duration_s"] += float(u.get("duration_s") or 0)
        total_p += int(u.get("prompt_tokens") or 0)
        total_com += int(u.get("completion_tokens") or 0)
        total_t += int(u.get("total_tokens") or 0)
    return {
        "llm_calls": int(total["llm_calls"]),
        "llm_calls_cached": int(total["llm_calls_cached"]),
        "duration_s": round(total["duration_s"], 2),
        "prompt_tokens": total_p,
        "completion_tokens": total_com,
        "total_tokens": total_t,
        "estimated_cost_usd": round(estimate_cost(total_p, total_com), 4),
    }


def run_benchmark(
    gold_path: Path,
    outdir: Path,
    *,
    prompt_version: str = "v1",
    pace_sec: float = 0.0,
) -> Dict[str, Any]:
    """执行 JD Extraction benchmark 全流程。

    :param gold_path: gold 数据集路径
    :param outdir: 预测输出目录
    :param prompt_version: prompt 版本（"v1" / "v3"）
    :param pace_sec: 每次未命中缓存的 LLM 调用后的强制间隔（防 429 限频）
    :return: 汇总 dict {case_results, usage, pred_files, prompt_version}
    """
    gold_cases = load_gold(gold_path)
    outdir.mkdir(parents=True, exist_ok=True)

    pred_name = "jd_ats_predictions.jsonl"
    if prompt_version != "v1":
        pred_name = f"jd_ats_predictions_{prompt_version}.jsonl"
    pred_file = outdir / pred_name
    t0 = time.perf_counter()
    ats_preds, usage = observed_generate_ats(
        gold_cases, pred_file, prompt_version=prompt_version, pace_sec=pace_sec
    )
    latency = time.perf_counter() - t0

    gold_by_id = {c["case_id"]: c for c in gold_cases}
    case_results = []
    raw_results = None
    for pred in ats_preds:
        gold = gold_by_id.get(pred["case_id"])
        if gold is None:
            continue
        ats = pred.get("ats") or {}
        g = gold.get("gold") or {}
        case_result = evaluate_case(ats, g)
        case_result["errors"] = classify_case_errors(ats, g)
        case_result["completeness"] = field_completeness(ats, g)
        case_results.append(case_result)
        if prompt_version == "v3" and pred.get("raw"):
            raw_result = evaluate_case(pred["raw"], g)
            raw_result["errors"] = classify_case_errors(pred["raw"], g)
            raw_result["completeness"] = field_completeness(pred["raw"], g)
            raw_results = raw_results or []
            raw_results.append(raw_result)

    return {
        "gold_cases": gold_cases,
        "case_results": case_results,
        "case_results_raw": raw_results,
        "usage": _sum_usages(ats_preds),
        "latency": round(latency, 2),
        "pred_file": pred_file,
        "prompt_version": prompt_version,
    }


def _agg_errors(case_results: list[dict]) -> list:
    """汇总所有 case 的错误记录。"""
    out: list = []
    for r in case_results:
        out.extend(r.get("errors") or [])
    return out


def e_desc(e: ErrorType) -> str:
    """ErrorType → 中文描述。"""
    return {
        ErrorType.MISSING: "gold 有，pred 没有",
        ErrorType.HALLUCINATED: "pred 有，gold 没有",
        ErrorType.MISCLASSIFIED: "字段间误分类",
        ErrorType.GRANULARITY: "粒度不匹配",
        ErrorType.SEMANTIC: "语义理解错误",
        ErrorType.DIMENSION: "D1-D8 等级错误",
        ErrorType.HIDDEN: "潜台词未识别",
        ErrorType.NORMALIZATION: "同义词/缩写/格式",
    }[e]


def _case_results_from_preds(
    preds: list[dict[str, Any]], gold_by_id: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """对一批预测条目计算 case_results（复用 run_benchmark 的评测口径）。"""
    out: list[dict[str, Any]] = []
    for pred in preds:
        gold = gold_by_id.get(pred["case_id"])
        if gold is None:
            continue
        ats = pred.get("ats") or {}
        g = gold.get("gold") or {}
        case_result = evaluate_case(ats, g)
        case_result["errors"] = classify_case_errors(ats, g)
        case_result["completeness"] = field_completeness(ats, g)
        out.append(case_result)
    return out


def _load_version_preds(outdir: Path, version: str) -> list[dict[str, Any]]:
    """读取某版本的预测缓存（未生成过返回空列表）。"""
    pred_name = "jd_ats_predictions.jsonl"
    if version != "v1":
        pred_name = f"jd_ats_predictions_{version}.jsonl"
    pred_file = outdir / pred_name
    if not pred_file.exists():
        return []
    return [
        v for v in (pred_file.read_text(encoding="utf-8").splitlines()) if v.strip()
    ]


def _criterion_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    """单组 case_results 的关键指标字典（供对比表）。"""
    if not case_results:
        return {}
    agg = aggregate_cases(case_results)
    errors = _agg_errors(case_results)
    return {
        "required_skills": agg["required_skills"]["f1"],
        "responsibilities": agg["responsibilities"]["f1"],
        "culture_keywords": agg["culture_keywords"]["f1"],
        "preferred_skills": agg["preferred_skills"]["f1"],
        "dimension": agg["dimension_accuracy"],
        "salary": f"{agg['salary'][0]}/{agg['salary'][1]}",
        "location": f"{agg['location'][0]}/{agg['location'][1]}",
        "critical": critical_error_rate(errors),
        "errors": len(errors),
    }


def _add_prompt_comparison(lines: list[str], result: Dict[str, Any]) -> None:
    """写 Prompt 版本对比小节（v3 含 raw / 校验两态）。"""
    baseline = result.get("baseline_cases") or []
    raw_results = result.get("case_results_raw") or []
    recon_results = result.get("case_results") or []
    groups: list[tuple[str, list[dict[str, Any]]]] = []
    if baseline:
        groups.append(("Prompt A (v1) 基线", baseline))
    if raw_results:
        groups.append(("Prompt C (v3) raw", raw_results))
    if recon_results and (baseline or raw_results):
        groups.append(("Prompt C (v3) 证据校验", recon_results))
    if not groups:
        return

    lines += ["", "## Prompt 版本对比", ""]
    header = "| 指标 | " + " | ".join(name for name, _ in groups) + " |"
    sep = "|" + "---|" * (len(groups) + 1)
    lines += [header, sep]
    rows = [
        ("Required Skills F1", "required_skills"),
        ("Responsibilities F1", "responsibilities"),
        ("Keywords F1", "culture_keywords"),
        ("Preferred Skills F1", "preferred_skills"),
        ("Dimension Accuracy", "dimension"),
        ("Salary Exact", "salary"),
        ("Location Exact", "location"),
        ("Critical Error Rate", "critical"),
        ("Error 总数", "errors"),
    ]
    for label, key in rows:
        cells = []
        for _, cr in groups:
            c = _criterion_summary(cr)
            if key == "critical":
                val = f"{c.get(key, 0.0):.2%}"
            else:
                val = c.get(key, "-")
            cells.append(str(val))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines.append("")

    # 证据校验统计（仅单次调用的确定性效果，无额外 LLM 成本）
    preds_path = result.get("pred_file")
    if preds_path and preds_path.exists():
        from app.agents.evidence import coverage_stats

        per_case = []
        for line in preds_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("raw") is not None:
                per_case.append(coverage_stats(row["raw"]))
        if per_case:
            total_ev = sum(c["evidence_total"] for c in per_case)
            total_dropped = sum(c["dropped_values"] for c in per_case)
            ev_cases = sum(1 for c in per_case if c["evidence_total"] > 0)
            lines += [
                "**证据校验统计（v3）**：LLM 单次输出 → 确定性校验去除无证据条目。",
                "",
                f"- 证据命中 case：{ev_cases}/{len(per_case)}",
                f"- 证据条目总数：{total_ev}",
                f"- 校验丢弃条目数：{total_dropped}（无证据支撑的幻造值）",
                "",
            ]


def build_report(result: Dict[str, Any], report_path: Path) -> None:
    """把 benchmark 结果写成报告（Markdown）。

    :param result: run_benchmark 返回值
    :param report_path: 输出路径
    """
    gold_cases = result["gold_cases"]
    case_results = result["case_results"]
    usage = result["usage"]
    prompt_version = result.get("prompt_version", "v1")
    summary = aggregate_cases(case_results)
    all_errors = _agg_errors(case_results)
    taxonomy = error_taxonomy_summary(all_errors)
    by_field = error_taxonomy_by_field(all_errors)
    crit_rate = critical_error_rate(all_errors)

    lines: list[str] = [
        "# JD Extraction Evaluation Report (v0.4)",
        "",
        "## Status",
        "",
        f"**v0.4 — JD Extraction 回测完成（{len(gold_cases)} 条中文合成 JD，2026-09）。**",
        "",
        "模型: `glm-4.7-flash`（用户已切换）。链路: JD 原文 → `JdAtsAgent` → `ATSProfile`。",
        "重点：**AI 是否正确抽取岗位要求**（Required/Preferred Skills、Responsibilities、Keywords、Dimension、Salary/Location、Hidden Requirement）。",
        "v0.4 新增：**Error Taxonomy（E1-E8）**、**Field Completeness**、**Critical Error Rate**、"
        f"**Prompt {prompt_version.upper()} 对比**。",
        "",
        f"- Prompt 版本: `{prompt_version}`"
        + ("（evidence-first，含 raw/校验两态对比）" if prompt_version == "v3" else ""),
        f"- LLM 调用: {usage['llm_calls']}（缓存命中 {usage['llm_calls_cached']}）",
        f"- Token 用量: prompt {usage['prompt_tokens']} / completion {usage['completion_tokens']} / total {usage['total_tokens']}",
        f"- 估算成本（$0.06/1M in + $0.4/1M out）: ${usage['estimated_cost_usd']:.4f}",
        f"- 墙钟延迟: {result['latency']}s",
        "",
        "## Results（字段抽取 P/R/F1，micro 聚合）",
        "",
        "| 维度 | Precision | Recall | F1 |",
        "|---|---:|---:|---:|",
    ]
    for field, _ in LIST_FIELDS:
        m = summary[field]
        lines.append(
            f"| {field} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} |"
        )

    lines += [
        "",
        "| 维度 | Accuracy |",
        "|---|---:|",
        f"| Dimension (D1-D8 level) | {summary['dimension_accuracy']:.4f} |",
    ]
    for field in ("salary", "location"):
        hit, total = summary[field]
        lines.append(f"| {field} Exact Match | {hit}/{total} |")

    _add_prompt_comparison(lines, result)

    lines += [
        "",
        "## Error Taxonomy",
        "",
        "错误分类（E1-E8）。自动识别 E1/E2/E3/E6/E7/E8；E4（粒度）用数量比启发式；缩写等需词典的归类为 E2。",
        "",
        "| 类型 | 含义 | 数量 |",
        "|---|---|---:|",
    ]
    for e in ErrorType:
        lines.append(f"| {e.value} {e.name} | {e_desc(e)} | {taxonomy[e.value]} |")
    lines += [
        "",
        f"**Critical Error Rate（required/preferred 字段误分类占比）: {crit_rate:.2%}**",
        "",
        "| 字段 | E1 Missing | E2 Hallucinated | E3 Misclassified | E4 Granularity | E6 Dimension | E7 Hidden | E8 Normalization |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    field_order = [attr for _, attr in LIST_FIELDS] + [
        "dimension_D" + str(i) for i in range(1, 9)
    ]
    for fld in field_order:
        row = by_field.get(fld) or {e.value: 0 for e in ErrorType}
        lines.append(
            f"| {fld} | {row['E1']} | {row['E2']} | {row['E3']} | {row['E4']} | {row['E6']} | {row['E7']} | {row['E8']} |"
        )

    lines += [
        "",
        "## Field Completeness",
        "",
        "gold 字段缺失字段完整性（被 pred 覆盖的比例，micro 平均）。",
        "",
        "| 字段 | Completeness |",
        "|---|---:|",
    ]
    for fld, _ in LIST_FIELDS + [("salary", "salary"), ("location", "location")]:
        vals = [r["completeness"].get(fld, 0.0) for r in case_results]
        avg = sum(vals) / len(vals) if vals else 0.0
        lines.append(f"| {fld} | {avg:.3f} |")

    lines += [
        "",
        "## Hidden Requirements（人工复核清单）",
        "",
        "模型 `subtext_decoded` 是对潜台词的解读，主观性高，脚本仅输出待审清单：",
        "",
    ]
    for i, (case_result, case) in enumerate(zip(case_results, gold_cases), 1):
        hidden = case_result["hidden"]
        lines.append(
            f"{i}. **{case['case_id']}** {case['job_title']} — 表面要求覆盖 "
            f"{hidden['surface_coverage']:.0%}（gold {hidden['gold_count']} / pred {hidden['pred_count']} 条）"
        )
        for pair in hidden["pairs"]:
            mp = pair["matched_pred"]
            mp_text = (
                f"→ 命中模型「{mp.get('surface_requirement')}」hidden={mp.get('hidden_meaning')}"
                if mp
                else "→ ✗ 未命中"
            )
            lines.append(f"   - gold「{pair['gold_surface']}」{mp_text}")

    lines += [
        "",
        "## Case-level 明细",
        "",
        "| case | job | RequiredSkills F1 | Responsibilities F1 | Keywords F1 | PreferredSkills F1 | DimAcc | Salary | Location | Errors |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for case_result, case in zip(case_results, gold_cases):
        r = case_result
        dim = r["dimension_hits"]
        dim_acc = f"{sum(1 for v in dim.values() if v)}/8"
        n_errors = len(r.get("errors") or [])
        rows = [
            case["case_id"],
            case.get("job_title", ""),
            f"{r['required_skills']['f1']:.2f}",
            f"{r['responsibilities']['f1']:.2f}",
            f"{r['culture_keywords']['f1']:.2f}",
            f"{r['preferred_skills']['f1']:.2f}",
            dim_acc,
            "✓" if r["salary"] else "✗",
            "✓" if r["location"] else "✗",
            str(n_errors),
        ]
        lines.append("| " + " | ".join(rows) + " |")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gold", type=Path, default=DEFAULT_DATASET.parent / "jd_cases.jsonl"
    )
    parser.add_argument(
        "--outdir", type=Path, default=Path(__file__).parent / "predictions"
    )
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument(
        "--prompt-version",
        choices=["v1", "v3"],
        default="v1",
        help="ATS 解析 prompt 版本（v1 基础 / v3 evidence-first）",
    )
    parser.add_argument(
        "--pace-sec",
        type=float,
        default=0.0,
        help="每次未命中缓存的 LLM 调用后强制间隔秒数（防账号级 429 限频）",
    )
    args = parser.parse_args()

    result = run_benchmark(
        args.gold,
        args.outdir,
        prompt_version=args.prompt_version,
        pace_sec=args.pace_sec,
    )
    # v3 运行时补 v1 基线（复用缓存，避免重复调用）
    if args.prompt_version == "v3":
        baseline_preds = []
        for line in _load_version_preds(args.outdir, "v1"):
            baseline_preds.append(json.loads(line))
        if baseline_preds:
            gold_by_id = {c["case_id"]: c for c in result["gold_cases"]}
            result["baseline_cases"] = _case_results_from_preds(
                baseline_preds, gold_by_id
            )
        else:
            print("[jd_eval] 提示: 无 v1 基线预测缓存，跳过 Prompt A 对比")

    summary = aggregate_cases(result["case_results"])
    print(f"[jd_eval] summary (prompt={args.prompt_version}):")
    for field, _ in LIST_FIELDS:
        m = summary[field]
        print(f"  {field}: P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1']:.4f}")
    print(f"  dimension_accuracy: {summary['dimension_accuracy']:.4f}")
    print(
        f"  salary: {summary['salary'][0]}/{summary['salary'][1]}  location: {summary['location'][0]}/{summary['location'][1]}"
    )
    build_report(result, args.report)
    print(f"[jd_eval] report -> {args.report}")


if __name__ == "__main__":
    main()
