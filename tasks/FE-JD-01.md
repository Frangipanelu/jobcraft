# FE-JD-01 — JD 分析域数据层迁移 + 只读视图（context 镜像过渡）

## Title

新建 `features/jd` 查询与删除层（`useJdAnalysesQuery` / `useDeleteJdAnalysisMutation`），迁移 `JDAnalysisCenterView` / `JDReportDetailView` 的 jdAnalyses 读路径与删除；`JobCraftContext.jdAnalyses` 降级为**过渡期镜像**，由 query 层与 legacy writers（`loadJdAnalyses` / `createJDAnalysis` / `createStructuredJDAnalysis` / `deleteJDAnalysis`）双向同步，直至 FE-CONTEXT-REMOVE 删除。

## Context

- `JobCraftContext.jdAnalyses: JDAnalysis[]`（Line 489）被 **5 组件 + context 内部逻辑**消费：
  - JDAnalysisCenterView（历史研判列表 + 搜索 + 删除 + 创建入口）、JDReportDetailView（按 id 取报告）——本 task 迁移读/删；
  - JobWorkspaceView（Line 54 `currentJD` 派生）、MainLayout（`selectedJDId` 选页）、NewInterviewModal（`createJDAnalysis`）——镜像 / legacy 保留。
- 现状读路径：登录期 `loadJdAnalyses(userId)` → `listJobAnalyses(userId)` → **逐条** `getJobAnalysis(id)`（N+1）→ 内联映射为富 `JDAnalysis`（skillGaps / atsKeywords / subtextAnalysis / jobGoals）→ `setJdAnalyses`（Line 685–760）。
- 现状写路径：
  - `createJDAnalysis`（Line 1072）：**同步返回**本地 id（`jd-<ts>`）→ 必要时自动创建 Job（跨域写 `jobs`）→ `tasksApi.runTaskOrSync('resume_generate', …)` 异步 → `analysisToJD` 前置插入 + 回写 job.steps + toast；
  - `createStructuredJDAnalysis`（Line 1170）：同构（`jd_analyze_structured`），内联构建 JDAnalysis；
  - `deleteJDAnalysis`（Line 1298）：仅本地过滤 + 当 id 匹配 `sub-(\d+)` 时 `deleteSubmission`；**后端无 JD 分析删除端点**。
- **两套 JDAnalysis 构造并存**：`analysisToJD`（JobAnalysisResult）与 load 内联富映射 —— 迁移时收敛为 mappers 单源。
- FE-JOBS-01 / FE-EXPERIENCES-01 已确立范式：`useXxxQuery` + mutations（cache 更新 `onSuccess`/`onMutate`）、`onSync` 注入镜像、`renderWithProviders` 测试。
- 迁移不变式：过渡期「cache = 权威、context jdAnalyses = 只读镜像」，FE-CONTEXT-REMOVE 拆除。

## Current State

```
登录 loadJdAnalyses(userId) → listJobAnalyses → N× getJobAnalysis → 内联富映射 → setJdAnalyses（唯一源）
  ├── JDAnalysisCenterView（历史列表 + 搜索 + deleteJDAnalysis + createStructuredJDAnalysis → navigateTo('jd_report')）
  ├── JDReportDetailView（jdAnalyses.find(id) || [0]，依赖 context isLoading）
  ├── JobWorkspaceView（currentJD 派生，读镜像）
  ├── NewInterviewModal（createJDAnalysis）
  └── MainLayout（selectedJDId → 渲染 JDReportDetailView）
createJDAnalysis / createStructuredJDAnalysis：跨域建 Job + runTaskOrSync 异步 + 同步返回 id
analysisToJD 定义于 JobCraftContext.tsx（私有）；load 内联映射与之独立
```

## Goal

- `src/features/jd/{mappers,hooks}.ts`：映射函数（`analysisToJD` 移出 + load 内联映射提取为 `analysisDetailToJD`）+ 查询/删除 hooks。
- `JDAnalysisCenterView` / `JDReportDetailView` 的 jdAnalyses 读路径与删除切 hooks（UI 零变化）；创建仍调 context legacy。
- context 增 `syncJdAnalyses` 镜像写入；`loadJdAnalyses` / `createJDAnalysis` / `createStructuredJDAnalysis` / `deleteJDAnalysis` 单点双向双写 query cache；`analysisToJD` 改由 `features/jd/mappers.ts` 提供。

## Design Decision

