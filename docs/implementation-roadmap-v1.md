# JobCraft Implementation Roadmap v1

> **版本**：v1.0
> **输入**：`docs/project-engineering-baseline-v1.md`（只读审计快照）
> **目标**：把 Baseline 发现的问题转化为可执行、小粒度、可独立回滚的开发 Task。
> **原则**：`Frontend-first → Existing Backend-first → Incremental Migration → Small Task → No Big Bang Rewrite`。
> **从属**：所有 Task 必须遵循 `docs/engineering-development-workflow-v1.md` 的标准流程（Read Docs → Analyze → Task → Design → Implement → Test → Document → Commit → PROGRESS）。
>
> **⚠️ 说明**：本 Roadmap 是**规划文档**。每个 Task 在开始实施前，必须先按 Engineering Workflow 完成独立分析，以真实代码为准校准 Scope（Baseline 为只读快照，实施时可能已变化）。

---

# 1. 排序原则

按优先级 `P0 → P1 → P2 → P3`，同时权衡 `Dependency / Risk / User Value / Implementation Cost`。

**第一阶段（P0）唯一目标**：让新 `frontend-jobcraft/` 真实由后端数据驱动，并补上会致命的**安全/所有权**漏洞。

```
Phase 0  安全基线（认证 + 所有权 + 注入收敛）        【P0，阻塞一切】
Phase 1  Contract 对齐（类型 + API 接通 + 去 Mock）   【P0，新 UI 数据驱动】
Phase 2  领域能力增强（Resume / Submission 状态机）   【P1】
Phase 3  DB 演进（迁移框架 + FK + 少拆）             【P2】
Phase 4  AI 工程化（Task/Cache/Retry/Usage/Prompt）  【P2】
Phase 5  清理与观测（监控/dead-code/依赖/docs 修正）  【P3】
```

---

# 2. Task Dependency Graph

```text
TASK-AUTH-001 ──────────────┐
TASK-OWN-001 ──────────────┤
TASK-INJ-001 ──────────────┼─→ 阶段 0 安全基线
                           │
TASK-AUTH-001 ─┐           │   (并行可独立提交，但建议先 AUTH)
TASK-TYPE-001 ─┼─→ TASK-REAL-DATA-001 → TASK-REAL-DATA-002 → ...   
TASK-FETCH-001 ┘
        │
        └─→ TASK-RESUME-001 (依赖 TASK-TYPE-001)
        └─→ TASK-STATUS-001 (依赖 TASK-AUTH-001)

TASK-DB-MIG-001 → TASK-DB-FK-001      (阶段 3)
TASK-AI-TASK-001 → TASK-AI-CACHE-001  (阶段 4)
TASK-OBS-001 / TASK-DEPS-001 / TASK-DOCS-001  (阶段 5)
```

**可并行**：阶段 0 内 AUTH/OWN/INJ；阶段 1 内 TYPE/FETCH；阶段 2 的 RESUME/STATUS 可并行（各自独立 Task）。

---

# 3. 阶段 0 — 安全基线（P0）

> Baseline R1/R2/R3/R4。**必须最先处理**，否则任何“接通真实数据”都暴露越权与注入风险。

### TASK-AUTH-001 强制业务端点认证

- **Goal**：所有业务端点（48 个）启用 JWT 认证，`user_id` 不再由客户端传入，改为从 `Depends(get_current_user)` 注入。
- **Why**：Baseline R1。当前仅 `GET /api/auth/me` 强制认证，其余端点 `user_id` 客户端可控。
- **Current State**：`auth/dependencies.py:16` `get_current_user` 已存在但未被业务路由使用；`user_id=1` 默认 37 处。
- **Evidence**：`app/api/*.py`、`app/schemas/jobcraft.py:83,111,263,310`、`app/workflows/*_flow.py`、`app/tools/db_*.py`。
- **Scope**：
  - 保留兼容：注册/登录/健康检查/`default-login`（P1 再移除）保持公开。
  - 其余端点：签名注入 `current_user: int = Depends(get_current_user)`。
  - 删除请求体/查询中的 `user_id` 参数（统一由认证注入）。
