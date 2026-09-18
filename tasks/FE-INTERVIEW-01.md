# FE-INTERVIEW-01 — 面试准备域数据层迁移（读查询 + 创建 mutation，context 镜像过渡）

## Title

新建 `features/interview` 查询与变更层（`useInterviewsQuery` / `useCreateInterviewMutation`），迁移 `InterviewPrepCenterView` / `InterviewPrepWorkspaceView` 读路径与 `NewInterviewModal` / `CreateInterview` 创建路径；`JobCraftContext.interviews` 降级为**过渡期镜像**（`syncInterviews`），复盘 writers（`addInterviewReview` / `commitExperienceDiff` / `applyReviewFeedback`）双写 cache，直至 FE-CONTEXT-REMOVE 删除。

## Context

- `JobCraftContext.interviews: Interview[]` 由面试准备中心与 workspace 消费；`createInterview`（submitTask+pollTaskUntilDone 降级 generateInterviewPrep）仅被 `NewInterviewModal` / `CreateInterview` 调用。
- 复盘域与面试**共享同一 `interviews` 数组**：`Interview.review`（`types/jobcraft.ts:341`）内嵌复盘；复盘数据来自创建/解析写的内存构建，后端 `listInterviewReviews` 等 8 API 无前端消费者。
- `nextActions` 无任何消费方（仅 context 自身 state）；`updateQuestionAnswer` / `addCustomQuestion` 已无组件消费——两者均不迁移。
- 既有范式（FE-QUERY-01 / FE-JOBS-01 / FE-JD-01）：`useXxxQuery` + `useXxxMutation`（cache 乐观更新），组件由 hook 消费，`onSync` 由组件注入 context 镜像。
- 不变式：cache = 权威，context = 镜像；迁移跨域写 JOBS cache 需同步 context.jobs（`onSyncJobs`）。

## Current State

```
登录 loadInterviews → listInterviewPreps → prepRecordToInterview (context 私有) → setInterviews
  ├── InterviewPrepCenterView（列表/搜索/过滤）
  ├── InterviewPrepWorkspaceView（详情读）
  ├── NewInterviewModal / CreateInterview（createInterview → navigateTo）
createInterview：submitTask → pollTaskUntilDone → 降级 generateInterviewPrep → buildInterviewFromPrep (context 私有)
mapRoundType / roundTypeToCn / prepRecordToInterview / buildInterviewFromPrep 定义于 JobCraftContext.tsx（私有函数）
复盘 writers（addInterviewReview / 等）只写 context.interviews，cache 无感知
```

## Goal

- `src/features/interview/{mappers,hooks}.ts`：映射函数（自 context 移出复用）+ 查询/创建 hooks。
- `InterviewPrepCenterView` / `InterviewPrepWorkspaceView` / `NewInterviewModal` / `CreateInterview` 读写切 hooks。
- context 增 `syncInterviews` 镜像写入；`loadInterviews` 与复盘 writers 单点双写 query cache；`createInterview` 从 context 移除（hook 等价实现）。
- 跨域：创建的 Interview 写入 INTERVIEWS cache 后，补写 JOBS cache（`interviewIds` / `steps.prepStage`），并 `onSyncJobs` 同步 context.jobs。

## Design Decision

- **JD1 权威与镜像**：react-query cache 是迁移视图的唯一读源；`context.interviews` 保留给未迁移消费者（workspace 内复盘叠加、其他模态）作只读镜像，由 hooks 与 legacy writers 双向同步（同 FE-JOBS-01 JD1）。
- **JD2 hooks 纯净**：`features/interview/hooks.ts` 不 import context；`onSync` / `onSyncJobs` 由消费组件注入。
- **JD3 userId 获取**：queryFn = `authApi.getCurrentUser()` → `user.id` → `listInterviewPreps(userId)`（与 legacy 对齐）。
- **JD4 映射单源**：`mapRoundType` / `roundTypeToCn` / `prepRecordToInterview` / `buildInterviewFromPrep` 移入 `mappers.ts`（导出 + 单测），context 改为引用或删除；行为零变化（含 legacy `业务`→`product` 分支顺序）。
- **JD5 与 legacy create 行为等价**：`useCreateInterviewMutation` 保持「JOBS cache 解析 jdAnalysisId（无则抛错）→ runTaskOrSync → 降级 generateInterviewPrep → 构建 Interview → cache 前置插入」语义；`mutateAsync` 返回创建后 Interview（含 id）供 navigateTo。
- **JD6 toast 归视图层、nextActions 不迁移**：toast 保留在视图层；创建后不再写 `nextActions`（无消费方，死数据）。
- **JD7 复盘写透 cache**：`addInterviewReview` / `commitExperienceDiff` / `applyReviewFeedback` 改块体 updater 并在 `setInterviews` 内双写 INTERVIEWS cache（复盘字段仅内存构建，cache 与镜像需一致）。
- **JD8 回滚**：改动收敛于 features/interview + 4 视图 + context 少量注入；`git revert` 单 commit 回滚数据层，双写随 commit 回退。

