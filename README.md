# JobCraft 求职助手

> AI 驱动的求职全流程管理工具：**求职路线 → 经历卡 → JD 分析库 → 面试准备 → 面试复盘**，以投递记录为 pipeline 核心，辅助求职者系统性管理求职过程。

## 目录

- [项目简介](#项目简介)
- [核心功能](#核心功能)
- [技术栈](#技术栈)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [环境变量配置](#环境变量配置)
- [API 概览](#api-概览)
- [数据库](#数据库)
- [测试](#测试)
- [代码规范与红线](#代码规范与红线)
- [文档索引](#文档索引)
- [已知问题](#已知问题)

---

## 项目简介

JobCraft 帮助求职者告别零散的 Word 简历和 Excel 投递表，把求职的每个环节串成一条可追踪的 pipeline：

1. **经历梳理**：上传简历 / 粘贴经历文本 → AI 抽取结构化经历卡（STAR + 标签）
2. **JD 分析**：输入岗位 JD → ATS 画像 + 暗话解码 + 经历卡匹配 + 缺口分析与润色
3. **简历定制**：按 JD 定制简历 → 自动创建投递记录（pipeline 核心）
4. **面试准备**：基于投递的 JD + 实际投出的简历 + 经历卡，生成预测题与答题要点
5. **面试复盘**：上传面试转写 → 自动 QA 配对 → 逐题评分、意图分析、诊断反馈

AI 负责分析，**用户自主决策**何时进入下一阶段。投递状态（已投递 → 面试邀约 → 一面 → 二面 → Offer / 已关闭）由用户切换。

---

## 核心功能

| 模块 | 页面 | 能力 |
|------|------|------|
| 🏠 求职路线 | `#/dashboard` | 投递时间线、5 步按钮矩阵（JD 分析 / 润色 / 简历 / 面试准备 / 复盘）、状态流转 |
| 📋 经历卡 | `#/experience` | 原始文本存储、AI 结构化缓存（S/A/R）、标签推荐、STAR 编辑、版本历史 |
| 🔍 JD 分析库 | `#/jd-analysis` | 独立 JD 工作台、ATS 画像（D1-D8 8 维能力）、暗话解码、卡片匹配、缺口+润色、简历生成 |
| 🎤 面试准备 | `#/prep/:submissionId` | 技术面 / 业务面 / HR 面、预测题 + 答题要点、公司调研（Tavily + 7 天缓存）、多轮衔接 |
| 📝 面试复盘 | `#/review/:submissionId` | 说话人拆分、QA 配对、问题表汇总、逐题详细解析（intent / 标准答案 / 反馈 / 改进建议）、Multi-Agent 分析 |

### 特色设计

- **JD 暗话解码**：解析 JD 表面要求背后的真实期望，3-6 条「表面要求 → 实际期望 → 关键能力 → 证明方式」
- **8 维能力矩阵（D1-D8）**：技术深度 / 业务理解 / 问题拆解 / 方案设计 / 落地执行 / 数据复盘 / 协作沟通 / 职业规划
- **简历模板化生成**：A4 模板拼装（header + 技能标签 + 经历条目），支持 HTML 预览、`.md` / `.html` 下载、`window.print()` 打印 PDF
- **经历卡版本快照**：定制文本存 `card_versions` 表，不修改原卡，投递记录可追溯所用版本
- **多轮面试衔接**：自动提取上一轮复盘摘要，注入下一轮准备 prompt
- **API 统一响应**：所有接口返回 `{code, msg, data}`，前端类型由后端 Schema 同步

---

## 技术栈

### 后端

| 技术 | 用途 |
|------|------|
| Python 3.12 | 运行时 |
| FastAPI + Uvicorn | Web 框架 / ASGI 服务器 |
| LangGraph | 核心 Workflow 引擎（StateGraph 编排 LLM 调用） |
| LangChain | LLM 抽象层（`init_chat_model`、结构化调用） |
| Pydantic v2 | Schema 校验 + LLM 结构化输出 |
| MySQL 8.4 | 数据持久化 |
| Tavily | 公司背景调研搜索 |
| uv | 依赖管理与虚拟环境 |
| ruff / pytest | 代码质量 / 测试 |

### 前端

| 技术 | 用途 |
|------|------|
| React 18 + TypeScript | 前端框架 |
| Vite 7 | 构建工具与开发服务器（`/api` 代理到后端） |
| Ant Design 5 | UI 组件库 |
| Hash 路由 | 自实现 `useRoute.ts`（支持 `prep/:id` 等参数化路由） |

---

## 系统架构

四层架构：**Controller → Workflow → Agent → Tool**

```
┌─────────────┐   HTTP   ┌─────────────────────────────────────┐
│  前端 React │ ───────▶ │ Controller (app/api/server.py)      │
│  Ant Design │          │  路由注册 / 参数校验 / 统一响应格式    │
└─────────────┘          └──────────────────┬──────────────────┘
                                            ▼
                              Workflow (app/workflows/*)
                              LangGraph StateGraph 编排
                              ├─ 面试复盘：Router → Tech/Soft → Gate（6 节点）
                              ├─ 岗位分析 / 面试准备 / 经历卡抽取 / 问题表（单节点）
                                            │
                                            ▼
                              Agent (app/agents/*)
                              职责单一的 LLM 调用节点（结构化调用封装）
                                            │
                                            ▼
                              Tool (app/tools/*)
                              纯函数：DB CRUD / 文件解析 / 规则引擎（无 LLM）
```

- **面试复盘 Workflow**：`interview_review_flow.py` 使用多 Agent 协作（Router 分类 → Tech/Soft 并行分析 → Gate 质检），单 Agent prompt 控制在 1500~2000 tokens，缓解长文本 TPM 限制
- **简单功能单节点**：岗位分析、面试准备、经历卡抽取均为「1 次 LLM 调用」的单节点 Workflow，避免过度设计

### 数据流

```
经历卡 (experience_card)
    │ raw_text + tags + ai_structured 缓存
    ▼
JD 分析 (job_analysis) ──▶ 定制简历 (card_versions 版本快照)
                                  │
                                  ▼
                    resume_submission（投递记录，pipeline 核心）
                          │                 │
                          ▼                 ▼
              interview_preps（面试准备）  interview_records（面试复盘）
```

---

## 快速开始

### 环境要求

- Python >= 3.12（`uv` 已安装）
- Node.js >= 18
- Docker（用于 MySQL）
- 智谱 AI API Key（`https://open.bigmodel.cn/`，默认模型 `glm-4-flash`）
- Tavily API Key（可选，用于公司调研）

### 1. 启动 MySQL

```bash
# 在项目根目录执行
docker compose -f docker/docker-compose.yaml up -d
```

首次启动会自动执行 `docker/mysql/jobcraft.sql` 初始化表结构。默认映射到宿主机 `3307` 端口（避免与本机已有 MySQL 3306 冲突），可用 `MYSQL_PORT` 覆盖。

> 启动后确认 `jobcraft` 库存在：`docker exec jobcraft-mysql mysql -uroot -proot -e "SHOW DATABASES;"`

### 2. 配置环境变量

```bash
# 复制环境变量模板并填写真实密钥
cp .env.example .env
```

关键项：

```dotenv
# LLM（智谱 AI OpenAI 兼容端点）
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
OPENAI_API_KEY=你的Key
LLM_model=glm-4-flash

# 数据库
MYSQL_USER=root
MYSQL_PASSWORD=root
MYSQL_DATABASE=jobcraft
MYSQL_HOST=localhost
MYSQL_PORT=3307
```

### 3. 安装依赖

```bash
# 后端（自动创建 .venv）
uv sync

# 前端
cd frontend-jobcraft
npm install
```

### 4. 启动后端

```bash
uv run uvicorn app.api.server:app --host 127.0.0.1 --port 8000
```

验证：`curl http://127.0.0.1:8000/api/jobcraft/dashboard`

> 若 8000 端口被占用，改用 8001 并把 `frontend-jobcraft/vite.config.ts` 的代理 target 一并改掉。

### 5. 启动前端

```bash
cd frontend-jobcraft
npm run dev
```

访问 **http://localhost:5175** 。

### 生产构建

```bash
cd frontend-jobcraft
npm run build        # 产物输出到 dist/，可交给任意静态服务器
```

---

## 环境变量配置

| 变量 | 说明 | 必填 |
|------|------|------|
| `OPENAI_BASE_URL` | LLM 兼容端点地址 | ✅ |
| `OPENAI_API_KEY` | LLM API Key | ✅ |
| `LLM_model` | 模型名（如 `glm-4-flash`） | ✅ |
| `TAVILY_API_KEY` | Tavily 搜索 Key（公司调研） | ❌ |
| `MYSQL_USER` / `MYSQL_PASSWORD` | 数据库账号 | ✅ |
| `MYSQL_DATABASE` | 数据库名（默认 `jobcraft`） | ✅ |
| `MYSQL_HOST` | 数据库主机 | ✅ |
| `MYSQL_PORT` | 数据库端口（默认 `3307`） | ✅ |
| `MYSQL_CHARSET` / `MYSQL_COLLATION` | 字符集（`utf8mb4`） | ✅ |
| `MYSQL_SQL_MODE` | SQL 模式（`TRADITIONAL`） | ❌ |
| `RAGFLOW_API_URL` / `RAGFLOW_API_KEY` | RAGFlow 集成（已弃用，可留空） | ❌ |

---

## API 概览

所有业务接口前缀 `/api/jobcraft`，统一响应格式 `{code, msg, data}`（`code=0` 成功）。

### 经历卡

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/experience/upload` | 上传简历/文本 → 抽取经历卡 |
| GET | `/experience/cards` | 经历卡列表 |
| POST | `/experience/cards` | 手动创建经历卡 |
| PATCH | `/experience/cards/{card_id}` | 更新经历卡 |
| DELETE | `/experience/cards/{card_id}` | 删除经历卡 |
| POST | `/experience/cards/{card_id}/structure` | 生成/刷新结构化缓存（S/A/R） |
| POST | `/experience/cards/{card_id}/recommend-tags` | 标签推荐 |

### JD 分析与简历

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/job/analyze` | JD 完整分析（ATS + 推荐） |
| POST | `/job/step1-ats-recommend` | Step1：ATS 画像 + 推荐卡 |
| POST | `/job/step2-gap-polish` | Step2：缺口分析 + 润色建议 |
| POST | `/job/save-card-version` | 保存润色版本 |
| POST | `/job/save-resume` | 生成并保存简历 |
| GET | `/job/analyses` | JD 分析列表 |
| GET / DELETE | `/job/analyze/{job_id}` | 单个 JD 分析详情 / 删除 |
| POST | `/job/analyze-ats` | 仅 ATS 解析 |
| POST | `/job/{job_id}/resume-preview` | 简历 HTML 预览 |
| GET | `/resume/download` | 下载简历 |

### 投递记录（Pipeline 核心）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/submission` | 创建投递 |
| POST | `/submission/manual` | 手动补录（上传简历 → 解析 → 建卡 → 建投递） |
| GET / PATCH / DELETE | `/submission/{submission_id}` | 投递详情 / 更新状态 / 删除 |
| GET | `/dashboard` | 主页数据（所有投递 + 按钮状态） |
| GET | `/job/{job_id}/selected-cards` | 投递所选经历卡 |

### 面试准备 / 复盘

| 方法 | 路径 | 说明 |
|------|------|------|
| POST / GET | `/job/{job_id}/interview-prep` | 生成 / 获取面试准备稿 |
| POST | `/interview-review` | 面试复盘分析 |
| POST | `/interview-review/upload` | 上传面试记录 |
| POST | `/interview-review/parse-preview` | 解析预览（说话人拆分 + QA 配对） |
| GET | `/interview-review` | 复盘记录列表 |
| POST | `/interview-review/{record_id}/question-table` | 生成问题表 |
| POST | `/interview-review/{record_id}/analyze` | 勾选问题详细解析（Multi-Agent） |
| GET / DELETE | `/interview-review/{record_id}` | 复盘详情 / 删除 |

---

## 数据库

MySQL 8.4，表结构初始化见 [`docker/mysql/jobcraft.sql`](docker/mysql/jobcraft.sql)，涉及建表/加列的迁移统一走 `app/tools/db_tools.py` 的兼容层。

核心表：

| 表 | 说明 |
|----|------|
| `experience_card` | 经历卡（`raw_text` + `tags` + `ai_structured` 缓存） |
| `card_versions` | 定制简历版本快照 |
| `job_analysis` | JD 分析结果（ATS 画像 + 暗话解码 + 8 维能力） |
| `resume_submission` | 投递记录（pipeline 核心） |
| `interview_preps` | 面试准备稿 |
| `interview_records` | 面试复盘记录 |
| `interview_qa_pairs` | 复盘 QA 对 |
| `company_research` | 公司调研缓存（7 天过期） |
| `experience_job_mapping` | 经历卡 ↔ 投递关联 |

**DB 前向兼容原则**：DDL 只加列/表、不改/删列，保证旧代码可读。

---

## 测试

```bash
# 单元测试（无 LLM/DB 依赖，39+ 用例）
uv run pytest tests/ -q

# 代码质量
uv run ruff check --fix .
uv run ruff format .
```

> 调试脚本（`tests/check_*.py`）以 `check_` 前缀命名，避免被 pytest 收集。e2e 测试依赖服务运行，未就绪时自动跳过。

---

## 代码规范与红线

完整规范见 [`AGENTS.md`](AGENTS.md)，核心红线：

- ❌ 禁止硬编码密钥（一律走 `.env`）
- ❌ 禁止裸 `except:`
- ❌ 禁止未经授权引入第三方库
- ❌ 禁止业务代码中 `print`（用日志模块）
- ❌ 禁止提交 `.env`（已在 `.gitignore`）
- ❌ 禁止破坏现有 API 契约（改 Schema 必须同步调用方与测试）
- ✅ 提交必须通过 `ruff check`、`ruff format`、`pytest` 与前端 `npm run build`

Agent 节点规范：单一职责、无状态、单次节点最多 1 次 LLM 调用、Pydantic 类型标注、可独立测试。

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [`PRODUCT.md`](PRODUCT.md) | 产品愿景、MVP 边界、Non-Goals、验收标准 |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 目录结构、分层架构、数据模型、API 规范 |
| [`PROGRESS.md`](PROGRESS.md) | 版本进度与历史决策 |
| [`AGENTS.md`](AGENTS.md) | AI 协作行为规范与红线 |
| [`docs/CODE_REVIEW.md`](docs/CODE_REVIEW.md) | 代码审查清单与历次问题记录 |
| [`tests/TEST_PLAN.md`](tests/TEST_PLAN.md) | 测试计划 |
| [`docs/design-decisions/`](docs/design-decisions/) | 产品设计决策（8 篇） |

---

## 已知问题

- **LLM TPM 限制**：面试复盘长文本当前仅分析前 8 个核心 QA 对（Multi-Agent 重构后已显著缓解）
- **端口占用**：本地 8000 端口若被其他服务占用，可用 8001 并同步修改 vite 代理
- **语音转写边界 case**：复杂反问/插话的切分仍有少量边界情况
- **antd vendor 偏大**：antd-vendor 约 964KB（gzip 300KB），已通过 `manualChunks` 单独成 chunk 长期缓存，页面已按路由懒加载（3~18KB/页），首屏不再全量加载
- **测试覆盖**：核心 LLM 业务路径（岗位分析、面试准备、复盘）的稳定回归测试仍在完善

详细进度与决策见 [`PROGRESS.md`](PROGRESS.md)。