- **Non-goals**：不做微服务/多角色；不重写 auth 机制。
- **Dependencies**：无。
- **Files**：`app/api/*.py`、`app/auth/dependencies.py`、`app/schemas/jobcraft.py`（移除 user_id 默认）、`app/workflows/*_flow.py`、`app/tools/db_*.py`。
- **API**：Breaking——移除 `user_id` 入参（按 workflow.doc 的 breaking change 流程处理）。
- **Database**：无。
- **AI**：无。
- **Tests**：新增认证端点测试（register/login/me）+ 未认证 401 测试。
- **Documentation**：更新 `frontend-backend-contract-audit-v1.md`、`PROGRESS.md`。
- **Acceptance Criteria**：无 token 访问业务端点返回 401；有 token 以 token 用户身份访问。
- **Expected Commit**：`feat(auth): enforce JWT on business endpoints`
- **Status（2026-09-02）**：✅ 已完成——commit `8599e80`（后端强制认证+注册加固+测试，合法）与 `6a0f121`（前端登录/注册闭环，移除 default-login）。工作区与提交快照 `pytest 315 passed / 6 skipped`，`ruff check .` 与前端 `npm run build`/`tsc --noEmit` 通过。
- **遗留**：~~R2（TASK-OWN-001 按 ID 的所有权过滤）~~ 已于 commit `09aa805` 完成；前端合同已记账为后续阶段。

### TASK-OWN-001 get/update/delete DAO 增加所有权过滤

- **Goal**：按 ID 读取/更新/删除时强制 `WHERE user_id = current_user`。
- **Why**：Baseline R2。`db_experience.py:296/361/426`、`db_job.py:69/108`、`db_submission.py:160/182/204`、`db_interview.py:180/163/387` 无 user_id 过滤 → 越权。
- **Current State**：列表类已过滤 user_id；get/update/delete 未过滤。
- **Scope**：为上述 DAO 增加 `user_id` 参数与 WHERE 条件；Controller 传入认证用户。
- **Dependencies**：TASK-AUTH-001（依赖其注入用户）。
- **Files**：`app/tools/db_*.py`、`app/api/*.py`。
- **Tests**：越权测试（用户 A 的 ID，用户 B 访问 → 404/403，不得返回数据）。
- **Acceptance Criteria**：跨用户按 ID 访问返回空/404；同级用户不可读他人数据。
- **Expected Commit**：`fix(security): enforce ownership on by-id DAO operations`
- **Status（2026-09-02）**：✅ 已完成——commit `09aa805`。`get_card/update_card/delete_card`（db_experience）、`get_job_analysis/delete_job_analysis`（db_job）、`get_submission/update_submission/delete_submission`（db_submission）、`get_interview_prep_by_job/get_interview_record/delete_interview_record`（db_interview）均增加 `user_id`（可选）参数，传入时 WHERE 追加 `AND user_id=%s`；Controller/工具/工作流全部传入 `current_user`。新增 `get_submission` 复盘摘要路径过滤（`list_interview_records_by_submission`）。新增 `tests/test_ownership_filtering.py`（15 passed），提交快照 `pytest 184 passed` 且 `ruff check` 绿。

### TASK-INJ-001 收敛 SQL 注入面

