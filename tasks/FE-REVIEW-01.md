# FE-REVIEW-01 — 面试复盘域写入迁移 + 复盘/新建复盘视图数据层（context 镜像过渡）

## Title

新建 `features/review` 写入层（`useCreateInterviewReviewMutation` / `useApplyReviewFeedbackMutation`），迁移 `InterviewReviewCenterView` / `InterviewReviewDetailView` / `CreateReview` 的读路径与 `createReviewFromTranscript` / `applyReviewFeedback` 写路径；`JobCraftContext` 删除 review 域 5 个 writer（`createReviewFromTranscript` / `applyReviewFeedback` / `addInterviewReview` / `syncReviewToExperience` / `commitExperienceDiff`），映射函数移入 `features/review/mappers.ts` 单源。复盘为 `Interview.review` 内嵌字段，**读源复用 `useInterviewsQuery`**，不新建独立 reviews cache key。

## Context

- 复盘对象挂在 `Interview.review`（`types/jobcraft.ts:341` 内嵌），后端 `listInterviewReviews` 等 API 无前端消费者；复盘数据全部由创建/解析写路径在内存构建。因此 review 域**没有自己的读数据源**，读 = `useInterviewsQuery()` → 过滤 `!!i.review`。
- `JobCraftContext` review 域 5 个 writer 现状：
  - `createReviewFromTranscript`（L1193）：`interviews.find` → `interviewApi.createInterviewReview` → `tasksApi.runTaskOrSync('interview_review_analyze', …, fallback analyzeInterviewReview, 180s)` → `buildReviewPatchFromAnalysis` 或 base patch → `addInterviewReview`。仅被 `CreateReview`（L191）调用。
  - `applyReviewFeedback`（L1403）：读入手 feedback 的 proposed changes → `setExperiences` 应用变更 + 版本记录 → `setInterviews` 标记 applied + 写 INTERVIEWS cache（L1472）→ `setActivities`。仅被 `InterviewReviewDetailView`（L52）调用。
  - `addInterviewReview`（L1246）：内部函数，构建完整 `InterviewReview` 并 `setInterviews` + 双写 INTERVIEWS cache（L1280）+ 跨域写 JOBS cache（reviewStage/prepStage done）。
  - `syncReviewToExperience`（L1304）：零组件消费者（仅 README 提及）——死代码。
  - `commitExperienceDiff`（L1328）：零组件消费者——死代码（grep 证实）。
- **漂移 bug**：`applyReviewFeedback` / `syncReviewToExperience` / `commitExperienceDiff` 用裸 `setExperiences`，**不写 EXPERIENCES cache**（与 `createExperience` 等双写实现不一致），已在迁移视图（`useExperiencesQuery` 为读源）下失效。FE-REVIEW-01 迁移后统一写 cache + `onSyncExperiences` 修复。
- `activities` 无组件消费者（grep 仅类型定义）→ 迁移后 hooks 不写活动日志。
- `InterviewPrepWorkspaceView` 已无复盘叠加引用（grep 证实），FE-INTERVIEW-01 遗留的「workspace 复盘叠加写路径」不存在。
- 既有镜像能力已就绪：`syncInterviews`（FE-INTERVIEW-01）、`syncJobs`（FE-JOBS-01）、`syncExperiences`（FE-EXPERIENCES-01）、`useJobsQuery` / `useExperiencesQuery` 均已存在。
- 不变式：cache = 权威，context = 镜像；hooks 不 import context。

## Current State

```
登录 loadInterviews → listInterviewPreps → prepRecordToInterview → setInterviews（双写 INTERVIEWS cache）
  ├── InterviewReviewCenterView（读 context.interviews，过滤 review 有无，navigateTo）
  ├── InterviewReviewDetailView（读 context.interviews，applyReviewFeedback → setExperiences/setInterviews 双写）
  └── CreateReview（读 context.jobs + context.interviews，createReviewFromTranscript → navigateTo detail）
buildReviewPatchFromAnalysis / addInterviewReview 定义于 JobCraftContext.tsx（私有）
applyReviewFeedback / commitExperienceDiff / syncReviewToExperience 裸 setExperiences（不写 EXPERIENCES cache）
```

## Goal

- `src/features/review/{mappers,hooks}.ts`：7 个映射 helper 移出 + 2 个写 mutation。
- `InterviewReviewCenterView` / `InterviewReviewDetailView` / `CreateReview` 读写切 hooks（UI 结构不变）；读统一走 `useInterviewsQuery` / `useJobsQuery`。
- context 删除 review 域 5 个 writer（含死代码 2 个）；收敛导入（`tasksApi`、`InterviewReviewResult` 变孤儿即删；`interviewApi` 因 `loadInterviews` 保留）。
- 跨域：create 写 INTERVIEWS + JOBS 两 cache（same as `addInterviewReview` legacy）；apply feedback 写 EXPERIENCES + INTERVIEWS 两 cache（修复漂移）。

