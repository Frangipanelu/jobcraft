# FE-RESUME-01 — 简历编辑域迁移（读 cache + 编辑/保存写路径 + context 删简历 key）

## Title

新建 `features/resume` 数据层（`RESUMES_QUERY_KEY` + `useResumesQuery` + 9 个 mutation），迁移 `ResumeEditorView` 全量读写、`JDReportDetailView` 的简历生成写路径、`JobCraftContext` 删除简历域全部 key（`resumes` / `setResumes` / `activeResumeId` / `setActiveResumeId` / 7 个 resume action）。简历 map 按 submission id 键控，**新建独立 RESUMES cache**（与 jobs/interviews 不同——简历没有独立后端列表端点，读源为 getDashboard(getSubmission) 聚合 + JD 生成写路径）。

## Context

- 简历对象 `Record<string, ResumeVersion>`（key = submission id 的字符串），由两处产生：
  1. **统一水合**：`loadDashboard`（JobCraftContext L318–340）对每个 `item.has_resume` 的投递调 `getSubmission` → `markdownToResume` → `setResumes`（内联，只写 context 不写 query cache）。
  2. **JD 生成写路径**：`JDReportDetailView.handleGoToResume`（L251–296）调 API `jobApi.saveResume`（`src/api/job.ts:213`，POST `/save-resume`，注意与 context 方法同名）→ 成功后动态 import `markdownToResume` → `setResumes` 并入 map。
- 唯一视图消费方 `ResumeEditorView.tsx`（487 行）：
  - 读：`resumes` / `activeResumeId` / `jobs`（bind by resumeId）/ `experiences`（证据链）。
  - 写：`applyResumeAISuggestion` / `rejectResumeAISuggestion` / `applyAllResumeAISuggestions` / `updateResumeBulletText` / `deleteResumeBullet` / `saveResume`；`addResumeBullet` 被解构但 **UI 零调用**（死解构）。
  - `setActiveResumeId`：唯一消费者即本组件（全局 active id 无跨视图用途）。
- context 简历方法现状（L739–1012）：
  - 除 `saveResume` 外全部为纯 `setResumes` 函数更新（改 sections / bullets / aiSuggestions 状态 + updatedAt='刚刚' + toast），无 API。
  - `saveResume(resumeId)`：`resumeToMarkdown` → `Number(id)` NaN 则 warning 早退（本地示例）；否则 `jobApi.updateSubmission(submissionId, { resume_markdown })` → 更新 updatedAt → toast；失败 toast。**唯一落库写路径**。
- `Job.resumeId` = `String(sub.id)`（`features/jobs/mappers.ts:38`）；`saveResume` 假设 `Number(id)` 是合法 submission id。
- `JDReportDetailView` 解构的 `resumes` 为死变量（仅注释提及）；`setResumes` 是它的真实写入口。
- 测试依赖：`src/test/jd-query.test.tsx:39` 的 `saveResume: vi.fn()` 是 mock **api/job** 模块（`vi.mock('../api/job', …)`），与移除 context `saveResume` 不冲突。
- 既有模式可复用：`useJobsQuery` / `useExperiencesQuery`、镜像 `syncJobs` / `syncExperiences`、Seeder/setTimeout(0) 测试法、mappers 单源、hooks 不 import context、业务代码禁 console（AGENTS 红线）。
- 不变式：cache = 权威；本域**无反读消费者遗留**（editor 与 JD report 均在本 task 内迁移）→ **不设 context 镜像**，直接删 context 简历 key。
- 历史简历（`historicalResumes` + add/delete/setDefault，消费者 `UserProfileView` / `CreateInterview`）**不在本 task 范围**，保留在 context（后续 FE-HISTORICAL-RESUMES 独立处理）。
- 设计参照：FE-REVIEW-01（REV1–REV8）、FE-JD-01。`activeResumeId` 决策：仅 editor 使用 → 改组件局部 state。

## Current State

```
login → loadDashboard → getDashboard → getSubmission(每 has_resume) → markdownToResume → setResumes（只写 context）
  ├── ResumeEditorView（读 context.resumes/activeResumeId，7 个纯 setResumes 写 + saveResume 落库）
  └── JDReportDetailView（API saveResume POST → markdownToResume → setResumes 并入；resumes 死解构）
JobCraftContext：resumes/setResumes/activeResumeId/setActiveResumeId + 7 个 resume action（L739–1012）+ 内联水合（L318–340）
```

## Goal

- `src/features/resume/mappers.ts`：`RESUMES_QUERY_KEY = ['resumes']`。
- `src/features/resume/hooks.ts`：`useResumesQuery` + 9 个写 mutation（apply/reject/applyAll suggestion、update/add/delete bullet、save、upsert）。
- `ResumeEditorView`：读 `useResumesQuery` / `useJobsQuery` / `useExperiencesQuery`；写走 mutation；`activeResumeId` 转组件局部 state；删除 7 个 context 解构。
- `JDReportDetailView`：`setResumes` → `useUpsertResumeMutation`；清理 `resumes` 死解构。
- context 删除简历域 key（interface + state + loadDashboard 内联水合 + 7 个 action + provider value + 孤儿导入 `ResumeVersion` / `resumeParser`）。
- 新增 `src/test/resume-query.test.tsx`（读水合 + 建议应用/忽略/全部 + bullet 编辑/删除 + 保存落库 + 空态）。

## Design Decision

