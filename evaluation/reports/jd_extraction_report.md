# JD Extraction Evaluation Report (v0.4)

## Status

**v0.4 — JD Extraction 回测完成（10 条中文合成 JD，2026-09）。**

模型: `glm-4.7-flash`（用户已切换）。链路: JD 原文 → `JdAtsAgent` → `ATSProfile`。
重点：**AI 是否正确抽取岗位要求**（Required/Preferred Skills、Responsibilities、Keywords、Dimension、Salary/Location、Hidden Requirement）。
v0.4 新增：**Error Taxonomy（E1-E8）**、**Field Completeness**、**Critical Error Rate**。

- LLM 调用: 0（缓存命中 10）
- Token 用量: prompt 0 / completion 0 / total 0
- 估算成本（$0.06/1M in + $0.4/1M out）: $0.0000
- 墙钟延迟: 0.0s

## Results（字段抽取 P/R/F1，micro 聚合）

| 维度 | Precision | Recall | F1 |
|---|---:|---:|---:|
| required_skills | 0.6143 | 0.6825 | 0.6466 |
| responsibilities | 0.4390 | 0.3529 | 0.3913 |
| culture_keywords | 0.2812 | 0.3600 | 0.3158 |
| preferred_skills | 0.6818 | 0.7500 | 0.7143 |

| 维度 | Accuracy |
|---|---:|
| Dimension (D1-D8 level) | 0.4125 |
| salary Exact Match | 10/10 |
| location Exact Match | 9/10 |

## Error Taxonomy

错误分类（E1-E8）。自动识别 E1/E2/E3/E6/E7/E8；E4（粒度）用数量比启发式；缩写等需词典的归类为 E2。

| 类型 | 含义 | 数量 |
|---|---|---:|
| E1 MISSING | gold 有，pred 没有 | 33 |
| E2 HALLUCINATED | pred 有，gold 没有 | 79 |
| E3 MISCLASSIFIED | 字段间误分类 | 41 |
| E4 GRANULARITY | 粒度不匹配 | 1 |
| E5 SEMANTIC | 语义理解错误 | 0 |
| E6 DIMENSION | D1-D8 等级错误 | 47 |
| E7 HIDDEN | 潜台词未识别 | 5 |
| E8 NORMALIZATION | 同义词/缩写/格式 | 33 |

**Critical Error Rate（required/preferred 字段误分类占比）: 33.90%**

| 字段 | E1 Missing | E2 Hallucinated | E3 Misclassified | E4 Granularity | E6 Dimension | E7 Hidden | E8 Normalization |
|---|---:|---:|---:|---:|---:|---:|---:|
| required_skills | 10 | 15 | 18 | 0 | 0 | 0 | 4 |
| responsibilities | 12 | 9 | 15 | 0 | 0 | 0 | 20 |
| culture_keywords | 10 | 17 | 6 | 1 | 0 | 0 | 6 |
| preferred_skills | 1 | 6 | 2 | 0 | 0 | 0 | 3 |
| dimension_D1 | 0 | 0 | 0 | 0 | 5 | 0 | 0 |
| dimension_D2 | 0 | 0 | 0 | 0 | 5 | 0 | 0 |
| dimension_D3 | 0 | 0 | 0 | 0 | 7 | 0 | 0 |
| dimension_D4 | 0 | 0 | 0 | 0 | 3 | 0 | 0 |
| dimension_D5 | 0 | 0 | 0 | 0 | 7 | 0 | 0 |
| dimension_D6 | 0 | 0 | 0 | 0 | 10 | 0 | 0 |
| dimension_D7 | 0 | 0 | 0 | 0 | 3 | 0 | 0 |
| dimension_D8 | 0 | 0 | 0 | 0 | 7 | 0 | 0 |

## Field Completeness

gold 字段缺失字段完整性（被 pred 覆盖的比例，micro 平均）。

| 字段 | Completeness |
|---|---:|
| required_skills | 0.735 |
| responsibilities | 0.462 |
| culture_keywords | 0.350 |
| preferred_skills | 0.800 |
| salary | 1.000 |
| location | 0.900 |

## Hidden Requirements（人工复核清单）

