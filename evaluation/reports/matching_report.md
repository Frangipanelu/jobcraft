# Experience Matching Evaluation Report

## Status

**v0.1 pilot — benchmark run completed on the 10-case dataset (Keyword / LLM / Hybrid), 2026-09.**

Model: `glm-4-flash`. Predictions generated via `evaluation.generate.py`, evaluated by `evaluation/run_matching_eval.py`. Chinese JD inputs were used for Keyword; LLM/Hybrid used the same gold cases through `ScoreMatchAgent`.

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
| Accuracy | 0.4667 | **0.9333** | 0.5667 |
| Macro F1 | 0.1566 | **0.8007** | 0.2716 |
| Precision (relevant) | 1.0000 | 1.0000 | 1.0000 |
| Recall (relevant) | 0.1111 | **0.8889** | 0.2778 |
| Score MAE ↓ | 42.8367 | **9.2667** | 25.6300 |
| NDCG@3 ↑ | 0.9740 | **0.9767** | 0.9585 |

## Failure Analysis

Record errors using these categories:

- **F1 Keyword Miss** — relevant experience lacks exact requirement wording.
- **F2 Semantic Miss** — meaning is related but the model fails to recognize it.
- **F3 False Positive** — unrelated experience receives an excessive score.
- **F4 Score Calibration** — direction is correct but numeric score is poorly calibrated.
- **F5 Ranking Error** — relevant cards are identified but ordered incorrectly.

| Case | Gold | Prediction | Failure Type | Root Cause | Improvement |
|---|---|---|---|---|---|
| match_001 e3 | medium | irrelevant (33.3) | F1 | Keyword 语义改写（"drone control" 等）无法命中 | 扩充同义词/词根归一化（chinese→course 等） |
| match_002 e1 | high | irrelevant (0.0) | F1 | "user research / cross-functional" 无字面命中 | 引入语义同义词表或模糊匹配 |
| match_003 e1 | high | irrelevant (0.0) | F1 | AI PM 经历全部为动词改写，零关键词命中 | 语义匹配落地 Keyword 不可行，转 Hybrid |
| match_005 e1 | high | medium (60.0) | F2/F4 | LLM 识别到相关但分数偏低（60 vs 88） | 校准 LLM score prompt 或使用 Hybrid 权重 |
| match_007 e2 | high | medium (70.0) | F4 | LLM 方向正确，分数欠校准（70 vs 84） | 增加评分锚点示例，做 score alignment |

### 关键模式

1. **Keyword 精准但召回极低**：Precision=1.0 但 Recall=0.11，语义改写的经历几乎全部漏判（f1）。
2. **LLM 大幅领先**：Recall 0.89 / MAE 9.3 / Macro-F1 0.80，只有 match_005/007 分数偏低属校准问题。
3. **Hybrid 被 Keyword 拖累**：融合 0.4 的 keyword 分把 LLM 高分（如 match_003 e1=80）拉到 48，整体低于纯 LLM。
4. **NDCG@3 全部接近 1**：排序层面三种策略都基本把相关经历排前面，问题集中在打分而非排序。

## Decision Rule

Do not optimize for score alone. Prefer the strategy that gives the best overall decision quality while keeping latency and LLM cost acceptable.

A successful next iteration should demonstrate fewer false positives and ranking errors, not merely a higher average score.

## Next Iteration

1. ~~Run all 10 cases for Keyword, LLM and Hybrid.~~ Done 2026-09.
2. Inspect every failure manually.
3. Fix the highest-impact failure pattern: **Hybrid 的 keyword 权重拖累 LLM 高分** — 建议实验 keyword 权重降至 0.2 或改用 max(local, llm) 融合。
4. Rerun the 10-case regression set.
5. Expand to 30 cases only after the pilot is stable.