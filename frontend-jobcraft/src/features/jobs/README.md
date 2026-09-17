# features/jobs — 岗位领域查询层

> FE-JOBS-01：将岗位数据的获取与本地状态变更迁入 react-query，视图不再直接读 `JobCraftContext.jobs`。

## 数据流（cache 为权威，context 为过渡镜像）

```
jobApi.getDashboard ──► useJobsQuery ──► react-query cache(['jobs']) ──► 已迁移视图
                                          │  onSync ──► context.jobs ──► 未迁移视图
legacy writer (JobCraftContext.createJob/t…)
  ── 写入 cache ─────────────────────────┘
```

- **已迁移视图只读 cache**；`context.jobs` 仅是给未迁移视图（JobWorkspace / JD 详情 / 面试记录 / *Create 表单等）保留的**只读镜像**。
- 两侧双写：hooks 的 mutation 通过 `onSync` 调 `useJobCraft().syncJobs` 同步镜像；context 的 legacy writer 反向 `setQueryData` 写回 cache。
- 两者共用同一映射实现（`mappers.ts`），保证 status/steps 推导一致，防止漂移。

## 模块

| 文件 | 内容 |
|------|------|
| `mappers.ts` | `JOBS_QUERY_KEY`、`submissionToJob`（后端 `DashboardItem` → 前端 `Job`）、`deriveJobStatus`（steps → status 单一事实源） |
| `hooks.ts` | `useJobsQuery` 查询；`useCreateJobMutation` / `useTerminateJobMutation` / `useResumeJobMutation` 变更 |

## Hooks API

| Hook | 说明 |
|------|------|
| `useJobsQuery()` | 取当前用户岗位列表。queryFn：`authApi.getCurrentUser()` → `jobApi.getDashboard(user.id)` → `submissionToJob`。返回 `UseQueryResult<Job[]>`。 |
| `useCreateJobMutation({ onSync })` | 与 legacy `createJob` 等价：本地乐观 Job（`steps` 初始 → pending）→ `createSubmission` 回填 `id`/`backendId`（失败静默保留本地 Job）→ `onSuccess` cache 前置插入 + `onSync`。`mutateAsync` 返回最终 `Job`（含回填后的 `id`，供跳转）。 |
| `useTerminateJobMutation({ onSync })` | 纯本地更新（无后端调用）：目标 Job `steps.terminated=true`，`status=deriveJobStatus(steps)`。 |
| `useResumeJobMutation({ onSync })` | 纯本地更新：`steps.terminated=false`，重算 status。 |

变更统一 `{ onSync: syncJobs }` 用法：`const { syncJobs } = useJobCraft()`，把 `syncJobs` 注入 mutation，缓存更新后同步镜像。

## 新视图迁移清单（对照 FE-CONTEXT-REMOVE）

1. `useJobsQuery()` 取数据；`const jobs = data || []`；`isLoading && data === undefined` 时渲染加载态。
2. 变更用 hooks mutation（读 cache），删除 `useJobCraft()` 里的 `jobs/terminateJob/resumeJob/createJob` 依赖。
3. 若使用 lambda（`patch(j)`）需遵循 Rules of Hooks（无状态变更基类已封装内部，勿在视图内自建乐观更新）。
4. 全部迁移完成后执行 FE-CONTEXT-REMOVE：删除 `syncJobs`、legacy double-write、`JobCraftContext.jobs` 相关 state 与遗留 writers。

## 测试

- `mappers.test.ts`：映射参数与 `deriveJobStatus` 优先级。
- `jobs-query.test.tsx`：视图渲染、create 前置写入 + 镜像同步、terminate/resume 乐观更新、Workbench 统计；通过 `vi.mock('../api/job')` + mock `../api/auth` 隔离后端。