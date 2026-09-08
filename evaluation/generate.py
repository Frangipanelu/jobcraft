"""
Experience Matching 预测生成器 CLI.

用指定策略（keyword/llm/hybrid）在 gold dataset 上生成预测，
输出为 run_matching_eval.py 可消费的预测文件（每行一条 case 预测）。

用法:
    python -m evaluation.generate --strategy all
    python -m evaluation.generate --strategy llm
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from evaluation.strategies import get_strategy

DEFAULT_GOLD = Path(__file__).parent / "datasets" / "matching_cases.jsonl"
DEFAULT_OUTDIR = Path(__file__).parent / "predictions"


def load_gold(path: Path) -> list[dict[str, Any]]:
    """加载 gold 数据集（jsonl）。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def generate(
    strategy_name: str, gold_cases: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """用指定策略为全部 case 生成预测。

    :param strategy_name: keyword / llm / hybrid
    :param gold_cases: 加载后的 gold case 列表
    :return: [{case_id, predictions: [...]}, ...]
    """
    strategy = get_strategy(strategy_name)
    predictions = []
    for case in gold_cases:
        try:
            pred = strategy.predict_case(case)
        except Exception as exc:  # noqa: BLE001 - 单 case 失败不中断整体生成
            print(
                f"[generate] {case['case_id']} {strategy_name} 失败: {exc}",
                file=sys.stderr,
            )
            pred = [
                {"experience_id": exp["id"], "label": "irrelevant", "score": 0.0}
                for exp in case["experiences"]
            ]
        predictions.append({"case_id": case["case_id"], "predictions": pred})
    return predictions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strategy",
        choices=["keyword", "llm", "hybrid", "all"],
        default="all",
        help="要运行的策略，all 表示三种都跑",
    )
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    args = parser.parse_args()

    gold_cases = load_gold(args.gold)
    names = ["keyword", "llm", "hybrid"] if args.strategy == "all" else [args.strategy]

    args.outdir.mkdir(parents=True, exist_ok=True)
    for name in names:
        preds = generate(name, gold_cases)
        out = args.outdir / f"predictions_{name}.jsonl"
        with out.open("w", encoding="utf-8") as fh:
            for item in preds:
                fh.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"[generate] {name}: {len(preds)} cases -> {out}")


if __name__ == "__main__":
    main()