- **RES1 独立 cache key**：简历无后端「列表」端点且结构（`Record<submissionId, ResumeVersion>`）与其它域（数组）不同，读源跨 getDashboard+getSubmission 聚合 + 生成写路径 → 新建 `RESUMES_QUERY_KEY`。key 恒常、禁用自动刷新竞争（默认 staleTime 即满足，查询仅由水合 + 写路径驱动）。
- **RES2 查询水合**：`useResumesQuery` queryFn = getCurrentUser → getDashboard → 对 `has_resume` 的 submission `getSubmission` → `markdownToResume(detail.resume_markdown, {position, company, id: String(item.id)})`；单条失败容忍（return null 跳过，不 console——AGENTS 红线）；空/无经历 → `{}`。与 legacy 内联水合行为一致，N+1 量与 legacy 完全相等（provider loadDashboard 不再重复 getSubmission，总请求数不变）。
- **RES3 hooks 纯净**：hooks 不 import context；无镜像需求 → **不带 onSync 参数**（消费方已全迁移，无回写对象）。`navigateTo`/`showToast` 由视图自行从 context 取（非数据域）。
- **RES4 纯编辑 mutation（cache 内函数更新）**：apply/reject/applyAll/update/add/delete 六者 mutationFn 读取当前 `RESUMES_QUERY_KEY` cache → 函数式更新（节选 legacy L740–982 逻辑）→ onSuccess `setQueryData(next)`。入参均含 `resumeId`（不再隐式依赖 context.activeResumeId，由视图显式传入 activeId）。`updatedAt='刚刚'` 语义保留。不存在断言失败（目标是深度复制 legacy，不做行为变更）。
- **RES5 保存落库**：`useSaveResumeMutation` mutationFn = `resumeToMarkdown` → `Number(resumeId)` NaN → resolve `{ saved: false, reason: 'local' }`（不抛错，视图 warning toast，等价 legacy 早退）；否则 `await jobApi.updateSubmission(submissionId, { resume_markdown })` → resolve `{ saved: true, markdown }`；失败抛错（视图 error toast，等价 legacy catch）。onSuccess：saved 时更新 cache `updatedAt='刚刚'`。**业务代码不 console.error**（legacy 的 catch console 不再保留）。
- **RES6 生成写路径**：`useUpsertResumeMutation({ resumeId, resume })` 纯 cache 写（并入 `[resumeId]`），替换 `JDReportDetailView` 的 `setResumes(prev => ({...prev, [id]: resumeVersion}))`。API POST `save-resume` 仍在组件内调用（属 JD 域产出，非本域职责）。
- **RES7 局部 activeId**：`activeResumeId`/`setActiveResumeId` 全局语义无跨视图用途（editor 唯一消费者）→ 迁移为 `ResumeEditorView` 内 `useState` + `useEffect` 绑定 `boundResumeId`；context 删除。`addResumeBullet` 无 UI 消费但在 hooks 保留（维持域能力完整，如前 review 保留 apply 全部能力）。
- **RES8 无镜像 + 收敛删除**：消费方已全部迁移 → 不建 context 镜像，直接删 context 简历 key；孤儿导入清理（`ResumeVersion`、`markdownToResume/resumeToMarkdown`；`Submission` 若不再使用一并删）。历史简历 key 保留。
- **RES9 回滚**：commit 1 = features/resume + 2 视图 + 测试（context 旧 key 仍存在但无引用，编译通过）；commit 2 = context 删除。单 commit 可独立回滚。

## Scope

- 新增：`frontend-jobcraft/src/features/resume/mappers.ts`、`hooks.ts`、`src/test/resume-query.test.tsx`。
- 修改：`frontend-jobcraft/src/components/resume/ResumeEditorView.tsx`、`src/components/jd/JDReportDetailView.tsx`、`src/context/JobCraftContext.tsx`、`features/resume/README.md`、`PROGRESS.md`、`TODO.md`（本地）。
- 不触碰：`historicalResumes` 域（UserProfileView / CreateInterview 保留 context 读取，FE-HISTORICAL-RESUMES 处理）、`api/job.ts` / `api/experience.ts`（`uploadResume` 双定义另立 task）、resumeParser（保持 single source）。

## Steps

1. `features/resume/mappers.ts`：`RESUMES_QUERY_KEY`。
2. `features/resume/hooks.ts`（RES1–RES6）。
3. `ResumeEditorView` 迁移（RES7）。
4. `JDReportDetailView` 迁移（RES6）。
5. `JobCraftContext` 删除简历 key + 孤儿导入（RES8）。
6. `resume-query.test.tsx`（Seeder 模式，renderWithProviders）。
7. README / PROGRESS / TODO 更新。
8. 验证：`npm run lint` → `npm run build` → `npx vitest run` → `python scripts/check_encoding.py`。
9. commit 1 `feat(resume)` + commit 2 `refactor(context)`（或按需 docs commit）→ push。

## Acceptance Criteria

- `useResumesQuery` 水合：editor 渲染简历名/要点；空数据渲染空态 CTA。
- apply/reject/applyAll：按钮更新 bullet 文本与 applied/rejected badge（本地示例 markdown parse 后 aiSuggestions 为空，测试经 Seeder 注入 aiSuggestions 验证）。
- update/delete bullet：编辑保存写入新文本 / 点击删除移除要点。
- 保存：NaN id → warning「该简历为本地示例」不调 API；合法 id → `updateSubmission` 收到含当前 bullet 文本的 `resume_markdown`。
- `JDReportDetailView`：生成简历写 RESUMES cache（新 submission 可立即在 editor 看到）。
- context：无简历 key 残留（tsc + grep 双证）；无 console log 新增。
- 全量：tsc / build / 测试（原 98 回归 + 新增）全绿；`check_encoding.py` 0 错误；2 commits 已 push。