"""Spot-Check — 口径校准小工具（不调用 LLM，纯指标复算）。

目的：真实 40 语料的 gold 为 GPT 生成 + 人工粗略核对，噪声明显（前缀杂物、
拆分粒度不一致）。本脚本支持对同一批 case 用「官方 gold」与「重标 spot gold」
分别计算 v3/v4 指标，验证版本对比信号（required/preferred F1 差距）是否真实。

用法:
    # 1. 用官方 gold 全量计算并抽样（rank 取 |Δrequired|+|Δpreferred| 最大 N 条）
    python -m evaluation.spot_check --dump <inspect> --sample-ids <ids.txt>

    # 2. 用 spot gold 在抽样的同批 case 上复算（--only 限定计算范围）
    python -m evaluation.spot_check --spot-gold <spot.jsonl> --only <ids.txt>

说明：控制台只输出 ASCII；中文数据一律写入文件（Windows 控制台 GBK 兼容）。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.jd_metrics import (
    aggregate_cases,
    classify_case_errors,
    critical_error_rate,
    evaluate_case,
)
from evaluation.run_jd_eval import _load_version_preds_latest

DEFAULT_GOLD = Path(__file__).parent / "datasets" / "real_jd_cases.jsonl"
DEFAULT_PREDS = Path(__file__).parent / "predictions_real_jd"
VERSIONS = ("v3", "v4")

# 参与排名的字段（口径校准关心的版本差距来源）
RANK_FIELDS = ("required_skills", "preferred_skills")
SUMMARY_FIELDS = (
    "required_skills",
    "preferred_skills",
    "responsibilities",
    "culture_keywords",
)


def load_gold(path: Path) -> list[dict[str, Any]]:
    """加载 gold 数据集（jsonl，与 run_jd_eval 同构）。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _valid_preds(outdir: Path, version: str) -> list[dict[str, Any]]:
    """读取某版本 latest-per-case 预测，剔除失败兜底条目。"""
    out: list[dict[str, Any]] = []
    for row in _load_version_preds_latest(outdir, version):
        ats = row.get("ats") or {}
        if not ats:
            continue
        if "job_title" not in ats and "required_skills" not in ats:
            continue
        out.append(row)
    return out


def case_results(
    preds: list[dict[str, Any]],
    gold_by_id: dict[str, dict[str, Any]],
    only: set[str] | None,
) -> list[dict[str, Any]]:
    """计算一批预测在给定 gold 下的 case_results（口径与 run_jd_eval 一致）。"""
    out: list[dict[str, Any]] = []
    for pred in preds:
        if only is not None and pred["case_id"] not in only:
            continue
        gold = gold_by_id.get(pred["case_id"])
        if gold is None:
            continue
        r = evaluate_case(pred.get("ats") or {}, gold.get("gold") or {})
        r["case_id"] = pred["case_id"]
        r["errors"] = classify_case_errors(
            pred.get("ats") or {}, gold.get("gold") or {}
        )
        out.append(r)
    return out


def _summary(crs: list[dict[str, Any]]) -> dict[str, float]:
    """单组 case_results 的指标摘要（与 run_jd_eval _criterion_summary 口径一致）。"""
    if not crs:
        return {}
    agg = aggregate_cases(crs)
    return {
        "required_skills": agg["required_skills"]["f1"],
        "preferred_skills": agg["preferred_skills"]["f1"],
        "responsibilities": agg["responsibilities"]["f1"],
        "culture_keywords": agg["culture_keywords"]["f1"],
        "critical": critical_error_rate(
            [e for r in crs for e in r.get("errors") or []]
        ),
        "cases": len(crs),
    }


