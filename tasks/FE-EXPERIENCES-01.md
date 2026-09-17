# FE-EXPERIENCES-01 — Experience 域数据层迁移 + 纯经历视图（context 镜像过渡）

## Title

新建 `features/experiences` 查询与变更层（`useExperiencesQuery` / `useCreateExperienceMutation` / `useUpdateExperienceMutation` / `useDeleteExperienceMutation` / 本地版本演进 mutation），迁移 `ExperiencesView` / `NewExperienceModal` 的 experiences 读写；`JobCraftContext.experiences` 降级为**过渡期镜像**，由 hooks mutations 与 legacy writers（review 域写入方）双向同步，直至 FE-CONTEXT-REMOVE 删除。

## Context

- `JobCraftContext.experiences: Experience[]`（Line 512）当前为唯一真实源，被 **5+ 组件 + context 内部逻辑**消费：
  - ExperiencesView（列表/分类/搜索/编辑/删除/版本演进/AI 润色）、NewExperienceModal（创建）——本 task 迁移目标；
  - ResumeEditorView（Line 41、123 联动手风琴）、JDReportDetailView（Line 58、102 选择经历卡）、UserProfileView（Line 44 计数）——只读镜像保留；
  - context 内部写入方：`loadExperiences`、`createExperience`/`updateExperience`/`deleteExperience`、`addExperienceVersion`（纯本地）、`syncReviewToExperience`（Line 1933）、`commitExperienceDiff`（Line 1957，review→经历落盘）。
- 现状读路径：登录期 `loadExperiences` → `experienceApi.listCards(userId)` → `cardToExperience` → `setExperiences`；创建走 `createExperience`（→ `createCard` 建卡 → 本地前置插入 → 返回 `String(card.id)`）；更新/删除亦先 `updateCard`/`deleteCard` 再 `setExperiences`。
- **关键差异（vs FE-JOBS-01）**：后端**无经历版本端点**——`addExperienceVersion` 为纯前端演进（`currentVersion` + `versionHistory` 拼装），故版本演进 = cache 内本地 patch，不新增后端。
- FE-QUERY-01 / FE-JOBS-01 已确立范式：`useXxxQuery` + mutations（`setQueryData` 乐观更新），组件由 hook 消费，`renderWithProviders` 测试；`cardToExperience` 目前私有于 JobCraftContext（Line 265）。
- 迁移不变式与 FE-JOBS-01 同源（AGENTS §1.3 / workflow §11）：过渡期「cache = 权威、context experiences = 只读镜像」，FE-CONTEXT-REMOVE 一并删除。

## Current State

```
登录 loadExperiences → listCards(userId) → cardToExperience → setExperiences (context，唯一源)
  ├── ExperiencesView（列表 + update/delete/addExperienceVersion + AI 润色 + navigateTo resume_editor）
  ├── NewExperienceModal（createExperience → 返回新 id）
  ├── ResumeEditorView / JDReportDetailView / UserProfileView（只读 experiences）
  └── context 内部（syncReviewToExperience / commitExperienceDiff 直接 setExperiences）
cardToExperience 定义于 JobCraftContext.tsx（私有函数）
```

## Goal

- `src/features/experiences/{mappers,hooks}.ts`：`cardToExperience` 移出复用 + 查询/变更 hooks。
- `ExperiencesView` / `NewExperienceModal` 的 experiences 读写切换至 hooks（UI 零变化）。
- context 增 `syncExperiences` 镜像写入；`loadExperiences`/`createExperience`/`updateExperience`/`deleteExperience`/`addExperienceVersion` 单点双向同步 query cache；`syncReviewToExperience`/`commitExperienceDiff` 补双写防漂移；`cardToExperience` 改由 `features/experiences/mappers.ts` 提供（context 引用，杜绝双份映射漂移）。

## Design Decision

- **ED1 权威与镜像**：react-query cache 为迁移后视图唯一读源；`context.experiences` 保留给未迁移消费者（ResumeEditorView/JDReportDetailView/UserProfileView）作**只读镜像**：
  - hooks mutations 成功/乐观更新后调 `onSync(nextExperiences)` → context `syncExperiences`；
  - legacy writers（`loadExperiences`、create/update/delete/addVersion、review 写入方）在 `setExperiences` 后同步写 query cache。
  - 镜像偏差窗口接受（仅影响未迁移视图在无动作期间显示），FE-CONTEXT-REMOVE 拆除。
- **ED2 hooks 纯净**：`features/experiences/hooks.ts` 不 import context；`onSync` 由消费组件注入 `useJobCraft().syncExperiences`。
- **ED3 userId 获取**：queryFn = `authApi.getCurrentUser()` → `user.id` → `listCards(userId)`（与 legacy `loadExperiences(userId)` 对齐；与 FE-JOBS-01 的 JD3 同构）。
- **ED4 映射单源**：`cardToExperience` 移入 `mappers.ts`（含 `ai_structured` 归一），context 改为 import；行为零变化。
- **ED5 版本演进为纯本地**（后端无版本端点）：`useAddExperienceVersionMutation`（或并入 update 后的本地 patch）仅在 cache 内展开 `currentVersion`/`versionHistory`，语义与 `addExperienceVersion` 逐字等价；不借此引入后端版本 API。
- **ED6 回滚**：改动收敛于 features/experiences + 2 组件 + context 少量注入；`git revert` 单 commit 回滚数据层，context 双写亦随 commit 回退。

