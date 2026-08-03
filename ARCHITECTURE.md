# ARCHITECTURE.md — JobCraft 求职助手 · 技术架构约束

> 本文档规定 JobCraft 的目录结构、分层架构、数据模型、API 规范、技术选型及性能/安全要求。

## 1. 目录结构

```
jobcraft/
├── AGENTS.md                  # AI 协作行为规范
├── PRODUCT.md                 # 产品需求边界
├── ARCHITECTURE.md            # 本文件
├── PROGRESS.md                # 进度追踪
├── pyproject.toml             # Python 依赖（uv 管理）
├── .env / .env.example        # 环境变量
├── app/                       # 后端主代码
│   ├── api/                   # FastAPI 路由与入口
│   │   ├── server.py          # FastAPI 应用实例与路由注册（仅参数校验+调用workflow）
│   │   └── monitor.py         # 健康检查与监控
│   ├── core/                  # 核心基础设施
│   │   └── llm.py             # 模型初始化（glm-4-flash）
│   ├── workflows/             # LangGraph 工作流定义
│   │   ├── base.py            # Workflow 基类
│   │   ├── interview_review_flow.py  # 面试复盘 Multi-Agent 工作流
│   │   ├── job_analysis_flow.py      # 岗位分析工作流（step1/step2/旧版兼容）
│   │   ├── question_table_flow.py    # 面试问题表生成工作流
│   │   ├── interview_prep_flow.py    # 面试准备工作流
│   │   └── extract_flow.py           # 经历卡抽取/标签/简历解析/回填工作流
│   ├── agents/                # 可复用 Agent 节点（单一职责，最多 1 次 LLM 调用）
│   │   ├── base_agent.py      # Agent 节点基类
│   │   ├── structured_caller.py    # LLM 结构化调用封装
│   │   ├── interview_review 相关:
│   │   │   ├── router_agent.py     # 问题分类路由
│   │   │   ├── tech_analyzer.py    # 技术类问题分析
│   │   │   ├── soft_analyzer.py    # 行为/业务类问题分析
│   │   │   └── gate_agent.py       # 质检/一致性检查
│   │   ├── 岗位分析相关:
│   │   │   ├── jd_ats_agent.py     # JD ATS 解析
│   │   │   ├── ats_recommend_agent.py # Step1: ATS+推荐卡（合并一次 LLM）
│   │   │   ├── score_match_agent.py   # 卡片语义评分
│   │   │   ├── gap_polish_agent.py    # Step2: 缺口+润色
│   │   │   └── sug_agent.py           # 旧版优化建议
│   │   ├── 面试准备相关:
│   │   │   └── interview_prep_agent.py # 面试逐字稿生成
│   │   ├── 经历卡/公司相关:
│   │   │   ├── extract_agent.py        # 结构化抽取/简历解析/标签推荐
│   │   │   ├── question_table_agent.py # 问题表意图识别
│   │   │   ├── question_intent_agent.py # 解析预览意图识别
│   │   │   └── company_research_agent.py # 公司调研（Tavily+缓存）
│   ├── tools/                 # 纯工具函数（无 LLM 调用）
│   │   ├── db_tools.py        # 数据库 CRUD
│   │   ├── llm_json.py        # LLM 底层调用封装（唯一允许 LLM 的工具）
│   │   ├── interview_review.py # 规则引擎 + prompt 构建（_parse_dialogue、_build_qa_pairs）
│   │   ├── interview_pre.py    # 面试准备 prompt 构建 + DB 读取
│   │   ├── jobcraft_analyze.py # 本地匹配纯函数（compute_match、fuse_gap_scores）
│   │   ├── jobcraft_resume.py  # 简历生成编排
│   │   ├── jobcraft_resume_gen.py # Markdown 简历模板（无 LLM）
│   │   ├── upload_file_read_tool.py # 文件读取
│   │   └── tavily_tool.py     # 网络搜索
│   ├── schemas/               # Pydantic 数据模型
│   └── output/                # 结果输出目录
├── frontend-jobcraft/         # 前端（React + TS + Vite + Ant Design）
│   ├── src/
│   │   ├── pages/             # 页面组件（5 个）
│   │   │   ├── CareerRoutePage.tsx    # 🏠 求职路线（主页）
│   │   │   ├── ExperiencePage.tsx     # 📋 经历卡管理
│   │   │   ├── JDAnalysisPage.tsx     # 🔍 JD 分析库
│   │   │   ├── InterviewPrepPage.tsx  # 🎤 面试准备（从投递进入）
│   │   │   └── InterviewReviewPage.tsx# 📝 面试复盘（从投递进入）
│   │   ├── components/        # 可复用组件
│   │   ├── api.ts             # 后端接口封装
│   │   ├── useRoute.ts        # hash 路由（支持参数化 prep/:id review/:id）
│   │   └── types.ts           # TypeScript 类型定义
│   └── package.json
├── tests/                     # 测试用例
├── docker/                    # Docker 配置
└── docs/                      # 补充文档
    └── design-decisions/      # 设计决策文档（共 8 篇）
```

