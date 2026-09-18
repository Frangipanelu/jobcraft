# FE-JD-02 — JD create 收尾：createJDAnalysis / createStructuredJDAnalysis 迁入 features/jd hooks

## Title

新建 `useCreateJdAnalysisMutation` / `useCreateStructuredJdAnalysisMutation`（`features/jd/hooks.ts`），接管 legacy `JobCraftContext.createJDAnalysis` / `createStructuredJDAnalysis` 的岗位 find-or-create、`runTaskOrSync` 任务编排、JDAnalysis 映射与 jobs/jdAnalyses 双写；迁移 `JDAnalysisCenterView` 与 `NewInterviewModal` 两个消费方后从 context 删除对应 method 与镜像双写，context 仅保留 `deleteJDAnalysis`（仍随 FE-CONTEXT-REMOVE 拆除）。

## Context

- FE-JD-01 明确 JD6 create 非目标（跨域写 jobs + 任务编排风险大），当时仅补 cache 双写；本次完成收尾。
- legacy 行为（JobCraftContext L843 / L945，随后被删除）：
  - `createJDAnalysis`：find-or-create 自动岗位（`steps.jdAnalysis/expMatched: true`）→ `runTaskOrSync('resume_generate', …, fallback=analyzeJob, timeout 180s)` → `analysisToJD` 前置插入 cache/mirror → 岗位 `jdAnalysisId=String(job_analysis_id)` + matchScore + steps → toast。
  - `createStructuredJDAnalysis`：同构（`jd_analyze_structured`，timeout 120s），内联构建 JDAnalysis（合成 `jd-<ts>` id、matchScore 0、verdictSummary '结构化分析完成'、subtext_decoded → subtextAnalysis），岗位 `jdAnalysisId=合成 id`（**与文本路径的真实 job_analysis_id 不一致，legacy 瑕疵**）。
  - 两者均 **fire-and-forget**：同步返回合成 id 供调用方立即 `navigateTo('jd_report')`。
- 消费方：
  - `JDAnalysisCenterView` L85-108：`setTimeout(800)` 后调 `createStructuredJDAnalysis` → **立即** `navigateTo('jd_report', { jdId: newId })`；`isAnalyzing` 只覆盖 800ms 假等待。
  - `NewInterviewModal` L219：调 legacy `createJob` 得 newJobId 后 **fire-and-forget** `createJDAnalysis({…, jobId})`，无消费返回值。
- 既有范式（interview hooks）：mutationFn 内 `runTaskOrSync` + cache 更新，`onSync`/`onSyncJobs` 由消费组件注入 context 镜像。

## Design Decision

- **JD-C1 行为语义：由「fire-and-forget + 立即跳转」改为「await 完成后跳转 / 可反馈错误」。**
  - 结构化路径（JDAnalysisCenterView）：`mutateAsync` 全程生成（真 loading），成功才 navigate 到**已就绪**报告；失败留在表单页 + error toast（legacy 失败时已跳转但报告页永远等不到缓存，属误导）。
  - 文本路径（NewInterviewModal）：保持 fire-and-forget（`mutate(…, { onSuccess/onError })`），toast 归视图层，岗位 jdAnalysisId 完成后回填。
  - 此偏差已写入本 task 验收；成功 toast 由 legacy 的 context 内展示改为视图层展示。
- **JD-C2 岗位解析/自动创建收敛到 hook 内 helper `resolveTargetJob`**：显式 `jobId` 直接复用；否则按「公司+岗位」查找，未命中创建自动岗位（写入 JOBS cache，不产生后端提交，语义与 legacy 一致）；自动创建后**同步** `onSyncJobs`（镜像补写时机与 legacy `setJobs` 一致）。
- **JD-C3 映射单源扩展**：`dutiesText` / `requirementsText` / `structuredResultToJD` 移入 `features/jd/mappers.ts`，context 不再持有内联构造。
- **JD-C4 hooks 纯净不变式延续**：`features/jd/hooks.ts` 不 import context；`currentUserId` 取 `authApi.getCurrentUser()`；`card_ids` 读 EXPERIENCES cache（与原 context `experiences` 镜像同源）。
- **JD-C5 删除清理**：context 删除两个 method + 接口声明 + provider 值 + `dutiesText`/`requirementsText` 私有 helpers + 不再使用的 `analysisToJD`/`JobAnalysisResult` import。

## Scope

- `features/jd/mappers.ts`：+`dutiesText` / `requirementsText` / `StructuredJDAnalysisMeta` / `structuredResultToJD`。
- `features/jd/hooks.ts`：`JDMutationOptions` +`onSyncJobs`；+`useCreateJdAnalysisMutation`、`useCreateStructuredJdAnalysisMutation`、`resolveTargetJob`。
- `JDAnalysisCenterView.tsx`：绑定 `useCreateStructuredJdAnalysisMutation`，`handleStartAnalysis` 改 `async/await` + `mutateAsync`，移除 `setTimeout(800)`，注入 `onSyncJobs: syncJobs`。
- `NewInterviewModal.tsx`：`createJDAnalysis` → `useCreateJdAnalysisMutation`（per-call onSuccess/onError 展示 toast），destructure 增 `syncJdAnalyses`。
- `JobCraftContext.tsx`：删除 `createJDAnalysis` / `createStructuredJDAnalysis`（constructor 实现 + interface + provider），删除 `dutiesText`/`requirementsText`，收敛 import。
- 测试：`features/jd/mappers.test.ts`（dutiesText/requirementsText/structuredResultToJD 3 组）+ `test/jd-query.test.tsx`（结构化自动建岗 / 结构化复用 jobId / 原始文本 fire-and-forget / 失败 reject 4 例）。
- 文档：本文件 + TODO.md + PROGRESS.md。

## Non-Goals (遗留至后续)

- `NewInterviewModal` 的 `createJob`（context legacy）仍为旧路径，随 FE-CONTEXT-REMOVE 处理。
- `JDAnalysisCenterView` 的结构化合成 id（`jd-<ts>`）与文本路径真实 job_analysis_id 的不一致为 legacy 数据模型缺陷，不在本次修复（可选 FE-JD-03 立项）。
- `deleteJDAnalysis` 未迁（FE-CONTEXT-REMOVE 统一拆除）。

## Implementation Result

- commit：见 Git log（`feat(jd): …`）。
- 验证：`npx vitest run`（17 文件 / 81 用例）、`npx tsc --noEmit`、`npm run build` 全绿；`python scripts/check_encoding.py` 289 文件 0 错误。
- 验收要点：grep `createJDAnalysis|createStructuredJDAnalysis` 在 src 下仅剩（如有）非消费引用为 0。