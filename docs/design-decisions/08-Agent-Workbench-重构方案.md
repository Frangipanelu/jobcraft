# 08 — Agent Workbench 重构方案

## 背景

JobCraft 当前架构存在两个独立系统：

1. **DeepAgents 系统**（`app/agent/`）— 通用问答，与求职业务无关
2. **JobCraft 业务系统**（`app/tools/`）— 求职功能，直接拼 prompt → 调 LLM → 解析返回

两套系统不互通。System 2 的问题是"胶水代码"——每个功能文件（`interview_review.py`、`jobcraft_analyze.py`、`interview_pre.py` 等）各自管理 prompt 拼接和 LLM 调用，没有统一编排层。复杂功能（如面试复盘分析）只能靠 if/else 硬撑，无法扩展。

## 方案

### 整体变更

```
    重构前                                   重构后
┌─────────────────┐                  ┌─────────────────┐
│  System 1       │                  │  React UI       │  ← 不变
│  DeepAgents     │  删除             │  REST API       │  ← 不变
│  (app/agent/)   │                  ├─────────────────┤
└─────────────────┘                  │  server.py      │  ← 变薄
                                     │  (仅参数校验+   │
┌─────────────────┐                  │   调用workflow) │
│  System 2       │  重构             ├─────────────────┤
│  app/tools/     │   →              │  workflows/     │  ★ 新增
│  (直接调LLM)    │                  │  agents/        │  ★ 新增
│  胶水代码        │                  ├─────────────────┤
└─────────────────┘                  │  tools/         │  ← 纯化，移除LLM
                                     │  core/          │  ★ 新增
                                     └─────────────────┘
```

### 关键变化

| 层面 | 变更 |
|------|------|
| 删除 | System 1 全部文件（`main_agent.py`, `prompts.py`, `subagents/`, `prompts.yml`, `markdown_tools.py`, `pdf_tools.py`） |
| 迁移 | `app/agent/llm.py` → `app/core/llm.py` |
| 新增 | `app/workflows/`（LangGraph StateGraph 工作流）、`app/agents/`（可复用 Agent 节点） |
| 纯化 | `tools/` 保留无 LLM 的纯工具（`db_tools.py` 不变，`interview_review.py` 只保留规则引擎，`jobcraft_analyze.py` 只保留本地匹配） |
| 薄化 | `server.py` 从 1820 行减至 ~600 行，只做参数校验和调用 workflow |

---

## 新架构分层

```
API 层（server.py）
  ↓
Workflow 层（workflows/）
  ├── interview_review_flow.py    ★ 多 Agent（最复杂）
  ├── job_analysis_flow.py         ← 单节点 × 2
  ├── interview_prep_flow.py       ← 单节点
  ├── profile_aggregation_flow.py  ← v0.6 新增
  └── experience_extract_flow.py   ← 单节点
  ↓
Agent 层（agents/）
  ├── structured_caller.py         ← 封装 invoke_structured
  ├── router_agent.py              ← 问题分类路由
  ├── tech_analyzer.py             ← 技术类问题分析
  ├── soft_analyzer.py             ← 行为/业务类问题分析
  ├── gate_agent.py                ← 质检/一致性检查
  └── aggregator_agent.py          ← 数据聚合分析
  ↓
Tools 层（tools/）
  ├── db_tools.py                  ← 纯 CRUD，不变
  ├── interview_review.py          ← 只保留规则引擎（_parse_dialogue、_build_qa_pairs）
  ├── jobcraft_analyze.py          ← 只保留本地匹配（compute_match、关键词映射）
  ├── llm_json.py                  ← 底层 LLM 调用封装
  ├── upload_file_read_tool.py     ← 文件读取
  └── tavily_tool.py               ← 网络搜索
```

---

## 核心 Workflow 设计

### 1. 面试复盘（复杂多 Agent）

```
用户勾选问题 → POST /api/jobcraft/interview-review/{id}/analyze

State: { raw_text, dialogue, qa_pairs, selected_sequences,
         classified_questions, tech_results, soft_results, gate_report }

1. parse_dialogue (规则引擎)      —— 无 LLM
2. build_qa_pairs (规则引擎)       —— 无 LLM
3. route_questions (Router Agent)  —— 1次轻量LLM，分类 tech/soft
4. tech_analyze (Tech Agent)       —— 1次LLM，只分析技术题
   soft_analyze (Soft Agent)       —— 1次LLM，只分析行为题（与上一步并行）
5. quality_gate (Gate Agent)       —— 1次LLM，检查一致性和幻觉
6. save_and_return                  —— 无 LLM，写入 DB
```

| 维度 | 当前（单 LLM） | 重构后（Multi-Agent） |
|------|-------------|-------------------|
| 每次 LLM 调用次数 | 1 次（全量） | 3~4 次（分类 + 并行分析 + 质检） |
| 每次 prompt 长度 | 4000+ tokens | 每个 Agent 1500~2000 tokens |
| 单个问题细节深度 | 中 | 高（Agent 只处理同类问题） |
| 可并行度 | 无 | 2 个分析 Agent 可并行 |
| 质检 | 无 | Gate Agent 可发现矛盾 |

### 2. 岗位分析（简单单节点）

保持现有的**两步各 1 次 LLM** 模式，只是把 prompt 管理从 `tools/` 移到 `workflows/`：

