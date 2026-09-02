# JobCraft Project Engineering Baseline v1

> **版本**：v1.0
> **性质**：只读式全量工程审计快照（SCAN ONLY — 未修改任何业务代码/数据库/配置/依赖）
> **审计时间**：2026-09-02
> **范围**：`frontend-jobcraft/`、`app/`、`tests/`、`scripts/`、`docker/`、`docs/` 及根目录工程配置
> **原则**：`真实代码 > 文档描述 > 推测`。所有结论以文件 + 行号作为证据；无法确认的数据记为 `UNKNOWN` / `NOT VERIFIED`，不虚构数字。

---

# 1. Executive Summary

JobCraft 是一个 **FastAPI + LangGraph/LangChain + MySQL 8.4** 后端与 **React 19 + TypeScript + Vite + Tailwind CSS v4** 新前端的求职助手。前端 `frontend-jobcraft/` 是一个**全新的、基于 bytebase 风格原型重构的 UI**，与旧前端（`frontend-jobcraft-backup/`）并存。

本次只读审计得出核心结论：

1. **后端已经具备完整业务能力**：52 个 HTTP 端点、6 类 Domain Workflow、15 个 Agent、16 个工具、10 张表、266 个测试函数。
2. **安全/所有权是最大风险**：所有业务端点**未强制认证**，`user_id` 由客户端传入且大量默认值 `=1`（37+ 处）；get/update/delete 类 DAO 按 ID 操作**不过滤 user_id**（越权面）。
3. **新前端存在大量 Mock/硬编码占位**：`Math.random()` 假评分（面试复盘、模拟面试）、硬编码 ID（`res-byte-1` / `int-byte-1` / `jd-byte-1` / `exp-1`）、假 `setTimeout` 进度、硬编码仪表盘数字。**Resume 编辑功能因 state 永不填充而静默失效**。
4. **存在双重类型系统**：`src/types/jobcraft.ts`（camelCase）与 `src/api/types.ts`（snake_case）字段名不一致，靠 `JobCraftContext.tsx` 中多个 mapper 手工转换。
5. **AI 工程化缺失**：Prompt 全部内联硬编码（无版本）、无 LLM retry、无 AI Task/Cache 通用设施、Prometheus 指标定义但从不记录（dead code）。
6. **数据库无外键、无迁移框架**：10 张表 0 个 FK；表结构靠运行时 `ALTER TABLE`/`CREATE TABLE IF NOT EXISTS` 演进。
7. **文档与代码有确定 MISMATCH**：`AGENTS.md` 强制“纯原生 Ant Design”，但新前端使用 Tailwind；`pyproject.toml` version=0.6.0 与 PROGRESS 记录的 v0.14 不一致。

**总体架构健康度评分：约 59/100**（详见 §12，各维度有证据支撑）。**安全是当前唯一 P0**。

---

# 2. Repository Statistics

## 2.1 目录结构（顶层）

```text
app/                  # 后端（8762 行 Python）
frontend-jobcraft/    # 新前端（React 19 + TS + Tailwind）
frontend-jobcraft-backup/  # 旧前端备份（未扫描业务，见 §2.4）
tests/                # 测试（4767 行 Python，12 个文件）
scripts/              # 脚本
docker/               # mysql schema + docker-compose + Dockerfile
docs/                 # 文档（含 archive/ 历史归档）
output/  updated/     # 产物目录（忽略）
.github/workflows/    # CI（ci.yml + frontend-ci.yml）
```

## 2.2 代码规模（按语言）

| 类别 | LOC |
|---|---:|
| 后端 Python（app/） | 8,762 |
| 测试 Python（tests/） | 4,767 |
| 前端 TS/TSX（frontend-jobcraft/src/） | 13,826 |
| 文档 Markdown（docs/ + 根目录） | ~10,300+ |

## 2.3 文件数量