- **Goal**：收紧/下线 `execute_sql_query` 与 f-string 表名。
- **Why**：Baseline R3。`db_tools.py:143` 直接 `cursor.execute(query)`；`:104` f-string 表名。
- **Current State**：`db_tools.py` 暴露 `execute_sql_query/get_table_data/list_sql_tables`。
- **Scope**：确认这些工具的调用方；若无必要则由所有调用方移除，或改为参数化/白名单校验后保留只读。
- **Non-goals**：不开通用 SQL 控制台。
- **Dependencies**：无。
- **Files**：`app/tools/db_tools.py` 及调用方。
- **Tests**：注入 payload 测试（`'; DROP TABLE ...`）。
- **Expected Commit**：`fix(security): remove raw SQL execution surface`
- **Status（2026-09-02）**：✅ 已完成——commit `b681f2c`。确认 `list_sql_tables/get_table_data/execute_sql_query` 三个 `@tool` 无任何调用方（死代码），予以下线；`db_tools.py` 改为自包含的兼容层（本地定义 `get_db_config/_jc_config/JOBCRAFT_DB`，保留 `connect` 与各 `db_*` re-export），提交快照不引用未跟踪的 `db_config.py`。`tests/test_tools_extra_unit.py` 恢复全绿（53 passed）。

### TASK-AUTH-002 移除默认凭据与后门

- **Goal**：移除源码兜底密钥与 `default-login` 弱口令。
- **Why**：Baseline R4。`auth/__init__.py:15` secret 兜底、`auth/router.py:123` `default_password_123`、`db/config.py:18` `root/root`。
- **Scope**：secret 改为启动时强制 env（缺失则失败）；`default-login` 移入 dev-only 或删除；DB 默认账号移除。
- **Dependencies**：TASK-AUTH-001。
- **Expected Commit**：`fix(security): remove hardcoded secrets and default-login backdoor`
- **Status（2026-09-02）**：✅ 已完成——`default-login` 已随 commit `6a0f121` 移除；commit `8878459` 处理剩余两项：`auth/__init__.py` 改为 `load_dotenv(override=True)` 后强制要求 `JWT_SECRET_KEY`（缺失即 `RuntimeError`），移除硬编码 dev secret 兜底；`db/config.py` 移除 `root/root` 默认账号，`MYSQL_USER/MYSQL_PASSWORD` 必须由 env 注入。已验证缺失时启动即失败。

---

# 4. 阶段 1 — Contract 对齐（P0，新 UI 数据驱动）

> Baseline R5/R6/R7/R10 及 §15 MISMATCH。前端接入真实后端。

### TASK-TYPE-001 统一前端类型系统

- **Goal**：消除双重类型系统，统一为后端 snake_case DTO。
- **Why**：Baseline R10。`src/types/jobcraft.ts`（camelCase）与 `src/api/types.ts`（snake_case）并行，靠 mapper 桥接易漂移。
- **Current State**：`JobCraftContext.tsx:159/186/241` 三处 mapper。
- **Scope**：以 `src/api/types.ts`（后端 DTO）为唯一契约；迁移 `types/jobcraft.ts`，删除 mapper 或改为纯字段映射。
- **Non-goals**：不引入 tRPC/OpenAPI 代码生成（P2 再考虑）。
- **Files**：`src/types/jobcraft.ts`、`src/api/types.ts`、`src/context/JobCraftContext.tsx`、各页面组件。
- **Tests**：`npm run build`（tsc 严格）+ 需新增前端单测（若配置 vitest）。
- **Expected Commit**：`refactor(frontend): unify API types to backend DTOs`

### TASK-FETCH-001 审计并固化 fetch 出口

- **Goal**：确认无组件直连后端之外的非标请求，token/错误处理统一。
- **Why**：Baseline 已确认 fetch 集中在 `api/client.ts` ✅（基线正面项，需保持并固化为规范）。
- **Current State**：`api/client.ts` 为唯一 fetch 出口。
- **Scope**：补充 README/文档强调；可选将 `any`（`api/job.ts:43,45,57,58` 等）收紧为具体类型。
- **Expected Commit**：`docs(frontend): document api client as single fetch source`

### TASK-REAL-DATA-001 首页（WorkbenchView）接真实数据

