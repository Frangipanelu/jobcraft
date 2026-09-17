# FE-ROUTE-02 — 工作台 / 岗位列表 / 岗位空间真实路由迁移

## Title

将 `/workbench`、`/jobs`（岗位列表）、`/jobs/:jobId`（岗位空间）从 `LegacyPageWrapper + MainLayout` 迁入 `AppShell` 壳的真实路由，页面间跳转改为 react-router `useNavigate`；`currentTab` 由新钩子 `useSyncRouteTab` 保持同步（面包屑/侧边栏高亮/selectedJobId 与新路由一致）。`jd_report` / `prep` / `review` / `experiences` 等仍走 LegacyPageWrapper（后续任务）。

## Context

- 现状：`AppRouter` 中 `/workbench`、`/jobs/:jobId` 均经 `LegacyPageWrapper`（URL→context `navigateTo`）渲染 `MainLayout` 的 switch 视图；`/jobs` 列表无真实路由（仅 legacy tab 可达）。
- FE-ROUTE-01 已确立「AppShell 壳 + `useNavigate` + `renderWithProviders(route)` 路由测试」范式；FE-JOBS-01 已让 `WorkbenchView`/`JobsListView`/`NewJobModal` 读 react-query cache（job 数据与导航解耦）。
- 迁移对象中仍保留的 context 读取：`job jobs/interviews/jdAnalyses`（镜像/未迁移域）、`selectedJobId/jobWorkspaceSubTab`（过渡兜底）、`navigateTo`（仅 legacy 目标继续使用）。

## Goal

1. 路由表迁移：`/workbench`、`/jobs`、`/jobs/:jobId` 改走 `<AppShell/>`（真实路由，不经 LegacyPageWrapper）。
2. `AppShell` 通过 `<Outlet context>` 下发 modal openers（`onOpenNewJob` / `onOpenMockInterview` / `onOpenNewInterview`），页面用 `useOutletContext` 消费。
3. 新增 `useSyncRouteTab(tab)` 钩子（提取自 LegacyPageWrapper 的 URL→context 同步 effect），LegacyPageWrapper 与三个新页面共用。
4. 页面内导航切换 react-router：WorkbenchView / JobsListView / NewJobModal / JobWorkspaceView / TopHeader 面包屑 / Sidebar 的 jobs 域导航。
5. 路由测试升级；`npm test` / lint / build 全绿。

## Design Decision

- **RD1 页面壳**：三个真实路由均 `<Route element={<AppShell/>}><Route index element={Page}/></Route>`（与 `/profile` 同构）。`AppShell` 暴露 `AppShellOutletContext` 类型 + `useAppShellOutlet` 钩子。
- **RD2 路由态同步**：`useSyncRouteTab(tab)` 在页面 mount 时调 `navigateTo(tab, params)`，使 sidebar 高亮、面包屑、`selectedJobId` 跟 URL 一致；LegacyPageWrapper 复用同钩子，行为零变化。
- **RD3 导航收敛**：已真实路由的目标一律 `useNavigate`：
  - WorkbenchView：`jobs→/jobs`，`job_workspace→/jobs/{id}`；prep/jd/review/experiences 仍 legacy。
  - JobsListView：`job_workspace→/jobs/{id}`。
  - NewJobModal：创建后 `→/jobs/{id}?tab=jd`（subTab 改 query 传参）。
  - JobWorkspaceView：返回 `→/jobs`，复盘 `→/review/{interviewId}`，准备 `→/prep/{interviewId}`；`jobId` 由路由 prop 注入，`selectedJobId` 兜底；`?tab=` 初值 + jobId 变化重置 `jd`。
  - TopHeader 面包屑 / Sidebar：workbench、jobs 两项改 router。
  - 不动的 legacy 调用方：`ResumeEditorView.tsx:79`（其主场景在 MainLayout 内，嵌入式 workspace 内误触无副作用）。
- **RD4 保留边界**：`/jobs/:jobId/jd/:jdId`、`/prep/:interviewId`、`/review/:interviewId`、`/experiences*` 仍走 LegacyPageWrapper（FE-ROUTE 后续任务）。`currentTab` 由使用新路由同步钩子维护；真实路由内点击遗留侧边栏项切换 currentTab→MainLayout 视图但 URL 不变，为过渡期接受行为（与 FE-ROUTE-01 一致）。
- **RD5 回滚**：改动收敛于 router + AppShell + 3 views + 2 布局 + 新增 3 页面 + 1 钩子；`git revert` 单 commit 可整体回退。

## Scope

- 新增：`src/features/jobs/pages/{WorkbenchPage,JobsPage,JobWorkspacePage}.tsx`；`src/router/useSyncRouteTab.ts`
- 修改：`src/router/AppRouter.tsx`、`src/router/LegacyPageWrapper.tsx`（复用钩子）、`src/app/AppShell.tsx`（Outlet context）、`src/components/{workbench/WorkbenchView,jobs/JobsListView,jobs/NewJobModal,jobs/JobWorkspaceView,layout/TopHeader,layout/Sidebar}.tsx`
- 测试：`src/test/router.test.tsx`（三个新路由 + /profile 保留）；新增 `src/test/jobs-route.test.tsx`（工作台进入岗位 → 岗位空间渲染）