## 2. 分层架构

后端采用 **Controller → Workflow → Agent → Tool** 四层结构：

### 2.1 Controller（app/api/server.py）

- 负责 HTTP 路由、请求校验、响应封装。
- 不直接包含业务逻辑，仅做参数提取与调用 Workflow。
- 统一返回 `{code, msg, data}` 格式。

### 2.2 Workflow（app/workflows/*）

- 负责业务流程编排，使用 LangGraph StateGraph 定义。
- 复杂功能（面试复盘）= 多节点 Multi-Agent 编排。
- 简单功能（岗位分析）= 单节点 Workflow。
- 可观测：每一步 State 可日志、可打断、可重试。
- 处理异常转换，确保 Controller 拿到统一错误。

### 2.3 Agent（app/agents/*）

- 可复用的 LLM 调用节点，每个 Agent 职责单一。
- 每个 Agent 节点最多 1 次 LLM 调用，不循环、不递归；如需多次调用拆分为多个节点。
- 无状态：Agent 节点不持有状态，所有输入输出通过 Workflow State 传递。
- 输入/输出必须使用 Pydantic 模型标注。
- 通过 `structured_caller` / `llm_json.invoke_structured` 统一封装 LLM 调用。
- 不依赖 HTTP 上下文，可独立测试（给定相同输入返回符合 schema 的输出）。

### 2.4 Tool（app/tools/*）

- 纯工具函数，**不包含 LLM 调用**（唯一例外：`llm_json.py` 底层调用封装）。
- 负责最小可复用能力：DB CRUD、文件解析、文本切分、规则引擎、本地关键词匹配、prompt 构建等。
- 所有工具函数必须有类型提示与 Docstring。
- 涉及 LLM 的编排逻辑一律上移至 Workflow + Agent。

## 3. 数据模型（Schema）

所有数据模型统一定义在 `app/schemas/jobcraft.py`，使用 Pydantic v2。

### 3.1 核心模型

- `ExperienceCardSchema`：经历卡（服务端完整响应结构）
- `ExperienceCardCreate` / `ExperienceCardUpdate`：经历卡请求体验证
- `CardStructuredCache` / `Achievement` / `AchievementAction`：经历卡 AI 结构化缓存（按需生成）
- `JDRequirements` / `ATSProfile`：岗位需求
- `JobAnalysisResult`：岗位分析结果
- `InterviewPrepResult`：面试准备稿
- `InterviewReviewResult` / `ReviewedQuestion`：面试复盘结果

### 3.2 经历卡数据模型设计决议

**存储模型**：`raw_text`（用户原始输入）+ `tags`（扁平标签）+ `ai_structured`（AI 缓存）

**为什么不是"强制 STAR 输入"**：
1. 用户写不出干净 STAR：要求用户按 S/A/R 分段填写会增加心理负担和放弃率
2. 减少 LLM 幻觉：如果一开始就让 LLM 把零散文本硬转成字段，字段会填充虚假细节
3. 同样内容不同解读：同一经历投不同岗位，LLM 应基于 JD 上下文灵活解读，而非固定死

**标签设计规则**：
- 扁平标签，不做层级/分类
- 打标单元是「整段经历」，不是单个成就
- 存在两个入口：AI 推荐（自动读文本推荐 3-5 个）+ 搜索式添加（free tag 补全）
- 标签是 hint 不是锁死：LLM 优先按标签方向解读，但不会排除其他可能性

**架构决策**：REST API + 直接 LLM 调用，非多 Agent 协作。每个步骤是确定性的单次 LLM 调用，不是多智能体推理问题。

### 3.3 投递记录（resume_submission）模型

**2026-07-30 新增**，pipeline 核心实体，取代四步线性流程：

```sql
resume_submission (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  user_id          INT DEFAULT 1,
  job_analysis_id  INT,               -- nullable, 从哪个 JD 分析创建的
  position         VARCHAR(200) NOT NULL,
  company          VARCHAR(200) DEFAULT '',
  jd_text          LONGTEXT,          -- 从分析带过来或手动填
  resume_markdown  LONGTEXT,          -- 实际投出的简历全文
  resume_file_path VARCHAR(500),      -- 上传的文件路径（可选）
  card_version_ids JSON,              -- [version_id, ...] 快照
  status           VARCHAR(32) DEFAULT '已投递',
  notes            TEXT,
  created_at       TIMESTAMP,
  updated_at       TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)
```

状态流转：`已投递 → 面试邀约 → 一面 → 二面 → Offer / 已关闭`

### 3.4 模型规范

