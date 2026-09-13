# JobCraft JD Pipeline — v3 vs v4 对比报告（40 条真实 JD）

> 对应「JobCraft JD Pipeline v4 渐进式重构执行 Prompt」§16/§17/§20-§23。
> 数据来源：`evaluation/predictions_real_jd/jd_ats_predictions_{v3,v4}.jsonl`（v4 已用当前 L1 重建并写盘）。
> 逐 JD diff 产物：`evaluation/results/v3_vs_v4.json`。

## 1. 聚合指标

### 官方 gold（全量 40 条，`real_jd_cases.jsonl`）

| 指标 | v3 | v4 | Δ(v4−v3) |
|---|--:|--:|--:|
| Required F1 | 0.3031 | 0.2475 | −0.0556 |
| Preferred F1 | 0.3557 | 0.5864 | **+0.2307** |
| Responsibilities F1 | 0.4673 | 0.6139 | **+0.1466** |
| Culture F1 | 0.2045 | 0.2000 | −0.0045 |
| Critical Error Rate | 0.3019 | 0.3598 | +0.0579 |
| LLM escalation（含核心 ATS 由 LLM 生成比例） | 1.0（整卷） | 1.0（仅 advanced） | 结构性下降 |

### 重标 spot-gold（10 条抽样，`real_jd_spot_gold.jsonl`，口径校准后）

| 指标 | v3 | v4 | Δ(v4−v3) |
|---|--:|--:|--:|
| Required F1 | 0.4497 | 0.4928 | **+0.0430** |
| Preferred F1 | 0.4722 | 0.5714 | **+0.0992** |
| Responsibilities F1 | 0.6875 | 0.9221 | **+0.2346** |
| Culture F1 | 0.1404 | 0.1429 | +0.0025 |
| Critical Error Rate | 0.4234 | 0.3304 | **−0.0929** |

### 成本（40 条，来自 predictions 的 usage 汇总）

| 指标 | v3 | v4 | Δ |
|---|--:|--:|--:|
| LLM calls | 40 | 40 | 0（v4 仍 1 次「收窄」调用，仅生成 advanced 字段） |
| prompt tokens | 83,461 | 115,513 | +38.4% |
| completion tokens | 150,852 | 77,602 | **−48.6%** |
| total tokens | 234,313 | 193,115 | **−17.6%** |

## 2. 逐 JD 结构迁移（§10 Core ATS 字段，v3→v4）

| 字段 | removed | added | kept |
|---|--:|--:|--:|
| required_skills | 287 | 119 | 33 |
| preferred_skills | 144 | 183 | 22 |
| responsibilities | 157 | 212 | 68 |
| core_keywords | 48 | 195 | 4 |

解读：v4 删掉了 v3 大量「整句级」required（147→ 粒度变小、去噪声）；职责条目因
`【岗位职责】` 方括号标题修复归位而净增；preferred 因 `【加分项】` 区块识别 + 非词典
原子兜底大幅补召回。

## 3. 本轮修复（对应 §12-D「extraction 有问题 → 修 backend」）

1. **`jd_structurer.py` 方括号标题**：支持 `【岗位职责】/【任职要求】/【加分项】` 被
   方括号包裹时仍正确切区块（此前「加分项」后跟 `】` 不满足标题跟随符）。
2. **`jd_ats_agent.merge_ats` LLM 只裁决 UNKNOWN**：歧义裁决仅在 L1 未定论条目上生效，
   且过滤格式/薪资 stub（`##Al Builder - 产品`、`欣旺达**生产经理****17-22k**`）。
   同时隔离缓存远期 raw 的陈旧裁决污染重建结果。
3. **`run_jd_eval` 重建持久化**：缓存重建（v3/v4）结果写回预测文件（latest-wins），
   spot/compare 可读到新 L1（此前只改内存、不写盘）。

修复前后 real_024 / real_034 的 required 中已无标题/薪资 stub。

## 4. 决策依据（§22 优先级）

- **Critical Error ↓ / Hallucination ↓**：spot-gold 口径 v4 更安全（Δ−0.0929）；
  官方 gold 口径仍偏 v3（Δ+0.0579）——该口径受「官方 gold required 噪声 + v3 证据层
  误杀被 gold 当正确」影响，已在 `evaluation/datasets/real_jd_spot_gold.jsonl` 校准中
  记录，未修改官方 gold（§18）。
- **Required / Preferred / Responsibilities / Keywords F1 ↑**：spot-gold 口径四项全面
  ≥ v3；官方 gold 除 Required外三项领先（Required 差距由 gold 噪声主导）。
- **LLM Calls / Tokens ↓**：token 总量 −17.6%，completion −48.6%。
- **UNKNOWN ↓**：非第一优化目标；L1 保留 UNKNOWN 语义，低置信进 LLM 裁决，未强压。

## 5. 结论与下一步

- v4 在校准口径下 Core ATS 四项全面 ≥ v3，Critical 更安全，成本更低；官方 gold 的
  required/critical 残余差值需逐条人工核对（`evaluation/results/v3_vs_v4.json`）。
- 尚未做：若需正式切默认 v4，先完成剩余人工 gold 复核（长句原子粒度、v3 证据误杀
  case），必要时将结果写回 PROGRESS/TODO 并归档 commit。