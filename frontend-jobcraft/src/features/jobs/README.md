# features/jobs — 岗位领域查询层

> FE-JOBS-01：将岗位数据的获取与本地状态变更迁入 react-query，视图不再直接读 `JobCraftContext.jobs`。

## 数据流（react-query cache 为唯一权威）

```
jobApi.listJobEntities（主源，job 表） + getDashboard（join 事实）
  ──► useJobsQuery ──► react-query cache(['jobs']) ──► 已迁移视图
```

- **T-M5-2 数据源切 job 表**：行身份 = job 实体（`jobRowToJob`，`id=job-${id}`、`jobId=entity.id`）；
  steps/阶段事实按 `job_id` join dashboard submission 行（delivered/has_analysis/has_resume/prep/review 计数）。
  - **存量兼容**：dashboard 中无对应在用 job 行的 submission（`job_id` 缺失/悬空）按 `submissionToJob` 兜底补行，不丢存量数据。
  - **降级**：`listJobEntities` 失败（后端未升级）→ 退化为纯 dashboard 行（行为≈切换前）；版本接口失败退回 `has_resume` 判定。
- **T-M6-2**：按 `job_analysis_id` 归组取最新简历版本，`customResume`/`resumeId` 以版本 id 为准。

## 模块

| 文件 | 内容 |
|------|------|
| `mappers.ts` | `JOBS_QUERY_KEY`、`submissionToJob`（存量兜底：`DashboardItem` → `Job`）、`jobRowToJob`（job 实体 + join 事实 → `Job`，T-M5-2 主 mapper）、`jobEntityToJob`（job-only 薄封装，T-M5-1 兼容）、`deriveJobStatus`（steps → status 单一事实源） |
| `hooks.ts` | `useJobsQuery` 查询；`useCreateJobMutation` / `useTerminateJobMutation` / `useResumeJobMutation` / `useSetDeliveredMutation` 变更 |

岗位实体写路径 API 在 `api/jobEntity.ts`（`updateJobEntity` → `PATCH /job/{id}`，与投递/分析域隔离）。

## Hooks API

| Hook | 说明 |
|------|------|
| `useJobsQuery()` | 取当前用户岗位列表（T-M5-2 job 表主源）。queryFn：`listJobEntities`（主）→ `getDashboard` join 事实 + 存量兜底 → `listResumeVersions` 版本归组。返回 `UseQueryResult<Job[]>`。 |
| `useCreateJobMutation()` | **T-M5-1 Job 先行（创建 ≠ 投递）**：本地乐观 Job → `createJobEntity`（`POST /job`）回填 `jobId`（失败静默保留本地 Job）→ `onSuccess` cache 前置插入 + jobId 存在时 invalidate。`mutateAsync` 返回最终 `Job`（供跳转）。 |
| `useTerminateJobMutation()` | 乐观 `steps.terminated=true` → 有 `backendId` 时 PATCH submission `status=CLOSED`（P11-b）；**job-only 行（T-M5-2）→ `PATCH /job/{id}` status=CLOSED** → invalidate。 |
| `useResumeJobMutation()` | 乐观 `steps.terminated=false` → 有 `backendId` 时 PATCH reopen（按 delivered 落 APPLIED/PREPARED）；job-only 行 → `PATCH /job/{id}` status=PREPARED → invalidate。 |
| `useSetDeliveredMutation(delivered)` | P0-1 手工确认投递。**T-M5-1**：标记 + 无 `backendId` 有 `jobId` → `POST /submission`（APPLIED+delivered）首建投递并回填 `backendId`/`jobId`；其余 → PATCH `delivered`。均乐观更新 + invalidate。 |

变更统一读 cache 做乐观更新；后端失败静默保留本地乐观状态（fire-and-forget，失败回滚+toast 归 T-M5-6）。

## 测试

- `mappers.test.ts`：`submissionToJob` / `jobRowToJob`（join 派生/job-only 降级/读时投影）/ `jobEntityToJob` 映射与 `deriveJobStatus` 优先级。
- `jobs-query.test.tsx`：视图渲染、create 改建 job 实体、job-only 行合并 + 标记投递首建 submission、T-M5-2 主源 join + 存量兜底、job-only 终止/恢复持久化到 job 表、terminate/resume 乐观更新、Workbench 统计；通过 `vi.mock('../api/job')` + `vi.mock('../api/jobEntity')` + mock `../api/auth` 隔离后端（有状态 mock server 服务 FE-CACHE-01）。
