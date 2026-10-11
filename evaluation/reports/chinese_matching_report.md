# Chinese Real-world Matching Benchmark (v0.2)

## Status

**v0.2 — 中文真实风格 JD 回测完成（10 cases，2026-10-11）。**

模型: `glm-4.7-flash`。对比 Keyword baseline / LLM / Hybrid A（0.4 加权）/ Hybrid C（max）。
LLM 预测共享同一份文件，Hybrid A/C 为确定性离线融合；Latency/Calls/Cost 由 usage observer 实测。

- LLM 调用: 10（缓存命中 0）
- Token 用量: prompt 5504 / completion 9938 / total 15442
- 估算成本（$0.06/1M in + $0.4/1M out）: $0.0043

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
| macro_f1 ↑ | 0.1676 | 0.5216 | 0.2788 | 0.5216 |
| precision_relevant ↑ | 1.0000 | 0.8571 | 1.0000 | 0.8571 |
| recall_relevant ↑ | 0.1875 | 0.7500 | 0.2500 | 0.7500 |
| score_mae ↓ | 40.1333 | 16.0333 | 21.5000 | 16.2000 |
| ndcg_at_3 ↑ | 0.9845 | 0.9813 | 0.9813 | 0.9813 |

### 工程维度：Latency / LLM Calls / Estimated Cost

| Strategy | Latency (s) | LLM Calls | Est. Cost (USD) |
|---|---:|---:|---:|
| Keyword | 0.0 | 0 | 0.0000 |
| LLM | 207.73 | 10 | 0.0043 |
| Hybrid A | 207.73 | 10 | 0.0043 |
| Hybrid C | 207.73 | 10 | 0.0043 |

> 说明：LLM 与 Hybrid A/C 的 LLM Calls 相同——A/C 的语义信号仍然来自那一次 LLM 调用，融合本身是零成本的本地计算。
> Keyword 为 0 次 LLM 调用，但精度显著低于语义匹配。

## 关键结论

1. **max(Local, LLM) 与纯 LLM 在质量上持平，且不减少 LLM 调用。**
2. max 的真正价值是**安全融合**：不改变 LLM 的评分，只在 LLM 缺位/兜底下限时依靠本地分，而不是性能或成本优化。
3. 若目标是**减少 LLM 调用**，应引入路由/缓存，而非融合权重。
