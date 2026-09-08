# Experience Matching Evaluation Report

## Status

**v0.1 pilot — dataset and evaluator prepared; benchmark results not yet run.**

Do not add invented metrics. Results should only be filled after running the same predictions against all ten gold cases.

## Objective

Determine whether JobCraft's experience matching can reliably identify relevant experience and rank it for a target JD.

## Methods

| Strategy | Description |
|---|---|
| Keyword | Deterministic/local keyword overlap baseline |
| LLM | Semantic matching from the LLM matching agent |
| Hybrid | Current product strategy combining local and LLM signals |

## Results

| Metric | Keyword | LLM | Hybrid |
|---|---:|---:|---:|
| Accuracy | TBD | TBD | TBD |
| Macro F1 | TBD | TBD | TBD |
| Precision (relevant) | TBD | TBD | TBD |
| Recall (relevant) | TBD | TBD | TBD |
| Score MAE ↓ | TBD | TBD | TBD |
| NDCG@3 ↑ | TBD | TBD | TBD |

## Failure Analysis

Record errors using these categories:

- **F1 Keyword Miss** — relevant experience lacks exact requirement wording.
- **F2 Semantic Miss** — meaning is related but the model fails to recognize it.
- **F3 False Positive** — unrelated experience receives an excessive score.
- **F4 Score Calibration** — direction is correct but numeric score is poorly calibrated.
- **F5 Ranking Error** — relevant cards are identified but ordered incorrectly.

| Case | Gold | Prediction | Failure Type | Root Cause | Improvement |
|---|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD | TBD |

## Decision Rule

Do not optimize for score alone. Prefer the strategy that gives the best overall decision quality while keeping latency and LLM cost acceptable.

A successful next iteration should demonstrate fewer false positives and ranking errors, not merely a higher average score.

## Next Iteration

1. Run all 10 cases for Keyword, LLM and Hybrid.
2. Inspect every failure manually.
3. Fix the highest-impact failure pattern.
4. Rerun the 10-case regression set.
5. Expand to 30 cases only after the pilot is stable.