- **Goal**：`WorkbenchView.tsx` 从硬编码改为读取后端 dashboard 数据。
- **Why**：Baseline §11.1。`WorkbenchView.tsx:30-102` 硬编码计数/步骤/评分/公司名。
- **Current State**：首页显示假数据（12/3/5/2、字节跳动/腾讯、82/76/68）。
- **Scope**：用 Context 已加载的 dashboard/submissions/jobs 渲染真实计数与列表。
- **Files**：`src/components/workbench/WorkbenchView.tsx`、`src/context/JobCraftContext.tsx`。
- **Tests**：前端构建通过；必要时补充渲染单测。
- **Expected Commit**：`feat(frontend): drive workbench from real dashboard data`

### TASK-REAL-DATA-002 MockInterview 去 Mock

- **Goal**：模拟面试由真实后端 mock-chat/复盘数据驱动，去掉 `Math.random` 假评分。
- **Why**：Baseline §11.1。`MockInterviewModal.tsx:42-99` 硬编码题目/假评分/假录音。
- **Current State**：模拟面试验证结论由 `Math.random()` 生成。
- **Scope**：复用现有 `/interview-review/mock-chat`（`interview_review.py:359`）或明确该能力边界；评分改真实 AI。
- **Dependencies**：TASK-TYPE-001。
- **Expected Commit**：`feat(frontend): real mock interview scoring from backend`

### TASK-REAL-DATA-003 复盘/新增向导去 Mock 评分

- **Goal**：`JobCraftContext.tsx:1126/1189` 及 `NewReviewModal.tsx:51-86` 的假评分/占位改为后端真实分析。
- **Why**：Baseline §11.1。
- **Scope**：复用现有 `interview-review/analyze`、`question-table` 返回结构化结果，去掉手工 `overallScore/qaBreakdown` 假数据。
- **Dependencies**：TASK-TYPE-001。
- **Expected Commit**：`feat(frontend): use backend review analysis instead of mock scores`

### TASK-DOCFIX-001 修正文档与代码 MISMATCH

- **Goal**：消除可立即修正的文档漂移。
- **Why**：Baseline §10/§15。`AGENTS.md` 强制 Ant Design（实际 Tailwind）、`pyproject` v0.6.0（实际 v0.14）、缺失的 v2 文档引用。
- **Scope**：更新 `AGENTS.md`（UI 规范改为 Tailwind 事实）、校正版本号、删除孤儿引用或补建缺失文档。
- **Expected Commit**：`docs: align AGENTS.md and version with actual code`

---

# 5. 阶段 2 — 领域能力增强（P1）

> Baseline R6（Resume）、状态机（Domain v2 §4）。

### TASK-RESUME-001 Resume 编辑接真实数据

- **Goal**：修复 Resume 编辑静默失效。
- **Why**：Baseline R6。`resumes` state 永不填充；所有操作引用硬编码 `'res-byte-1'`。
- **Current State**：`JobCraftContext.tsx:295,668,712,780,...`、`ResumeEditorView.tsx:34,84-85`。
- **Scope**：填充 `resumes` state；从 `resume_submission.resume_markdown` 读取并渲染；修正中文标识符 `allBullets紧`。
- **Dependencies**：TASK-TYPE-001。
- **Non-goals**：不新增独立 resume 表（P2 DB 阶段）。
- **Expected Commit**：`fix(frontend): wire resume editor to real submission resume`

### TASK-STATUS-001 引入 Submission 状态机

- **Goal**：统一 `resume_submission.status` 为英文枚举，前后端共享。
- **Why**：Baseline §11.2 + Domain v2 §4。当前 `"已投递"` 等中文字符串散落（`db_submission.py:98`、`submission.py:26,191`）。
- **Current State**：状态为中文字符串、无枚举/流转约束。
- **Scope**：定义 `SUBMISSION_STATUS` 枚举；后端校验流转（APPLIED/INVITED/ROUND_1/ROUND_2/OFFER/CLOSED）；前端显示映射中文。
- **Dependencies**：TASK-AUTH-001、TASK-TYPE-001。
- **Expected Commit**：`feat(submission): introduce status enum and transitions`

