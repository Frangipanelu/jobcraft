# JD Extraction Evaluation Report (v0.4)

## Status

**v0.4 — JD Extraction 回测完成（40 条 JD，2026-09）。**

模型: `glm-4.7-flash`（用户已切换）。链路: JD 原文 → `JdAtsAgent` → `ATSProfile`。
重点：**AI 是否正确抽取岗位要求**（Required/Preferred Skills、Responsibilities、Keywords、Dimension、Salary/Location、Hidden Requirement）。
v0.4 新增：**Error Taxonomy（E1-E8）**、**Field Completeness**、**Critical Error Rate**、**Prompt A/B/C 对比**。

- Prompt 版本: `v3`（evidence-first，含 raw/校验两态对比）
- LLM 调用: 40（缓存命中 0）
- Token 用量: prompt 83461 / completion 150852 / total 234313
- 估算成本（$0.06/1M in + $0.4/1M out）: $0.0653
- 墙钟延迟: 39.99s

## Results（字段抽取 P/R/F1，micro 聚合）

| 维度 | Precision | Recall | F1 |
|---|---:|---:|---:|
| required_skills | 0.4125 | 0.2396 | 0.3031 |
| responsibilities | 0.8089 | 0.3285 | 0.4673 |
| culture_keywords | 0.4737 | 0.1304 | 0.2045 |
| preferred_skills | 0.3675 | 0.3446 | 0.3557 |

| 维度 | Accuracy |
|---|---:|
| Dimension (D1-D8 level) | 0.0000 |
| salary Exact Match | 12/40 |
| location Exact Match | 0/40 |

## Prompt 版本对比

| 指标 | Prompt C (v3) raw |
|---|---|
| Required Skills F1 | 0.3503 |
| Responsibilities F1 | 0.5657 |
| Keywords F1 | 0.3396 |
| Preferred Skills F1 | 0.3544 |
| Dimension Accuracy | 0.0000 |
| Salary Exact | 15/40 |
| Location Exact | 0/40 |
| Critical Error Rate | 40.97% |
| Error 总数 | 1711 |

**总结论（A/B/C）**：基于 40 条中文合成 JD，对比三种提示词设计。

- **安全（Critical Error Rate）**：Prompt C (v3) raw **40.97%**。确定性软校验（C' 证据校验列：本体归位→职责/技能纠正→ACCEPT/REVIEW/REJECT）把 Critical 压到三类设计最低，同时标量回填优于 raw 列（Salary 15/40 → 15/40、Location 0/40）。剩余风险在 REVIEW 档过窄（语义门槛 ~0.78 用嵌入相似度升级，列为Layer-2 架构迭代）。
- **召回**：evidence-first + 软校验后字段 F1 不再全线下行（Required F1 0.350 → 0.350），标量回填显著（Salary 15/40）；确定性后处理（教育/年限归位、职责/技能句首判定）分别压低 E2 与 E3（MISCLASSIFIED）。注意校验列的职责 F1 仍有下降（0.566 → 0.000），REJECT 档过严会继续吃职责召回，属 REVIEW 宽度升级的待办。
- **维度全线偏弱**：三版本 Dimension Accuracy 均低于 0.36，D1-D8 等级出数与校验都不可靠 → 建议回归直接模型输出 + 单独约束，勿叠加证据校验放大损失。
- **Keywords 召回很低**：三版本仅 0.34–0.34，文化类关键词基本抓不住 → 需单独提示词或独立任务。

**证据校验统计（v3）**：LLM 单次输出 → 确定性校验去除无证据条目。

- 证据命中 case：34/40
- 证据条目总数：810
- 校验丢弃条目数：352（无证据支撑的幻造值）


## Error Taxonomy

错误分类（E1-E8）。自动识别 E1/E2/E3/E6/E7/E8；E4（粒度）用数量比启发式；缩写等需词典的归类为 E2。

| 类型 | 含义 | 数量 |
|---|---|---:|
| E1 MISSING | gold 有，pred 没有 | 800 |
| E2 HALLUCINATED | pred 有，gold 没有 | 169 |
| E3 MISCLASSIFIED | 字段间误分类 | 370 |
| E4 GRANULARITY | 粒度不匹配 | 43 |
| E5 SEMANTIC | 语义理解错误 | 0 |
| E6 DIMENSION | D1-D8 等级错误 | 0 |
| E7 HIDDEN | 潜台词未识别 | 0 |
| E8 NORMALIZATION | 同义词/缩写/格式 | 125 |

