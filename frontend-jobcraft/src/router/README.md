# router — 路由表与 tab 导航

本目录负责 URL ↔ 视图的映射。全部页面均为 `AppShell` 真实路由页（LegacyPageWrapper / MainLayout 已删除）。

## 路由表

| URL | 页面 | useSyncRouteTab |
|-----|------|-----------------|
| `/workbench` | `WorkbenchPage` | `workbench` |
| `/jobs` | `JobsPage` | `jobs` |
| `/jobs/:jobId` | `JobWorkspacePage` | `job_workspace` |
| `/jd-analysis` | `JdAnalysisCenterPage` | `jd_analysis_center` |
| `/jd-report/:jdId`、`/jobs/:jobId/jd/:jdId` | `JdReportPage` | `jd_report` |
| `/experiences`、`/experiences/:experienceId` | `ExperiencesPage` | `experiences` |
| `/resume`、`/resume/:jobId` | `ResumeEditorPage` | `resume_editor` |
| `/prep` | `InterviewPrepCenterPage` | `interview_prep_center` |
| `/prep/:interviewId` | `InterviewPrepPage` | `interview_prep_workspace` |
| `/review` | `InterviewReviewCenterPage` | `interview_review_center` |
| `/review/:interviewId` | `InterviewReviewPage` | `interview_review_detail` |
| `/review/new`、`/review/new/:jobId` | `CreateReviewPage` | `create_review` |
| `/profile` | `ProfilePage` | `user_profile` |
| `*` | — | 重定向 `/workbench` |

> **T-M7-1 页面收敛（2026-10-02）**：`/interview/new`（+`:jobId`）已删除——新建面试只走 `NewInterviewModal`（AppShell 全局挂载）；`NavigationTab` 不再有 `create_interview`。JD 报告页「返回继续」回流经 AppShell outlet 开 Modal；返回意图 `jdAnalysisReturnTarget` 的持位/作废迁至 Modal（FE-STATE-01）。

## tab → URL 单一映射

`tabPaths.ts` 的 `tabToPath(tab, params)` 是唯一映射实现。

- **组件内触发跳转**：`useTabNavigate()`（签名对齐 legacy `navigateTo`）。
- **context 入口 `navigateTo(tab, params)`**（FE-NAV-01）：`syncTabState` 回填选中态 + `navigate(tabToPath(...))` 真实跳转，与 `useTabNavigate` 行为一致，不再是"只改 state 不改 URL"的死按钮。
- **`syncTabState(tab, params)`**：只回填 context、不改 URL，专供 `useSyncRouteTab` 使用——URL → context 回填若再触发跳转会与来源 URL 打架（`/jobs/:jobId/jd/:jdId` 别名不能被重定向到 `/jd-report/:jdId`）。
- **URL → context 回填**由 `useSyncRouteTab(tab)` 负责（`selectedJobId` / `selectedJDId` / `selectedInterviewId` / `currentTab` / sidebar 高亮），每条路由页在挂载时调用一次（FE-TAB-01）。
- `BrowserRouter` 位于 `App.tsx` Provider 之上（`JobCraftProvider.navigateTo` 需要 `useNavigate`）；测试侧 `test-utils` 的 `MemoryRouter` 同样外提。

## 相关任务

- `tasks/FE-ROUTE-01.md`、`tasks/FE-ROUTE-02.md`、`tasks/FE-ROUTE-03.md`
- T-M10-1 导航收口：FE-NAV-01（navigateTo 真导航）/ FE-TAB-01（14 路由 currentTab 回填）/ FE-STATE-01（返回意图清理）