| 类型 | 数量 |
|---|---:|
| Python 文件（app/） | ~50 |
| TS/TSX 文件（frontend-jobcraft/src/） | 36 |
| SQL 文件 | ≥8（docker/*.sql） |
| Markdown 文件（全仓，含 docs/） | 39 |

## 2.4 备份目录说明

`frontend-jobcraft-backup/` 是旧前端（含 Ant Design、`api.ts`、旧页面 `CareerRoutePage/ExperiencePage/JobPage` 等）的备份。它不在本次新前端范围。**建议后续确认是否保留或 `.gitignore`**（当前未跟踪，见 §11）。

---

# 3. Frontend Statistics

## 3.1 页面（pages/）

`App.tsx`（159 行）通过 `switch` 手动路由（无 React Router，无 React.lazy/Suspense）。

| Page | File | LOC | API 依赖 | 状态 |
|---|---|---|---|---|
| CreateInterview | `pages/CreateInterview.tsx` | 802 | Context `createInterview` | 存在 |
| CreateReview | `pages/CreateReview.tsx` | 750 | Context `createReviewFromTranscript` | 存在 |
| NewInterviewPrep | `pages/NewInterviewPrep.tsx` | 956 | `createInterview`/`createJob`/`createJDAnalysis` | 最大页面 |
| NewReview | `pages/NewReview.tsx` | 759 | `addInterviewReview`/`createReviewFromTranscript`/`createJob`/`createJDAnalysis` | 存在 |

`App.tsx` 定义的 `settings` 导航 Tab（`types/jobcraft.ts:17`）在 switch 中无对应 handler（落到默认 Workbench）——见 §11。

## 3.2 组件（components/，按领域；均为业务/UI 混合，无纯 UI 库）

| 领域 | 文件数 | LOC | 关键问题 |
|---|---:|---|
| workbench | 1 | 410 | **仪表盘数字硬编码**（`WorkbenchView.tsx:30-102`） |
| experiences | 2 | 1,109 | 正常 |
| jobs | 3 | 717 | 硬编码 ID（`JobWorkspaceView.tsx:121/192/203`） |
| jd | 2 | 995 | `sampleJD` mock + 假 setTimeout（`JDAnalysisCenterView.tsx:32-69`） |
| resume | 1 | 418 | **Resume 编辑静默失效** + 中文字符标识符 |
| interview | 4 | 2,192 | 大量 mock + `Math.random` 评分（`MockInterviewModal.tsx`） |
| review | 3 | 800 | mock 复盘（`NewReviewModal.tsx`） |
| user | 1 | 520 | 正常 |
| layout | 2 | 462 | logout 未调用 API（`TopHeader.tsx`） |
| common | 5 | 224 | 自定义 UI 原语 |
| **合计** | **25** | **8,847** | |

## 3.3 API Client（src/api/）

| 文件 | LOC | 说明 |
|---|---:|---|
| `client.ts` | 82 | `BASE_URL=''`（相对）；`request<T>`/`requestFormData<T>`；**唯一 fetch 出口**（`client.ts:53,71`） |
| `auth.ts` | 60 | `autoLogin()`（default-login）、`getCurrentUser()`、`logout()` |
| `experience.ts` | 100 | 经历卡 CRUD + upload/structure/recommend-tags/backfill |
| `job.ts` | 160 | analyzeJob/list/step1/step2/submissions CRUD/dashboard/saveResume |
| `interview.ts` | 186 | interview-prep + interview-review CRUD/upload/parse-preview/question-table/analyze |
| `types.ts` | 354 | 后端 DTO（snake_case） |
| `index.ts` | 10 | barrel export |

**关键事实：组件/页面中无直接 `fetch()`** —— 所有 HTTP 已集中到 `api/client.ts`（符合工程规范 ✅）。Token 存于 `localStorage['jobcraft_token']`。

## 3.4 Types

存在 **双重并行类型系统**：

| 文件 | 命名 | 领域 |
|---|---|---|
| `src/types/jobcraft.ts`（393 行） | camelCase | Experience/JDAnalysis/Interview/Resume 前端域模型 |
| `src/api/types.ts`（354 行） | snake_case | 后端 DTO（ExperienceCard/JobAnalysisResult/...） |

`JobCraftContext.tsx` 用 mapper 桥接（`cardToExperience:159`、`analysisToJD:186`、`submissionToJob:241`）。后果：**任一后端字段变更需同步 mapper，重复且易错**。

`any` / 类型转换：12 处（`api/types.ts:10,128,191`、`api/job.ts:43,45,57,58`、`JobCraftContext.tsx:1456,1487,1508`、`WorkbenchView.tsx:98`、`JDReportDetailView.tsx:503`）。

## 3.5 State

- **单一全局 Context**：`JobCraftContext.tsx`（1,626 行）持有全部业务状态（jobs/experiences/jdAnalyses/resumes/interviews/nextActions/activities/aiSuggestions/historicalResumes）+ 导航 + toast。
- 仅 `useState`，无 `useReducer`。
- `resumes` 初始 `{}` 且**永不从后端填充** → 所有 resume 变异操作引用硬编码 key `'res-byte-1'` → **Resume 编辑静默 no-op**（`JobCraftContext.tsx:295,668,712,780,...`）。
- `interviews`/`jdAnalyses`/`activityLog`/`nextActions` 仅前端内存态，**未持久化到后端**。
- UI vs Server state 未清晰分离；同一业务数据（jobs/experiences）同时存在于 Context + 页面局部 state。

---

# 4. Backend Statistics

## 4.1 模块规模

| 目录 | LOC | 说明 |
|---|---:|---|
| app/api | 1,795 | Controller 层（6 文件） |
| app/tools | 3,590 | 最大模块；DAO + 纯函数 + 工具 |
| app/agents | 1,007 | 15 个 Agent 节点 |
| app/workflows | 989 | 6 个 Workflow 文件 |
| app/tasks | 339 | 后台任务（Redis-backed，未消费） |
| app/utils | 316 | path_utils + word_converter |
| app/schemas | 339 | Pydantic |
| app/auth | 212 | JWT 认证 |
| app/monitoring | 126 | Prometheus（dead code） |
| app/db | 38 | SQLAlchemy engine（未使用） |
| app/core | 11 | llm 单例 |

## 4.2 分层现状

| 标准分层 | 实际实现 | 说明 |
|---|---|---|
| Controller | `app/api/*.py` | 路由 → 直接调用 db/workflow |
| Application Service | **无独立层** | 业务逻辑散落在 Controller + tools |
| Workflow | `app/workflows/*.py` | LangGraph StateGraph（同步 `.invoke()`） |
| Agent | `app/agents/*.py` | 继承 `BaseAgent`，单 LLM 调用 |
| Repository/DAO | `app/tools/db_*.py` | 原生 `mysql.connector` |
| Database | MySQL 8.4 | 表结构运行时演进 |

**观察**：`JobCraftContext.tsx`（前端）是当前项目的“God State”；后端侧 Controller 直接持有较多业务编排（`app/api/interview_review.py:357` 直接 new OpenAI client 做 mock-chat）。分层存在“扁七”现象，但功能完整。

---

# 5. API Statistics

## 5.1 总览

| 项 | 值 |
|---|---:|
| 端点总数 | 52 |
| GET | 16 |
| POST | 28 |
| PATCH | 1 |
| DELETE | 5 |
| 认证端点（强制 JWT） | 1（`GET /api/auth/me`） |
| 未认证业务端点 | 48 |

## 5.2 端点清单与后端依赖

### AUTH（`/api/auth`）
| Method | Path | 认证 | 说明 |
|---|---|---|---|
| POST | `/register` | 否 | 注册 |
| POST | `/login` | 否 | 登录 |
| POST | `/default-login` | 否 | **后门**（硬编码密码，`auth/router.py:123`） |
| GET | `/me` | **是** | 当前用户 |

### SERVER（server.py）
| Method | Path | 说明 |
|---|---|---|
| GET | `/health`、`/api/jobcraft/health` | 健康检查 |
| POST | `/api/jobcraft/tasks/submit` | 提交任务 |
| GET | `/api/jobcraft/tasks/{id}`、`/tasks` | 任务状态 |
| POST | `/api/jobcraft/tasks/{id}/cancel` | 取消任务 |

### EXPERIENCE（`/api/jobcraft/experience`）
upload / cards(list/search/batch/CRUD/backfill) / export / cards/{id}/versions / structure / recommend-tags（13 个）

### JOB（`/api/jobcraft/job`）
step1-ats-recommend / step2-gap-polish / save-card-version / analyze / analyses / analyze/{id} / save-resume / analyze-ats / {id}/resume-preview / resume/download（11 个）

### SUBMISSION + DASHBOARD（`/api/jobcraft/`）
submission CRUD + manual + dashboard（6 个）

### INTERVIEW PREP（`/api/jobcraft/job/{job_id}/`）
interview-prep (POST/GET) + selected-cards（3 个）

### INTERVIEW REVIEW（`/api/jobcraft/interview-review`）
create/upload/parse-preview/list/question-table/analyze/mock-chat/detail/delete（9 个）

> 完整端点→文件:行号映射已由审计 Agent 建立（见 §18 Evidence）。更细的前后端映射见仓库已有 `FRONTEND_BACKEND_MAPPING.md`。

## 5.3 HTTP 契约约定

错误统一返回 `{code, msg, data}`（全局异常处理器，`server.py`）。此约定前后端一致 ✅。

---

# 6. Database Statistics

## 6.1 表清单（10 张）

| 表 | 定义位置 | 列数 | 说明 |
|---|---|---:|---|
| `experience_card` | `docker/mysql/jobcraft.sql:13` | 24 | 经历卡（raw_text + tags + ai_structured） |
| `card_versions` | `jobcraft.sql:165` | 11 | 经历卡版本 |
| `job_analysis` | `jobcraft.sql:43` | 10 | 岗位分析 |
| `experience_job_mapping` | `jobcraft.sql:59` | 4 | 经历↔岗位匹配（复合主键） |
| `resume_submission` | `jobcraft.sql:96` | 14 | 投递记录（Pipeline 核心） |
| `interview_preps` | `jobcraft.sql:70` | 12+ | 面试准备 |
| `interview_records` | `jobcraft.sql:117` | 14+ | 面试记录 |
| `interview_qa_pairs` | `jobcraft.sql:138` | 21 | 面试 QA 对 |
| `company_research` | `jobcraft.sql:87` | 3 | 公司背调（7 天缓存） |
| `users` | `app/tools/db_user.py:20` | 7 | 用户（运行时建表） |

## 6.2 Schema 指标

| 指标 | 值 |
|---|---:|
| 表数量 | 10 |
| 总列数 | ~110 |
| 主键 | 10 |
| **外键约束** | **0** |
| 唯一约束 | 1（`users.username`） |
| 非主键索引 | 13 |
| JSON 列 | 16 |
| 时间戳列 | 16 |

## 6.3 JSON 列清单（16）

`experience_card.tags/metrics/dimensions`、`job_analysis.jd_requirements/dimension_requirements`、`interview_preps.standard_version_json/extended_version_json/ability_matrix_json/company_research_json`、`company_research.info`、`resume_submission.card_version_ids`、`interview_records.parsed_dialogue_json/analysis_json`、`interview_qa_pairs.feedback_json/suggestions_json`、`card_versions.tags`。

## 6.4 关系映射（应用层保证，无 FK）

```text
users ─┬─ experience_card ─┬─ card_versions
       ├─ job_analysis ── experience_job_mapping(composite PK)
       │        ├─ resume_submission ── interview_preps / interview_records
       │        └─ interview_preps
       └─ company_research (standalone, company PK)
interview_records ── interview_qa_pairs
```

## 6.5 Schema 演进机制

无迁移框架（无 Alembic）。靠运行时 `_ensure_*` 函数 `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE`（9 处）：`db_experience.py:17,612`、`db_job.py:15`、`db_submission.py:15,44`、`db_interview.py:15,109,135`、`db_user.py:13`。另 `docker/*.sql` 存在多个 dump 文件（`dump.sql/dump2/dump3/full.sql/fulldump*.sql/fulldump_utf8.sql`），内容未统一（多份快照）。

---

# 7. AI Statistics

## 7.1 LLM 配置

- `app/core/llm.py:15-18`：单一全局 model 单例，`init_chat_model(model=os.getenv("LLM_model"), model_provider="openai")`，provider 硬编码 `"openai"`。
- 实际模型：智谱 AI OpenAI 兼容端点（`open.bigmodel.cn`），默认 `glm-4-flash`（PROGRESS v0.8 记录；`interview_review.py:389` 硬编码 `glm-4-flash` 兜底）。

## 7.2 LLM 调用点（4 处）

1. `tools/llm_json.py:77` — `bind_tools` 结构化输出（主路径）
2. `tools/llm_json.py:153` — 纯 JSON fallback
3. `agents/gate_agent.py:77` — 绕过基类的直接 `llm.invoke`
4. `api/interview_review.py:388-394` — mock-chat 直接 `OpenAI().chat.completions.create()`

## 7.3 Workflow（全部同步 .invoke()，StateGraph）

| Workflow | 入口 | Node | LLM 调用 | DB |
|---|---|---|---|---|
| extract_flow | run_extract_structured/recommend_tags/parse_resume/backfill | 1 | 1 | backfill | 
| job_analysis_flow | step1/step2/analyze/analyze_ats/resume_preview | 1 | 1–3 | 部分 |
| interview_prep_flow | run_interview_prep_workflow | 1 | 1 | 读+写 |
| interview_review_flow | run_interview_review_workflow | **6** | 1–3（Router→Tech/Soft→Gate） | 读+写 |
| question_table_flow | run_question_table_workflow | 3 | 1 | 读+写 |
| base.py | BaseWorkflow | — | — | — |

## 7.4 Agent（15 个，全部单 LLM 调用、无状态、不直连 DB ✅）

`extract_agent(3)` / `jd_ats_agent` / `ats_recommend_agent` / `score_match_agent` / `gap_polish_agent` / `sug_agent` / `router_agent` / `tech_analyzer` / `soft_analyzer` / `gate_agent` / `interview_prep_agent` / `question_table_agent` / `question_intent_agent` / `company_research_agent`。

**Prompt 全为 Agent 文件内硬编码（无外部 prompt 文件、无版本、无历史保留）** —— 违反工程规范（AGENTS.md §7 / workflow 文档 §15）。

## 7.5 AI 工程化缺口

| 能力 | 现状 | 证据 |
|---|---|---|
| AI Task 持久化 | 有 `tasks/worker.py`（Redis-backed TaskManager）但**无后台消费 worker**；`handlers.py:78` 导入不存在的 `interview_flow` | `tasks/worker.py`、`tasks/handlers.py:78` |
| AI Cache | 仅公司背调 7 天 DB 缓存 | `db_experience.py:568-591`；无通用 hash/TTL 抽象 |
| Retry | 无瞬态错误重试（仅有 bind_tools→JSON 两段 fallback） | `llm_json.py` |
| Prompt 版本 | 无 | 所有 agent |
| AI Usage/token | 有指标定义但**从不记录** | `monitoring/metrics.py` |
| AI Output Schema 校验 | 有（Pydantic `invoke_structured`）✅ | `llm_json.py` |

---

# 8. Testing Statistics

## 8.1 测试文件与函数

| 文件 | 测试函数 | 类型 |
|---|---:|---|
| test_api_routes_unit.py | 89 | Unit（mock DB/Workflow） |
| test_tools_extra_unit.py | 53 | Unit（mock DB） |
| test_workflows_unit.py | 27 | Unit（mock agents+DB） |
| test_agents_extra_unit.py | 21 | Unit（mock LLM） |
| test_jobcraft_analyze_unit.py | 17 | Unit（纯函数） |
| test_agents_mock_unit.py | 14 | Unit（mock LLM） |
| test_resume_gen_unit.py | 14 | Unit（模板） |
| test_jobcraft_e2e.py | 11 | E2E（@slow，需真实 server+DB+LLM，默认跳过） |
| test_misc_unit.py | 10 | Unit |
| test_fuse_gap_scores_unit.py | 5 | Unit |
| test_qa_pairs_unit.py | 5 | Unit |
| **合计** | **266** | |
| test_qa_pairs.py | 0 | 非测试脚本（import 时打印，会被 pytest 收集） |
| conftest.py | — | `--runslow` + `server_available` fixture（探测 `/health`） |

## 8.2 按功能覆盖

| 功能 | 单元/接口 | E2E | Auth/Security |
|---|---|---:|---|
| Experience CRUD | ✅ 充分 | ✅ | ❌ 无 |
| Job Analysis | ✅ 充分 | ✅(slow) | ❌ |
| Submission | ✅ | ❌ | ❌ |
| Interview Prep | ✅ | ✅(slow) | ❌ |
| Interview Review | ✅ | ❌ | ❌ |
| Auth（register/login/me） | ❌ **无** | ❌ | ❌ |
| CORS / 越权 / 注入 | ❌ | ❌ | ❌ |

**缺口**：无任何认证/越权/所有权/注入安全测试；全部 E2E 默认跳过。

## 8.3 质量工具

- **ruff**：已配置（`pyproject.toml:42-49`，select E/F/W）
- **前端 lint/type**：`package.json` 有 `lint: tsc --noEmit`；CI 跑 `npm run build` + `tsc --noEmit`
- **pre-commit**：`.pre-commit-config.yaml`（trailing-whitespace / end-of-file-fixer / check-yaml / check-toml / ruff-check / ruff-format）
- **mypy**：无
- **.github/workflows**：存在 ✅（`ci.yml` + `frontend-ci.yml`）
  - `ci.yml`：lint（ruff check）+ format + pytest + security-scan（`ruff --select S`）
  - `frontend-ci.yml`：`npm ci` + `npm run build` + `npx tsc --noEmit`
- **pre-commit 缺**：pytest / eslint 未纳入 hook

---

# 9. Security Statistics

## 9.1 认证现状

| 项 | 状态 |
|---|---|
| 机制 | JWT（HS256，7 天），python-jose + bcrypt（`auth/__init__.py`） |
| Secret | `JWT_SECRET_KEY` env；**源码兜底** `"jobcraft-dev-secret-key-change-in-production"`（`auth/__init__.py:15`） |
| 强制认证端点 | 仅 `GET /api/auth/me`（`auth/router.py:139`） |
| 未认证业务端点 | **48** |
| `default-login` | 自动建 `default_user`，密码 `"default_password_123"`（`auth/router.py:123`） |
| `get_optional_user` | 定义于 `auth/dependencies.py:47`，失败返回 user_id=1，**无任何路由使用** |

## 9.2 数据所有权（user_id）

- **硬编码 `user_id=1` 默认值：37 处**（API 16 / 取数 10 / Workflow 4 / Schema 4 / Auth fallback 2）。
- **按 ID 读取/更新/删除不到 user_id 过滤的 DAO**（越权面）：
  - `db_experience.py`: `get_card:296`、`update_card:361`、`delete_card:426`
  - `db_job.py`: `get_job_analysis:69`、`delete_job_analysis:108`
  - `db_submission.py`: `get_submission:160`、`update_submission:182`、`delete_submission:204`
  - `db_interview.py`: `get_interview_record:180`、`get_interview_prep_by_job:163`、`delete_interview_record:387`
- 列表类 DAO（list/count/search/dashboard）均按 user_id 过滤 ✅。

## 9.3 注入与凭证

| 项 | 位置 | 严重度 |
|---|---|---|
| `execute_sql_query` 传原始 LLM SQL | `db_tools.py:143` | HIGH（LLM 注入面） |
| `get_table_data` f-string 表名 | `db_tools.py:104` | MEDIUM |
| DB 默认账号兜底 `root/root` | `db/config.py:18` | MEDIUM |
| CORS 硬编码 fallback origins | `server.py:61` | LOW |

## 9.4 认证端点 / 所有权保护 / 潜在不安全端点数

| 项 | 数量 |
|---|---:|
| 认证端点（强制 JWT） | 1 |
| 未认证端点 | 51（含 auth 的公开端点） |
| 所有权保护端点 | **0**（无一端点做“当前用户→数据”绑定校验） |
| 潜在不安全端点 | 48（全部业务端点） |

---

# 10. Documentation Statistics

## 10.1 Markdown 清单

**根目录**：`AGENTS.md`、`AI_WORKFLOW.md`、`ANALYSIS_SUMMARY.md`、`ARCHITECTURE.md`、`FRONTEND_BACKEND_MAPPING.md`、`PRODUCT.md`、`PROGRESS.md`、`PROGRESS_TEMPLATE.md`、`TODO.md`、`README.md`

**docs/**：`CODE_REVIEW.md`、`REVIEW_DIMENSIONS.md`、`UI_DESIGN.md`、`domain-model-v2.md`、`engineering-development-workflow-v1.md`、`frontend-backend-contract-audit-v1.md`、`archive/`（7 个历史）+ `design-decisions/`、`harness/`、`superpowers/`

## 10.2 过期/矛盾（MISMATCH）

| 文档声明 | 实际代码 | 状态 |
|---|---|---|
| `AGENTS.md §3.2`：**纯原生 Ant Design** | 新前端用 **Tailwind CSS v4**（0 antd import） | **MISMATCH** |
| `pyproject.toml version=0.6.0` | PROGRESS 记录到 v0.14 | MISMATCH |
| 文档体系含 `database-schema-v2.md`/`api-contract-v2.md`/等（workflow 文档引用） | 这些文件**不存在**（实际只有 contract-audit-v1、domain-model-v2、engineering-workflow-v1） | **MISSING** |
| `AGENTS.md §5` 提到 `#/job/:jobId`、hash 路由 | 新前端用 switch 手动路由 | ADAPT |

---

# 11. Mock / Hardcoded Data

## 11.1 前端 Mock/占位（高影响）

| 项 | 证据 | 影响 |
|---|---|---|
| **假评分 `Math.random()`** | `JobCraftContext.tsx:1126,1189`；`MockInterviewModal.tsx:68-71` | 复盘/模拟面试评分非真实 AI |
| **硬编码 ID** | `res-byte-1`（`JobCraftContext.tsx:670,696,714,...`、`ResumeEditorView.tsx:34`、`JobWorkspaceView.tsx:203`）；`int-byte-1/2`；`jd-byte-1`；`exp-1/2`；`job-1` | 伪数据占位 |
| **Resume 编辑失效** | `resumes` state 永不填充（`JobCraftContext.tsx:295`）+ 硬编码 key | **Resume 编辑静默无效果** |
| **假 setTimeout 进度** | `JDAnalysisCenterView.tsx:48`、`JDReportDetailView.tsx:299`、`NewReviewModal.tsx:49`、`MockInterviewModal.tsx:65,99`、4 个 pages、`UserProfileView.tsx:104` 等 10+ 处 | 模拟加载 |
| **硬编码仪表盘** | `WorkbenchView.tsx:30-102`（12/3/5/2 计数、jobSteps、statusBadge、matchScore 82/76/68、公司名“字节跳动/腾讯”） | 首页非真实数据 |
| **mock 扬本/transcript** | `JDAnalysisCenterView.tsx:32`（sampleJD）、`NewReviewModal.tsx:34-38` | 占位数据 |
| `interviewTime` 硬编码今天 | `NewInterviewPrep.tsx:69` | 默认值 |
| `rawText:'待补充JD内容'` 占位 | `NewReview.tsx:116` | 占位 |
| `as any` | `JDReportDetailView.tsx:503` | 类型逃逸 |
| 中文标识符 | `ResumeEditorView.tsx:84-85`（`allBullets紧`，现代 JS 合法但为编码残留） | 可读性/维护风险 |

## 11.2 后端硬编码

| 项 | 证据 |
|---|---|
| `user_id=1` 默认 | 37 处（见 §9.2） |
| 默认模型 `glm-4-flash` | `interview_review.py:389` |
| DB 兜底 `root/root` | `db/config.py:18` |
| JWT secret 兜底 / default 密码 | `auth/__init__.py:15`、`auth/router.py:123` |
| 状态中文字符串 `"已投递"` / `"pending"` / `"done"` 等 | `db_submission.py:98`、`submission.py:26,191`、`db_interview.py:197,219,258,285`、`interview_review.py:78,178`、`question_table_flow.py:131`、`tasks/worker.py:20-24` |

---

# 12. Architecture Health Score

评分依据：证据支撑，非主观。

| 维度 | Score | 证据（关键） | 主要问题 |
|---|---:|---|---|
| Architecture | 62 | 分层基本成型；Workflow/Agent 拆分清晰；但无 Application Service 层，Controller 持有较多编排 | God Context 前端；分层扁七 |
| Frontend | 50 | 无 fetch 散落✅、状态集中；但大量 Mock/硬编码/Resume 失效/双重类型系统 | 非数据驱动；God State |
| Backend | 68 | 50+ 端点、DAO/Workflow/Agent 结构完整；tools 3.5K 行较臃肿 | tools 大模块；偶发工具调 agent |
| API Contract | 55 | 统一 `{code,msg,data}`✅；但双重类型 + 大量 `any`；无自动生成 | mapper 桥接易错 |
| Database | 50 | 表设计合理；但 0 FK、无迁移框架、16 JSON、多份 dump 快照 | 引用完整性由应用保证 |
| AI | 45 | Workflow+Agent 工程化✅；但 prompt 无版本、无 cache/retry/usage、AC 系统 broken | 工程化缺失 |
| Security | **20** | 认证未强制、所有权缺失（越权）、默认凭据、注入口 | **P0 风险** |
| Testing | 64 | 266 测试、充分单元/接口；但无安全测试，E2E 全跳过，`test_qa_pairs.py` 被误收集 | 覆盖盲区 |
| Documentation | 58 | 文档体系丰富；但与代码 MISMATCH（antd/Tailwind、version） | 过期/矛盾 |
| Maintainability | 55 | 模块职责大体清晰；God Context 1.6K 行、tools 3.5K 行、组件 1.1K 行 | 大文件重构候选 |

**综合健康度 ≈ 59/100。**

---

# 13. Critical Findings

## P0 — Critical
1. **认证未强制 + 所有权缺失（越权）**：48 个业务端点无认证，`user_id` 客户端可控（默认 1），get/update/delete 不过滤 user_id → **任意用户可读写任意数据**。证据：所有 `app/api/*.py`、`db_*.py` 的 get/delete、`auth/dependencies.py`。
2. **SQL 注入面（LLM 生成 SQL）**：`db_tools.py:143` `execute_sql_query` 直接 `cursor.execute(query)` + `:104` f-string 表名。
3. **泄露的默认凭据/后门**：JWT secret 兜底（`auth/__init__.py:15`）、`default-login` 硬编码密码（`auth/router.py:123`）、DB `root/root`（`db/config.py:18`）。

## P1 — High
4. **前置 UI 大量 Mock/硬编码**，非数据驱动（尤其 WorkbenchView 首页、MockInterviewModal、Review 假评分）。
5. **Resume 编辑功能静默失效**（`resumes` 不填充 + 硬编码 `res-byte-1`）。
6. **AI 后台任务系统 broken**：`handlers.py:78` 导入不存在 `interview_flow`；无消费 worker。
7. **双重类型系统 + `any`** 导致契约漂移。
8. **无 FK、无数据库迁移框架**，表结构靠运行时 ALTER。

## P2 — Medium
9. **Prompt 无版本化**；无 AI Cache/Retry/Usage 通用设施。
10. **监控指标 dead code**（`monitoring/metrics.py` 从不 .inc()/.observe()）。
11. **SQLAlchemy engine（app/db/config.py）未使用**（全走 `mysql.connector`）——死代码。
12. **`get_optional_user` / `PaginatedResponse` / `ApiResponse(common)` 死代码**。
13. **无认证/越权/注入安全测试**；E2E 全 skip。
14. **多份 docker dump SQL 快照未统一**；`frontend-jobcraft-backup/` 未跟踪。
15. **等价前端与像素契约偏离**:AGENTS.md 声明 antd，实际 Tailwind — 文档与代码不一致。
16. 潜在未用依赖：`passlib[bcrypt]`、`aiofiles`、`playwright`(dev)、`requests`；（前端）`express`、`@google/genai`、`vite` 误入 prod。

---

# 14. Technical Debt

| 类别 | 明细 |
|---|---|
| 架构分层 | 无 Application Service 层；Controller 直接编排工作流/DB（`app/api/interview_review.py` 直接 new OpenAI） |
| God 模块 | `JobCraftContext.tsx`（1,626 行）、`app/tools/db_experience.py`（659 行）、`NewInterviewModal.tsx`（1,106 行）、`NewInterviewPrep.tsx`（956 行） |
| 类型契约 | 双重类型系统 + mapper 桥接（`cardToExperience/analysisToJD/submissionToJob`） |
| 数据库 | 0 FK、运行时 DDL、16 JSON 列承载关系/结构、多份 dump |
| AI | prompt 内联无版本、无 cache/retry/usage、AC 系统 broken、监控 dead code |
| 安全 | 默认凭据、未强制认证、无所有权、SQL 注入面 |
| 前端 | 大量 mock、Resume 失效、中文标识符、`as any` |

**重构候选（>500 行文件）**：`test_api_routes_unit.py(932)`、`test_workflows_unit.py(921)`、`interview_review.py(767)`、`db_experience.py(659)`、`api/experience.py(494)`、`JobCraftContext.tsx(1626)`、`NewInterviewModal.tsx(1106)`、`NewInterviewPrep.tsx(956)`、`CreateInterview.tsx(802)`、`NewReview.tsx(759)`、`CreateReview.tsx(750)`。

---

# 15. Contract Mismatch

| 前端期望/声明 | 后端实际 | 状态 |
|---|---|---|
| 类型 camelCase（types/jobcraft.ts） | 后端 snake_case（types.ts/api DTO） | MISMATCH（靠 mapper 桥接） |
| AGENTS.md 强制 Ant Design | 前端用 Tailwind | MISMATCH |
| `pyproject` v0.6.0 | PROGRESS v0.14 | MISMATCH |
| workflow 文档引用的 database-schema-v2/api-contract-v2/ai-architecture-v2/state-machine.md | 文件不存在 | MISSING |
| Resume 编辑 | 后端无独立 resume 表/API（resume_markdown 存 submission） | ADAPT |

> 详细的前后端端点映射沿用仓库已有 `FRONTEND_BACKEND_MAPPING.md`，本文不再重复展开。

---

# 16. Risk Matrix

| # | Issue | Severity | Evidence | Impact | Recommended Action |
|---|---|---|---|---|---|
| R1 | 业务端点认证缺失 + user_id 客户端可控 | P0 | 48 端点、37 处 user_id=1、`auth/dependencies.py` | 越权/数据泄露 | 强制 JWT + inject current_user |
| R2 | get/update/delete 无所有权过滤 | P0 | `db_*.py`（§9.2 清单） | 跨用户读写 | DAO 加 user_id 过滤 + 测试 |
| R3 | SQL 注入面（LLM SQL） | P0 | `db_tools.py:143,104` | 数据/DB 被控 | 移除/收紧 execute_sql_query |
| R4 | 默认凭据/后门 | P1 | `auth/__init__.py:15`、`auth/router.py:123`、`db/config.py:18` | 未授权访问 | 移除默认、强制 env、禁 default-login |
| R5 | 前端大量 Mock/硬编码 | P1 | §11.1 | 产品不可信 | 逐个接入真实 API |
| R6 | Resume 编辑失效 | P1 | `JobCraftContext.tsx:295,668,780` | 功能不可用 | 填充 resume state/接 API |
| R7 | AI 后台任务 broken | P1 | `tasks/handlers.py:78` | 异步功能坏 | 修 import + 消费 worker |
| R8 | 无 DB 迁移/FK | P2 | `_ensure_*`、0 FK | 演进风险 | 引入迁移框架 |
| R9 | Prompt 无版本/AI 工程化缺失 | P2 | agents 内联 | 结果不可复现 | prompt 版本化 + cache/usage |
| R10 | 双重类型系统 | P2 | types/ 两份 | 契约漂移 | 统一 snake_case DTO |
| R11 | 无安全测试 | P2 | tests/ 无 auth | 回归风险 | 补越权/认证测试 |
| R12 | 监控 dead code | P3 | `monitoring/metrics.py` | 不可观测 | 挂钩点记录指标 |

---

# 17. Current System Map

```text
[frontend-jobcraft/]  React19 + TS + Tailwind v4
   |
   | src/api/* (唯一 fetch，localStorage token → autoLogin)
   |
   v
[app/api/*.py]  FastAPI 52 端点
   |
   +--> [app/workflows/*] StateGraph (同步)
   |        |
   |        v
   |   [app/agents/*] BaseAgent → invoke_structured
   |        |
   |        v
   |   [app/core/llm.py] model (glm-4-flash, openai-compatible)
   |
   +--> [app/tools/db_*.py] mysql.connector DAO
   |
   v
[MySQL 8.4]  10 表 / 0 FK / 16 JSON / 运行时 DDL
```

**AI 横切链（现状）**：`Controller → Workflow → Agent → LLM → Pydantic 校验 → DB`。**缺**：AI Task 持久化、Cache、Retry、Usage、Prompt 版本。

---

# 18. Evidence

- 代码规模/文件计数：本会话 `git status`、PowerShell 统计脚本。
- 坐标数据（规模/占比）来自对 `app/`、`frontend-jobcraft/src/`、`tests/` 的只读文件读取。
- 端点清单：对 `app/api/*.py`、`app/auth/router.py` 的逐文件读取。
- Agent/Workflow/Tool：对 `app/agents/`、`app/workflows/`、`app/tools/` 的逐文件读取。
- 前端：对 `frontend-jobcraft/src/**` 全量读取 + `npx tsc --noEmit` + `npm run build`（构建产物写入 `dist/`，未改业务源码）。
- 数据库：`docker/mysql/jobcraft.sql` + 各 `db_*` 运行时 DDL。
- CI：`ci.yml`、`frontend-ci.yml` 实际内容（本会话核验存在）。

**边界说明**：
- 评分中的“异常 `get_optional_user`/`PaginatedResponse`”等 dead-code 结论基于导入搜索。
- 未对 `docker/*.sql` 各 dump 做逐份比对（内容未统一已近似验证）。
- `output/`、`updated/`、`.venv`、`frontend-jobcraft-backup/`、`node_modules` 排除在业务扫描外。

> **本轮仅扫描与报告，未修改任何业务代码、数据库、配置与依赖。**

---

## Scan Complete

- **Repository**: JobCraft
- **Scan Scope**: Frontend / Backend / Database / AI / Tests / Docs / Dependencies / Security
- **Statistics**: 详见 §2–§10
- **Critical Findings**: 详见 §13
- **Generated**: `docs/project-engineering-baseline-v1.md`（本文）
- **No source code was modified.**
