# FE-ROUTE-03 — 剩余 tab 路由补全 + 导航收敛到 react-router

## Title

为全部遗留 tab 建立显式 URL 路由，并把 `/experiences(/:experienceId)`、`/prep/:interviewId`、`/review/:interviewId`、`/jd-report/:jdId` 迁移为 AppShell 真实路由页；新增 `tabToPath` / `useTabNavigate` 统一 tab→URL 映射，收敛 AppShell 内所有 `navigateTo` 调用。

## Context

- FE-ROUTE-01/02 已迁移 `/profile`、`/workbench`、`/jobs`、`/jobs/:jobId` 为真实路由（AppShell + 域页面），其余 tab 仍靠 `LegacyPageWrapper` + context `currentTab` 渲染（`MainLayout.renderActiveView`）。
- **已知缺陷（本任务动机）**：真实路由页由 AppShell 固定渲染，组件内调用 legacy `navigateTo(tab)` 只会改 context `currentTab`，**URL 不变 → AppShell 重渲染同一页面 → 该跳转静默失效**。当前 `/workbench` 的「面试准备中心 / JD 分析 / 复盘中心 / 职业资产」入口（WorkbenchView）、AppShell 内挂载的 `NewInterviewModal`（创建后跳 prep workspace、跳 JD 分析）与 `MockInterviewModal`（保存复盘跳中心）均受影响。
- 详情路由 `/experiences/:experienceId`、`/prep/:interviewId`、`/review/:interviewId`、`/jobs/:jobId/jd/:jdId` 目前由 `LegacyPageWrapper` 承接，视图经 context `selectedXxxId` 取参（非 URL 参数）。
- `useSyncRouteTab(tab)`（`src/router/useSyncRouteTab.ts`）已建立 URL→context 同步（jobId/jdId/interviewId/experienceId），真实路由页与 LegacyPageWrapper 共用。
- 详情页返回/跳转按钮仍 `navigateTo`（InterviewPrepWorkspaceView 返回中心、JDReportDetailView 跳简历/经历/复盘等）；一旦详情页进入 AppShell，这些按钮必须改为真实导航，否则同样静默失效 → **要求中心 tab 也具备 URL**。
- `ExperiencesView` 已声明 `initialSelectedExpId?: string` 但**从未使用**（FE-EXPERIENCES-01 遗留）；`/experiences/:experienceId` 现无可见效果。
- 既有测试基线：14 文件 / 48 测试；`router.test.tsx` 断言 AppShell 壳 + 视图。

## Current State

```
AppRouter:
  /workbench /jobs /jobs/:jobId /profile  → AppShell + 域页面（navigate 正常）
  /jobs/:jobId/jd/:jdId /prep/:interviewId /review/:interviewId
  /experiences(/:experienceId)             → LegacyPageWrapper(tab=...)（context 取参）
  *                                        → LegacyPageWrapper（无 tab → MainLayout 默认 workbench）
其余 tab（jd_analysis_center / resume_editor / interview_prep_center / create_interview /
      interview_review_center / create_review）无 URL，仅靠 currentTab 切换
```

## Goal

- `src/router/tabPaths.ts`：`tabToPath(tab, params?)` 单一 tab→URL 映射 + `useTabNavigate()`（封装 `useNavigate`，签名对齐 legacy `navigateTo`）。
- 路由表补全：所有 tab 有 URL；详情路由迁 AppShell 页面；`*` 兜底改 `<Navigate to="/workbench" replace/>`。
- 新增页面：`ExperiencesPage`、`InterviewPrepPage`、`InterviewReviewPage`、`JdReportPage`。
- 收敛 **AppShell 可达组件**的导航：WorkbenchView、TopHeader、Sidebar、NewInterviewModal、MockInterviewModal、JDReportDetailView、ExperiencesView、InterviewPrepWorkspaceView、InterviewReviewDetailView（及 MainLayout 的 opener）。
- `ExperiencesView` 接线 `initialSelectedExpId`（`/experiences/:id` 打开对应经历编辑弹窗）。