## Design Decision

- **REV1 权威与镜像**：reviews 内嵌 `Interview.review`，读源 = `useInterviewsQuery`（INTERVIEWS cache 权威、context.interviews 镜像，FE-INTERVIEW-01 已建立）；**不新建 `useReviewsQuery` / review 独立 cache key**，避免与 INTERVIEWS cache 双源漂移。
- **REV2 hooks 纯净**：`features/review/hooks.ts` 不 import context；`onSync`（interviews）/ `onSyncJobs` / `onSyncExperiences` 由消费组件注入。
- **REV3 create 与 legacy 等价**：`useCreateInterviewReviewMutation` 保持「INTERVIEWS cache 解析 interview（缺则抛错，视图 toast）→ `createInterviewReview` → `runTaskOrSync('interview_review_analyze', … fallback analyzeInterviewReview, 180s)` → patch（分析成功用 `reviewPatchFromAnalysis`，失败用 base patch，**不留 console.error**——AGENTS 红线）→ `buildReviewFromPatch` 构建完整 `InterviewReview` → INTERVIEWS cache（review + status completed）→ 跨域 JOBS cache（steps.reviewStage/'prepStage' done）」语义；`mutateAsync` 返回 `{ interviewId, review }` 供导航。`createInterviewReview` 硬失败向上抛（视图 toast + 停留）。
- **REV4 await 后跳转**：`CreateReview` 沿用 FE-JD-02 模式 —— `await mutateAsync` resolve 后 `navigateTo('interview_review_detail', { interviewId })`；失败 `setIsAnalyzing(false)` + error toast 停留（legacy 失败跳 center 的行为改为停留，更诚实）。
- **REV5 apply feedback 双写 + 修复漂移**：`useApplyReviewFeedbackMutation` 的 `onSuccess` 更新 EXPERIENCES cache（`applyProposedChanges` / suggestions 兜底 / `buildVersionRecord`）+ `onSyncExperiences`；更新 INTERVIEWS cache（feedback.applied = true）+ `onSync`。**不复写 activities（零消费者）**。
- **REV6 映射单源**：`buildReviewPatchFromAnalysis`（L42–115）、`addInterviewReview` 的 review 构建逻辑、`applyReviewFeedback` / `commitExperienceDiff` / `syncReviewToExperience` 的经历版本递增 / 变更应用 / 版本记录逻辑统一提取为 mappers 纯函数：
  - `buildReviewPatchFromAnalysis(analysis, qaCount): Partial<InterviewReview>`
  - `buildReviewFromPatch(interview, patch?): InterviewReview`
  - `nextExperienceVersion(exp): { version: string; newAction: string }`（V 递增 0.1 + `[实战高光沉淀]` 前缀，来自 syncReviewToExperience）
  - `applyProposedChanges(exp, changes): Experience`（responsibility / actions / background 字段法，来自 applyReviewFeedback + commitExperienceDiff）
  - `applyFeedbackSuggestions(exp, suggestions): Experience`（来自 applyReviewFeedback 兜底）
  - `buildVersionRecord(version, changes, reason, source): ExperienceVersionRecord`
  context 删除本地实现；死 writer 一并删除。
- **REV7 死 writer 清理（收窄）**：`syncReviewToExperience` / `commitExperienceDiff` 零消费者，且逻辑并入 mappers helpers → 本 task 一并从 context 移除（grep + tsc 可证），避免遗留「裸 setExperiences 不写 cache」的漂移地雷；比留给 FE-CONTEXT-REMOVE 更小风险。
- **REV8 回滚**：改动收敛于 features/review + 3 视图 + context 少量删除；`git revert` 单 commit 回滚。

## Scope

- 新增 `frontend-jobcraft/src/features/review/mappers.ts`（REV6 的 6 个纯函数 + `REVIEW` 相关常量若需要）。
- 新增 `frontend-jobcraft/src/features/review/hooks.ts`（`useCreateInterviewReviewMutation` / `useApplyReviewFeedbackMutation` + options 类型）。
- 修改 `JobCraftContext.tsx`：接口 + provider 删除 `createReviewFromTranscript` / `applyReviewFeedback` / `addInterviewReview` / `syncReviewToExperience` / `commitExperienceDiff` 及其实现；收敛导入（`tasksApi` / `InterviewReviewResult` 孤儿删除；`interviewApi` 保留）；删除 `buildReviewPatchFromAnalysis` 与 review 构建本地实现。
- 迁移 `InterviewReviewCenterView`、`InterviewReviewDetailView`、`CreateReview`（读 + 写切 hooks，UI 结构不变）。
- `src/features/review/README.md` 从「未迁移」改写为已迁移契约。
- 测试：`src/features/review/mappers.test.ts` + `src/test/review-query.test.tsx`。

