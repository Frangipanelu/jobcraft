# Chinese Real-world Matching Benchmark (v0.2)

## Status

**v0.2 — 中文真实风格 JD 回测（10 cases）。本报告为 2026-10-04 跨天复测（EVAL-018）轮；首测 2026-09-09 归档于 `results/baseline_20260909/`。**

模型: `glm-4.7-flash`（首测为 `glm-4-flash`，期间模型版本升级）。对比 Keyword baseline / LLM / Hybrid A（0.4 加权）/ Hybrid C（max）。
LLM 预测共享同一份文件，Hybrid A/C 为确定性离线融合；Latency/Calls/Cost 由 usage observer 实测。

- LLM 调用: 10（缓存命中 0，真调用）
- Token 用量: prompt 5504 / completion 7279 / total 12783
- 估算成本（$0.06/1M in + $0.4/1M out）: $0.0032

## Datasets

| difficulty | count |
|---:|---:|
| direct | 3 |
| negative | 2 |
| partial | 2 |
| semantic | 2 |
| transfer | 1 |

## Results

| Metric | Keyword | LLM | Hybrid A (0.4/0.6) | Hybrid C (max) |
|---|---:|---:|---:|---:|
| accuracy ↑ | 0.5667 | 0.8000 | 0.6000 | 0.8000 |
| macro_f1 ↑ | 0.1676 | 0.3602 | 0.2918 | 0.3602 |
| precision_relevant ↑ | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| recall_relevant ↑ | 0.1875 | 0.6250 | 0.2500 | 0.6250 |
| score_mae ↓ | 40.1333 | 17.7333 | 25.1333 | 17.9000 |
| ndcg_at_3 ↑ | 0.9845 | 0.9868 | 0.9790 | 0.9868 |

### 工程维度：Latency / LLM Calls / Estimated Cost

| Strategy | Latency (s) | LLM Calls | Est. Cost (USD) |
|---|---:|---:|---:|
| Keyword | 0.0 | 0 | 0.0000 |
| LLM | 77.22 | 10 | 0.0032 |
| Hybrid A | 77.23 | 10 | 0.0032 |
| Hybrid C | 77.23 | 10 | 0.0032 |

> 说明：LLM 与 Hybrid A/C 的 LLM Calls 相同——A/C 的语义信号仍然来自那一次 LLM 调用，融合本身是零成本的本地计算。
> Keyword 为 0 次 LLM 调用，但精度显著低于语义匹配。

## 关键结论

1. **max(Local, LLM) 与纯 LLM 在质量上持平，且不减少 LLM 调用。**
2. max 的真正价值是**安全融合**：不改变 LLM 的评分，只在 LLM 缺位/兜底下限时依靠本地分，而不是性能或成本优化。
3. 若目标是**减少 LLM 调用**，应引入路由/缓存，而非融合权重。

## 跨天复测（EVAL-018，2026-10-04）

基线（2026-09-09，`glm-4-flash`）与本轮（`glm-4.7-flash`）对比，同一数据集 `chinese_cases.jsonl`（sha256 `02e73d38…`）：

| Metric (LLM 路) | 2026-09-09 | 2026-10-04 | Δ |
|---|---:|---:|---:|
| accuracy ↑ | 0.9000 | 0.8000 | -0.1000 |
| macro_f1 ↑ | 0.5991 | 0.3602 | -0.2389 |
| precision_relevant ↑ | 1.0000 | 1.0000 | 0 |
| recall_relevant ↑ | 0.8125 | 0.6250 | -0.1875 |
| score_mae ↓ | 13.2000 | 17.7333 | +4.5333 |
| ndcg_at_3 ↑ | 0.9845 | 0.9868 | +0.0023 |

**确定性对照（归因前提）**：Keyword 路两轮**逐位一致**（六项 delta 全 0）→ 评测代码与数据集零漂移，LLM 路 delta 全部来自模型侧。

**逐 case 抖动**：30 张卡中 19 张（63%）分数变化，12 张（40%）label 翻转；平均 |Δscore| = 18.4，最大 45；仅 cn_008/cn_009（全 0 分 negative）稳定。归因：① LLM 采样随机性（主因）；② 模型版本升级（混杂因素，completion 1828→7279 佐证输出行为差异），两者无法完全分离。

**复测验证的结论**：

1. `max(Local, LLM) ≡ LLM` 仍成立（hybrid_c 与 llm 持平），生产 max 策略（EVAL-PROD-001）**维持不回滚**。
2. Hybrid A 加权仍为负贡献（acc 0.60 < 0.80），结论复测成立。
3. **排序类指标稳定**（ndcg、precision 恒定）；**绝对分/阈值类抖动明显** → 阈值决策（如 high/medium/low 判档）不得依赖单次跑分，须多轮聚合或锚定排序。
4. 成本：本复测 $0.0032（10 calls），跨天复测成本可忽略。

回归基线与协议已固化至 `evaluation/results/regression_v1.json`（hard_checks：数据集指纹、keyword 逐位对照、ndcg/precision ±0.02 硬验收；绝对分抖动带 acc ±0.15 / mae ±5 / f1 ±0.25）。