## Design Decision

- **R1 URL 方案**（`tabToPath`）：
  | tab | URL |
  |---|---|
  | workbench | `/workbench` |
  | jobs | `/jobs` | 
  | job_workspace | `/jobs/:jobId` |
  | jd_analysis / jd_analysis_center | `/jd-analysis` |
  | jd_report | `/jd-report/:jdId`（另保留 `/jobs/:jobId/jd/:jdId` 别名） |
  | experiences | `/experiences` / `/experiences/:expId` |
  | resume_editor | `/resume` / `/resume/:jobId` |
  | interview_prep_center | `/prep` |
  | interview_prep_workspace | `/prep/:interviewId` |
  | create_interview | `/interview/new` |
  | interview_review_center | `/review` |
  | create_review | `/review/new` |
  | interview_review_detail | `/review/:interviewId` |
  | user_profile / settings | `/profile` |
- **R2 真实路由 vs 过渡路由**：详情（experiences/prep/review/jd-report）用 AppShell + 页面；尚未拆分的中心/创建/简历编辑仍用 `LegacyPageWrapper`（`MainLayout` 按 tab 渲染），但**拥有 URL**，保证 AppShell 内导航可达。
- **R3 `useTabNavigate` 语义**：与 legacy `navigateTo` 对齐（tab + params → URL），但副作用（`setSelectedXxxId` / 滚动）交由路由落地后的 `useSyncRouteTab` 承担；URL 参数是详情页唯一取参来源。
- **R4 收敛范围**：仅替换 **AppShell 内可渲染组件**的 `navigateTo`（否则静默失效）；由 `MainLayout` 渲染的 legacy 中心/创建视图内部导航**保持 `navigateTo`**（context 驱动仍有效），URL 可能滞后 → 记留白，交 FE-ROUTE-04/ FE-CONTEXT-REMOVE。
- **R5 无循环**：`useSyncRouteTab`（URL→tab）与 `useTabNavigate`（tab→URL）不同时对同一变更生效；LegacyPageWrapper 的 effect 依赖不变，legacy `navigateTo` 改 `currentTab` 不触发 URL 变化。
- **R6 `initialSelectedExpId` 接线**：`ExperiencesView` 在数据就绪后若 `initialSelectedExpId` 命中且未打开编辑，`setEditingExp(exp)`（一次性，避免重复弹窗）。
- **R7 回滚**：单 commit；路由/页面/映射集中，`git revert` 即可回退（不涉后端/DB）。

## Scope

- 新增 `src/router/tabPaths.ts`（`tabToPath` + `useTabNavigate`）。
- 修改 `src/router/AppRouter.tsx`（补全路由表 + catch-all 重定向）。
- 新增页面：`src/features/experiences/pages/ExperiencesPage.tsx`、`src/features/interview/pages/InterviewPrepPage.tsx`、`src/features/review/pages/InterviewReviewPage.tsx`、`src/features/jd/pages/JdReportPage.tsx`。
- 修改导航：`src/app/legacy/MainLayout.tsx`、`src/components/workbench/WorkbenchView.tsx`、`src/components/layout/TopHeader.tsx`、`src/components/layout/Sidebar.tsx`、`src/components/interview/NewInterviewModal.tsx`、`src/components/interview/MockInterviewModal.tsx`、`src/components/jd/JDReportDetailView.tsx`、`src/components/experiences/ExperiencesView.tsx`、`src/components/interview/InterviewPrepWorkspaceView.tsx`、`src/components/review/InterviewReviewDetailView.tsx`。
- 测试：`router.test.tsx` 增补新路由断言；新增 `src/test/routes-03.test.tsx`（tabPaths 映射 + AppShell 内跳转生效）；`legacy-pages.test.tsx` 回归。