## Non-goals

- 不新建 `useReviewsQuery` / 独立 reviews cache key（REV1）。
- 不迁移 `updateQuestionAnswer` / `addCustomQuestion` / `nextActions` / `activities`（无消费者，FE-CONTEXT-REMOVE 清理）。
- 不迁移 `loadInterviews` / 其他复盘读源外的 context 读写（镜像保留，FE-CONTEXT-REMOVE 拆除）。
- 不实现后端端点 / 不改 `interviewApi` / `tasksApi` 契约。
- 不涉及 `CreateInterview` / `MockInterviewModal` 等面试域视图。
- 无后端 / DB / API 契约改动。

## Affected Files

- 新增：`frontend-jobcraft/src/features/review/mappers.ts`、`hooks.ts`
- 新增：`frontend-jobcraft/src/features/review/mappers.test.ts`、`frontend-jobcraft/src/test/review-query.test.tsx`
- 修改：`frontend-jobcraft/src/context/JobCraftContext.tsx`（删 5 writer + 导入收敛）
- 修改：`frontend-jobcraft/src/components/review/InterviewReviewCenterView.tsx`、`InterviewReviewDetailView.tsx`、`src/pages/CreateReview.tsx`
- 修改：`frontend-jobcraft/src/features/review/README.md`

## API Impact

无（仅复用 `authApi.getCurrentUser` / `interviewApi.createInterviewReview` / `analyzeInterviewReview` / `tasksApi.runTaskOrSync`）。

## Database Impact

无。

## AI Impact

无（复盘分析沿用 `runTaskOrSync('interview_review_analyze')`：任务服务 ⇒ 异步任务，不可用 ⇒ 同步降级 `analyzeInterviewReview`，单节点单次 LLM 调用由后端任务保证）。

## Acceptance Criteria

- 三个视图不再从 context 读取 `interviews` / `jobs` / `createReviewFromTranscript` / `applyReviewFeedback`（grep 证实；`useJobCraft()` 仅保留 `syncInterviews` / `syncJobs` / `syncExperiences` / `navigateTo` / `setJdAnalysisReturnTarget` / `showToast` 等）。
- context 删除 5 个 review writer（grep `createReviewFromTranscript|applyReviewFeedback|addInterviewReview|syncReviewToExperience|commitExperienceDiff` 在 context 下 0 命中）；`buildReviewPatchFromAnalysis` 仅存于 `features/review/mappers.ts`。
- 写路径双写一致：create 后 INTERVIEWS cache（review + status completed）与 JOBS cache（steps done）+ 两镜像；apply 后 EXPERIENCES cache（新版本 + 变更）与 INTERVIEWS cache（applied）+ 两镜像；刷新持久一致（复盘为内存构建，刷新后按 legacy 语义消失——与 FE-JD-02 一致的 legacy 数据模型瑕疵，不在本 task 修）。
- `npm run lint`（tsc）/ `npm run build` / `npm test` 全绿；新增测试覆盖：映射、center/detail/create 渲染、create（任务降级 + 双 cache + 双镜像 + 分析失败兜底）、apply feedback（双 cache + 修漂移断言）。
- 手工 E2E：新建复盘 → 粘贴速记 → 生成报告 → 详情可见 → 沉淀至经历库 → 详情「已同步」+ 经历库版本升级。

## Test Plan

- `mappers.test.ts`：
  - `buildReviewPatchFromAnalysis`（真实 score 派生四维/competencies、qaList 映射、空 questions → 无 competencies）；
  - `buildReviewFromPatch`（字段兜底：overallScore 0 / totalQACount 派生 / id `rev-` 前缀 / reviewDate 今日）；
  - `nextExperienceVersion`（V1.0→V1.1、`[实战高光沉淀]` 前缀）；`applyProposedChanges`（responsibility / actions / background 字段法、其余字段忽略）；`applyFeedbackSuggestions`（suggestions[0] → actions 前置）；`buildVersionRecord`（date/source/changes）。
