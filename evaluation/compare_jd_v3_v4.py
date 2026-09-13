"""Compare — v3 vs v4 逐 JD 对比产物（不调用 LLM，纯读取本地预测）。

对应「JobCraft JD Pipeline v4 渐进式重构执行 Prompt」§16/§17：
- §16 聚合指标对比（Required / Preferred / Responsibilities / Keywords F1 + Critical）
- §17 逐 JD 结构 diff（`evaluation/results/v3_vs_v4.json`），供人工检查 v4 到底改对了什么

用法:
    # 官方 gold 全量 40
    python -m evaluation.compare_jd_v3_v4

    # 重标 spot gold（同一批重标 case 上复算，供口径校准）
    python -m evaluation.compare_jd_v3_v4 --spot-gold evaluation/datasets/real_jd_spot_gold.jsonl

说明：控制台只输出 ASCII；中文数据一律写入 JSON 文件（Windows 控制台 GBK 兼容）。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluation.spot_check import (
    DEFAULT_GOLD,
    DEFAULT_PREDS,
    VERSIONS,
    _summary,
    _valid_preds,
    case_results,
    load_gold,
)

RESULTS_DIR = Path(__file__).parent / "results"
RESULT_PATH = RESULTS_DIR / "v3_vs_v4.json"

# 参与逐 JD diff 的核心字段（对应 §10 Core ATS）
DIFF_FIELDS = (
    "required_skills",
    "preferred_skills",
    "responsibilities",
    "core_keywords",
)

SUMMARY_FIELDS = (
    "required_skills",
    "preferred_skills",
    "responsibilities",
    "culture_keywords",
)


def _canon(value: Any) -> str:
    """把值规范化为 diff 用的字符串键。"""
    if isinstance(value, dict):
        value = value.get("keyword") or value.get("text") or str(value)
    return str(value).strip()


def _as_list(values: Any) -> list[Any]:
    return list(values or [])


def _field_diff(a: list[Any], b: list[Any]) -> dict[str, list[str]]:
    """返回 only_v3 / only_v4 / both，按规范字符串集合比较。"""
    a_set = {_canon(v) for v in a}
    b_set = {_canon(v) for v in b}
    return {
        "only_v3": sorted(a_set - b_set),
        "only_v4": sorted(b_set - a_set),
        "both": sorted(a_set & b_set),
    }


def build_per_case(
    preds3: dict[str, dict[str, Any]], preds4: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """构造 §17 要求的逐 JD diff 列表（v3/v4 合集内每个 case 一条）。"""
    rows: list[dict[str, Any]] = []
    for cid in sorted(set(preds3) | set(preds4)):
        ats3 = (preds3.get(cid) or {}).get("ats") or {}
        ats4 = (preds4.get(cid) or {}).get("ats") or {}
        per_field: dict[str, dict[str, list[str]]] = {}
        for field in DIFF_FIELDS:
            per_field[field] = _field_diff(
                _as_list(ats3.get(field)), _as_list(ats4.get(field))
            )
        rows.append(
            {
                "case_id": cid,
                "v3": {f: _as_list(ats3.get(f)) for f in DIFF_FIELDS},
                "v4": {f: _as_list(ats4.get(f)) for f in DIFF_FIELDS},
                "diff": per_field,
            }
        )
    return rows


def aggregate_moves(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """跨全部 case 统计每个字段 v3→v4 的净迁移量（新增/删除/保留）。"""
    out: dict[str, dict[str, int]] = {}
    for field in DIFF_FIELDS:
        only3 = sum(len(r["diff"][field]["only_v3"]) for r in rows)
        only4 = sum(len(r["diff"][field]["only_v4"]) for r in rows)
        both = sum(len(r["diff"][field]["both"]) for r in rows)
        out[field] = {"removed": only3, "added": only4, "kept": both}
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--spot-gold", type=Path, default=None)
    args = parser.parse_args()

    gold = load_gold(args.spot_gold or args.gold)
    gold_by_id = {c["case_id"]: c for c in gold}
    preds = {v: _valid_preds(DEFAULT_PREDS, v) for v in VERSIONS}
    pred_by_id = {v: {p["case_id"]: p for p in preds[v]} for v in VERSIONS}

    # §16 聚合指标（与 spot_check 同一口径）；spot gold 只覆盖重标 case
    crs = {v: case_results(preds[v], gold_by_id, None) for v in VERSIONS}
    s3, s4 = _summary(crs["v3"]), _summary(crs["v4"])
    aggregate = {"v3": s3, "v4": s4}
    aggregate["delta"] = {
        f: s4.get(f, 0.0) - s3.get(f, 0.0) for f in SUMMARY_FIELDS + ("critical",)
    }

    # §17 逐 JD diff
    per_case = build_per_case(pred_by_id["v3"], pred_by_id["v4"])

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "versions": ["v3", "v4"],
                "gold": (args.spot_gold or args.gold).name,
                "aggregate": aggregate,
                "moves": aggregate_moves(per_case),
                "per_case": per_case,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"[compare] gold={args.spot_gold or args.gold.name}")
    for v in VERSIONS:
        s = aggregate[v]
        print(
            f"[compare] {v}: cases={s.get('cases', 0)} "
            + " ".join(f"{f}={s.get(f, 0.0):.4f}" for f in SUMMARY_FIELDS)
            + f" critical={s.get('critical', 0.0):.4f}"
        )
    d = aggregate["delta"]
    print(
        "[compare] delta(v4-v3): "
        + " ".join(f"{f}={d.get(f, 0.0):+.4f}" for f in SUMMARY_FIELDS + ("critical",))
    )
    print("[compare] field moves (removed/added/kept):")
    for f, m in aggregate_moves(per_case).items():
        print(f"[compare]   {f}: {m['removed']}/{m['added']}/{m['kept']}")
    print(f"[compare] {len(per_case)} cases -> {RESULT_PATH}")


if __name__ == "__main__":
    main()
