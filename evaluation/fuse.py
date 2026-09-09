"""
Hybrid 融合权重实验 CLI（确定性离线融合）.

在**同一份** LLM 预测（predictions_llm.jsonl）之上，用本地分数做确定性融合，
产出 A（0.4/0.6）、B（0.2/0.8）、C（max）三个变体的预测文件。

隔离 LLM 非确定性：本 CLI 不发起任何新 LLM 调用。

用法:
    python -m evaluation.generate --strategy llm        # 先产出一份共享 LLM 预测
    python -m evaluation.fuse --llm-pred evaluation/predictions/predictions_llm.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from evaluation.fusion import FUSION_MODES, generate_fused

DEFAULT_GOLD = Path(__file__).parent / "datasets" / "matching_cases.jsonl"
DEFAULT_OUTDIR = Path(__file__).parent / "predictions"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--llm-pred", required=True, type=Path, help="共享的 LLM 预测文件"
    )
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    args = parser.parse_args()

    llm_preds = {p["case_id"]: p for p in load_jsonl(args.llm_pred)}
    gold_cases = {c["case_id"]: c for c in load_jsonl(args.gold)}

    args.outdir.mkdir(parents=True, exist_ok=True)
    for name in FUSION_MODES:
        out = args.outdir / f"predictions_{name}.jsonl"
        rows = []
        for cid, case in gold_cases.items():
            if cid not in llm_preds:
                print(f"[fuse] {cid} 缺少 LLM 预测，跳过", file=sys.stderr)
                continue
            pred = generate_fused(llm_preds[cid], case, name)
            rows.append({"case_id": cid, "predictions": pred})
        with out.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"[fuse] {name}: {len(rows)} cases -> {out}")


if __name__ == "__main__":
    main()
