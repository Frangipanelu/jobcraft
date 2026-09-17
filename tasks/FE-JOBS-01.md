# FE-JOBS-01 — Job 域数据层迁移 + 纯 Job 视图（context 镜像过渡）

## Title

新建 `features/jobs` 查询与变更层（`useJobsQuery` / `useCreateJobMutation` / `useTerminateJobMutation` / `useResumeJobMutation`），迁移 `JobsListView` / `NewJobModal` / `WorkbenchView` 的 jobs 读写；`JobCraftContext.jobs` 降级为**过渡期镜像**，由 hooks mutations 与 legacy writers 双向同步，直至 FE-CONTEXT-REMOVE 删除。

## Context

- `JobCraftContext.jobs: Job[]`（Line 548）被 **7+ 组件 + context 内部逻辑**消费：WorkbenchView（统计/列表）、JobsListView（列表 CRUD）、NewJobModal（创建）、JobWorkspaceView（currentJob）、JDReportDetailView、NewInterviewModal（创建+选择）、CreateInterview/CreateReview（选择）+ context 内 `createJDAnalysis`/面试创建通过 `jobs.find` 找/建岗位。全量迁移超单 commit 粒度 → 本 task 采用「镜像过渡」。
- 现状读写路径：登录期 `loadDashboard` → `jobApi.getDashboard(userId)` → `submissionToJob` → `setJobs`；创建走 `createJob`（本地乐观 Job → `createSubmission` 回填 id，失败仅本地）；`terminateJob/resumeJob/deleteJob` 为纯本地状态变更（delete 无消费者）。
- FE-QUERY-01（`368cfdb`）/ FE-ROUTE-01（`f0b8151`, `3ad1a13`）已确立范式：`useXxxQuery` + `useXxxMutation`（`setQueryData` 乐观更新），组件由 hook 消费，`renderWithProviders` 测试。
- 迁移不变式（AGENTS §1.3 / workflow §11）：server state 单一真相源原则在过渡期由「cache = 权威、context jobs = 只读镜像」承担；镜像在 FE-CONTEXT-REMOVE 一并删除。

## Current State

```
登录 loadDashboard → getDashboard → submissionToJob → setJobs (context)
  ├── WorkbenchView（统计/下一步/近期动态）
  ├── JobsListView（列表 + terminateJob/resumeJob）
  ├── NewJobModal（createJob → navigateTo job_workspace）
  ├── JobWorkspaceView / JDReportDetailView / NewInterviewModal / Create*（只读 currentJob/选择）
  └── context 内部（createJDAnalysis / 面试创建 find 或 createJob）
submissionToJob / deriveJobStatus 定义于 JobCraftContext.tsx（私有函数）
```

## Goal

- `src/features/jobs/{mappers,hooks}.ts`：映射函数（自 context 移出复用）+ 查询/变更 hooks。
- `JobsListView` / `NewJobModal` / `WorkbenchView` 的 jobs 读写切换至 hooks。
- context 增 `syncJobs` 镜像写入；`loadDashboard` / `createJob` 单点双向同步 query cache；`submissionToJob`/`deriveJobStatus` 改由 `features/jobs/mappers.ts` 提供（context 引用，杜绝双份映射漂移）。

## Design Decision

- **JD1 权威与镜像**：react-query cache 是迁移后视图的唯一读源；`context.jobs` 保留给未迁移消费者（JobWorkspaceView/JD/Interview 系/Create*）作**只读镜像**，由两侧写入方同步：
  - hooks mutations 成功/乐观更新后调 `onSync(nextJobs)` → context `syncJobs`；
  - legacy writers（`loadDashboard`、`createJob`）在 `setJobs` 后同步写 query cache。
  - 镜像偏差窗口接受（仅影响未迁移视图在无动作期间的显示），FE-CONTEXT-REMOVE 拆除。
- **JD2 hooks 纯净**：`features/jobs/hooks.ts` 不 import context；`onSync` 由消费组件注入 `useJobCraft().syncJobs`。
- **JD3 userId 获取**：queryFn = `authApi.getCurrentUser()` → `user.id` → `getDashboard(userId)`（与 legacy `loadDashboard(userId)` 对齐；后端同时支持 token 推导，取 id 保证一致）。
- **JD4 映射单源**：`submissionToJob`/`deriveJobStatus` 移入 `mappers.ts`（导出 + 单测），context 改为 import；行为零变化。
- **JD5 与 legacy create 行为等价**：`useCreateJobMutation` 保持「本地乐观 Job → createSubmission 回填 id/backendId → 前置插入」与「后端失败仅本地（fire-and-forget）」语义；`mutateAsync` 返回最终 Job 供 navigateTo。
- **JD6 回滚**：改动收敛于 features/jobs + 3 组件 + context 少量注入；`git revert` 单 commit 回滚数据层，context 双写亦随 commit 回退（无残留破坏）。

