# Chinese Real-world Matching Benchmark (v0.2)

## Status

**v0.2 — 中文真实风格 JD 回测完成（10 cases，2026-09-09）。**

模型: `glm-4-flash`。对比 Keyword baseline / LLM / Hybrid A（0.4 加权）/ Hybrid C（max）。
LLM 预测共享同一份文件，Hybrid A/C 为确定性离线融合；Latency/Calls/Cost 由 usage observer 实测。

- LLM 调用: 10（缓存命中 0）
- Token 用量: prompt 5944 / completion 1828 / total 7772
- 估算成本（$0.06/1M in + $0.4/1M out）: $0.0011

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
| accuracy ↑ | 0.5667 | 0.9000 | 0.6333 | 0.9000 |
| macro_f1 ↑ | 0.1676 | 0.5991 | 0.3592 | 0.5991 |
| precision_relevant ↑ | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| recall_relevant ↑ | 0.1875 | 0.8125 | 0.3125 | 0.8125 |
| score_mae ↓ | 40.1333 | 13.2000 | 21.0867 | 12.8667 |
| ndcg_at_3 ↑ | 0.9845 | 0.9845 | 0.9845 | 0.9845 |

### 工程维度：Latency / LLM Calls / Estimated Cost

| Strategy | Latency (s) | LLM Calls | Est. Cost (USD) |
|---|---:|---:|---:|
| Keyword | 0.0 | 0 | 0.0000 |
| LLM | 85.90 | 10 | 0.0011 |
| Hybrid A | 85.90 | 10 | 0.0011 |
| Hybrid C | 85.90 | 10 | 0.0011 |

> 说明：LLM 与 Hybrid A/C 的 LLM Calls 相同——A/C 的语义信号仍然来自那一次 LLM 调用，融合本身是零成本的本地计算。
> Keyword 为 0 次 LLM 调用，但精度显著低于语义匹配。

Latency 按次估算：LLM 10 次调用合计 85.9s，平均约 8.6s/case；融合附加延迟 <1ms，可忽略。

## 关键结论

1. **max(Local, LLM) 与纯 LLM 在质量上持平，且不减少 LLM 调用。**
2. max 的真正价值是**安全融合**：不改变 LLM 的评分，只在 LLM 缺位/兜底下限时依靠本地分，而不是性能或成本优化。
3. 若目标是**减少 LLM 调用**，应引入路由/缓存，而非融合权重。
4. 部署建议：切到 `max(Local, LLM)` —— 质量对齐 LLM，同时保留零成本本地兜底；当前加权 Hybrid A 在中文数据上同样确认是质量负贡献。
5. 成本量级：10 case 全流程 LLM token 成本仅约 **$0.0011**（Flash 单价下），成本不是限制因素，**打分校准质量才是**。