## Non-goals

- 不迁移中心/创建/简历编辑视图为 AppShell 页面（仍 `LegacyPageWrapper`，R2）。
- 不删除 `navigateTo` / `currentTab` / `MainLayout` / `LegacyPageWrapper`（FE-CONTEXT-REMOVE）。
- 不迁移 `ResumeEditorView`、`JDAnalysisCenterView`、`InterviewPrepCenterView`、`InterviewReviewCenterView`、`CreateInterview`、`CreateReview` 的**内部** `navigateTo`（R4，URL 滞后留白）。
- 不改 `useSyncRouteTab` 参数集；不新增后端 / DB / AI。
- 不实现 `/experiences/:id` 的独立详情页（仅打开编辑弹窗，R6）。

## Affected Files

- 新增：`src/router/tabPaths.ts`、`src/features/{experiences,interview,review,jd}/pages/*.tsx`、`src/test/routes-03.test.tsx`
- 修改：`src/router/AppRouter.tsx`、`src/app/legacy/MainLayout.tsx`、`src/components/workbench/WorkbenchView.tsx`、`src/components/layout/{TopHeader,Sidebar}.tsx`、`src/components/interview/{NewInterviewModal,MockInterviewModal,InterviewPrepWorkspaceView}.tsx`、`src/components/review/InterviewReviewDetailView.tsx`、`src/components/jd/JDReportDetailView.tsx`、`src/components/experiences/ExperiencesView.tsx`、`src/test/router.test.tsx`

## API Impact

无。

## Database Impact

无。

## AI Impact

无。

## Acceptance Criteria

- 所有 `NavigationTab` 均有可解析 URL；`/jd-analysis`、`/prep`、`/review`、`/resume`、`/interview/new`、`/review/new` 可直接访问（渲染对应 legacy tab 视图，侧栏高亮正确）。
- AppShell 内导航生效：`/workbench` → 职业资产 / JD 分析 / 面试准备中心 / 复盘中心；`NewInterviewModal` 创建后进入 `/prep/:id`；`MockInterviewModal` 保存后进入 `/review`。
- 详情路由直连可用：`/experiences/:experienceId` 打开对应经历编辑弹窗；`/prep/:interviewId`、`/review/:interviewId`、`/jd-report/:jdId` 按 URL 参数渲染对应视图。
- 未迁移中心视图内部 `navigateTo` 行为不回归（context 驱动仍生效）。
- 全量 `npm test` 绿（新增用例覆盖 tab→path 与 AppShell 跳转）；`npm run lint`、`npm run build` 通过。
- 手工 E2E：登录 → 工作台四处入口可达 → 各中心 → 详情 → 返回；刷新详情 URL 仍在同一视图。

## Test Plan

- `routes-03.test.tsx`：
  - `tabToPath` 全 tab 映射断言（含带参 jobId/jdId/interviewId/expId）。
  - `renderWithProviders(<AppRoutes/>, {route})` 断言 `/experiences`（经历资产库）、`/prep`（面试准备中心）、`/review`（复盘中心）、`/jd-report/jd-1`（报告/加载态）、`/resume`（简历编辑器）。
  - AppShell 内跳转生效：`/workbench` 点击「职业资产」→ 断言经历资产库出现（URL 驱动）。
- `router.test.tsx`：补 `/experiences`、`/prep/:id`（无数据 → 未找到/空态）、`/review/:id` 断言。
- `legacy-pages.test.tsx`：保持绿（MemoryRouter 内 `useTabNavigate` 可用）。
- 回归：既有 14 文件 / 48 测试不回归。

## Documentation

- 完成后更新 `PROGRESS.md` / `TODO.md`；`src/features/jobs/README.md` 或 `src/router/README.md`（如不存在则新增简短路由表说明）。

## Expected Commit

`feat(router): complete tab routes and converge navigation to react-router (FE-ROUTE-03)`