模型 `subtext_decoded` 是对潜台词的解读，主观性高，脚本仅输出待审清单：

1. **jd_001** 后端开发工程师 — 表面要求覆盖 100%（gold 1 / pred 4 条）
   - gold「熟悉分布式缓存与消息队列」→ 命中模型「扎实掌握MySQL、Redis，熟悉分布式缓存与消息队列」hidden=需要具备数据库设计和缓存优化能力，能够处理高并发场景
2. **jd_002** 数据分析师 — 表面要求覆盖 100%（gold 1 / pred 5 条）
   - gold「具备良好的业务理解能力」→ 命中模型「具备良好的业务理解能力」hidden=需要能从业务角度提出有价值的分析洞察
3. **jd_003** AI 产品经理 — 表面要求覆盖 100%（gold 1 / pred 3 条）
   - gold「能与算法团队高效沟通」→ 命中模型「能与算法团队高效沟通」hidden=需要具备足够的技术理解力，否则无法有效协作
4. **jd_004** 前端开发工程师 — 表面要求覆盖 0%（gold 1 / pred 3 条）
   - gold「熟悉前端工程化」→ ✗ 未命中
5. **jd_005** 测试开发工程师 — 表面要求覆盖 0%（gold 1 / pred 4 条）
   - gold「具备良好的缺陷分析能力」→ ✗ 未命中
6. **jd_006** DevOps 工程师 — 表面要求覆盖 0%（gold 1 / pred 3 条）
   - gold「有大流量实战经验优先」→ ✗ 未命中
7. **jd_007** 产品运营专员 — 表面要求覆盖 0%（gold 1 / pred 4 条）
   - gold「责任心强，善于跨部门沟通」→ ✗ 未命中
8. **jd_008** iOS 工程师 — 表面要求覆盖 100%（gold 1 / pred 4 条）
   - gold「有完整的 App Store 上架经验」→ 命中模型「有完整的 App Store 上架经验」hidden=熟悉应用发布流程和合规要求，能够独立完成应用上架工作
9. **jd_009** 财务会计 — 表面要求覆盖 100%（gold 1 / pred 3 条）
   - gold「持有 CPA 或中级会计师证书优先」→ 命中模型「持有 CPA 或中级会计师证书」hidden=证明专业能力和职业成熟度
10. **jd_010** 客户成功经理 — 表面要求覆盖 0%（gold 1 / pred 4 条）
   - gold「结果导向，抗压能力强」→ ✗ 未命中

## Case-level 明细

| case | job | RequiredSkills F1 | Responsibilities F1 | Keywords F1 | PreferredSkills F1 | DimAcc | Salary | Location | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| jd_001 | 后端开发工程师 | 0.74 | 0.36 | 0.80 | 0.80 | 5/8 | ✓ | ✓ | 20 |
| jd_002 | 数据分析师 | 0.67 | 0.67 | 0.33 | 1.00 | 3/8 | ✓ | ✓ | 19 |
| jd_003 | AI 产品经理 | 0.33 | 0.25 | 0.29 | 0.50 | 2/8 | ✓ | ✓ | 29 |
| jd_004 | 前端开发工程师 | 0.92 | 0.44 | 0.00 | 0.80 | 5/8 | ✓ | ✗ | 22 |
| jd_005 | 测试开发工程师 | 0.53 | 0.44 | 0.50 | 0.50 | 2/8 | ✓ | ✓ | 27 |
| jd_006 | DevOps 工程师 | 0.71 | 0.00 | 0.33 | 0.50 | 6/8 | ✓ | ✓ | 26 |
| jd_007 | 产品运营专员 | 0.60 | 0.44 | 0.80 | 1.00 | 3/8 | ✓ | ✓ | 20 |
| jd_008 | iOS 工程师 | 0.86 | 0.25 | 0.00 | 1.00 | 4/8 | ✓ | ✓ | 20 |
| jd_009 | 财务会计 | 0.36 | 0.60 | 0.00 | 0.00 | 1/8 | ✓ | ✓ | 31 |
| jd_010 | 客户成功经理 | 0.62 | 0.40 | 0.40 | 1.00 | 2/8 | ✓ | ✓ | 25 |