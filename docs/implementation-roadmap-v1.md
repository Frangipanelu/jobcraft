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
TASK-AUTH-001 ─────────────────┐
TASK-OWN-001 ──────────────────┤
TASK-INJ-001 ──────────────────┼─→ 阶段 0 安全基线 ✅ 全部完成
                               │
TASK-TYPE-001 ─┬─→ TASK-FETCH-001（文档固化，随 TYPE 合并提交）
               ├─→ TASK-REAL-DATA-001 → TASK-REAL-DATA-002
               ├─→ TASK-REAL-DATA-003
               ├─→ TASK-INTERVIEW-001（面试持久化）
               └─→ TASK-TASK-SYS-001（任务系统接线）

TASK-INTERVIEW-001 ──→ TASK-REAL-DATA-002（mock-chat 依赖 interviews 持久化）
TASK-INTERVIEW-001 ──→ TASK-REAL-DATA-003（复盘依赖 interview 数据持久化）

TASK-RESUME-001 (依赖 TASK-TYPE-001)
TASK-STATUS-001 (依赖 TASK-AUTH-001)
TASK-FIX-001 (独立)

TASK-DB-MIG-001 → TASK-DB-FK-001                    (阶段 3)
TASK-AI-001 → TASK-AI-002 → TASK-AI-003             (阶段 4)
TASK-OBS-001 / TASK-DEPS-001 / TASK-CLEAN-001       (阶段 5)
TASK-CLEANUP-WIP-001                                 (随时可做，无依赖)
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

### TASK-TYPE-001 文档化两层类型 + 收紧 any 泄漏

- **Goal**：记录双层类型为有意设计；收紧后端 api 层 7 处 `any`，消除契约模糊。
- **Why**：Baseline R10 提出"统一为 api/types.ts"。实际校准（2026-09-02）：该两层系统是**有意的架构设计**——`api/types.ts`（snake_case 后端 DTO）仅在 `JobCraftContext.tsx` 映射层使用；`types/jobcraft.ts`（camelCase 领域模型）被 10 个组件消费，零死代码，115 处活跃引用。真正问题是 api 层的 `any` 泄漏（模糊返回结构）。
- **Current State**：`src/api/types.ts:10` `APIResponse<T=any>`、`:128` `Record<string, any>`、`:191` `any[]`；`src/api/job.ts:43` `ats: any`、`:45` `all_cards: any[]`、`:57` `per_card: any[]`、`:58` `global_suggestions: any[]`（共 7 处）。
- **Scope**：
  - `api/types.ts:10` → 保留 `any` 作为泛型默认并加 JSDoc 注释（安全，下游类型已约束）；或改为 `Record<string, unknown>` 视调用方兼容性；
  - `api/types.ts:128` → `company_context: Record<string, string | number | boolean | null> | null`；
  - `api/types.ts:191` → `parsed_dialogue?: InterviewReviewParsePreviewItem[]`（复用已有接口）；
  - `api/job.ts:43` → `ats: ATSProfile`（复用已有类型）；
  - `api/job.ts:45` → `all_cards: ExperienceCard[]`（复用已有类型）；
  - `api/job.ts:57` → 新增 `CardGapItem`（对齐后端 `app/agents/gap_polish_agent.py` `CardGapItem` + fuse 覆盖字段）；
  - `api/job.ts:58` → 新增 `GlobalSuggestion`（对齐后端 `GlobalSuggestion`：`missing_ability`/`priority`/`action`/`steps`）；
  - 在 `types.ts` 或 `JobCraftContext.tsx` 顶部添加 JSDoc 注释说明双层架构及职责。
