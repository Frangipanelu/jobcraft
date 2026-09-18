# features/interview — 面试域查询层

> FE-INTERVIEW-01：将面试准备数据的读与创建迁入 react-query，视图不再直接读 `JobCraftContext.interviews` / 调 `createInterview`。

## 数据流（cache 为权威，context 为过渡镜像）

```
interviewApi.listInterviewPreps ──► useInterviewsQuery ──► react-query cache(['interviews']) ──► 已迁移视图（Center / Workspace）
                                                                │  onSync ──► context.interviews ──► 未迁移视图
legacy writers（loadInterviews、复盘 writers addInterviewReview / commitExperienceDiff / applyReviewFeedback）
  ── 写入 cache ───────────────────────────────────────────────┘
```

- **已迁移视图只读 cache**；`context.interviews` 仅是给未迁移消费者保留的**只读镜像**。
- 创建为**跨域写**：`useCreateInterviewMutation` 写 `['interviews']` 后按 `variables.jobId` 补写 `['jobs']`（`interviewIds` / `steps.prepStage`），并分别 `onSync` / `onSyncJobs` 同步两个镜像。
- 复盘字段（`Interview.review`）后端不加载，仅在写路径于内存构建；复盘 writers 必须双写 `['interviews']` cache，保证镜像与 cache 一致。
- 两侧共用同一映射实现（`mappers.ts`），杜绝漂移。

## 模块

| 文件 | 内容 |
|------|------|
| `mappers.ts` | `INTERVIEWS_QUERY_KEY`、`mapRoundType` / `roundTypeToCn`（轮次枚举 ↔ 中文）、`prepRecordToInterview`（后端 `InterviewPrepRecord` → 前端 `Interview`，含 company_research / dimension_questions 兜底）、`buildInterviewFromPrep`（prep + meta → 最终 `Interview`） |
| `hooks.ts` | `useInterviewsQuery` 查询；`useCreateInterviewMutation` 创建 |

## Hooks API

| Hook | 说明 |
|------|------|
| `useInterviewsQuery()` | 取当前用户面试准备列表。queryFn：`authApi.getCurrentUser()` → `interviewApi.listInterviewPreps(user.id)` → `prepRecordToInterview`。返回 `UseQueryResult<Interview[]>`。 |
| `useCreateInterviewMutation({ onSync, onSyncJobs })` | 与 legacy `createInterview` 等价：从 `['jobs']` cache 解析 `jdAnalysisId`（`jobId` 缺失或无分析则抛「尚未完成 AI 岗位分析」）→ `tasksApi.runTaskOrSync('interview_prep', …, fallback)=generateInterviewPrep` → 构建 `Interview` → `onSuccess` 前置插入 `['interviews']` + 补写 `['jobs']` + 双镜像。`mutateAsync` 返回创建后的 `Interview`（含 `id` 供 navigateTo）；不内置 toast（归视图层）/ 不写 `nextActions`（无消费者）。 |

变更统一用法：`const { syncInterviews, syncJobs } = useJobCraft()`，注入 mutation。创建后导航：
```ts
const created = await createInterview.mutateAsync({ jobId, company, role, roundNumber, roundName, roundType, time, format, interviewer, supplementNotes });
navigateTo('interview_prep_workspace', { interviewId: created.id });
```

## 新视图迁移清单（对照 FE-CONTEXT-REMOVE）

1. 读路径：`useInterviewsQuery()`；`const interviews = data || []`；`isLoading && data === undefined` 时渲染加载态。
2. 创建路径：`useCreateInterviewMutation({ onSync: syncInterviews, onSyncJobs: syncJobs })`；`mutateAsync(...).id` 导航；删除 `createInterview` context 依赖。
3. 未迁移写路径（workspace 复盘叠加 `addInterviewReview` 等）保持 context 直写，但必须维持 cache 双写（已有）。
4. 全部迁移完成后执行 FE-CONTEXT-REMOVE：删除 `syncInterviews`、legacy double-write、`JobCraftContext.interviews` 相关 writers 与无消费者的 `updateQuestionAnswer` / `addCustomQuestion` / `nextActions`。

## 测试

- `mappers.test.ts`：映射参数与兜底（含 legacy `业务`→`product` 分支顺序）。
- `interview-query.test.tsx`：Center 渲染 + 搜索过滤 + 镜像计数；创建（`getDashboard` seed JOBS cache → runTaskOrSync 走 fallback → `generateInterviewPrep` → 双镜像 + `jobs.interviewIds`）；`jdAnalysisId` 缺失抛错且不触发任务服务；通过 `vi.mock` auth/job/interview/tasks/experience 隔离后端。