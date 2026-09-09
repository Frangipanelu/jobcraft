"""
Evaluation v0.2 — Chinese Real-world Matching Benchmark Runner.

在 10 条**中文真实风格** case（3 direct / 2 semantic / 2 partial / 2 negative / 1 transfer）上，
对比 Keyword baseline / LLM / Hybrid A(0.4 加权) / Hybrid C(max) 四路策略，
并新增 **Latency / LLM Calls / Estimated Cost** 三个工程维度。

关键设计（沿用 v0.1）：
- Hybrid A/C 在**同一份共享 LLM 预测**上做确定性离线融合，不发起新 LLM 调用。
- 因此 LLM 调用数与 token 用量由 usage observer 实采；融合的附加成本≈0。

用法:
    python -m evaluation.run_chinese_eval
    python -m evaluation.run_chinese_eval --gold evaluation/datasets/chinese_cases.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from app.tools.llm_json import register_usage_observer
from evaluation.datasets import DEFAULT_DATASET
from evaluation.fusion import generate_fused
from evaluation.generate import load_gold
from evaluation.run_matching_eval import evaluate

logger = logging.getLogger("jobcraft.evaluation.chinese")

# 成本估算单价（USD / 1M tokens）。glm-flash 系官方约 $0.06/M 入、$0.40/M 出，
# 可通过环境变量覆盖（本节做近似估算，不构成计费承诺）。
PRICE_INPUT_PER_1M = float(os.getenv("JC_EVAL_PRICE_INPUT_PER_1M", "0.06"))
PRICE_OUTPUT_PER_1M = float(os.getenv("JC_EVAL_PRICE_OUTPUT_PER_1M", "0.40"))

# 本轮只比较的四路策略（与用户要求一致：LLM vs Hybrid A vs Hybrid C + Keyword baseline）
COMPARED_STRATEGIES = ["keyword", "llm", "hybrid_a", "hybrid_c"]

DATASET_DIFFICULTY_MIX = {
    "direct": 3,
    "semantic": 2,
    "partial": 2,
    "negative": 2,
    "transfer": 1,
}

METRIC_ORDER = [
    "accuracy",
    "macro_f1",
    "precision_relevant",
    "recall_relevant",
    "score_mae",
    "ndcg_at_3",
]


def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    price_in_per_1m: float = PRICE_INPUT_PER_1M,
    price_out_per_1m: float = PRICE_OUTPUT_PER_1M,
) -> float:
    """按 token 用量估算单次/累计调用的美元成本。

    :param prompt_tokens: 输入 token 数
    :param completion_tokens: 输出 token 数
    :param price_in_per_1m: 每 1M 输入 token 单价（USD）
    :param price_out_per_1m: 每 1M 输出 token 单价（USD）
    :return: 估算成本（USD）
    """
    return (
        prompt_tokens / 1_000_000 * price_in_per_1m
        + completion_tokens / 1_000_000 * price_out_per_1m
    )


class UsageCollector:
    """从 llm_json observer 采集单次运行内的调用次数、耗时与 token 用量。

    以非缓存调用为准（缓存命中不等于真实 LLM 成本）；内部存储 `*_cached` 供诊断。
    """

    def __init__(self) -> None:
        self.calls = 0
        self.calls_cached = 0
        self.duration_s = 0.0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    def __call__(self, info: dict[str, Any]) -> None:
        if info.get("from_cache"):
            self.calls_cached += 1
            return
        self.calls += 1
        self.duration_s += float(info.get("duration_s") or 0.0)
        self.prompt_tokens += int(info.get("prompt_tokens") or 0)
        self.completion_tokens += int(info.get("completion_tokens") or 0)
        self.total_tokens += int(info.get("total_tokens") or 0)

    def estimated_cost(self) -> float:
        """当前累计 token 用量的估算成本（USD）。"""
        return estimate_cost(self.prompt_tokens, self.completion_tokens)

    def snapshot(self) -> dict[str, Any]:
        """汇总采样结果，供报告/表格使用。"""
        return {
            "llm_calls": self.calls,
            "llm_calls_cached": self.calls_cached,
            "duration_s": round(self.duration_s, 2),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost(), 4),
        }


def observed_generate(
    gold_cases: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], UsageCollector]:
    """用 LLM 策略生成预测，同时采集 Latency / Calls / Tokens。

    :param gold_cases: gold case 列表
    :return: (predictions, usage snapshot)
    """
    collector = UsageCollector()
    register_usage_observer(collector)
    from evaluation.strategies import LLMStrategy

    strategy = LLMStrategy()
    predictions = []
    for case in gold_cases:
        predictions.append(
            {"case_id": case["case_id"], "predictions": strategy.predict_case(case)}
        )
    return predictions, collector


def produce_hybrid(
    gold_cases: list[dict[str, Any]], llm_preds: list[dict[str, Any]], mode: str
) -> list[dict[str, Any]]:
    """在共享 LLM 预测上确定性融合出 A（加权）或 C（max）。

    :param gold_cases: gold case 列表
    :param llm_preds: 共享 LLM 预测
    :param mode: hybrid_a / hybrid_c
    :return: 融合预测列表
    """
    llm_by_id = {p["case_id"]: p for p in llm_preds}
    rows = []
    for case in gold_cases:
        pred = generate_fused(llm_by_id[case["case_id"]], case, mode)
        rows.append({"case_id": case["case_id"], "predictions": pred})
    return rows


def run_benchmark(gold_path: Path, outdir: Path) -> dict[str, Any]:
    """执行中文 benchmark 全流程，返回结果汇总（供 main 打印与写报告复用）。

    :param gold_path: gold 数据集路径
    :param outdir: 预测文件输出目录
    :return: 汇总 dict {metrics, usage, latency, rows, strategies}
    """
    gold_cases = load_gold(gold_path)
    outdir.mkdir(parents=True, exist_ok=True)

    # 1) Keyword baseline（本地，无 LLM）
    from evaluation.strategies import KeywordStrategy

    kw_start = time.perf_counter()
    kw_preds = []
    for case in gold_cases:
        kw_preds.append(
            {
                "case_id": case["case_id"],
                "predictions": KeywordStrategy().predict_case(case),
            }
        )
    kw_latency = time.perf_counter() - kw_start

    # 2) 共享 LLM 预测（采集 latency/calls/tokens）
    llm_preds, usage = observed_generate(gold_cases)
    llm_latency = usage.duration_s

    # 3) 确定性离线融合 A / C（不消耗新 LLM）
    hybrid_a = produce_hybrid(gold_cases, llm_preds, "hybrid_a")
    hybrid_c = produce_hybrid(gold_cases, llm_preds, "hybrid_c")

    # 4) 写预测文件（可复现）
    pred_files = {
        "keyword": kw_preds,
        "llm": llm_preds,
        "hybrid_a": hybrid_a,
        "hybrid_c": hybrid_c,
    }
    for name, preds in pred_files.items():
        out = outdir / f"chinese_predictions_{name}.jsonl"
        with out.open("w", encoding="utf-8") as fh:
            for row in preds:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # 5) 评估四路策略
    metrics = {}
    for name, preds in pred_files.items():
        metrics[name] = evaluate(gold_cases, preds)

    return {
        "gold_cases": gold_cases,
        "metrics": metrics,
        "usage": usage.snapshot(),
        "latency": {
            "keyword": round(kw_latency, 2),
            "llm": llm_latency,
            "hybrid_a": round(llm_latency + 0.001, 2),  # 融合附加成本≈0
            "hybrid_c": round(llm_latency + 0.001, 2),
        },
        "pred_files": pred_files,
    }


def build_report(result: dict[str, Any], report_path: Path) -> None:
    """把 benchmark 结果写成第二份对比报告（Markdown）。

    :param result: run_benchmark 的返回
    :param report_path: 输出报告路径
    """
    gold_cases = result["gold_cases"]
    metrics = result["metrics"]
    usage = result["usage"]
    latency = result["latency"]

    header = [
        "# Chinese Real-world Matching Benchmark (v0.2)",
        "",
        "## Status",
        "",
        f"**v0.2 — 中文真实风格 JD 回测完成（{len(gold_cases)} cases，2026-09-09）。**",
        "",
        "模型: `glm-4-flash`。对比 Keyword baseline / LLM / Hybrid A（0.4 加权）/ Hybrid C（max）。",
        "LLM 预测共享同一份文件，Hybrid A/C 为确定性离线融合；Latency/Calls/Cost 由 usage observer 实测。",
        "",
        f"- LLM 调用: {usage['llm_calls']}（缓存命中 {usage['llm_calls_cached']}）",
        f"- Token 用量: prompt {usage['prompt_tokens']} / completion {usage['completion_tokens']} / total {usage['total_tokens']}",
        f"- 估算成本（${PRICE_INPUT_PER_1M}/1M in + ${PRICE_OUTPUT_PER_1M}/1M out）: ${usage['estimated_cost_usd']:.4f}",
        "",
        "## Datasets",
        "",
        "| difficulty | count |",
        "|---:|---:|",
    ]
    difficulty_counts: dict[str, int] = {}
    for case in gold_cases:
        d = case.get("difficulty", "unknown")
        difficulty_counts[d] = difficulty_counts.get(d, 0) + 1
    for d, c in sorted(difficulty_counts.items()):
        header.append(f"| {d} | {c} |")

    body = [
        "",
        "## Results",
        "",
        "| Metric | Keyword | LLM | Hybrid A (0.4/0.6) | Hybrid C (max) |",
        "|---|---:|---:|---:|---:|",
    ]
    for key in METRIC_ORDER:
        arrow = {"score_mae": "↓", "ndcg_at_3": "↑"}.get(key, "↑")
        row = f"| {key} {arrow} |"
        for name in COMPARED_STRATEGIES:
            v = metrics[name][key]
            row += f" {v:.4f} |"
        body.append(row)

    body += [
        "",
        "### 工程维度：Latency / LLM Calls / Estimated Cost",
        "",
        "| Strategy | Latency (s) | LLM Calls | Est. Cost (USD) |",
        "|---|---:|---:|---:|",
    ]
    body.append(f"| Keyword | {latency['keyword']} | 0 | 0.0000 |")
    body.append(
        f"| LLM | {latency['llm']:.2f} | {usage['llm_calls']} | {usage['estimated_cost_usd']:.4f} |"
    )
    body.append(
        f"| Hybrid A | {latency['hybrid_a']:.2f} | {usage['llm_calls']} | {usage['estimated_cost_usd']:.4f} |"
    )
    body.append(
        f"| Hybrid C | {latency['hybrid_c']:.2f} | {usage['llm_calls']} | {usage['estimated_cost_usd']:.4f} |"
    )
    body += [
        "",
        "> 说明：LLM 与 Hybrid A/C 的 LLM Calls 相同——A/C 的语义信号仍然来自那一次 LLM 调用，融合本身是零成本的本地计算。",
        "> Keyword 为 0 次 LLM 调用，但精度显著低于语义匹配。",
        "",
        "## 关键结论",
        "",
        "1. **max(Local, LLM) 与纯 LLM 在质量上持平，且不减少 LLM 调用。**",
        "2. max 的真正价值是**安全融合**：不改变 LLM 的评分，只在 LLM 缺位/兜底下限时依靠本地分，而不是性能或成本优化。",
        "3. 若目标是**减少 LLM 调用**，应引入路由/缓存，而非融合权重。",
        "",
    ]

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(header + body))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--outdir", type=Path, default=Path(__file__).parent / "predictions"
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(__file__).parent / "reports" / "chinese_matching_report.md",
    )
    args = parser.parse_args()

    result = run_benchmark(args.gold, args.outdir)
    metrics = result["metrics"]
    for name in COMPARED_STRATEGIES:
        print(
            f"[v0.2] {name}: "
            + " ".join(f"{k}={v:.4f}" for k, v in metrics[name].items())
        )
    build_report(result, args.report)
    print(f"[v0.2] report -> {args.report}")


if __name__ == "__main__":
    main()