- **Non-goals**：不删除 mapper；不改 `types/jobcraft.ts`；不引入 tRPC/OpenAPI 代码生成（P2）。
- **Dependencies**：无（独立提交）。
- **Tests**：`cd frontend-jobcraft && npm run build && npm run lint`（vite + tsc --noEmit）。
- **Verify（2026-09-02 已核对）**：`step2-gap-polish` 返回 `{ per_card, global_suggestions, overall_score, match_level, score_weights }`；`per_card` 元素 = `CardGapItem`{card_id, score, local_score, llm_score, matched[], missing[], action, rewrite_suggestion?, supplement_suggestion?, supplement_steps[], dimension_analysis[], transferable_skills[], domain_overlap, quantified_note}；`global_suggestions` 元素 = `GlobalSuggestion`{missing_ability, priority, action, steps[]}（见 `app/agents/gap_polish_agent.py:25-62`、`app/tools/jobcraft_analyze.py:243-256`）。step1 的 `ats` 为 `ATSProfile`、`all_cards` 为 `ExperienceCard[]`（`app/api/job_analysis.py:69,88-93`）。
- **Expected Commit**：`refactor(frontend): tighten api layer any types, document type architecture`

### TASK-FETCH-001 fetch 出口审计（✅ 已核验，仅需文档固化）

- **Goal**：确认 `api/client.ts` 为唯一 fetch 出口。
- **Why**：Baseline 审计项。
- **Current State（2026-09-02 校准）**：✅ 已确认。扫描 `frontend-jobcraft/src/**`：fetch 仅出现在 `api/client.ts:53`（JSON）与 `:71`（FormData）；组件层无任何直接 fetch/axios/XHR/WebSocket。auth token 通过 `setAuthToken()`/`getAuthToken()` 集中管理，注入 `Authorization: Bearer` header。
- **Remaining Work**：`api/job.ts` 的 4 处 `any` 收紧纳入 TASK-TYPE-001 一并完成；本 task 仅需在 `api/client.ts` 顶部添加 JSDoc 注释标注为唯一 fetch 出口 + auth 注入点。
- **Scope（简化）**：添加 JSDoc 注释。
- **Expected Commit**：随 TASK-TYPE-001 合并提交（`docs(api): document client.ts as single fetch source`）或独立 commit。
- **Status（2026-09-02）**：实质性完成，待文档固化。

### TASK-REAL-DATA-001 首页（WorkbenchView）接真实数据

- **Goal**：`WorkbenchView.tsx` 从硬编码改为读取后端 dashboard 数据。
- **Why**：Baseline §11.1。`WorkbenchView.tsx:30-102` 硬编码计数/步骤/评分/公司名。
- **Current State**：首页显示假数据（12/3/5/2、字节跳动/腾讯、82/76/68）——硬编码计数、公司名、匹配度、最近活动均与真实 `jobs` 无关；`jobs` 已由 `loadDashboard`→`submissionToJob` 加载但被忽略。
- **Scope**：
  - 移除 `:30-33` hardcoded 计数（`deliveredCount=12` 等），改用 `jobs.length` 与 `jobs.filter(status)` 派生真实计数；
  - 移除 `:38-67` `getJobSteps()` 硬编码步骤映射，改用 `job.steps`（真实，来自 dashboard）；
  - 移除 `:70-102` `getStatusBadge()`/`getNextStepText()`/`getJobMatchScore()`/`getRoleName()`/`getCompanyName()` 硬编码查找，改用 `job.company`/`job.role`/`job.status`/`job.currentStage`；
  - 匹配度：真实 `job.matchScore`（当前 mapper 恒为 0）无 dashboard 数据来源，显示 `—` 或隐藏，不造假数；
  - 移除「下一步行动/最近活动」区块的硬编码「字节跳动/腾讯」字串，改为基于真实 jobs 或空态占位；
  - 补充空状态：无数据时显示引导文案而非假数据。