- 所有字段必须带 `Field(description=...)`。
- 可选字段使用 `Optional[T]`，并提供合理的默认值。
- 数值字段必须标注范围（`ge`, `le`）。
- LLM 结构化输出模型以 `_` 前缀命名（如 `_InterviewReviewAnalysisOut`），避免与对外 Schema 混淆。

## 3.6 页面路由

| 路由 | 页面 | 导航位置 |
|------|------|----------|
| `#/dashboard` | 求职路线（主页） | 侧边栏 🏠 |
| `#/experience` | 经历卡管理 | 侧边栏 📋 |
| `#/jd-analysis` | JD 分析库 | 侧边栏 🔍 |
| `#/prep/:submissionId` | 面试准备 | 从投递详情跳转 |
| `#/review/:submissionId` | 面试复盘 | 从投递详情跳转 |

面试准备和复盘不占导航位，通过主页投递卡片的按钮矩阵进入，顶部带 ◀ 返回。

## 4. API 接口规范

### 4.1 统一响应格式

```json
{
  "code": 0,
  "msg": "success",
  "data": { ... }
}
```

- `code=0` 表示成功，非 0 表示业务错误。
- `msg` 为可读错误信息。
- `data` 为实际载荷，可为空对象/数组。

### 4.2 路由前缀

- 所有业务接口统一前缀：`/api/jobcraft/*`
- 健康检查：`/health`

### 4.3 核心接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/jobcraft/experience/upload` | 上传简历 → 创建经历卡 |
| GET | `/api/jobcraft/experience/cards` | 列出经历卡 |
| POST | `/api/jobcraft/experience/cards/backfill` | 单卡整简历拆分（LLM 解析 + DB 拆卡） |
| POST | `/api/jobcraft/job/step1-ats-recommend` | 岗位 ATS 分析 + 推荐卡 |
| POST | `/api/jobcraft/job/step2-gap-polish` | 缺口分析 + 润色建议 |
| POST | `/api/jobcraft/job/save-card-version` | 保存润色版本 |
| POST | `/api/jobcraft/job/analyze-ats` | 仅 JD ATS 解析（轻量） |
| POST | `/api/jobcraft/job/analyze` | 旧版完整岗位分析（兼容） |
| POST | `/api/jobcraft/job/{job_id}/resume-preview` | 简历 Markdown 预览 |
| POST | `/api/jobcraft/submission` | 创建投递记录 |
| GET | `/api/jobcraft/submission/{id}` | 获取投递详情 |
| PATCH | `/api/jobcraft/submission/{id}` | 更新投递（状态/简历等） |
| DELETE | `/api/jobcraft/submission/{id}` | 删除投递 |
| GET | `/api/jobcraft/dashboard` | 主页：所有投递 + 按钮状态 |
| POST | `/api/jobcraft/job/{id}/interview-prep` | 生成面试准备稿 |
| GET | `/api/jobcraft/job/{id}/interview-prep` | 获取面试准备稿 |
| POST | `/api/jobcraft/interview-review` | 面试复盘分析 |
| POST | `/api/jobcraft/interview-review/parse-preview` | 解析预览（QA 配对） |

## 5. 技术选型理由

| 技术 | 选型理由 |
|------|----------|
| Python 3.12 | 稳定的类型提示与性能。 |
| FastAPI + Uvicorn | 异步高性能，原生支持 Pydantic，适合 AI 服务。 |
| Pydantic v2 | 统一前后端数据校验与 LLM 结构化输出。 |
| LangChain | LLM 抽象层，提供 `init_chat_model`、`bind_tools`。 |
| LangGraph | 核心 Workflow 引擎，用 StateGraph 编排所有 LLM 调用。 |
| OpenAI SDK | 兼容多厂商 LLM（当前使用 Groq）。 |
| React 18 + TS + Vite | 现代前端栈，编译快，类型安全。 |
| Ant Design 5 | 提供完整企业级组件，减少自定义样式。 |
| uv | 快速依赖管理与虚拟环境。 |
| ruff | 统一 lint 与 format，速度快。 |
| pytest | Python 单元测试标准。 |

## 6. 性能与安全要求

### 6.1 性能

- API P95 < 3 秒（简单调用），复杂 LLM 调用 P95 < 10 秒。
- LLM 调用必须设置 `max_tokens`，防止输出过长导致 TPM 超限。
- 长文本必须截断，优先保留前 N 个核心 QA 对/经历卡。
- 前端使用 Vite 懒加载，控制首屏包体积。

### 6.2 安全

- API Key、数据库连接串必须从 `.env` 注入，禁止硬编码。
- 上传文件必须校验格式与大小，禁止执行用户上传内容。
- 错误响应禁止暴露完整堆栈与内部路径。
- 所有用户输入进入 LLM prompt 前需做长度截断，防止 prompt injection 导致成本暴涨。