- **JD1 权威与镜像**：react-query cache 为迁移后视图读源；`context.jdAnalyses` 保留给未迁移消费者（JobWorkspaceView / NewInterviewModal / MainLayout）作只读镜像：
  - `useDeleteJdAnalysisMutation` 更新 cache 后 `onSync` → context `syncJdAnalyses`；
  - legacy writers 在 `setJdAnalyses` 后写 cache。
  - 偏差窗口接受（未迁移视图在无动作期间显示），FE-CONTEXT-REMOVE 拆除。
- **JD2 hooks 纯净**：`features/jd/hooks.ts` 不 import context；`onSync` 由消费组件注入 `useJobCraft().syncJdAnalyses`。
- **JD3 查询保持 N+1 语义**：queryFn = `authApi.getCurrentUser()` → `listJobAnalyses(user.id)` → `Promise.all(summaries.map(getJobAnalysis))` → 富映射（与 legacy 逐条拉取一致，行为零变化）。
- **JD4 映射单源**：`analysisToJD`（用于 create 回填）移入 `mappers.ts`；load 内联富映射提取为 `analysisDetailToJD(detail)`（skillGaps / atsKeywords / subtextAnalysis 逻辑原样搬移）；context 引用，杜绝双份漂移。
- **JD5 delete 语义原样**：后端无分析删除端点 —— `useDeleteJdAnalysisMutation` 仅 cache 过滤 + `sub-(\d+)` → `deleteSubmission`（失败忽略），toast 归视图层（legacy context 的 info toast 由视图保留一次）。
- **JD6 create 保持 legacy（非目标）**：`createJDAnalysis` / `createStructuredJDAnalysis` 跨域写 `jobs` + `runTaskOrSync` 异步 + 同步返回本地 id 供 `navigateTo` —— 迁 hooks 需拆分 jobs 域与任务编排，风险与粒度超本 task；仅补 cache 双写。
- **JD7 回滚**：改动收敛于 features/jd + 2 组件 + context 注入；`git revert` 单 commit 回滚数据层与双写。

## Scope

- 新增 `frontend-jobcraft/src/features/jd/mappers.ts`（`analysisToJD` / `analysisDetailToJD` / `JD_ANALYSES_QUERY_KEY`）。
- 新增 `frontend-jobcraft/src/features/jd/hooks.ts`（`useJdAnalysesQuery` / `useDeleteJdAnalysisMutation`）。
- 修改 `JobCraftContext.tsx`：接口 + provider 增 `syncJdAnalyses`；`loadJdAnalyses` / create×2 / delete 双写 cache；`analysisToJD` 改 import；load 内联映射改调 `analysisDetailToJD`。
- 迁移 `JDAnalysisCenterView`（历史列表读 query + 删除走 mutation；创建仍 legacy）、`JDReportDetailView`（读 query，`isLoading` 改用 query 的 loading）。
- 测试：`src/features/jd/mappers.test.ts` + `src/test/jd-query.test.tsx`。

## Non-goals

- 不迁移 `createJDAnalysis` / `createStructuredJDAnalysis`（跨域 + 异步任务，JD6；后续独立 task）。
- 不迁移 `NewInterviewModal` 的 `createJDAnalysis` 调用（legacy 保留）。
- 不迁移 `JobWorkspaceView` 的 `currentJD` 派生读（读镜像）。
- 不迁移 `/jd_analysis`、`/jd_report` 路由与 `selectedJDId`（FE-ROUTE 系列）。
- 不引入后端 JD 分析删除端点 / 不改 `jobApi` 契约。
- 不删除 context `jdAnalyses` / create / delete（FE-CONTEXT-REMOVE）。
- 无后端 / DB / API 契约改动。

## Affected Files

- 新增：`frontend-jobcraft/src/features/jd/mappers.ts`、`hooks.ts`
- 新增：`frontend-jobcraft/src/features/jd/mappers.test.ts`、`frontend-jobcraft/src/test/jd-query.test.tsx`
- 修改：`frontend-jobcraft/src/context/JobCraftContext.tsx`（syncJdAnalyses + 双写 + 映射复用）
- 修改：`frontend-jobcraft/src/components/jd/JDAnalysisCenterView.tsx`、`src/components/jd/JDReportDetailView.tsx`

## API Impact

无（仅复用 `jobApi.listJobAnalyses` / `getJobAnalysis` / `deleteSubmission`）。

## Database Impact

无。

## AI Impact

无（`jobs`/`jd` 分析仍由 legacy `runTaskOrSync` 触发，本 task 不触碰任务编排）。

## Acceptance Criteria