- **Files**：`src/components/workbench/WorkbenchView.tsx`、`src/context/JobCraftContext.tsx`。
- **Tests**：`cd frontend-jobcraft && npm run build && npm run lint`。
- **Expected Commit**：`feat(frontend): drive workbench from real dashboard data`
- **Status（2026-09-04）**：✅ 已完成（commit `3c03cde`，与 Expected Commit 完全一致）。实际代码已全部满足 scope，无遗留 hardcode：
  - 计数（已投递/面试中/待处理/已完成/本周新增/activeCount）全部由 `jobs.filter(status)` 派生（WorkbenchView.tsx:31-53），无 `12/3/5/2`
  - `getJobSteps()` 用真实 `job.steps`（:65-85）；`getStatusBadge`/`getNextStepText`/company/role 均读 `job` 字段（:87-104）
  - 匹配度：`job.matchScore > 0 ? ...% : '—'`，mapper 无数据时显示 `—` 不造假数（:288）
  - 「下一步行动/最近活动」由真实 jobs 派生（:106-146），无「字节跳动/腾讯」硬编码
  - 空态：正在推进/下一步/最近活动均有引导文案（:268-281、385-389、431-435）
  - AI 建议 data-driven，不虚构计数（:148-153）
  - `Job` 类型已含 `steps`/`matchScore`/`applyDate`/`lastUpdated`/`currentStage`（jobcraft.ts:372-377）

### TASK-REAL-DATA-004 JD 报告详情页去 FALLBACK_DATA

- **Goal**：`JDReportDetailView.tsx` 移除 `:29-99` 写死的字节跳动模板，改为真实 `jdAnalyses` 数据 + 空态占位。
- **Why**：Baseline §11.1。`:221-246` 用 `jdAnalyses` 真实字段（company/position/date/matchScore），但 `:29-99` `FALLBACK_DATA` 用于 goals/competencies/atsGroups/subtextSections/recommended。
- **Current State（2026-09-02 校准）**：`JDAnalysis` 已含真实字段（`whyMatch`/`resumeAdvice`/`coreRequirements`/`atsKeywords`/`recommendedExperiences`），但 mapper（`analysisToJD`）部分字段未填充——`subtextAnalysis=[]`、`skillGaps` 的 `userEvidence`/`requirement`/`recommendation` 为空占位；因此细节区块即使接真数据也会渲染成空态。
- **Scope**：
  - 核心字段（company/position/score/date/verdict/职责/ATS关键词/推荐经历）改用 `currentAnalysis` 真实字段；
  - 隐含要求解析、能力匹配佐证区块：后端未填时显示「待分析」占位，不显示假数据；
  - 视需要扩展 `analysisToJD` mapper 补填字段（关联后端 `gap_items`/`gap_analysis`/`subtext`），属可选增强；
  - 删除整个 `FALLBACK_DATA` 常量。
- **Files**：`src/components/jd/JDReportDetailView.tsx`、`src/context/JobCraftContext.tsx`。
- **Tests**：`cd frontend-jobcraft && npm run build && npm run lint`。
- **Expected Commit**：`feat(frontend): remove fallback mock data from JD report detail`
- **Status（2026-09-04）**：✅ 已完成（commit `8870c26`，与 Expected Commit 完全一致）。`FALLBACK_DATA` 常量已删除，`src` 内无残留。各区块均接 `currentAnalysis` 真实数据 + 空态占位：
  - 核心职责 → `coreRequirements`；能力匹配 → `skillGaps`；ATS → `atsKeywords`（hardSkills/softSkills/expKeywords）；推荐经历 → `recommendedExperiences`；隐含要求 → `subtextAnalysis`；评分/结论 → `matchScore`/`whyMatch`/`verdictSummary`/`keyRisks`/`resumeAdvice`
  - 无数据区块显示「待分析/带动引导文案」占位，不渲染伪造报告；无分析时整页空态引导去「JD 分析」（JDReportDetailView.tsx:159-180）
  - 验证：`tsc --noEmit` 通过（本会话复核）

### TASK-REAL-DATA-002 MockInterview 去 Mock（后端 endpoint 已就绪，前端未接线）

