# Experience Matching Evaluation Report

## Status

**v0.1 pilot — benchmark run completed on the 10-case dataset (Keyword / LLM / Hybrid weight variants), 2026-09.**

Model: `glm-4-flash`. Predictions generated via `evaluation.generate.py`, fused by `evaluation.fuse.py`, evaluated by `evaluation/run_matching_eval.py`. Hybrid A/B/C all derive from the **same** shared LLM prediction file (deterministic offline fusion), so comparisons isolate the fusion weight from LLM nondeterminism.

## Objective

Determine whether JobCraft's experience matching can reliably identify relevant experience and rank it for a target JD.

## Methods

| Strategy | Description |
|---|---|
| Keyword | Deterministic/local keyword overlap baseline |
| LLM | Semantic matching from the LLM matching agent |
| Hybrid A | 0.4 Local + 0.6 LLM（现状） |
| Hybrid B | 0.2 Local + 0.8 LLM（LLM-heavy） |
| Hybrid C | max(Local, LLM)（Local 只抬升不拉低） |

## Results

| Metric | Keyword | LLM | Hybrid A (0.4/0.6) | Hybrid B (0.2/0.8) | Hybrid C (max) |
|---|---:|---:|---:|---:|---:|
| Accuracy | 0.4667 | **0.9333** | 0.5667 | 0.7333 | **0.9333** |
| Macro F1 | 0.1566 | 0.6340 | 0.2471 | 0.3519 | 0.6340 |
| Precision (relevant) | 1.0000 | 0.9444 | 1.0000 | 1.0000 | 0.9444 |
| Recall (relevant) | 0.1111 | 0.9444 | 0.2778 | 0.5556 | 0.9444 |
| Score MAE ↓ | 42.8367 | 11.7000 | 20.3433 | 14.6833 | **11.6900** |
| NDCG@3 ↑ | 0.9740 | 0.9535 | 0.9612 | 0.9612 | **0.9740** |

### 关于本表数字（重要）

- 之前报告的 Hybrid=0.5667 / Macro-F1=0.2716 是独立 LLM 调用的版本；本轮 A/B/C 全部基于**同一份** LLM 预测文件融合，消除 LLM 抖动后 A=0.5667 与历史一致，说明融合路径可复现。
- LLM 与 Hybrid C 在大多数字段几乎相同，因为本数据集中 local 分数极少高于 llm 分，max() 大多直接取 LLM 分。二者不是"巧合相同"，而是 max 融合在有 LLM 兜底时的数学必然。

## Hybrid Weight Ablation（本轮实验）

**结论先行：在本 10-case 数据集上，Local signal 没有为语义匹配增加价值，反而被 0.4 权重显著拖累。**

### 逐实例胜者（min |predicted - gold|，共 30 个 experience 实例）

| 胜者 | 胜出实例数 |
|---|---:|
| LLM | 24 |
| Hybrid A (0.4/0.6) | 3 |
| Hybrid B (0.2/0.8) | 2 |
| Hybrid C (max) | 1 |
| (并列归胜者) | — |

- LLM 在 30 个实例中 24 次最接近人工分数。
- A/B 只在 llm 分数偏高、local 0 分能"拉回来"的少数 case 胜出（match_006、match_005 e3 等），但它们的平均 MAE 仍远高。
- C 几乎没有独立胜场 —— 因为能抬升 LLM 的 local 分在本数据集里几乎不存在（Keyword Recall 只有 0.11）。

### 权重每升一档，误差如何变（Score MAE）

```
LLM(纯)  11.70
C, max  11.69   ← 与纯 LLM 几乎无差
B, 0.2  14.68   ← local 权重开始拉低
A, 0.4  20.34   ← 现状权重误差接近翻倍
Keyword 42.84   ← 纯 local 是下限
```

### 为什么 local 权重有害：病灶不是"权重"而是"分数语义不同"