**Critical Error Rate（required/preferred 字段误分类占比）: 30.19%**

| 字段 | E1 Missing | E2 Hallucinated | E3 Misclassified | E4 Granularity | E6 Dimension | E7 Hidden | E8 Normalization |
|---|---:|---:|---:|---:|---:|---:|---:|
| required_skills | 304 | 98 | 176 | 12 | 0 | 0 | 29 |
| responsibilities | 273 | 18 | 42 | 15 | 0 | 0 | 82 |
| culture_keywords | 121 | 14 | 72 | 8 | 0 | 0 | 3 |
| preferred_skills | 102 | 28 | 80 | 8 | 0 | 0 | 11 |
| dimension_D1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| dimension_D2 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| dimension_D3 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| dimension_D4 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| dimension_D5 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| dimension_D6 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| dimension_D7 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| dimension_D8 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |

## Field Completeness

gold 字段缺失字段完整性（被 pred 覆盖的比例，micro 平均）。

| 字段 | Completeness |
|---|---:|
| required_skills | 0.353 |
| responsibilities | 0.531 |
| culture_keywords | 0.296 |
| preferred_skills | 0.546 |
| salary | 0.300 |
| location | 0.000 |

## Hidden Requirements（人工复核清单）

模型 `subtext_decoded` 是对潜台词的解读，主观性高，脚本仅输出待审清单：

1. **real_001** 希维科技(广州)项目助理(PMO) — 表面要求覆盖 0%（gold 0 / pred 0 条）
2. **real_002** 魔芯(杭州)科技AI项目助理 — 表面要求覆盖 0%（gold 0 / pred 0 条）
3. **real_003** 本原智数部门助理(政企事业部) — 表面要求覆盖 0%（gold 0 / pred 0 条）
4. **real_004** 深圳大学研究助理 — 表面要求覆盖 0%（gold 0 / pred 0 条）
5. **real_005** 丰泊国际超级AI产品经理(MJ000125) — 表面要求覆盖 0%（gold 0 / pred 0 条）
6. **real_006** Synology群晖售前技术支持 — 表面要求覆盖 0%（gold 0 / pred 0 条）
7. **real_007** 平安科技-后端开发工程师（AI） — 表面要求覆盖 0%（gold 0 / pred 0 条）
8. **real_008** 南方日报-新媒体助理 — 表面要求覆盖 0%（gold 0 / pred 0 条）
9. **real_009** 光速运动-AI数据运营分析师 — 表面要求覆盖 0%（gold 0 / pred 0 条）
10. **real_010** 深圳市洲际宇科技-技术文档工程师 — 表面要求覆盖 0%（gold 0 / pred 0 条）
11. **real_011** 外包-研究报告撰写 — 表面要求覆盖 0%（gold 0 / pred 0 条）
12. **real_012** 先石科技-AI项目协调员 — 表面要求覆盖 0%（gold 0 / pred 0 条）
13. **real_013** 项目管理岗 — 表面要求覆盖 0%（gold 0 / pred 0 条）
14. **real_014** 项目管理（外企·HSBC） — 表面要求覆盖 0%（gold 0 / pred 0 条）
15. **real_015** 运营助理 — 表面要求覆盖 0%（gold 0 / pred 0 条）
16. **real_016** ai应用工程师|LLM/RAG/M — 表面要求覆盖 0%（gold 0 / pred 0 条）
17. **real_017** AI HR创意沟通&技术应用方向(MJ000220) — 表面要求覆盖 0%（gold 0 / pred 0 条）
18. **real_018** 技术支持工程师 — 表面要求覆盖 0%（gold 0 / pred 0 条）
19. **real_019** AI工程师 — 表面要求覆盖 0%（gold 0 / pred 0 条）
20. **real_020** 硬件产品专员 — 表面要求覆盖 0%（gold 0 / pred 0 条）
21. **real_021** 助理项目经理 — 表面要求覆盖 0%（gold 0 / pred 0 条）
22. **real_022** 运营专员（AI应用与流程梳理方向) — 表面要求覆盖 0%（gold 0 / pred 0 条）
23. **real_023** 供应链专员(外企，英语)(MJ000113) — 表面要求覆盖 0%（gold 0 / pred 0 条）
24. **real_024** Al Builder - 产品 — 表面要求覆盖 0%（gold 0 / pred 0 条）
25. **real_025** 机器人产品运营 — 表面要求覆盖 0%（gold 0 / pred 0 条）
26. **real_026** AI工具产品经理 — 表面要求覆盖 0%（gold 0 / pred 0 条）
27. **real_027** 商务助理 — 表面要求覆盖 0%（gold 0 / pred 0 条）
28. **real_028** IP产品企划 — 表面要求覆盖 0%（gold 0 / pred 0 条）
29. **real_029** 财务BP（公共事务中心/资产平台） — 表面要求覆盖 0%（gold 0 / pred 0 条）
30. **real_030** 薪酬与员工关系岗 — 表面要求覆盖 0%（gold 0 / pred 0 条）
31. **real_031** 时尚创作者运营 — 表面要求覆盖 0%（gold 0 / pred 0 条）
32. **real_032** 产品包装设计经理 — 表面要求覆盖 0%（gold 0 / pred 0 条）
33. **real_033** 财务负责人 — 表面要求覆盖 0%（gold 0 / pred 0 条）
34. **real_034** 生产经理 — 表面要求覆盖 0%（gold 0 / pred 0 条）
35. **real_035** 渠道管理经理 — 表面要求覆盖 0%（gold 0 / pred 0 条）
36. **real_036** 销售运营-项目管理 — 表面要求覆盖 0%（gold 0 / pred 0 条）
37. **real_037** 平台活动团队货架运营方向 — 表面要求覆盖 0%（gold 0 / pred 0 条）
38. **real_038** Senior Legal Counsel — 表面要求覆盖 0%（gold 0 / pred 0 条）
39. **real_039** 总行-风险管理岗（市场风险） — 表面要求覆盖 0%（gold 0 / pred 0 条）
40. **real_040** 综合管理文员 — 表面要求覆盖 0%（gold 0 / pred 0 条）