- **Goal**：模拟面试由真实后端 mock-chat 驱动，去掉 `Math.random` 假评分。
- **Why**：Baseline §11.1。`MockInterviewModal.tsx:42-99` 硬编码题目/假评分/假录音。
- **Current State**：
  - 后端 `POST /api/jobcraft/interview-review/mock-chat`（`interview_review.py:361-404`）已实现：`MockChatPayload`（messages/company/position/round_type/experience_context）→ `{ reply: str, role: "interviewer" }`，使用 `openai.OpenAI` + `LLM_model` env。
  - 前端 `MockInterviewModal.tsx` **零 API 调用**：`:42-55` `mockQuestions` hardcoded 数组；`:65` `setTimeout` fake delay；`:68-72` `Math.random()` 评分；`:96-105` `handleToggleRecording()` 用 `setTimeout` 模拟录音。
  - `src/api/interview.ts` 无 `mockChat()` 函数。
- **Scope**：
  - `src/api/interview.ts` 新增 `mockChat(payload)` 调用后端 `/interview-review/mock-chat`；
  - `MockInterviewModal` 改为多轮对话模式：用户输入 → POST mock-chat → 展示 LLM 面试官回复 → 循环；
  - 对话结束后调用 `interviewApi.createInterviewReview()` 获取真实 AI 评分，替换 `Math.floor(78+Math.random()*12)` 假分数；
  - 移除 `:42-55` `mockQuestions`、`:65` fake delay、`:68-72` `Math.random()`。
- **Dependencies**：TASK-TYPE-001、TASK-INTERVIEW-001（面试持久化）。
- **Files**：`src/components/interview/MockInterviewModal.tsx`、`src/api/interview.ts`。
- **Tests**：`cd frontend-jobcraft && npm run build && npm run lint`。
- **Expected Commit**：`feat(frontend): real mock interview via backend mock-chat endpoint`
- **Status（2026-09-04）**：✅ 已完成（commit `59ab3f0`）。实际代码已全部满足 scope，无遗留 mock：
  - `api/interview.ts` 已有 `mockChat()`（`/interview-review/mock-chat` POST）
  - `MockInterviewModal` 已是真实多轮对话：打开→`mockChat([])` 开场、`handleSend`→`mockChat(messages)` 循环、`handleComplete`→`createInterviewReview` 生成真实复盘
  - 无 `Math.random` 假评分、无 `setTimeout` 假延迟、无 hardcoded `mockQuestions`、无假录音
  - 验证：`tsc --noEmit` 通过（本会话复核）

### TASK-REAL-DATA-003 复盘/新增向导/面试准备去 Mock 评分

- **Goal**：复盘、新增向导、面试准备的假评分/占位改为后端真实分析。
- **Why**：Baseline §11.1。
- **Current State（2026-09-03 校准）**：`createReviewFromTranscript` 已改为 create+analyze 串联并用真实 `InterviewReviewResult` 填充缓存（`buildReviewPatchFromAnalysis`），删除 `Math.random`；`NewReviewModal` 改调 `createReviewFromTranscript`，删除 `setTimeout` 假延迟与 hardcoded 数据；`addInterviewReview` 移除伪造默认值；`createInterview` 已由 TASK-INTERVIEW-001 接通真实 `/interview-prep`。
- **Completed**：
  - `buildReviewPatchFromAnalysis(analysis, qaCount)`：真实映射 overall_score/summary/strengths/weaknesses/questions→qaList；
  - `createReviewFromTranscript`：删除 `Math.floor` 假分 + 硬编码 competencies/aiDiagnosis，复用 `addInterviewReview` 落库；
  - `NewReviewModal`：删除 hardcoded overallScore=88/highlights/drawbacks/qaBreakdown 与 1000ms fake delay；
  - 面试准备：经核查无硬编码（`generateInterviewPrep`→`buildInterviewFromPrep`）。
- **Status（2026-09-03）**：✅ 完成 `5eb2810`

### TASK-DOCFIX-001 修正文档与代码 MISMATCH

- **Goal**：消除可立即修正的文档漂移。
- **Why**：Baseline §10/§15。`AGENTS.md` 强制 Ant Design（实际 Tailwind）、`pyproject` v0.6.0（实际 v0.14）、缺失的 v2 文档引用。
- **Scope**：更新 `AGENTS.md`（UI 规范改为 Tailwind 事实）、校正版本号、删除孤儿引用或补建缺失文档。
- **Expected Commit**：`docs: align AGENTS.md and version with actual code`

