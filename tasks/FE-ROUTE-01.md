# FE-ROUTE-01 — 路由迁移试点（/profile 与 AppShell）

## Title

引入 AppShell 布局，把 `/profile` 从 `LegacyPageWrapper` 迁移为真实路由页；Sidebar 导航改为「已迁移 tab 走 react-router、未迁移 tab 仍走 `navigateTo`」的双模实现。

## Context

- FE-ARCH-00（commit `dce9933`）路由表（`src/router/AppRouter.tsx`）：全部 10 条路由均经过 `LegacyPageWrapper`；`/profile` → tab `user_profile` → `MainLayout` 渲染 `UserProfileView`。
- `LegacyPageWrapper`：`useEffect` 将 URL 参数同步为 `navigateTo(tab, params)`，随后渲染 `MainLayout`。
- `MainLayout`（`src/app/legacy/MainLayout.tsx`，待移除）承担：`Sidebar` + `TopHeader` + `<main>`switch + 3 个全局 Modal（NewJobModal / MockInterviewModal / NewInterviewModal）+ `ToastContainer`；当前视图由 `currentTab` / `selected*` 驱动。
- `Sidebar` 当前以 `currentTab === item.key` 判定激活态，点击导航调 `navigateTo`。
- 数据层前置：`FE-QUERY-01` 已将 profile 展示/提交迁移到 react-query hooks，`UserProfileView` 不再读 context `user`。

## Current State

```
AppRouter → <Route path="/profile" element={<LegacyPageWrapper tab="user_profile" />} />
             → LegacyPageWrapper(navigateTo) → MainLayout(currentTab 驱动) → UserProfileView
Sidebar 点击 → navigateTo('user_profile')   （仅改 context，URL 不变）
```

## Goal

- 新增 `src/app/AppShell.tsx`：与 MainLayout 等价的应用壳（Sidebar + TopHeader + `<Outlet/>` + 3 个全局 Modal + Toast），作为迁移后页面的统一宿主。
- `/profile` 改为真实路由：`<Route path="/profile" element={<AppShell><ProfilePage/></AppShell>} />`，`ProfilePage` 先委托渲染 `UserProfileView`（后续由 FE-CONTEXT-REMOVE 将 UI 资产下沉到 features）。
- `Sidebar` 双模导航：导航项可声明 `route?: string`；已迁移项渲染 react-router `<Link>` 且激活态走 `useLocation().pathname`，未迁移项维持 `onClick → navigateTo`。**试点期仅 profile 一项带 route**。
- 移除 `/profile` 对应的 `LegacyPageWrapper`（该路由不再经过 MainLayout / currentTab）。

## Design Decision

- **EH1 并行壳**：MainLayout（legacy）与 AppShell（migrated）并存；同一时刻某一 tab 只由二者之一渲染（AppShell 路由与 LegacyPageWrapper 路由互斥），全局 Modal 不出现双实例。
- **EH2 入口一致性**：Sidebar 双模是迁移的强制配套——避免「从工作台点 Profile 仍是 MainLayout/currentTab 渲染、直接访问 /profile 却是 AppShell」的双态分裂。
- **EH3 回滚**：改动收敛于 AppShell + AppRouter + Sidebar + ProfilePage；`git revert` 单 commit 可回滚；历史 `/profile`（LegacyPageWrapper 分支）在本 commit 中被替换但不删除文件，FE-CONTEXT-REMOVE 阶段才删除。
- **EH4 与 FE-QUERY-01 解耦**：本 task 不碰数据层；ProfilePage 仅做路由层壳。

## Scope

- 新增 `src/app/AppShell.tsx`（Sidebar + TopHeader + Outlet + Modals + Toast）。
- 新增 `src/features/profile/ProfilePage.tsx`（委托渲染 `UserProfileView`）。
- 修改 `src/router/AppRouter.tsx`：`/profile` 真实路由。
- 修改 `src/components/layout/Sidebar.tsx`：双模导航 + URL 激活态。
- 更新 `src/test/router.test.tsx`：`/profile` 断言改为「不经 wrapper 直接渲染 UserProfileView」；新增 AppShell smoke。

## Non-goals

- 不迁移其他 9 条路由 / tab。
- 不拆分 MainLayout 内 Modal（保持原样，仅 AppShell 复制等价接线）。
- 不触碰数据层（profile 数据迁移已完成于 FE-QUERY-01）。
- 不删除 `LegacyPageWrapper` / `MainLayout` / `currentTab`（属 FE-CONTEXT-REMOVE）。

## Affected Files

- 新增：`frontend-jobcraft/src/app/AppShell.tsx`
- 新增：`frontend-jobcraft/src/features/profile/ProfilePage.tsx`
- 修改：`frontend-jobcraft/src/router/AppRouter.tsx`
- 修改：`frontend-jobcraft/src/components/layout/Sidebar.tsx`
- 修改：`frontend-jobcraft/src/test/router.test.tsx`
- 新增：`frontend-jobcraft/src/test/app-shell.test.tsx`（可选 smoke）

## API Impact

无。

## Database Impact

无。

## AI Impact

无。

## Acceptance Criteria

- 直接访问 `/profile`：渲染 `UserProfileView`（不依赖 LegacyPageWrapper），刷新后不跳回工作台，URL 高亮正确。
- 从工作台/其他 tab 点「个人中心」进入 `/profile`（真实路由，URL 变为 /profile），页面内 tab 行为与迁移前一致。
- 其余 9 条路由行为不变：`src/test/router.test.tsx` 既有断言保持绿。
- `npm run lint` / `npm run build` / `npm test` 全绿。
- Sidebar 双模：profile 激活态由 pathname 判定，其余 tab 激活态仍由 currentTab 判定。

## Test Plan

- router.test.tsx 更新 + 新增断言（/profile 直接渲染）。
- AppShell smoke：渲染含 Sidebar/TopHeader/Toast。
- 既有 13 项 FE-ARCH-00 测试 + FE-QUERY-01 新增测试全部保持绿。
- 手工 E2E：登录后点侧边栏「个人中心」→ URL /profile；直接刷新 /profile；返回工作台再进其它 tab。

## Documentation

- 完成后更新 `PROGRESS.md`（记录 commit_id）；`src/features/profile/README.md` 补充路由映射说明。

## Expected Commit

`feat(profile): add app shell and real /profile route (FE-ROUTE-01)`