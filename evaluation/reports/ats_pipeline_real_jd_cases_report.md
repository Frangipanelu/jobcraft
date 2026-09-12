# Pipeline 分层评测报告（L1 无 LLM 基线）

- 语料：real_jd_cases.jsonl（40 条）
- 范围：L1 确定性管道 + 空 inference 的 ATS 合并；L2（culture/D1-D8/subtext）不在本层

## L1-1 Structurer
span 失配：0

## L1-2 Classifier
条目数：694；UNKNOWN：199（28.7%）

## L1-3 Extractor（gold 近似命中）
| field | hit/total | rate |
|---|---|---|
| required | 138/769 | 17.95%
| preferred | 36/211 | 17.06%
| responsibility | 572/888 | 64.41%

- education 覆盖：35/40；years 覆盖：13/40
- key_metrics 总计：47
- core_keywords 分布：high 91 / medium 66 / low 42

## ATS-Safety（每个输出值是否被证据 span 支撑）
- accept（EXACT/CONTAINED）：479
- review（PARAPHRASE/INFERRED）：0
- reject（UNSUPPORTED）：0
- 支撑率 = (accept+review)/total：100.00%