### TASK-INTERVIEW-001 面试记录后端持久化

- **Goal**：面试记录（interviews）从后端加载/保存，不再仅存内存。
- **Why**：`JobCraftContext.tsx` 的 `interviews` state 永不从后端加载——`createInterview()` 创建的记录全部在内存，刷新即丢失。后端 `GET /api/jobcraft/interview-review`（`interview.ts:54`）已实现但从未被 `loadInterviews()` 调用。
- **Current State**：`interviews` 数组由 `createInterview()` 手动构建（context `:953-1077`）；后端有 `listInterviewRecords`（`db_interview.py`）但无 `loadInterviews()` 函数。`InterviewPrepCenterView` 的 `companyResearch`/`aiStrategy`/`highFreqQuestions`（context `:978-1033`）全部 hardcoded。
- **Scope**：
  - `JobCraftContext.tsx` 新增 `loadInterviews()` 调用 `interviewApi.listInterviewRecords()`；
  - `loadUserProfileAndData()` 中集成调用；
  - `createInterview()` 改为先调用后端 `POST /api/jobcraft/interview-review`（`interview.ts:61`）创建记录，再用返回的 `record_id` 更新本地 state；
  - 删除 context 中 hardcoded 的 `companyResearch`/`aiStrategy`/`highFreqQuestions`（`$:978-1033`），改为从 `interviewApi.getJobInterviewPrep` 返回数据填充。
- **Dependencies**：TASK-TYPE-001（类型对齐）。
- **Files**：`src/context/JobCraftContext.tsx`、`src/api/interview.ts`、`src/components/interview/InterviewPrepCenterView.tsx`。
- **Tests**：`cd frontend-jobcraft && npm run build && npm run lint`。
- **Expected Commit**：`feat(frontend): load interviews from backend, remove in-memory-only state`
- **Status（2026-09-04）**：✅ 完成。实际 scope 校准：`loadInterviews`/`buildInterviewFromPrep`/前端 `companyResearch` 等已接后端真实数据（roadmap 原「全部 hardcoded」描述过时）。真正缺口是**后端生成落库后未把 `id` 返回前端**，导致前端 `createInterview` 用假 ID `-Date.now()`，刷新后与 `loadInterviews` 加载的真实 `prep-{id}` 重复。
  - 后端 `InterviewPrepResult` schema 加 `id: Optional[int]`；`_generate_prep` 捕获 `insert_interview_prep()` 返回的 `record_id` 写入 `result.id`
  - 前端 `api/types.ts` `InterviewPrepResult` 加 `id?: number`；`createInterview` 用 `result.id` 生成 `newId`（`prep-{id}`）并填充 `prepSource.id`，与加载路径 ID 格式一致，消除重复
  - 验证：`tsc --noEmit` + `npm run build` 通过；后端 `uv run pytest tests/ -q` 340 passed/11 skipped；`ruff check` 绿

### TASK-TASK-SYS-001 接线前端任务系统

- **Goal**：前端接入后端异步任务轮询（`/api/jobcraft/tasks/*`），为长 AI 调用提供进度反馈。
- **Why**：后端 `server.py` 已定义 4 个 task 路由（`/tasks/submit`、`/tasks/{task_id}`、`/tasks/{task_id}/cancel`、`/tasks`），前端完全未调用（无 `api/tasks.ts`），AI 调用无进度指示。
- **Current State**：后端 4 个 task endpoint 已定义但无 consumer worker（`tasks/handlers.py:78` 错误 import `interview_flow`）；前端零引用。
- **Scope**：新建 `src/api/tasks.ts`；在 AI workflow 调用（JD 分析/面试准备/复盘分析）启动时提交 task 并轮询进度，UI 显示加载状态。
- **Dependencies**：TASK-TYPE-001、TASK-FIX-001（修 task handler import）。
- **Files**：`src/api/tasks.ts`（新建）、`src/context/JobCraftContext.tsx`、`app/api/server.py`。
- **Tests**：`cd frontend-jobcraft && npm run build && npm run lint`。
- **Expected Commit**：`feat(frontend): wire task system for AI operation progress feedback`

