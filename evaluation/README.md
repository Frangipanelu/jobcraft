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
├── run_matching_eval.py
└── reports/
    └── matching_report.md
```

## Running the evaluator

The evaluator is deliberately separated from the model invocation. It consumes a prediction file so that different strategies/models can be compared under the same gold labels.

```bash
python evaluation/run_matching_eval.py \
  --gold evaluation/datasets/matching_cases.jsonl \
  --pred predictions.jsonl \
  --strategy hybrid
```

Prediction format:

```json
{"case_id":"match_001","predictions":[{"experience_id":"e1","label":"high","score":88}]}
```

One JSON object per line.

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

## Important limitation

The first version evaluates the matching layer independently from JD extraction. The gold dataset therefore uses normalized requirements rather than measuring the upstream `JdAtsAgent` itself.

Future versions should add:

- 30–100 cases
- real/public JD examples with licensing checked
- blind second-pass human labeling
- inter-rater agreement
- model/version/cost/latency tracking
- regression runs in CI