- `review-query.test.tsx`（renderWithProviders + `vi.mock` auth/interview/tasks/jobs/experiences）：
  - Center/Detail 渲染：seed INTERVIEWS cache → 含/不含 review 过滤 + 搜索 + 镜像计数 + 空态；
  - create：`createInterviewReview` → runTaskOrSync fallback `analyzeInterviewReview` → INTERVIEWS cache 置 review + status completed + JOBS cache steps done + `onSync`/`onSyncJobs` 断言；`mutateAsync` 返回 interviewId；
  - create 分析失败：任务抛错 → 容忍落 base patch（overallScore = qa_count×10），不回滚；
  - create 缺面试：reject（不触 API）；
  - applyFeedback：EXPERIENCES cache 应用 proposedChanges + version 记录 + `onSyncExperiences` 断言 + INTERVIEWS cache applied + `onSync`（**断言接口收到 cache 而非裸 setState**——修复漂移）。
- 回归：既有 17 文件 / 81 测试保持绿。

## Documentation

- 完成后更新 `PROGRESS.md`（commit_id）；`TODO.md` 勾选 FE-REVIEW-01。
- `src/features/review/README.md`：hooks 契约、读源复用 useInterviewsQuery 规则、双写规则、镜像过渡（FE-CONTEXT-REMOVE 前置）。
- 更新 `src/features/interview/README.md` 中「复盘 writers 待迁移」的相关措辞。

## Expected Commit

`feat(review): add review write mutations and migrate review views (FE-REVIEW-01)`

## Implementation Result

### 2026-09-19 已实现（commit `a1d1d8a`）

- **`features/review/mappers.ts`**：6 个纯 helper 落地（`buildReviewPatchFromAnalysis` / `buildReviewFromPatch` / `nextExperienceVersion` / `applyProposedChanges` / `applyFeedbackSuggestions` / `buildVersionRecord`），语义与 legacy 逐字对齐（score 一律真实派生；`[实战高光沉淀]` / `[面试复盘升级]` 前缀；`rev-`+Date.now id）。
- **`features/review/hooks.ts`**：
  - `useCreateInterviewReviewMutation`：cache 解析面试（缺抛「未找到对应的面试记录，请返回重试」）→ `createInterviewReview` → `runTaskOrSync('interview_review_analyze', fallback=analyzeInterviewReview, 180s)`；**分析失败容忍**（空 catch、无 console，保留 base patch）；onSuccess 双写 INTERVIEWS（review + status completed）+ 跨域 JOBS（steps reviewStage/prepStage done）+ `onSync`/`onSyncJobs` 镜像；无 toast/activities（归视图/无消费者）。
  - `useApplyReviewFeedbackMutation`：读两 cache → finalExp（proposedChanges 字段法 / suggestions 兜底 + currentVersion + versionHistory 前置 buildVersionRecord，source `interview_review`）→ 返回 `{experienceId, finalExp}`；onSuccess 双写 EXPERIENCES（**修复 legacy 裸 setExperiences 不写 cache 的漂移 bug**）+ INTERVIEWS（feedback.applied）+ `onSync`/`onSyncExperiences`；不写 activities。
- **视图迁移**：
  - `InterviewReviewCenterView`：读 `useInterviewsQuery`（镜像只读视图逻辑不变）。
  - `InterviewReviewDetailView`：`useApplyReviewFeedbackMutation({ onSync: syncInterviews, onSyncExperiences: syncExperiences })` + await 后成功 toast / catch 失败 toast + 按钮 pending 禁用。
  - `CreateReview`：`useJobsQuery` + `useInterviewsQuery` + `useCreateInterviewReviewMutation({ onSync: syncInterviews, onSyncJobs: syncJobs })`；await 成功后 `navigateTo('interview_review_detail', { interviewId })`；失败 `setIsAnalyzing(false)` + error toast 停留（同 REV4）。
- **context 清理**：删除 5 个 writer（接口 + 实现 + provider value）与 `buildReviewPatchFromAnalysis`；导入收敛（去 `tasksApi` / `InterviewReviewResult` / `InterviewReview` / `InterviewQA`；保留 `interviewApi` 供 loadInterviews）。
- **测试**：`mappers.test.ts` 11 条 + `review-query.test.tsx` 6 条（create 双写双镜像 / 分析失败容忍 / 缺面试 reject / apply 缓存+镜像 + 漂移修复断言 / suggestions 兜底 / Center 读路径过滤）；全量 **19 文件 / 98 测试全绿**；`npm run lint`（tsc）/ `npm run build` / `python scripts/check_encoding.py` 通过。
- **文档**：`features/review/README.md` 新增；`features/interview/README.md` / `features/experiences/README.md` 数据流图更新（复盘写入已迁 review hooks）。
- **推拉**：commit `a1d1d8a` + push origin/main。

- 待填