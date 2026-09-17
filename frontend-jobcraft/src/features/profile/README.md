# Profile（个人中心）

## 归属

个人资料相关的数据层与路由层。试点三件套：`useProfileQuery` / `useUpdateProfileMutation`（FE-QUERY-01）+ 真实 `/profile` 路由（FE-ROUTE-01）。

## 数据层契约（FE-QUERY-01）

- `useProfileQuery()`：`queryKey ['profile']`，合并 `authApi.getCurrentUser()`（`/api/auth/me`）与 `authApi.getProfile()`（`/api/auth/profile`）映射为领域 `UserProfile`（`src/types/jobcraft.ts`）。`getProfile` 失败时降级使用 auth 侧字段。
- `useUpdateProfileMutation()`：变量为 `Partial<UserProfile>`（领域字段），内部经 `toApiProfilePatch()` 映射为后端 snake_case `ProfilePayload` 后调用 `authApi.updateProfile()`（`PATCH /api/auth/profile`）；成功后 `setQueryData(['profile'], ...)` 乐观合并缓存，不整页 refetch。
- 空态：`EMPTY_PROFILE` 与 JobCraftContext 初始 user 对齐（`name:'' / role:'求职者' / ...`），供组件在查询加载前兜底。

## 组件消费方

- `components/layout/TopHeader.tsx`
- `components/user/UserProfileView.tsx`

## 路由映射（FE-ROUTE-01）

- `/profile` → `ProfilePage`（真实路由，经 `AppShell` 渲染，不再经过 `LegacyPageWrapper`）。
- `ProfilePage` 解析 `?tab={resumes,profile,preferences,settings}` 作为 `UserProfileView` 的 `initialTab`（URL 为挂载时单一来源）。
- TopHeader 头像下拉四个子项改为 `navigate('/profile?tab=...')`（router 驱动）。
- `AppShell`（`src/app/AppShell.tsx`）与遗留 `MainLayout` 并行存在，Fallback 留待 FE-CONTEXT-REMOVE。

## 已解决

- `/profile` 已从 `LegacyPageWrapper` 迁移为真实路由 + AppShell 壳（commit `f0b8151`）。

## 已知留白

- 读/写映射与 `JobCraftContext.updateUserProfile` 内联实现重复，待 FE-CONTEXT-REMOVE 时收敛到唯一 mapper。
- 目标子路由 `/profile/{resumes,profile,preferences,settings}` 待 FE-ROUTE-01 决策。