# Experience Matching Evaluation v0.1

This evaluation pilot measures how reliably JobCraft matches candidate experience cards to job requirements.

## Goal

Compare three matching strategies:

1. **Keyword** — deterministic/local matching.
2. **LLM** — semantic matching from `ScoreMatchAgent`.
3. **Hybrid** — the current product strategy that fuses local and LLM scores.

The pilot intentionally starts with **10 manually curated cases** before expanding to a larger benchmark.

## Evaluation Levels

### 1. Relevance classification

Each experience card is labeled as one of:

- `high`
- `medium`
- `low`
- `irrelevant`

### 2. Score calibration

Compare the model's 0–100 score with the human gold score using Mean Absolute Error (MAE).

### 3. Ranking quality

Compare the predicted ranking of experience cards against the human ranking using NDCG@3.

## Dataset design

The pilot contains five case types:

| Type | Count |
|---|---:|
| Direct Match | 2 |
| Semantic Match | 3 |
| Partial Match | 2 |
| Negative Match | 2 |
| Cross-domain Transfer | 1 |

The dataset contains synthetic portfolio-style examples for methodology validation. It is **not** a claim about real production accuracy.

## Files

```text
evaluation/
├── README.md
├── datasets/
│   └── matching_cases.jsonl
├── strategies.py
├── generate.py
├── run_matching_eval.py
└── reports/
    └── matching_report.md
```

- `strategies.py` — 三种策略的预测生成器，复用现有生产代码（`_local_score` / `ScoreMatchAgent`）。
- `generate.py` — 用指定策略跑 gold 数据集，产出预测文件（每行一条 case）。
- `run_matching_eval.py` — model-agnostic 评估器，消费预测文件计算指标。

## Running the pipeline

The evaluator is deliberately separated from the model invocation. It consumes a prediction file so that different strategies/models can be compared under the same gold labels.

```bash
# 1. 生成预测：keyword / llm / hybrid（每类独立跑）或 all
python -m evaluation.generate --strategy all

# 2. Hybrid 权重实验：在同一份 LLM 预测上做确定性离线融合（不消耗新 LLM）
python -m evaluation.fuse --llm-pred evaluation/predictions/predictions_llm.jsonl
# 产出 predictions_hybrid_a.jsonl (0.4/0.6) / hybrid_b.jsonl (0.2/0.8) / hybrid_c.jsonl (max)

# 3. 评估预测（对每种策略）
python evaluation/run_matching_eval.py \
  --gold evaluation/datasets/matching_cases.jsonl \
  --pred evaluation/predictions/predictions_hybrid_a.jsonl \
  --strategy hybrid_a
```

Prediction format:

```json
{"case_id":"match_001","predictions":[{"experience_id":"e1","label":"high","score":88}]}
```

One JSON object per line. The `label` is derived from `score` with thresholds aligned to `_match_level` (`>=80` high, `>=60` medium, `>=40` low).

### Hybrid fusion weights

`evaluation/fusion.py` provides pure fusion functions used by `evaluation/fuse.py`:

| Variant | Weight | Usage |
|---|---|---|
| hybrid_a | `0.4 * local + 0.6 * llm` | 现状产品权重 |
| hybrid_b | `0.2 * local + 0.8 * llm` | LLM-heavy 实验 |
| hybrid_c | `max(local, llm)` | Local 只抬升不拉低 |

Because `fuse.py` derives all variants from one shared LLM prediction file, the comparison isolates the fusion weight from LLM nondeterminism.

## Metrics

The pilot reports:

- Accuracy
- Macro F1
- Precision (binary: relevant vs irrelevant)
- Recall (binary: relevant vs irrelevant)
- Score MAE
- NDCG@3

### Relevance mapping

For binary precision/recall, `high` and `medium` are treated as **relevant**. `low` and `irrelevant` are treated as **not relevant**.

## Results (v0.1, glm-4-flash, shared LLM scores)

| Metric | Keyword | LLM | Hybrid A (0.4/0.6) | Hybrid B (0.2/0.8) | Hybrid C (max) |
|---|---:|---:|---:|---:|---:|
| Accuracy | 0.4667 | **0.9333** | 0.5667 | 0.7333 | **0.9333** |
| Macro F1 | 0.1566 | 0.6340 | 0.2471 | 0.3519 | 0.6340 |
| Recall (relevant) | 0.1111 | 0.9444 | 0.2778 | 0.5556 | 0.9444 |
| Score MAE ↓ | 42.8367 | 11.7000 | 20.3433 | 14.6833 | **11.6900** |
| NDCG@3 ↑ | 0.9740 | 0.9535 | 0.9612 | 0.9612 | **0.9740** |

Key findings:
- **Local signal did not add value to semantic matching on this dataset.** Case-by-instance, pure LLM was closest to the gold score in 24/30 instances; weighted fusion (A, and to a lesser degree B) drags LLM scores below thresholds.
- **`max(Local, LLM)` (C) matches pure LLM structurally** — it can never lower an LLM score, so local only participates when it is genuinely higher.
- Recommendation: switch production fusion from `0.4*local + 0.6*llm` to `max(local, llm)`, then re-validate on Chinese real JD data (dataset is synthetic English).

Full per-case failure analysis: [`reports/matching_report.md`](reports/matching_report.md).

## Important limitation

The first version evaluates the matching layer independently from JD extraction. The gold dataset therefore uses normalized requirements rather than measuring the upstream `JdAtsAgent` itself.

Future versions should add:

- 30–100 cases
- real/public JD examples with licensing checked
- blind second-pass human labeling
- inter-rater agreement
- model/version/cost/latency tracking
- regression runs in CI