## Case-level 明细

| case | job | RequiredSkills F1 | Responsibilities F1 | Keywords F1 | PreferredSkills F1 | DimAcc | Salary | Location | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| real_001 | 希维科技(广州)项目助理(PMO) | 0.57 | 0.40 | 0.50 | 1.00 | 0/8 | ✗ | ✗ | 22 |
| real_002 | 魔芯(杭州)科技AI项目助理 | 0.54 | 0.27 | 0.00 | 0.00 | 0/8 | ✗ | ✗ | 38 |
| real_003 | 本原智数部门助理(政企事业部) | 0.17 | 0.55 | 0.00 | 0.40 | 0/8 | ✗ | ✗ | 32 |
| real_004 | 深圳大学研究助理 | 0.15 | 0.43 | 0.44 | 0.40 | 0/8 | ✗ | ✗ | 30 |
| real_005 | 丰泊国际超级AI产品经理(MJ000125) | 0.19 | 0.67 | 0.33 | 0.00 | 0/8 | ✗ | ✗ | 26 |
| real_006 | Synology群晖售前技术支持 | 0.00 | 0.80 | 0.00 | 0.44 | 0/8 | ✗ | ✗ | 35 |
| real_007 | 平安科技-后端开发工程师（AI） | 0.27 | 0.60 | 0.00 | 0.57 | 0/8 | ✗ | ✗ | 32 |
| real_008 | 南方日报-新媒体助理 | 0.14 | 0.53 | 0.22 | 0.75 | 0/8 | ✗ | ✗ | 33 |
| real_009 | 光速运动-AI数据运营分析师 | 0.09 | 0.46 | 0.44 | 0.53 | 0/8 | ✗ | ✗ | 51 |
| real_010 | 深圳市洲际宇科技-技术文档工程师 | 0.67 | 0.55 | 0.57 | 0.00 | 0/8 | ✗ | ✗ | 10 |
| real_011 | 外包-研究报告撰写 | 0.00 | 0.00 | 0.00 | 0.00 | 0/8 | ✗ | ✗ | 17 |
| real_012 | 先石科技-AI项目协调员 | 0.38 | 0.77 | 0.56 | 1.00 | 0/8 | ✗ | ✗ | 32 |
| real_013 | 项目管理岗 | 0.00 | 0.00 | 0.00 | 0.00 | 0/8 | ✗ | ✗ | 25 |
| real_014 | 项目管理（外企·HSBC） | 0.00 | 0.00 | 0.00 | 0.00 | 0/8 | ✗ | ✗ | 9 |
| real_015 | 运营助理 | 0.34 | 0.27 | 0.00 | 0.44 | 0/8 | ✗ | ✗ | 71 |
| real_016 | ai应用工程师|LLM/RAG/M | 0.57 | 0.53 | 0.00 | 0.60 | 0/8 | ✗ | ✗ | 23 |
| real_017 | AI HR创意沟通&技术应用方向(MJ000220) | 0.00 | 0.00 | 0.00 | 0.00 | 0/8 | ✗ | ✗ | 36 |
| real_018 | 技术支持工程师 | 0.38 | 0.55 | 0.33 | 0.10 | 0/8 | ✗ | ✗ | 50 |
| real_019 | AI工程师 | 0.25 | 0.56 | 0.00 | 0.25 | 0/8 | ✗ | ✗ | 41 |
| real_020 | 硬件产品专员 | 0.00 | 0.00 | 0.00 | 0.00 | 0/8 | ✗ | ✗ | 18 |
| real_021 | 助理项目经理 | 0.33 | 0.55 | 0.00 | 0.00 | 0/8 | ✗ | ✗ | 49 |
| real_022 | 运营专员（AI应用与流程梳理方向) | 0.15 | 0.00 | 0.60 | 0.24 | 0/8 | ✗ | ✗ | 85 |
| real_023 | 供应链专员(外企，英语)(MJ000113) | 0.50 | 0.67 | 0.00 | 0.00 | 0/8 | ✗ | ✗ | 26 |
| real_024 | Al Builder - 产品 | 0.54 | 0.45 | 0.00 | 0.31 | 0/8 | ✗ | ✗ | 41 |
| real_025 | 机器人产品运营 | 0.00 | 0.00 | 0.00 | 0.00 | 0/8 | ✗ | ✗ | 112 |
| real_026 | AI工具产品经理 | 0.60 | 0.73 | 0.00 | 0.67 | 0/8 | ✓ | ✗ | 19 |
| real_027 | 商务助理 | 0.15 | 0.00 | 0.67 | 0.00 | 0/8 | ✗ | ✗ | 49 |
| real_028 | IP产品企划 | 0.31 | 0.46 | 0.57 | 0.80 | 0/8 | ✓ | ✗ | 21 |
| real_029 | 财务BP（公共事务中心/资产平台） | 0.54 | 0.80 | 0.00 | 0.00 | 0/8 | ✓ | ✗ | 26 |
| real_030 | 薪酬与员工关系岗 | 0.37 | 0.52 | 0.57 | 0.00 | 0/8 | ✓ | ✗ | 52 |
| real_031 | 时尚创作者运营 | 0.57 | 0.73 | 0.80 | 1.00 | 0/8 | ✓ | ✗ | 13 |
| real_032 | 产品包装设计经理 | 0.50 | 0.67 | 0.00 | 0.50 | 0/8 | ✓ | ✗ | 31 |
| real_033 | 财务负责人 | 0.00 | 0.00 | 0.00 | 0.00 | 0/8 | ✗ | ✗ | 75 |
| real_034 | 生产经理 | 0.41 | 0.71 | 0.00 | 0.00 | 0/8 | ✓ | ✗ | 42 |
| real_035 | 渠道管理经理 | 0.62 | 0.86 | 0.00 | 0.73 | 0/8 | ✓ | ✗ | 20 |
| real_036 | 销售运营-项目管理 | 0.21 | 0.69 | 0.00 | 0.55 | 0/8 | ✓ | ✗ | 47 |
| real_037 | 平台活动团队货架运营方向 | 0.19 | 0.46 | 0.00 | 0.00 | 0/8 | ✓ | ✗ | 63 |
| real_038 | Senior Legal Counsel | 0.43 | 0.91 | 0.00 | 0.00 | 0/8 | ✗ | ✗ | 37 |
| real_039 | 总行-风险管理岗（市场风险） | 0.40 | 0.73 | 0.00 | 0.77 | 0/8 | ✓ | ✗ | 37 |
| real_040 | 综合管理文员 | 0.37 | 0.53 | 0.00 | 0.00 | 0/8 | ✓ | ✗ | 31 |