- `JDAnalysisCenterView` / `JDReportDetailView` 不再从 context 读取 `jdAnalyses` 或调用 `deleteJDAnalysis`（grep 证实；`createStructuredJDAnalysis` / `navigateTo` / `showToast` 保留）。
- context `jdAnalyses` 与 query cache 双写一致：登录加载、创建（legacy）、删除后，未迁移视图（JobWorkspaceView / NewInterviewModal）与新迁移视图看到同一集合。
- `analysisToJD` 仅存于 `features/jd/mappers.ts`（context grep 无重复定义）；load 富映射逻辑仅在 `analysisDetailToJD`。
- `npm run lint` / `npm run build` / `npm test` 全绿；新增测试覆盖：映射（含 skillGaps/atsKeywords 提取）、query 渲染历史列表 + 搜索、delete 过滤 + 后端 `deleteSubmission` + 镜像。
- 手工 E2E：登录 → JD 分析中心历史列表来自 API；删除报告即时消失且刷新后不再出现；JD 报告详情页按 id 正确渲染。

## Test Plan

- `mappers.test.ts`：`analysisToJD`（match_score→recommendationStars、ats_profile→salary/coreRequirements/atsKeywords、created_at 兜底）；`analysisDetailToJD`（dimension_requirements→skillGaps 匹配/待补充、responsibilities→coreRequirements、keywords→expKeywords）。
- `jd-query.test.tsx`（renderWithProviders + `vi.mock('../api/job')` + mock auth getCurrentUser）：
  - `useJdAnalysesQuery` 渲染 JDAnalysisCenterView 历史列表（公司/岗位/计数/搜索过滤）；
  - delete：cache 过滤 + 镜像同步（`sub-N` id 断言 `deleteSubmission` 调用）；
  - JDReportDetailView 按 analysisId 从 query 渲染（公司 · 岗位）。
- 回归：既有 12 文件 / 40 测试保持绿。

## Documentation

- 完成后更新 `PROGRESS.md` / `TODO.md`（commit_id）；新增 `src/features/jd/README.md` 记录 hooks 契约、镜像过渡规则、create 仍 legacy 的边界。

## Expected Commit

`feat(jd): add jd analyses query layer and migrate jd views (FE-JD-01)`

## Implementation Result（2026-09-17，commit `3d777f7`）

**交付**

- `src/features/jd/mappers.ts`：`JD_ANALYSES_QUERY_KEY`、`analysisToJD`（自 context 移出）、`analysisDetailToJD`（自 `loadJdAnalyses` 内联映射提取）。
- `src/features/jd/hooks.ts`：`useJdAnalysesQuery`、`useDeleteJdAnalysisMutation`（`onSync` 可选注入）。
- `JobCraftContext.tsx`：接口/provider 增 `syncJdAnalyses`；`loadJdAnalyses` 改调 `analysisDetailToJD` 并双写 cache；create×2 / delete 单点双写 cache；删除本地 `analysisToJD` 定义改 import。
- 视图：`JDAnalysisCenterView`（列表/搜索/计数读 query，删除 mutation + 视图层 toast）、`JDReportDetailView`（按 id 读 query，`isLoading` 取 query）。
- 文档：`src/features/jd/README.md`；`features/jd-analysis/README.md` 改为指向 `features/jd`。
- 测试：`features/jd/mappers.test.ts`（4）+ `src/test/jd-query.test.tsx`（4）。

**验证结果**

- `npm test`：**14 文件 / 48 测试全绿**（原 12/40 + 新增 8）。
- `npm run lint`（tsc --noEmit）✓、`npm run build` ✓。
- grep 证实：两视图无 context `jdAnalyses` / `deleteJDAnalysis` 读取；`analysisToJD` 仅存在于 mappers。

**设计偏差（3 项）**

1. `analysisDetailToJD` 新增 `salaryRange: ''`：legacy 内联映射未设 `salaryRange`（靠 `as JDAnalysis[]` 断言绕过类型），运行时为 `undefined`。为满足类型单源，显式设 `''`；`JDAnalysisCenterView` 以 `{analysis.salaryRange && …}` 守卫渲染，故 UI 无变化。
2. `analysisToJD` 移出时删除了 legacy 中未被使用的 `companyCtx`（`result.company_context || {}`）死变量，无行为影响。
3. delete 的 info toast 由 context 迁至 `JDAnalysisCenterView` 视图层（`useDeleteJdAnalysisMutation` 不内置 toast），保持原提示一次、不重复。

**范围确认**：create 编排（`createJDAnalysis` / `createStructuredJDAnalysis`）与 `NewInterviewModal` / `JobWorkspaceView` / `MainLayout` 未迁移，按 spec Non-goals 保持 legacy / 镜像读。

**未推送**：commit `3d777f7` 留在本地 main。