1. **Keyword 分数不是校准过的语义分**。`_local_score` 输出的是"命中术语数/x10"的比例，命中率低时给 0~40；它从未被设计为"与 LLM 同量纲的置信度"。
2. **加权混合把校准问题传染给 LLM**。一处 0 分 local 会把 LLM 的 80 分拉到 48（0.4×0 + 0.6×80），直接跨过 threshold 掉档。这正是 match_003 e1（94 分经验被判 low）的原因。
3. **max 融合免疫了这种传染**。因为 max(local, llm) 永远不会低于 llm —— local 只在它确实更高时参与。这正是 C 表现等同 LLM 的结构性原因。
4. **Local 真正的价值不在"混合打分"**。它在整套系统里的正确定位是：recall 极低但 precision=1.0 的**确定性兜底**（无 LLM 成本、可解释），应在 LLM 失败/超时/降级时启用，而不是在正常路径上权重混合。

## Failure Analysis

Record errors using these categories:

- **F1 Keyword Miss** — relevant experience lacks exact requirement wording.
- **F2 Semantic Miss** — meaning is related but the model fails to recognize it.
- **F3 False Positive** — unrelated experience receives an excessive score.
- **F4 Score Calibration** — direction is correct but numeric score is poorly calibrated.
- **F5 Ranking Error** — relevant cards are identified but ordered incorrectly.

| Case | Gold | Prediction | Failure Type | Root Cause | Improvement |
|---|---|---|---|---|---|
| match_001 e3 | medium | irrelevant | F1 | Keyword 语义改写（"drone control" 等）无法命中 | 同义词/词根归一化 |
| match_003 e1 | high | low (A) → medium (B) → high (C) | F3 传染 | local 0 分把 LLM 80 分拉低，加权越重掉档越狠 | 改 max 或减小权重 |
| match_004 e2 | high | low (A) → medium (B) → high (C) | F3 传染 | 同上，LLM 86 分被 0 分 local 拉低 | 改 max 或减小权重 |
| match_005 e1 | high | medium | F2/F4 | LLM 识别到相关但分数偏低（60 vs 88） | 校准 score prompt |
| match_006 e1 | medium | high (llm) / medium (A) | F4/F2 | LLM 虚高，A 反而校正 | 保留本地分作兜底参考 |
| match_010 e1 | high | medium (llm/A/B) / medium (C) | F2 | 跨域转移 case LLM 保守给 60~70 | 提升语义校准 |

### 关键模式

1. **Keyword 精准但召回极低**：Precision=1.0 但 Recall=0.11，语义改写的经历几乎全部漏判（F1）。
2. **LLM 最优，Hybrid A 最差**：A 的 Macro-F1 0.25 是 LLM 的一半不到；把 local 权重从 0.4 降到 0.2（B）仅恢复到 0.35，仍显著低于 LLM。
3. **C 等同 LLM 是结构性结果，不是巧合**：max 融合永远不会拖低 LLM，本数据集 local 又几乎不高于 llm。
4. **NDCG@3 普遍高**：排序层三种策略基本正确，瓶颈在打分校准而非排序。

## Decision Rule

Do not optimize for score alone. Prefer the strategy that gives the best overall decision quality while keeping latency and LLM cost acceptable.

A successful next iteration should demonstrate fewer false positives and ranking errors, not merely a higher average score.

## Recommendation

基于本轮 10-case 回归，**建议生产路径从 `0.4 Local + 0.6 LLM` 切换到 `max(Local, LLM)`**：

- 期望收益：Score MAE ~20.3 → ~11.7，Macro-F1 0.25 → 0.63，且不额外消耗 LLM 调用。
- 风险：极小 —— max 在 LLM 已正确时不改变输出，只在 LLM 失败兜底时依赖 local。
- 需在**中文真实 JD** 上回测验证（本数据集为英文合成样本，local threshold 行为可能不同）。

## Next Iteration

1. ~~Run all 10 cases for Keyword, LLM and Hybrid.~~ Done 2026-09.
2. ~~Hybrid weight ablation (A/B/C against shared LLM scores).~~ Done 2026-09.
3. 在中文真实 JD + 真实经历上回测 `max(Local, LLM)`（验证是否同样优于 0.4/0.6）。
4. 复测量化 LLM 抖动对 A/B/C 结论的稳健性（同一份 llm 分已消除，跨天回归再验）。
5. 数据集补齐 30 条 + Regression 基线固化；仅当回归稳定后再扩量。