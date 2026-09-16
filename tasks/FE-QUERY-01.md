# FE-QUERY-01 — 查询层试点（Profile 域）

## Title

建立第一个 @tanstack/react-query 查询+变更闭环：`useProfileQuery` / `useUpdateProfileMutation`，由 `UserProfileView` / `TopHeader` 消费，替换 `JobCraftContext.user` 的**读路径**。

## Context

- FE-ARCH-00（commit `dce9933`）已交付：`QueryProvider`（`src/app/providers/QueryProvider.tsx`，staleTime 30s、retry 1、refetchOnWindowFocus 关闭）、通用传输层 `src/services/api/client.ts`（`request<T>`、`{error:{...}}` 契约、token 注入、超时、请求时解析 fetch）、vitest + testing-library 基建（`src/test/{setup,test-utils}`）。
- 遗留现状：`user: UserProfile` 存于 `src/context/JobCraftContext.tsx`（state 声明区 line ~540），登录期经 `loadUserProfileAndData` 用 `authApi.getCurrentUser()` / `getProfile()` 填充；`updateUserProfile` 调 `authApi.updateProfile`（已于 FIX-PROFILE-001 落库 `user_profiles` 表）。
- 消费方：
  - `UserProfileView`：读取 `user.name/role/targetSalary/yearsOfExp/city/email/phone/summary/targetRoles/targetCompanies`，`handleSubmit → updateUserProfile(profileForm)`。
  - `TopHeader`：头像首字母、`user.name`、`user.role` 展示。
- `src/api/auth.ts` 现状：`getCurrentUser(): Promise<UserProfile>`（强类型）；`getProfile()/updateProfile(): Promise<Record<string, unknown>>`（弱类型）。
- 本项目工程规范（`docs/engineering-development-workflow-v1.md` §10）：`Page → Feature Component → Hook/Query/Mutation → API Client → Backend`；server state 不允许复制到 Context / useState / localStorage 多份真相源（§11）。

## Current State

```
JobCraftContext.user  ←  loadUserProfileAndData（登录期）  ←  authApi.getCurrentUser/getProfile
  ├── TopHeader（name/role/头像）
  └── UserProfileView（表单字段 + handleSubmit → updateUserProfile → authApi.updateProfile）
```

## Goal

- 新增 `src/features/profile/hooks.ts`：`useProfileQuery`（queryKey `['profile']`，queryFn = 向后端取用户档案并归一为 `UserProfile`）、`useUpdateProfileMutation`（成功后 `setQueryData` 更新缓存，不整页 refetch）。
- 迁移 `UserProfileView` 与 `TopHeader`：profile 展示/提交的数据源从 context `user` 切换到 hooks。
- 全程不新增后端端点、不改 API 契约。

## Design Decision（实现阶段需按此收敛）

- **D1 查询函数源**：优先使用强类型的 `authApi.getCurrentUser()` 作为 queryFn；若其与 `getProfile()`（`/auth/me` vs `/auth/profile`）语义存在差异，在设计中确认统一走 profile 读，不引入后端改动。
- **D2 单一真相源**：迁移后这两个组件的 profile 数据只来自 react-query 缓存；context `user` 降级为「登录期一次性种子」，不再被这两个组件读取（不删除该 state，避免波及 Workbench 等其余消费方；标记待 FE-CONTEXT-REMOVE 清理）。
- **D3 回滚**：改动收敛于 hooks + 两组件，不触碰 context 其他状态；`git revert` 单 commit 即可整体回滚。
- **D4 传输层**：queryFn 仍走现有 `src/api/*`（项目规定的唯一 HTTP 出口）；`src/services/api/client.ts` 与新旧 client 统一属单独 sub-task（列入 FE-CONTEXT-REMOVE），本 task 不做传输层合并。

## Scope

- 新增 `frontend-jobcraft/src/features/profile/hooks.ts`（useProfileQuery / useUpdateProfileMutation）。
- 必要时新增强类型返回 wrapper（把 `getProfile/updateProfile` 泛型化，或新导出返回 `UserProfile` 的函数），不改 `src/api/auth.ts` 既有函数签名（向后兼容）。
- 迁移 `UserProfileView`、`TopHeader` 到 hooks。
- 补单元测试 + 组件测试。

## Non-goals

- 不迁移 jobs / experiences / jd / interview / review 任何 server state。
- 不删除 context 的 `user` / `updateUserProfile`，不搬登录流程。
- 不合并 `src/api/client.ts` 与 `src/services/api/client.ts`。
- 无后端 / DB / API 契约改动。

## Affected Files

- 新增：`frontend-jobcraft/src/features/profile/hooks.ts`
- 新增：`frontend-jobcraft/src/features/profile/hooks.test.ts`
- 新增：`frontend-jobcraft/src/test/profile-query.test.tsx`（组件级）
- 修改：`frontend-jobcraft/src/api/auth.ts`（仅可选强类型 wrapper）
- 修改：`frontend-jobcraft/src/components/user/UserProfileView.tsx`
- 修改：`frontend-jobcraft/src/components/layout/TopHeader.tsx`

## API Impact

无（仅前端侧复用现有端点）。

## Database Impact

无。

## AI Impact

无。

## Acceptance Criteria

- `UserProfileView` 的表单回填、保存成功提示，`TopHeader` 的头像/姓名/角色展示与迁移前一致，数据来自 hooks。
- grep 确认 `UserProfileView` / `TopHeader` 不再从 context 读取 `user`。
- `npm run lint`（tsc --noEmit）、`npm run build`、`npm test` 全绿；新增测试覆盖 loading / error / success 与 mutation 后缓存更新（`setQueryData` 生效断言）。
- 手工 E2E：登录 → 修改档案 → 刷新页面 → 修改已持久化且展示一致。

## Test Plan

- hooks 单测：mock `src/api/auth.ts`，断言 query 成功/失败、mutation 后缓存更新的值。
- 组件测试：`renderWithProviders`（含 QueryClient retry:false）渲染 `TopHeader` + `UserProfileView`。
- 回归：既有 13 项 FE-ARCH-00 测试保持绿。

## Documentation

- FE-QUERY-01 完成后更新 `PROGRESS.md`（记录 commit_id）；`src/features/profile/README.md` 记录 hooks 契约（queryKey / 返回 / 错误语义）。

## Expected Commit

`feat(profile): add react-query hooks and migrate profile reads (FE-QUERY-01)`