### TASK-CLEANUP-WIP-001 清理未提交 WIP

- **Goal**：归档/删除与 roadmap 无关的未提交 WIP 文件，避免干扰后续提交。
- **Why**：`git status --short` 显示 18+ 个未提交修改文件、7 个已删除 docs、12 个 untracked 文件，其中多数与当前 roadmap 无关。
- **Current State（2026-09-03 校准）**：工作区已干净（working tree clean）。
- **Completed**：
  - 7 个旧 docs（`ACCEPTANCE_CRITERIA`/`EXECUTION_PLAN`/`EXECUTION_SUMMARY`/`PROJECT_MINDMAP`/`PROJECT_REVIEW`/`REFACTORING_COMPLETE`/`REFACTORING_PLAN`）内容已在 `docs/archive/`，`git rm` 记录归档 → `794047b`；
  - **真实 WIP 保留并提交（非删除）**：后端 `mock-chat` 端点、`server.py` `text()` 修复、`db_*` 配置集中到 `db_config.py` → `4b64ca3`；docker 部署（compose/Dockerfile×2/nginx）与前端 `.env.example`/`.gitignore` → `f69f25c`；
  - `frontend-jobcraft-backup/`（191MB，含 node_modules）、`docker/dump*.sql`/`full*.sql`（~7MB）、`frontend-jobcraft/PROMPT.md`+`metadata.json` → 已从磁盘删除；
  - 11 个仅行尾噪音文件（`app/__init__.py` 等）→ `git restore`，无内容变更；
  - `app/tools/db_config.py` → **保留**（`db_*` 现依赖其 `_jc_config`，非死代码）。
- **Non-goals**：不修改业务逻辑。
- **Expected Commit**：`chore: clean up untracked WIP artifacts` → 已拆分完成（`794047b`/`4b64ca3`/`f69f25c`）

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
- **Status**：✅ 完成（前端为主，不改后端）
  - 新增 `markdownToResume` 解析器（`src/utils/resumeParser.ts`）：镜像 `generate_resume_markdown` 格式，`# 姓名`/联系方式行/键值行 → personalInfo/jobTitle/company/updatedAt；`## 核心能力` → summary；`## 工作经历` 内 `### A·B·C` 卡片条目 → item，`### 成就标题`+`**标签**：` STAR 行 → bullet。确定性规则、容忍怪异输入。
  - 新增 `resumeToMarkdown` 反序列化器：将编辑后的 `ResumeVersion` 序列化回 markdown（每个 bullet 用 `###` 子标题 + 原文行还原，与解析器互为逆运算，round-trip 验证 item/bullet 分组与内容一致），复用于持久化。
  - `loadDashboard` 对每个 `has_resume` 投递站 `getSubmission()` 解析 `resume_markdown` → 填充 `resumes`（key=submission id）；`submissionToJob.resumeId` 对齐为 `String(sub.id)`。
  - Context 新增 `activeResumeId`/`setActiveResumeId`；6 个编辑动作（apply/reject/applyAll suggestion、update/add/delete bullet）由硬编码 `'res-byte-1'` 改为读写 `activeResumeId`；新增 `saveResume(id)` = `resumeToMarkdown` → `PATCH /submission/{id}`（复用现有字段，无后端改动）。
  - `ResumeEditorView` 按 `resumeId ?? job.resumeId ?? 首个简历` 解析当前简历并 `setActiveResumeId`；「保存草稿」接入 `saveResume`；修正中文标识符 `allBullets紧`→`allBullets`、`isEditing迁移`→`isEditing`；无简历时友好空态。
  - `JobWorkspaceView` 不再写死 `'res-byte-1'`。
  - 验证：round-trip 脚本确认解析↔序列化一致；`tsc --noEmit` + `npm run build` 通过；后端 `uv run pytest tests/ -q` 340 passed/11 skipped 回归通过。