### TASK-FIX-001 修复 AI 后台任务系统

- **Goal**：修复 `tasks/handlers.py:78` 导入不存在的 `interview_flow`。
- **Why**：Baseline R7。`handlers.py:78` 引用 `app.workflows.interview_flow`（应为 `interview_prep_flow`）。
- **Current State**：任务系统无消费 worker + 错误 import。
- **Scope**：修 import；评估是否启用 Redis 消费循环或下线该路径。
- **Expected Commit**：`fix(tasks): correct workflow import and enable worker`

---

# 6. 阶段 3 — 数据库演进（P2）

> Baseline §6/§14。`Incremental Migration`，不做大重构。

### TASK-DB-MIG-001 引入数据库迁移框架

- **Goal**：用 Alembic（或文档化 SQL 迁移目录）替代运行时 `_ensure_*` DDL。
- **Why**：Baseline §6.5。9 处运行时 ALTER/CREATE 无版本、不可回滚。
- **Current State**：`db_*.py` 各 `_ensure_*` 函数 + 多份 dump 快照。
- **Scope**：建立 `migrations/`（或 alembic）；把现有 DDL 固化为 baseline；新变更走迁移。
- **Expected Commit**：`chore(db): introduce migration framework baseline`

### TASK-DB-FK-001 关键表补外键与索引

- **Goal**：为高价值关系补 FK（`submission→job_analysis`、`interview_preps→submission/analysis`、`qa_pairs→record`、`card_versions→card`）。
- **Why**：Baseline §6.2。0 FK，引用完整性靠应用。
- **Note**：遵循 AGENTS.md 前向兼容（只加不改）；FK 前先清理孤儿数据（见 `docs/domain-model-v2.md` §49）。
- **Dependencies**：TASK-DB-MIG-001。
- **Expected Commit**：`chore(db): add foreign keys to core relationships`

---

# 7. 阶段 4 — AI 工程化（P2）

> Baseline §7.5。对齐 Domain v2 §29-34 / Workflow doc §14-18。

### TASK-AI-001 Prompt 版本化

- **Goal**：把 15 个 Agent 内联 prompt 收敛到 `prompts/` 目录并版本化。
- **Why**：Baseline R9。所有 prompt 内联硬编码。
- **Scope**：建立 `prompts/`（experience/jd/resume/interview/review）；每个 prompt 带 `_v{N}`。
- **Expected Commit**：`refactor(ai): externalize and version prompts`

### TASK-AI-002 AI Task 持久化

- **Goal**：为 AI 调用建立 Task/AI 输出持久化（对应 `ai_tasks`/`ai_outputs`，Domain v2 §29-31）。
- **Why**：Baseline R9 + Domain 目标。当前仅 4 处散落 LLM 调用点。
- **Scope**：引入 AI Task 层包裹 Workflow 调用；记录 status/model/input_hash/schema_version。
- **Expected Commit**：`feat(ai): persist AI task metadata`

### TASK-AI-003 AI Cache + Usage

- **Goal**：通用 AI Cache（hash=feature:model:prompt:schema:input）+ token 用量记录。
- **Why**：Baseline §7.5。仅公司背调有 7 天缓存；无通用 TTL/hash。
- **Scope**：抽象 cache key + Redis 热缓存（可先回退到 DB/内存）；输出 `ai_usage` 记录。
- **Dependencies**：TASK-AI-001（cache key 需 prompt_version/schema_version）。
- **Expected Commit**：`feat(ai): add AI cache and usage tracking`

---

# 8. 阶段 5 — 清理与观测（P3）

> Baseline R12 及死代码/依赖清理。

### TASK-OBS-001 激活 Prometheus 指标