def _per_case_f1(crs: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """case_id → {field: f1}，供抽样排名。"""
    return {r["case_id"]: {f: r[f]["f1"] for f in RANK_FIELDS} for r in crs}


def rank_sample(
    v3_crs: list[dict[str, Any]], v4_crs: list[dict[str, Any]], n: int
) -> list[str]:
    """按 v3/v4 在 RANK_FIELDS 上 F1 差距之和排序，取前 n 个 case。"""
    f3 = _per_case_f1(v3_crs)
    f4 = _per_case_f1(v4_crs)
    deltas: list[tuple[float, str]] = []
    for cid in f3:
        if cid not in f4:
            continue
        d = sum(abs(f3[cid][f] - f4[cid][f]) for f in RANK_FIELDS)
        deltas.append((d, cid))
    deltas.sort(key=lambda t: -t[0])
    return [cid for _, cid in deltas[:n]]


def _dump_inspect(
    path: Path,
    gold_by_id: dict[str, dict[str, Any]],
    pred_by_id: dict[str, dict[str, Any]],
    sample: list[str],
    jd_by_id: dict[str, str],
) -> None:
    """导出抽样 case 的文案，供人工（粗标重读 + 重标决策）。"""
    fields = [
        "required_skills",
        "preferred_skills",
        "responsibilities",
        "culture_keywords",
    ]
    rows = []
    for cid in sample:
        gold = gold_by_id.get(cid, {}).get("gold") or {}
        row: dict[str, Any] = {"case_id": cid, "jd_text": jd_by_id.get(cid, "")}
        row["gold"] = {f: gold.get(f) or [] for f in fields}
        for version in VERSIONS:
            ats = pred_by_id[version].get(cid, {}).get("ats") or {}
            row[version] = {f: ats.get(f) or [] for f in fields}
        rows.append(row)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_PREDS)
    parser.add_argument("--spot-gold", type=Path, default=None)
    parser.add_argument(
        "--only", type=Path, default=None, help="一行一个 case_id，限定计算范围"
    )
    parser.add_argument("--sample", type=int, default=10, help="抽样条数")
    parser.add_argument("--dump", type=Path, default=None, help="抽样导出 jsonl 路径")
    parser.add_argument(
        "--sample-ids", type=Path, default=None, help="抽样 case_id 导出路径"
    )
    args = parser.parse_args()

    gold = load_gold(args.spot_gold or args.gold)
    gold_by_id = {c["case_id"]: c for c in gold}
    preds = {v: _valid_preds(args.outdir, v) for v in VERSIONS}

    only: set[str] | None = None
    if args.only is not None:
        only = {
            line.strip()
            for line in args.only.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    crs = {v: case_results(preds[v], gold_by_id, only) for v in VERSIONS}

    # —— 抽样（仅官方 gold 全量时）——
    sample: list[str] = []
    if args.sample_ids is not None or args.dump is not None:
        if only is not None:
            sample = sorted(only)
        else:
            sample = rank_sample(crs["v3"], crs["v4"], args.sample)
        if args.sample_ids is not None:
            args.sample_ids.write_text("\n".join(sample) + "\n", encoding="utf-8")
        if args.dump is not None:
            jd_text = {c["case_id"]: c.get("jd_text", "") for c in load_gold(args.gold)}
            raw_by_id = {v: {p["case_id"]: p for p in preds[v]} for v in VERSIONS}
            _dump_inspect(args.dump, gold_by_id, raw_by_id, sample, jd_text)
            print(f"[spot] sampled {len(sample)} cases -> {args.dump}")

    # —— 指标摘要 ——
    print(
        f"[spot] gold={args.spot_gold or args.gold.name}  scope={len(only) if only else 'all'}"
    )
    for v in VERSIONS:
        s = _summary(crs[v])
        print(
            f"[spot] {v}: cases={s.get('cases', 0)} "
            + " ".join(f"{f}={s.get(f, 0.0):.4f}" for f in SUMMARY_FIELDS)
            + f" critical={s.get('critical', 0.0):.4f}"
        )
    if only:
        s3, s4 = _summary(crs["v3"]), _summary(crs["v4"])
        for f in SUMMARY_FIELDS + ("critical",):
            a, b = s3.get(f, 0.0), s4.get(f, 0.0)
            print(f"[spot] delta {f}: v3={a:.4f} v4={b:.4f} (v4-v3={b - a:+.4f})")


if __name__ == "__main__":
    main()