### TASK-STATUS-001 引入 Submission 状态机

- **Goal**：统一 `resume_submission.status` 为英文枚举，前后端共享。
- **Why**：Baseline §11.2 + Domain v2 §4。当前 `"已投递"` 等中文字符串散落（`db_submission.py:98`、`submission.py:26,191`）。
- **Current State**：状态为中文字符串、无枚举/流转约束。
- **Scope**：定义 `SUBMISSION_STATUS` 枚举；后端校验流转（APPLIED/INVITED/ROUND_1/ROUND_2/OFFER/CLOSED）；前端显示映射中文。
- **Dependencies**：TASK-AUTH-001、TASK-TYPE-001。
- **Expected Commit**：`feat(submission): introduce status enum and transitions`
- **Status**：✅ 完成。后端 `d3254a8`、前端 `1a16001`
  - 新增 `app/schemas/submission_status.py`（枚举 + 中文映射 + 合法流转 §4.2 + 存量中文字符串读时归一化，前向兼容）
  - `db_submission` 建表默认/insert/update 用枚举码；get/list 读取归一化
  - submission API 创建校验状态合法性、更新校验流转（非法 400）；manual 默认 APPLIED
  - 前端 `SubmissionStatus` 类型 + `SUBMISSION_STATUS_CN` 映射 + `submissionToJob.statusMap` 对齐新枚举
  - 单测 `test_submission_status_unit.py` 9 用例；验证 `uv run pytest tests/ -q` 340 passed/11 skipped；`ruff` 绿；`npm run build` + `tsc --noEmit` 通过

### TASK-FIX-001 修复 AI 后台任务系统

- **Goal**：修复 `tasks/handlers.py:78` 导入不存在的 `interview_flow`。
- **Why**：Baseline R7。`handlers.py:78` 引用 `app.workflows.interview_flow`（应为 `interview_prep_flow`）。
- **Current State**：任务系统无消费 worker + 错误 import。
- **Scope**：修 import；评估是否启用 Redis 消费循环或下线该路径。
- **Expected Commit**：`fix(tasks): correct workflow import and enable worker`
- **Status**：✅ 完成（决策：**启用** Redis 异步消费循环，非下线）。`d3dee83`
  - 修 import 并对齐真实签名（`job_analysis_id` 必填校验 + 透传 submission_id/company_research/resume_markdown/previous_review_summary）
  - `worker.py` 新增 `_dispatch_one` + `run_worker` 消费循环 + `python -m app.tasks.worker` 入口
  - 4 个 `/tasks/*` 端点对 Redis 不可用降级 503；新增 `redis>=5.0.0` 依赖；单测 `test_tasks_handlers_unit.py` 5 用例
  - 验证：`uv run pytest tests/ -q` 330 passed/11 skipped；`ruff check` 绿

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

# 9. 优先实施清单

