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
from pathlib import Path
from typing import Any, Dict

from app.agents.jd_ats_agent import JdAtsAgent
from app.tools.llm_json import register_usage_observer
from evaluation.datasets import DEFAULT_DATASET
from evaluation.jd_metrics import (
    LIST_FIELDS,
    aggregate_cases,
    evaluate_case,
)
from evaluation.run_chinese_eval import UsageCollector, estimate_cost

REPORT_PATH = Path(__file__).parent / "reports" / "jd_extraction_report.md"


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
) -> tuple[list[dict[str, Any]], UsageCollector]:
    """用 JdAtsAgent 为每条 JD 生成 ATSProfile，同时采集 usage。

    支持断点续跑：pred_file 中已有的 case 直接复用，避免单 case 失败重来全量。
    每个真实生成的 entry 附带该次调用的 usage，供报告汇总全量成本。

    :param gold_cases: gold case 列表
    :param pred_file: 预测输出 jsonl 路径（兼作续跑缓存）
    :return: (ats 预测列表, usage snapshot)
    """
    collector = UsageCollector()
    register_usage_observer(collector)
    ats_preds: list[dict[str, Any]] = []
    existing = _load_existing_preds(pred_file)
    agent = JdAtsAgent()
    for case in gold_cases:
        cached = existing.get(case["case_id"])
        if cached is not None:
            ats_preds.append(cached)
            continue
        before = collector.snapshot()
        try:
            out = agent.run({"jd_text": case["jd_text"]})
            entry = {"case_id": case["case_id"], "ats": out["ats"]}
        except Exception as exc:  # noqa: BLE001 - 单 case 失败不中断整体
            print(f"[jd_eval] {case['case_id']} JdAtsAgent 失败: {exc}", flush=True)
            entry = {"case_id": case["case_id"], "ats": {"raw_summary": str(exc)}}
        entry["usage"] = _usage_delta(before, collector.snapshot())
        ats_preds.append(entry)
        with pred_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
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


def run_benchmark(gold_path: Path, outdir: Path) -> Dict[str, Any]:
    """执行 JD Extraction benchmark 全流程。

    :param gold_path: gold 数据集路径
    :param outdir: 预测输出目录
    :return: 汇总 dict {case_results, usage, pred_files}
    """
    gold_cases = load_gold(gold_path)
    outdir.mkdir(parents=True, exist_ok=True)

    pred_file = outdir / "jd_ats_predictions.jsonl"
    t0 = time.perf_counter()
    ats_preds, usage = observed_generate_ats(gold_cases, pred_file)
    latency = time.perf_counter() - t0

    gold_by_id = {c["case_id"]: c for c in gold_cases}
    case_results = []
    for pred in ats_preds:
        gold = gold_by_id.get(pred["case_id"])
        if gold is None:
            continue
        case_results.append(
            evaluate_case(pred.get("ats") or {}, gold.get("gold") or {})
        )

    return {
        "gold_cases": gold_cases,
        "case_results": case_results,
        "usage": _sum_usages(ats_preds),
        "latency": round(latency, 2),
        "pred_file": pred_file,
    }


def build_report(result: Dict[str, Any], report_path: Path) -> None:
    """把 benchmark 结果写成报告（Markdown）。

    :param result: run_benchmark 返回值
    :param report_path: 输出路径
    """
    gold_cases = result["gold_cases"]
    case_results = result["case_results"]
    usage = result["usage"]
    summary = aggregate_cases(case_results)

    lines: list[str] = [
        "# JD Extraction Evaluation Report (v0.3)",
        "",
        "## Status",
        "",
        f"**v0.3 — JD Extraction 回测完成（{len(gold_cases)} 条中文合成 JD，2026-09-09）。**",
        "",
        "模型: `glm-4.7-flash`（用户已切换）。链路: JD 原文 → `JdAtsAgent` → `ATSProfile`。",
        "重点：**AI 是否正确抽取岗位要求**（Required/Preferred Skills、Responsibilities、Keywords、Dimension、Salary/Location、Hidden Requirement）。",
        "",
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
        "| case | job | RequiredSkills F1 | Responsibilities F1 | Keywords F1 | PreferredSkills F1 | DimAcc | Salary | Location |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for case_result, case in zip(case_results, gold_cases):
        r = case_result
        dim = r["dimension_hits"]
        dim_acc = f"{sum(1 for v in dim.values() if v)}/8"
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
    args = parser.parse_args()

    result = run_benchmark(args.gold, args.outdir)
    summary = aggregate_cases(result["case_results"])
    print("[jd_eval] summary:")
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