## Scope

- 新增 `frontend-jobcraft/src/features/jobs/mappers.ts`（submissionToJob / deriveJobStatus / JOBS_QUERY_KEY）。
- 新增 `frontend-jobcraft/src/features/jobs/hooks.ts`（useJobsQuery / useCreateJobMutation / useTerminateJobMutation / useResumeJobMutation）。
- 修改 `JobCraftContext.tsx`：接口 + provider 增 `syncJobs`；`loadDashboard`/`createJob` 双写；`submissionToJob`/`deriveJobStatus` 改为 import mappers；terminate/resume/delete 标 deprecated（无消费者）。
- 迁移 `JobsListView`、`NewJobModal`、`WorkbenchView` 到 hooks（UI 结构不变）。
- 测试：`src/features/jobs/mappers.test.ts` + `src/test/jobs-query.test.tsx`。

## Non-goals

- 不迁移 `JobWorkspaceView` / `JDReportDetailView` / `NewInterviewModal` / `CreateInterview` / `CreateReview`（读镜像，后续独立 task）。
- 不迁移 `/workbench`、`/jobs/:jobId` 路由与 Sidebar 激活态（FE-ROUTE-02）。
- 不做 resume 富化迁移（`getSubmission` → ResumeVersion 属 resume 域）。
- 不删除 context `jobs/createJob/terminateJob/resumeJob/deleteJob`（FE-CONTEXT-REMOVE）。
- 无后端 / DB / API 契约改动。

## Affected Files

- 新增：`frontend-jobcraft/src/features/jobs/mappers.ts`、`hooks.ts`
- 新增：`frontend-jobcraft/src/features/jobs/mappers.test.ts`、`frontend-jobcraft/src/test/jobs-query.test.tsx`
- 修改：`frontend-jobcraft/src/context/JobCraftContext.tsx`（syncJobs + 双写 + 映射复用）
- 修改：`frontend-jobcraft/src/components/jobs/JobsListView.tsx`、`src/components/jobs/NewJobModal.tsx`、`src/components/workbench/WorkbenchView.tsx`

## API Impact

无（仅复用 `jobApi.getDashboard` / `createSubmission` / context reads）。

## Database Impact

无。

## AI Impact

无。

## Acceptance Criteria

- `JobsListView` / `NewJobModal` / `WorkbenchView` 不再从 context 读取 `jobs` / `terminateJob` / `resumeJob` / `createJob`（grep 证实；导航仍用 `navigateTo`）。
- context `jobs` 与 query cache 双写一致：登录加载、创建后，未迁移视图（JobWorkspaceView 等）与新迁移视图（JobsListView 等）看到同一集合。
- `submissionToJob` / `deriveJobStatus` 仅存于 `features/jobs/mappers.ts`（context grep 无重复定义）。
- `npm run lint` / `npm run build` / `npm test` 全绿；新增测试覆盖：映射、query 渲染、create 前置+镜像同步、terminate/resume 乐观更新、workbench 统计。
- 手工 E2E：登录 → 工作台统计来自 API；添加岗位 → 岗位空间可见新岗位（镜像）；列表「标记已结束/恢复处理」即时生效；刷新后持久一致。

## Test Plan

- `mappers.test.ts`：submissionToJob（各 status → steps/currentStage、job_analysis_id→jdAnalysisId、created_at 日期截断）、deriveJobStatus 优先级（terminated>prepStage>reviewStage>jdAnalysis）。
- `jobs-query.test.tsx`（renderWithProviders + `vi.mock('../api/job')` + mock auth getCurrentUser）：
  - useJobsQuery 渲染 JobsListView：岗位数据 + 状态筛选计数；
  - create：cache 前置 + Job 出现在后随读取（镜像经真实 provider syncJobs 生效）；
  - terminate / resume：status 徽标与 steps 更新；WorkbenchView 统计来自 query。
- 回归：既有 7 文件 / 20 测试保持绿。

## Documentation

- 完成后更新 `PROGRESS.md`（commit_id）；新增 `src/features/jobs/README.md` 记录 hooks 契约与镜像过渡规则（FE-CONTEXT-REMOVE 前置）。

## Expected Commit

`feat(jobs): add jobs query layer and migrate job views (FE-JOBS-01)`