## Scope

- 新增 `frontend-jobcraft/src/features/interview/mappers.ts`（INTERVIEWS_QUERY_KEY + 4 函数）。
- 新增 `frontend-jobcraft/src/features/interview/hooks.ts`（useInterviewsQuery / useCreateInterviewMutation）。
- 修改 `JobCraftContext.tsx`：接口 + provider 增 `syncInterviews`、删 `createInterview`；`loadInterviews` 双写；复盘 writers 双写；本地映射函数改引/删；清理未用导入。
- 迁移 `InterviewPrepCenterView`、`InterviewPrepWorkspaceView`、`NewInterviewModal`、`CreateInterview`（UI 结构不变）。
- 测试：`src/features/interview/mappers.test.ts` + `src/test/interview-query.test.tsx`。

## Non-goals

- 不迁移 `updateQuestionAnswer` / `addCustomQuestion`（无消费者，FE-CONTEXT-REMOVE 清理）。
- 不动 `nextActions`（无消费者，保留待清理）、不迁移复盘创建/解析 UI（读镜像）。
- 不迁移 workspace 内的复盘叠加写路径（保持 context）。
- 无后端 / DB / API 契约改动。

## Affected Files

- 新增：`frontend-jobcraft/src/features/interview/mappers.ts`、`hooks.ts`
- 新增：`frontend-jobcraft/src/features/interview/mappers.test.ts`、`frontend-jobcraft/src/test/interview-query.test.tsx`
- 修改：`frontend-jobcraft/src/context/JobCraftContext.tsx`
- 修改：`frontend-jobcraft/src/components/interview/InterviewPrepCenterView.tsx`、`InterviewPrepWorkspaceView.tsx`、`NewInterviewModal.tsx`、`src/pages/CreateInterview.tsx`

## API Impact

无（仅复用 `authApi.getCurrentUser` / `interviewApi.listInterviewPreps` / `generateInterviewPrep` / `tasksApi.runTaskOrSync`）。

## Database Impact

无。

## AI Impact

无（创建沿用 runTaskOrSync：优先异步任务，任务服务不可用时同步降级 generateInterviewPrep）。

## Acceptance Criteria

- 四个视图不再从 context 读取 `interviews` / `createInterview`（grep 证实；`useJobCraft()` 仅保留 `syncInterviews` / `syncJobs` / `navigateTo` 等）。
- context `interviews` 与 INTERVIEWS cache 双写一致：登录加载、创建后、复盘写入后，迁移与未迁移消费者看到同一集合。
- `mapRoundType` / `roundTypeToCn` / `prepRecordToInterview` / `buildInterviewFromPrep` 仅存于 `features/interview/mappers.ts`（context grep 无重复定义）。
- 创建路径跨域一致：INTERVIEWS cache 前置插入 + JOBS cache（interviewIds / prepStage）+ 两个镜像同步。
- `npm run lint`（tsc）/ `npm run build` / `npm test` 全绿；新增测试覆盖：映射、query 渲染 + 搜索、创建（任务服务降级 generateInterviewPrep + 双镜像）、jdAnalysisId 缺失抛错。
- 手工 E2E：登录 → 面试准备中心列表来自 API；创建面试 → workspace 可见 + 待备战计数 +1；复盘落盘后详情可读；刷新持久一致。

## Test Plan

- `mappers.test.ts`：mapRoundType / roundTypeToCn（含 `业务`→`product` legacy 顺序）、prepRecordToInterview（映射 + company_research/dimension_questions 兜底）、buildInterviewFromPrep（meta 覆盖 / 空兜底）。
- `interview-query.test.tsx`（renderWithProviders + `vi.mock` auth/job/interview/tasks/experience）：
  - useInterviewsQuery 渲染 InterviewPrepCenterView：列表 + 搜索过滤 + 镜像计数；
  - useCreateInterviewMutation：getDashboard seed JOBS cache → 创建（runTaskOrSync 走 fallback → generateInterviewPrep）→ cache 前置 + 双镜像 + jobs.interviewIds；
  - 缺失 jdAnalysisId：抛「尚未完成 AI 岗位分析」且不触发任务服务。
- 回归：既有 17 文件 / 72 测试保持绿。

## Documentation

- 完成后更新 `PROGRESS.md`（commit_id）。
- 新增 `src/features/interview/README.md` 记录 hooks 契约 + 复盘双写规则 + 镜像过渡（FE-CONTEXT-REMOVE 前置）。

## Expected Commit

`feat(interview): add interview query layer and migrate read/create paths (FE-INTERVIEW-01)`

## Implementation Result（2026-09-18，commit 待填）

- 待填