# features/jobs — 岗位领域查询层

> FE-JOBS-01：将岗位数据的获取与本地状态变更迁入 react-query，视图不再直接读 `JobCraftContext.jobs`。

## 数据流（cache 为权威，context 为过渡镜像）

```
jobApi.getDashboard + listJobEntities ──► useJobsQuery ──► react-query cache(['jobs']) ──► 已迁移视图
                                          │  onSync ──► context.jobs ──► 未迁移视图
legacy writer (JobCraftContext.createJob/t…)
  ── 写入 cache ─────────────────────────┘
```

- **T-M5-1 双源并存**：主源仍是 dashboard submission 行；`listJobEntities` 补「已建岗未投递」的 job-only 行（`submission_id == null` 且未被 `job_id` 覆盖），实体列表失败降级为空不阻断主源。单源切换见 T-M5-2。

- **已迁移视图只读 cache**；`context.jobs` 仅是给未迁移视图（JobWorkspace / JD 详情 / 面试记录 / *Create 表单等）保留的**只读镜像**。
- 两侧双写：hooks 的 mutation 通过 `onSync` 调 `useJobCraft().syncJobs` 同步镜像；context 的 legacy writer 反向 `setQueryData` 写回 cache。
- 两者共用同一映射实现（`mappers.ts`），保证 status/steps 推导一致，防止漂移。

## 模块

| 文件 | 内容 |
|------|------|
| `mappers.ts` | `JOBS_QUERY_KEY`、`submissionToJob`（后端 `DashboardItem` → 前端 `Job`）、`jobEntityToJob`（job-only 行 → `Job`，T-M5-1）、`deriveJobStatus`（steps → status 单一事实源） |
| `hooks.ts` | `useJobsQuery` 查询；`useCreateJobMutation` / `useTerminateJobMutation` / `useResumeJobMutation` / `useSetDeliveredMutation` 变更 |

## Hooks API

| Hook | 说明 |
|------|------|
| `useJobsQuery()` | 取当前用户岗位列表（T-M5-1 双源）。queryFn：`authApi.getCurrentUser()` → `getDashboard` submission 行 + `listJobEntities` job-only 行合并去重。返回 `UseQueryResult<Job[]>`。 |
| `useCreateJobMutation()` | **T-M5-1 Job 先行（创建 ≠ 投递）**：本地乐观 Job → `createJobEntity`（`POST /job`）回填 `jobId`（失败静默保留本地 Job）→ `onSuccess` cache 前置插入 + jobId 存在时 invalidate（job-only 合并行带回）。`mutateAsync` 返回最终 `Job`（供跳转）。 |
| `useTerminateJobMutation()` | 乐观 `steps.terminated=true` → 有 `backendId` 时 PATCH `status=CLOSED`（P11-b 持久化）→ invalidate。 |
| `useResumeJobMutation()` | 乐观 `steps.terminated=false` → 有 `backendId` 时 PATCH reopen（按 delivered 落 APPLIED/PREPARED）→ invalidate。 |
| `useSetDeliveredMutation(delivered)` | P0-1 手工确认投递。**T-M5-1**：标记 + 无 `backendId` 有 `jobId` → `POST /submission`（APPLIED+delivered）首建投递并回填 `backendId`/`jobId`；其余（已有 submission 的标记/取消）→ PATCH `delivered`。均乐观更新 + invalidate。 |

变更统一读 cache 做乐观更新；后端失败静默保留本地乐观状态（fire-and-forget）。

## 新视图迁移清单（对照 FE-CONTEXT-REMOVE）

1. `useJobsQuery()` 取数据；`const jobs = data || []`；`isLoading && data === undefined` 时渲染加载态。
2. 变更用 hooks mutation（读 cache），删除 `useJobCraft()` 里的 `jobs/terminateJob/resumeJob/createJob` 依赖。
3. 若使用 lambda（`patch(j)`）需遵循 Rules of Hooks（无状态变更基类已封装内部，勿在视图内自建乐观更新）。
4. 全部迁移完成后执行 FE-CONTEXT-REMOVE：删除 `syncJobs`、legacy double-write、`JobCraftContext.jobs` 相关 state 与遗留 writers。

## 测试

- `mappers.test.ts`：`submissionToJob` / `jobEntityToJob` 映射参数与 `deriveJobStatus` 优先级。
- `jobs-query.test.tsx`：视图渲染、create 改建 job 实体（不建 submission）、job-only 行合并 + 标记投递首建 submission、terminate/resume 乐观更新、Workbench 统计；通过 `vi.mock('../api/job')` + mock `../api/auth` 隔离后端（有状态 mock server 服务 FE-CACHE-01）。