## Scope

- 新增 `frontend-jobcraft/src/features/experiences/mappers.ts`（`cardToExperience` / `EXPERIENCES_QUERY_KEY`）。
- 新增 `frontend-jobcraft/src/features/experiences/hooks.ts`（`useExperiencesQuery` / `useCreateExperienceMutation` / `useUpdateExperienceMutation` / `useDeleteExperienceMutation` / `useAddExperienceVersionMutation`）。
- 修改 `JobCraftContext.tsx`：接口 + provider 增 `syncExperiences`；`loadExperiences`/create/update/delete/addVersion 双写 cache；`syncReviewToExperience`/`commitExperienceDiff` 补双写；`cardToExperience` 改 import mappers。
- 迁移 `ExperiencesView`、`NewExperienceModal` 到 hooks（UI 结构不变）。
- 测试：`src/features/experiences/mappers.test.ts` + `src/test/experiences-query.test.tsx`。

## Non-goals

- 不迁移 `ResumeEditorView` / `JDReportDetailView` / `UserProfileView`（读镜像，后续独立 task）。
- 不引入后端经历版本端点 / 不改 `experienceApi` 契约。
- 不迁移 `/experiences` 路由与 experiences 导航（FE-ROUTE-03）。
- 不做 `uploadResume` / `backfillCards` 迁移（简历解析属 resume 域）。
- 不删除 context `experiences` 及其 legacy 动作（FE-CONTEXT-REMOVE）。
- 无后端 / DB / 任何 API 契约改动。

## Affected Files

- 新增：`frontend-jobcraft/src/features/experiences/mappers.ts`、`hooks.ts`
- 新增：`frontend-jobcraft/src/features/experiences/mappers.test.ts`、`frontend-jobcraft/src/test/experiences-query.test.tsx`
- 修改：`frontend-jobcraft/src/context/JobCraftContext.tsx`（syncExperiences + 双写 + 映射复用）
- 修改：`frontend-jobcraft/src/components/experiences/ExperiencesView.tsx`、`src/components/experiences/NewExperienceModal.tsx`

## API Impact

无（仅复用 `experienceApi.listCards` / `createCard` / `updateCard` / `deleteCard` 与 context reads）。

## Database Impact

无。

## AI Impact

无（AI 润色 `tasksApi.runTaskOrSync` + `jobApi.polishExperience` 流程不动，仅其落盘动作切缓存）。

## Acceptance Criteria

- `ExperiencesView` / `NewExperienceModal` 不再从 context 读取/调用 `experiences` / `createExperience` / `updateExperience` / `deleteExperience` / `addExperienceVersion`（grep 证实；`showToast` / `navigateTo` 保留）。
- context `experiences` 与 query cache 双写一致：登录加载、创建、更新、删除、本地版本演进后，未迁移视图（ResumeEditorView/JDReportDetailView/UserProfileView）与新迁移视图看到同一集合。
- `cardToExperience` 仅存于 `features/experiences/mappers.ts`（context grep 无重复定义）。
- `npm run lint` / `npm run build` / `npm test` 全绿；新增测试覆盖：映射、query 渲染（列表/分类/搜索）、create 前置+镜像、update 乐观 patch+镜像、delete 过滤+镜像、本地版本演进（versionHistory 展开）。
- 手工 E2E：登录 → 经历资产库列表来自 API；沉淀/编辑/删除即时生效且刷新后持久一致；AI 润色版本演进本地展示；review 落盘经历在经历页可见。

## Test Plan

- `mappers.test.ts`：`cardToExperience` 全字段映射（id 字符串化、`ai_structured` 归一 achievements→actions/results、tags→capabilityTags、company/role/period 空值兜底、version→currentVersion `V{n}`）。
- `experiences-query.test.tsx`（renderWithProviders + `vi.mock('../api/experience')` + mock auth getCurrentUser）：
  - query 渲染 ExperiencesView：经历卡列表 + 分类计数 + 搜索过滤；
  - create：cache 前置 + 新卡出现（镜像经真实 provider syncExperiences 生效）；
  - update：乐观 patch + 镜像同步；
  - delete：过滤 + 镜像同步（含后端 deleteCard 调用断言）；
  - 本地版本演进：`versionHistory` 前置展开 + `currentVersion` 更新（不发网络请求）。
- 回归：既有 10 文件 / 32 测试保持绿（含 legacy-pages ExperiencesView 渲染用例——静态头部即时渲染不受 query error 影响）。

## Documentation

- 完成后更新 `PROGRESS.md` / `TODO.md`（commit_id）；更新 `src/features/experiences/README.md` 记录 hooks 契约、镜像过渡规则与版本演进本地性（FE-CONTEXT-REMOVE 前置）。

## Expected Commit

`feat(experiences): add experiences query layer and migrate experiences views (FE-EXPERIENCES-01)`