- **Goal**：让 `monitoring/metrics.py` 定义的指标真正 `.inc()/.observe()`。
- **Why**：Baseline R12。所有自定义指标从不记录。
- **Scope**：在 LLM 调用点、DB query、端点挂指标。
- **Expected Commit**：`feat(observability): wire up prometheus metrics`

### TASK-DEPS-001 依赖清理

- **Goal**：移除未用依赖（`passlib[bcrypt]`、`aiofiles`、`requests`、dev `playwright`；前端 `express`、`@google/genai`、vite 移出 prod）。
- **Why**：Baseline §依赖扫描。
- **Note**：遵循红线（先写入 pyproject/package.json 确认必要性再动）；避免误删。
- **Expected Commit**：`chore(deps): remove unused dependencies`

### TASK-CLEAN-001 死代码清理

- **Goal**：移除/归档 `app/db/config.py`（未用 SQLAlchemy）、`schemas/common.py` 的 `PaginatedResponse`/`ApiResponse`、`get_optional_user`、`test_qa_pairs.py` 误收集脚本。
- **Expected Commit**：`refactor: remove dead code`

---

# 9. 优先实施清单（前 6 个 Task）

| 顺序 | Task | 优先级 | 依赖 | 用户价值 | 状态 |
|---|---:|---|---|---|---|
| 1 | TASK-AUTH-001 强制认证 | P0 | — | 安全 | ✅ 完成 |
| 2 | TASK-OWN-001 所有权过滤 | P0 | AUTH | 安全 | ✅ 完成 |
| 3 | TASK-INJ-001 注入收敛 | P0 | — | 安全 | ✅ 完成 |
| 4 | TASK-AUTH-002 移除默认凭据 | P0 | AUTH | 安全 | ✅ 完成 |
| 5 | TASK-TYPE-001 统一类型 | P0 | — | 契约稳定 | ⏳ 待办 |
| 6 | TASK-REAL-DATA-001 首页真实数据 | P0 | TYPE | 产品可信 | ⏳ 待办 |

> 前 4 个安全基线任务已于 2026-09-02 全部完成（`8599e80`/`6a0f121`/`b681f2c`/`09aa805`/`8878459`）；随后进入 Contract 对齐。

---

# 10. 明确 Non-goals（不做）

- ❌ 重写整个后端 / PostgreSQL 迁移（Domain v2 §96：MVP 不切换）。
- ❌ 全面 API /v1 版本化 + OpenAPI→TS 代码生成（P2+，非当前阻塞）。
- ❌ 大规模 Clean Architecture 重写（无 Application Service 层暂缓）。
- ❌ 覆盖"关于 Resume 的独立表/多版本"等 Domain v2 远期目标（P2 阶段再推进）。

---

# 11. 退出标准（Phase 1 完成 = 新 UI 真实数据驱动）

```
[ ] 所有业务端点已强制认证 + 所有权过滤（P0 安全基线完成）
[ ] 前端类型统一为后端 DTO，无 mapper 桥接
[ ] 首页/复盘/模拟面试/向导 无 Math.random 假数据
[ ] Resume 编辑可用且读写真实 resume_markdown
[ ] 新 frontend-jobcraft 核心路径（经历卡→JD 分析→投递→面试准备→复盘）全部由后端数据驱动
[ ] 测试通过：uv run ruff check . && uv run pytest tests/ -q && npm run build
```

---

# 12. 文档依赖与后续

本 Roadmap 落地后同步推进：
- `docs/frontend-backend-contract-audit-v1.md` 更新（Auth/契约变化）
- `docs/domain-model-v2.md` 继续作为目标（DB/AI 演进对齐）
- `docs/engineering-development-workflow-v1.md` 为每一 Task 的标准流程
- TODO.md / PROGRESS.md 逐 Task 更新并记录 commit_id

> **本 Roadmap 为只读/规划产出，未修改任何业务代码、数据库、配置与依赖。**
