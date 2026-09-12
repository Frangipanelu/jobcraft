# Pipeline 分层评测报告（L1 无 LLM 基线）

- 语料：jd_cases.jsonl（40 条）
- 范围：L1 确定性管道 + 空 inference 的 ATS 合并；L2（culture/D1-D8/subtext）不在本层

## L1-1 Structurer
span 失配：0

## L1-2 Classifier
条目数：307；UNKNOWN：1

## L1-3 Extractor（gold 近似命中）
| field | hit/total | rate |
|---|---|---|
| required | 124/224 | 55.36%
| preferred | 15/71 | 21.13%
| responsibility | 83/183 | 45.36%

- education 覆盖：9/40；years 覆盖：38/40
- key_metrics 总计：32
- core_keywords 分布：high 97 / medium 37 / low 8

## ATS-Safety（每个输出值是否被证据 span 支撑）
- accept（EXACT/CONTAINED）：323
- review（PARAPHRASE/INFERRED）：1
- reject（UNSUPPORTED）：0
- 支撑率 = (accept+review)/total：100.00%