## Non-goals

- 不迁移 `ResourceView`、`JDReportDetailView` 独立页、`ResumeEditorView` 独立页、prep/review/experiences 路由（后续任务）。
- 不删 context `jobs/interviews/jdAnalyses/selectedJobId/jobWorkspaceSubTab` 及 `navigateTo`（FE-CONTEXT-REMOVE）。
- 不做 jobs 域「context 镜像 → query」的进一步收敛（FE-JOBS-02）。
- 无后端 / DB / API 契约改动。

## Affected Files

- 新增：`src/features/jobs/pages/WorkbenchPage.tsx`、`JobsPage.tsx`、`JobWorkspacePage.tsx`、`src/router/useSyncRouteTab.ts`
- 新增：`src/test/jobs-route.test.tsx`
- 修改：`src/router/AppRouter.tsx`、`src/router/LegacyPageWrapper.tsx`、`src/app/AppShell.tsx`、`src/components/workbench/WorkbenchView.tsx`、`src/components/jobs/JobsListView.tsx`、`src/components/jobs/NewJobModal.tsx`、`src/components/jobs/JobWorkspaceView.tsx`、`src/components/layout/TopHeader.tsx`、`src/components/layout/Sidebar.tsx`、`src/test/router.test.tsx`

## API Impact

无。

## Database Impact

无。

## Acceptance Criteria

- `/workbench`：AppShell 壳 + WorkbenchView 直接渲染（不经 MainLayout）；「进入岗位」跳 `/jobs/:id`
- `/jobs`：AppShell 壳 + JobsListView；点岗位跳 `/jobs/:id`
- `/jobs/:jobId`：AppShell 壳 + JobWorkspaceView；`?tab=jd|resume|interview` 作为子 tab 初值；jobId 变化重置 jd
- Sidebar/TopHeader 的面包屑与高亮与真实路由一致（`useSyncRouteTab`）
- `npm run lint` / `npm test` / `npm run build` 全绿
- 与既有 E2E 无冲突（见 FE-ROUTE-01 验证记录）

## Documentation

- 完成后更新 `PROGRESS.md`（commit_id）、`TODO.md`；新增/更新域 README 与 spec 的实现结果小节。

## Expected Commit

`feat(router): migrate workbench, jobs list and job workspace to real routes (FE-ROUTE-02)`

## Implementation Result（2026-09-17，commit `1b49e8c`）

- [x] 路由表：`/workbench`、`/jobs`、`/jobs/:jobId` → `<AppShell/>` + 域页面（WorkbenchPage/JobsPage/JobWorkspacePage），移除对应 LegacyPageWrapper；`jd_report`/`prep`/`review`/`experiences` 保持 legacy
- [x] `useSyncRouteTab(tab)` 钩子提取（URL→context `navigateTo`），LegacyPageWrapper 复用（行为零变化），三个新页面 mount 时同步 sidebar 高亮/面包屑/selectedJobId
- [x] `AppShell` 增加 `<Outlet context>`：`AppShellOutletContext`（onOpenNewJob / onOpenMockInterview / onOpenNewInterview）+ `useAppShellOutlet`；MockInterview/NewInterview modal openers 补齐（此前仅存在于 MainLayout）
- [x] 导航收敛：WorkbenchView（jobs/job_workspace→router，6 处）、JobsListView（1 处）、NewJobModal（创建后 `→/jobs/{id}?tab=jd`）、JobWorkspaceView（返回/复盘/准备→router，jobId prop + `?tab=` 初值 + jobId 变化重置 jd）、TopHeader 面包屑（workbench/jobs/job_workspace 3 处）、Sidebar（workbench/jobs 2 项）
- [x] **偏差 1**：JobsListView 的行动按钮文案为「进入岗位空间」（非「进入岗位」），测试按实际文案断言
- [x] **偏差 2**：岗位空间渲染后 TopHeader 面包屑与页面标题均含「公司 · 角色」，测试用 `getAllByText` 断言（≥1 处，即面包屑同步生效）
- [x] **偏差 3（基础设施）**：PowerShell `Set-Content -Encoding utf8` 重写测试文件导致 UTF-8 损坏（esbuild 解析失败），改为 Write 工具重写后恢复
- [x] 未改动的 legacy 调用方：`ResumeEditorView.tsx:79` 返回岗位工作台（主场景在 MainLayout 内；嵌入式 workspace 内误触仅改 currentTab 无视觉副作用）
- [x] 验证：`npm run lint`（tsc）✓；`npm test` **10 文件 / 32 测试全绿**（router.test 升级 5 + jobs-route.test 新增 2）✓；`npm run build` ✓
- [x] 文档：PROGRESS.md 记录 commit；TODO.md 勾选