| 顺序 | Task | 优先级 | 依赖 | 用户价值 | 状态 |
|---|---|---|---|---|---|
| 1 | TASK-AUTH-001 强制认证 | P0 | — | 安全 | ✅ 完成 `6a0f121` |
| 2 | TASK-OWN-001 所有权过滤 | P0 | AUTH | 安全 | ✅ 完成 `09aa805` |
| 3 | TASK-INJ-001 注入收敛 | P0 | — | 安全 | ✅ 完成 `b681f2c` |
| 4 | TASK-AUTH-002 移除默认凭据 | P0 | AUTH | 安全 | ✅ 完成 `8878459` |
| 5 | TASK-TYPE-001 any 收紧 + 文档 | P0 | — | 契约清晰 | ✅ 完成 `4e0d14e` |
| 6 | TASK-FETCH-001 fetch 审计 | P0 | TYPE | 安全合规 | ✅ 完成 `4e0d14e`（随 TYPE 合并提交） |
| 7 | TASK-REAL-DATA-001 Workbench 真实数据 | P0 | TYPE | 产品可信 | ✅ 完成 `3c03cde` |
| 12 | TASK-REAL-DATA-004 JD 报告去 FALLBACK | P0 | TYPE | 产品可信 | ✅ 完成 `8870c26` |
| 8 | TASK-REAL-DATA-002 MockInterview 去 Mock | P0 | INTERVIEW | 产品可信 | ✅ 完成 `59ab3f0` |
| 9 | TASK-REAL-DATA-003 复盘/向导去 Mock | P0 | INTERVIEW | 产品可信 | ✅ 完成 `5eb2810` |
| 10 | TASK-INTERVIEW-001 面试持久化 | P0 | TYPE | 数据不丢失 | ✅ 完成（列表/详情 + createInterview 真实生成 + 工作台 UI 板块重组）|
| 11 | TASK-CLEANUP-WIP-001 清理 WIP | P1 | — | 仓库整洁 | ✅ 完成 `794047b`/`4b64ca3`/`f69f25c` |

> 安全基线（Phase 0）4 个 task 全部完成（commit `6a0f121`→`8878459`→`09aa805`→`b681f2c`）。
> Phase 1 核心发现（2026-09-02 校准）：两层类型系统是有意设计（非漂移），真正问题是 api 层 7 处 any + 接口未接线（interviews/task system）。

---

# 10. 明确 Non-goals（不做）

- ❌ 重写整个后端 / PostgreSQL 迁移（Domain v2 §96：MVP 不切换）。
- ❌ 全面 API /v1 版本化 + OpenAPI→TS 代码生成（P2+，非当前阻塞）。
- ❌ 大规模 Clean Architecture 重写（无 Application Service 层暂缓）。
- ❌ 覆盖"关于 Resume 的独立表/多版本"等 Domain v2 远期目标（P2 阶段再推进）。

---

# 11. 退出标准（Phase 1 完成 = 新 UI 真实数据驱动）

> 校准后版本（2026-09-02）

```
[ ] 所有业务端点已强制认证 + 所有权过滤（P0 安全基线完成）✅
[ ] api 层无 any 泄漏（7 处收紧）—— TASK-TYPE-001
[ ] 双层类型架构有明确 JSDoc 注释 —— TASK-TYPE-001
[ ] fetch 出口有文档标注 —— TASK-FETCH-001
[x] WorkbenchView 从硬编码改为后端数据驱动（真实 jobs 计数/步骤/状态）—— TASK-REAL-DATA-001 ✅ `3c03cde`
[x] JDReportDetailView 移除 FALLBACK_DATA，真实字段 + 空态占位 —— TASK-REAL-DATA-004 ✅ `8870c26`
[ ] MockInterview 接通 /mock-chat 端点，移除 Math.random 假评分 —— TASK-REAL-DATA-002
[x] InterviewPrepCenterView 从后端加载面试准备数据 —— TASK-REAL-DATA-003
[x] 复盘/新增向导（NewReviewModal）用后端 analyze 返回结果 —— TASK-REAL-DATA-003
[ ] 面试记录从后端持久化（刷新不丢失）—— TASK-INTERVIEW-001
[ ] 核心路径全部后端数据驱动（经历卡→JD分析→投递→面试准备→复盘）
[ ] 测试通过：uv run ruff check . && uv run pytest tests/ -q && cd frontend-jobcraft && npm run build && npm run lint
```

---

# 12. 文档依赖与后续

本 Roadmap 落地后同步推进：
- `docs/frontend-backend-contract-audit-v1.md` 更新（Auth/契约变化）
- `docs/domain-model-v2.md` 继续作为目标（DB/AI 演进对齐）
- `docs/engineering-development-workflow-v1.md` 为每一 Task 的标准流程
- TODO.md / PROGRESS.md 逐 Task 更新并记录 commit_id

> **本 Roadmap 为只读/规划产出，未修改任何业务代码、数据库、配置与依赖。**
