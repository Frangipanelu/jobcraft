# router — 路由表与 tab 导航（FE 迁移过渡层）

本目录负责 URL ↔ 视图的映射。迁移期存在两套渲染宿主，职责划分如下：

| 宿主 | 渲染方式 | 适用 |
|------|----------|------|
| `AppShell` | 真实路由页面，URL 参数取参 | 已拆分完成的域（workbench / jobs / job_workspace / jd_report / experiences / prep detail / review detail / profile） |
| `LegacyPageWrapper` | 包一层 `MainLayout`，由 context `currentTab` 渲染 | 尚未拆分的中心 / 创建 / 简历编辑视图，但**同样拥有 URL**，保证 AppShell 内导航可达 |

## 路由表

| URL | 宿主 | tab / 页面 |
|-----|------|-----------|
| `/workbench` | AppShell | `WorkbenchPage` |
| `/jobs` | AppShell | `JobsPage` |
| `/jobs/:jobId` | AppShell | `JobWorkspacePage` |
| `/jd-report/:jdId`、`/jobs/:jobId/jd/:jdId` | AppShell | `JdReportPage` |
| `/experiences`、`/experiences/:experienceId` | AppShell | `ExperiencesPage`（`:id` 打开编辑弹窗） |
| `/prep/:interviewId` | AppShell | `InterviewPrepPage` |
| `/review/:interviewId` | AppShell | `InterviewReviewPage` |
| `/profile` | AppShell | `ProfilePage` |
| `/jd-analysis` | Legacy | `jd_analysis_center` |
| `/resume`、`/resume/:jobId` | Legacy | `resume_editor` |
| `/prep` | Legacy | `interview_prep_center` |
| `/interview/new` | Legacy | `create_interview` |
| `/review` | Legacy | `interview_review_center` |
| `/review/new` | Legacy | `create_review` |
| `*` | — | 重定向 `/workbench` |

## tab → URL 单一映射

`tabPaths.ts` 的 `tabToPath(tab, params)` 是唯一映射实现；`useTabNavigate()` 是组件内触发跳转的推荐方式（签名对齐 legacy `navigateTo`）。

```ts
const go = useTabNavigate();
go('interview_prep_workspace', { interviewId });
```

- **AppShell 可达组件必须用 `useTabNavigate`**：真实路由页由 AppShell 固定渲染，legacy `navigateTo` 只改 `currentTab`、不改 URL，在 AppShell 内会静默失效。
- **Legacy 中心 / 创建 / 简历编辑视图内部仍用 `navigateTo`**（context 驱动仍生效，URL 滞后，属过渡留白）。
- **URL → context 回填**由 `useSyncRouteTab(tab)` 负责（`selectedJobId` / `selectedJDId` / `selectedInterviewId` / `selectedExperienceId` / `currentTab` / sidebar 高亮）。

## 相关任务

- `tasks/FE-ROUTE-01.md`、`tasks/FE-ROUTE-02.md`、`tasks/FE-ROUTE-03.md`
- 后续：`FE-RESUME-01` / `FE-INTERVIEW-01` / `FE-REVIEW-01`（把 Legacy 中心拆为真实路由页）；`FE-CONTEXT-REMOVE`（删除 `LegacyPageWrapper` / `MainLayout` / `currentTab`）