```
Step 1: invoke_structured(ATSRecommendResult, prompt)     —— 1次LLM
        写入 job_analysis 表

Step 2: invoke_structured(GapPolishResult, prompt)        —— 1次LLM
        返回 per_card + global_suggestions
```

### 3. 面试准备（简单单节点）

```
1. 从 DB 加载 JD、经历卡、公司调研、简历
2. invoke_structured(InterviewPrepResult, prompt)         —— 1次LLM
3. 写入 interview_preps 表
```

### 4. 跨JD/复盘聚合（v0.6 新增）

```
跨JD聚合:
  → 查 DB 获取同角色所有 job_analysis
  → invoke_structured → 输出共性要求和公司差异
  → 写入 role_profile 表

跨复盘聚合:
  → 查 DB 获取同公司所有复盘记录
  → invoke_structured → 输出高频维度/题型规律
  → 写入 company_interview_profile 表
```

---

## 分步迁移计划

### Phase 1：基础设施（预计 1 天）

| 任务 | 说明 |
|------|------|
| 创建 `app/core/llm.py` | 从 `app/agent/llm.py` 迁移 model 初始化 |
| 创建 `app/workflows/` + `app/agents/` | 空目录骨架 |
| 实现 `workflows/base.py` | Workflow 基类（通用错误处理、日志） |
| 实现 `agents/base_agent.py` | Agent 节点基类 |
| 实现 `agents/structured_caller.py` | 封装 `invoke_structured` |

**可回滚**：新增文件不影响现有代码。

### Phase 2：清理 System 1（预计 0.5 天）

| 删除文件 | 原因 |
|----------|------|
| `app/agent/main_agent.py` | DeepAgent 编排 |
| `app/agent/prompts.py` | 加载 prompts.yml |
| `app/agent/subagents/` | 三个子 Agent |
| `app/prompt/prompts.yml` | System 1 提示词 |
| `app/tools/markdown_tools.py` | 只被 DeepAgent 用 |
| `app/tools/pdf_tools.py` | 只被 DeepAgent 用 |
| server.py 中 `/api/task` 系列路由 | DeepAgent 入口 |
| `deepagents` 依赖（pyproject.toml） | 不再使用 |

### Phase 3：迁移面试复盘（预计 2 天）

| 任务 | 文件 | 说明 |
|------|------|------|
| 拆分 `interview_review.py` | `tools/interview_review.py` | 只保留 `_parse_dialogue`、`_build_qa_pairs` |
| 实现 workflow | `workflows/interview_review_flow.py` | StateGraph: Router → Tech/Soft → Gate |
| 实现 Agent 节点 | `agents/router_agent.py` | 问题分类 |
| 实现 Agent 节点 | `agents/tech_analyzer.py` | 技术分析 |
| 实现 Agent 节点 | `agents/soft_analyzer.py` | 行为分析 |
| 实现 Agent 节点 | `agents/gate_agent.py` | 质检 |
| 更新路由 | `api/server.py` | 调用 workflow 替代直接调 tools |

**验证**：现有复盘路由所有功能不变。

### Phase 4：迁移岗位分析 + 面试准备（预计 1.5 天）

| 任务 | 文件 | 说明 |
|------|------|------|
| 拆分 `jobcraft_analyze.py` | `tools/jobcraft_analyze.py` | 只保留 `compute_match`、关键词映射 |
| 实现 workflow | `workflows/job_analysis_flow.py` | 单节点 × 2 |
| 实现 workflow | `workflows/interview_prep_flow.py` | 单节点 |
| 实现 workflow | `workflows/experience_extract_flow.py` | 单节点 |
| 更新路由 | `api/server.py` | 调用 workflow |

### Phase 5：v0.6 闭环迭代（预计 1 天）

| 任务 | 说明 |
|------|------|
| 新增 `role_profile` 表 | 跨JD聚合存储 |
| 新增 `company_interview_profile` 表 | 公司面试画像存储 |
| 实现 `profile_aggregation_flow.py` | 聚合 workflow |
| 新增 API 路由 | POST `/api/jobcraft/profile/role`、`/api/jobcraft/profile/company` |
| 反哺注入 | 在 `interview_prep_flow.py` 和 `job_analysis_flow.py` 中加入画像上下文 |

---

## LangGraph 选用原因

对比直接函数调用：

| 能力 | 当前面向过程 | LangGraph |
|------|------------|-----------|
| 拆分 prompt | 一个 4000 token prompt | 拆成多个 1500 token prompt，专注度更高 |
| 并行执行 | 不能 | Tech/Soft 分析可并行 |
| 条件分支 | if/else 硬编码 | 显式条件边 |
| 中间状态可观测 | 黑盒 | 每一步 State 可拿到 |
| 节点级别重试 | 整函数重来 | 单节点重试 |
| 加新步骤 | 改函数加 if | 加节点 + 加边 |
| 复用节点 | 复制粘贴 | gate_agent 可跨 workflow 复用 |

---

## 保持不变的契约

| 层 | 说明 |
|---|------|
| 前端 UI 页面 | 路由、组件、types.ts、api.ts 全不动 |
| API 签名 | 同 URL、同请求体、同响应 `{code,msg,data}` |
| 数据库表 | 所有表和 schema 不动 |
| DB CRUD 函数 | `db_tools.py` 不动 |
| 规则引擎解析 | `_parse_dialogue`、`_build_qa_pairs` 不动 |
| 本地匹配逻辑 | `compute_match`、关键词映射不动 |
