"""Evaluate experience-card matching predictions against human gold labels.

This runner is intentionally model-agnostic: generate predictions with any
matching strategy, save one JSON object per case, then run this script.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

LABELS = ["high", "medium", "low", "irrelevant"]
RELEVANT = {"high", "medium"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def dcg(relevances: list[int]) -> float:
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


def ndcg_at_k(
    predicted: list[str],
    gold_ranking: list[str],
    gold_labels: dict[str, str],
    k: int = 3,
) -> float:
    gold_pos = {item: i for i, item in enumerate(gold_ranking)}
    predicted = predicted[:k]
    rel = [
        max(0, len(gold_ranking) - gold_pos.get(item, len(gold_ranking)))
        for item in predicted
    ]
    ideal = sorted(
        [
            max(0, len(gold_ranking) - gold_pos.get(item, len(gold_ranking)))
            for item in gold_ranking
        ],
        reverse=True,
    )[:k]
    if not ideal or dcg(ideal) == 0:
        return 0.0
    return dcg(rel) / dcg(ideal)


def macro_f1(y_true: list[str], y_pred: list[str]) -> float:
    scores = []
    for label in LABELS:
        tp = sum(a == label and b == label for a, b in zip(y_true, y_pred))
        fp = sum(a != label and b == label for a, b in zip(y_true, y_pred))
        fn = sum(a == label and b != label for a, b in zip(y_true, y_pred))
        if tp == 0 and fp == 0 and fn == 0:
            continue
        precision = tp / (tp + fp) if tp + fp else 0
        recall = tp / (tp + fn) if tp + fn else 0
        scores.append(
            2 * precision * recall / (precision + recall) if precision + recall else 0
        )
    return mean(scores) if scores else 0.0


def evaluate(
    gold_cases: list[dict[str, Any]], predictions: list[dict[str, Any]]
) -> dict[str, float]:
    pred_by_case = {p["case_id"]: p for p in predictions}
    y_true: list[str] = []
    y_pred: list[str] = []
    binary_true: list[int] = []
    binary_pred: list[int] = []
    score_errors: list[float] = []
    ndcgs: list[float] = []

    for case in gold_cases:
        pred_case = pred_by_case.get(case["case_id"])
        if not pred_case:
            continue
        gold = case["gold"]
        pred_items = pred_case.get("predictions", [])
        pred_by_id = {x["experience_id"]: x for x in pred_items}
        for exp_id, label in gold["relevance"].items():
            item = pred_by_id.get(exp_id, {"label": "irrelevant", "score": 0})
            pred_label = item.get("label", "irrelevant")
            y_true.append(label)
            y_pred.append(pred_label)
            binary_true.append(int(label in RELEVANT))
            binary_pred.append(int(pred_label in RELEVANT))
            score_errors.append(
                abs(float(gold["score"].get(exp_id, 0)) - float(item.get("score", 0)))
            )
        ranking = [
            x["experience_id"]
            for x in sorted(
                pred_items, key=lambda x: float(x.get("score", 0)), reverse=True
            )
        ]
        ndcgs.append(ndcg_at_k(ranking, gold["ranking"], gold["relevance"], 3))

    tp = sum(a == 1 and b == 1 for a, b in zip(binary_true, binary_pred))
    fp = sum(a == 0 and b == 1 for a, b in zip(binary_true, binary_pred))
    fn = sum(a == 1 and b == 0 for a, b in zip(binary_true, binary_pred))
    tn = sum(a == 0 and b == 0 for a, b in zip(binary_true, binary_pred))
    accuracy = (tp + tn) / len(binary_true) if binary_true else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0

    return {
        "cases_evaluated": float(len(ndcgs)),
        "accuracy": accuracy,
        "macro_f1": macro_f1(y_true, y_pred),
        "precision_relevant": precision,
        "recall_relevant": recall,
        "score_mae": mean(score_errors) if score_errors else 0.0,
        "ndcg_at_3": mean(ndcgs) if ndcgs else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--pred", required=True, type=Path)
    parser.add_argument("--strategy", default="unknown")
    args = parser.parse_args()

    metrics = evaluate(load_jsonl(args.gold), load_jsonl(args.pred))
    print(f"Strategy: {args.strategy}")
    for key, value in metrics.items():
        if key == "cases_evaluated":
            print(f"{key}: {int(value)}")
        else:
            print(f"{key}: {value:.4f}")


if __name__ == "__main__":
    main()
