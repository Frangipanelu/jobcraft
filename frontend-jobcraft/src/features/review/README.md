# features/review — 面试复盘域（写入层）

> FE-REVIEW-01：将复盘创建与「复盘反馈 → 经历资产」落盘迁入 react-query；三视图（Review Center /
> Review Detail / CreateReview）读写均不再依赖 `JobCraftContext` 的 legacy 复盘 writers（已删除）。

## 数据流

```
CreateReview: createInterviewReview ──► runTaskOrSync('interview_review_analyze'，fallback analyzeInterviewReview, 180s)
  ──► buildReviewFromPatch ──► INTERVIEWS cache（review + status 'completed'）──► onSync → context.interviews 镜像
  └─ 跨域写：JOBS cache（job.steps.reviewStage/prepStage 'done'）──► onSyncJobs → context.jobs 镜像

ReviewDetail: useApplyReviewFeedbackMutation ──► EXPERIENCES cache（Vn+1 / 变更 / versionHistory 前置）
  ──► onSyncExperiences → context.experiences 镜像　│　INTERVIEWS cache（feedback.applied=true）──► onSync 镜像
```

## 模块

| 文件 | 内容 |
|------|------|
| `mappers.ts` | 6 个纯函数：`buildReviewPatchFromAnalysis`（分析结果 → review patch，score 一律来自真实数据）、`buildReviewFromPatch`（interview + patch → 完整 `InterviewReview`）、`nextExperienceVersion`、`applyProposedChanges`（field 字段法）、`applyFeedbackSuggestions`（动作前置兜底）、`buildVersionRecord` |
| `hooks.ts` | `useCreateInterviewReviewMutation`、`useApplyReviewFeedbackMutation` + `ReviewMutationOptions` |

## Hooks API

| Hook | 说明 |
|------|------|
| `useCreateInterviewReviewMutation({ onSync, onSyncJobs })` | 与 legacy `createReviewFromTranscript` 等价：从 `['interviews']` cache 解析 interview（缺则抛「未找到对应的面试记录」）→ `createInterviewReview` 落库 → `runTaskOrSync`（分析失败容忍，保留 base patch，不 console）→ `mutateAsync` 返回 `{ interviewId, review }`。`onSuccess` 写 INTERVIEWS cache + 跨域 JOBS cache + 双镜像。toast/跳转归视图层。 |
| `useApplyReviewFeedbackMutation({ onSync, onSyncExperiences })` | 与 legacy `applyReviewFeedback` 等价，**修复漂移**：legacy 仅 `setExperiences` 不写 cache，本实现同步写 EXPERIENCES cache + 镜像。不写 activities（零消费者）。返回 `{ experienceId, finalExp }`（供 toast）。 |

## 视图迁移清单（对照 FE-CONTEXT-REMOVE）

1. 读路径：`useInterviewsQuery()`（Center 过滤 / Detail 目标 / CreateReview 面试联表）、`useJobsQuery()`（CreateReview 岗位）。
2. 写路径：Center 无写；Detail `useApplyReviewFeedbackMutation`；CreateReview `useCreateInterviewReviewMutation`，await 成功后
   `navigateTo('interview_review_detail', { interviewId })`，失败 toast + `setIsAnalyzing(false)`。
3. `JobCraftContext` 删除：`addInterviewReview` / `applyReviewFeedback` / `syncReviewToExperience` / `createReviewFromTranscript` / `commitExperienceDiff` / `buildReviewPatchFromAnalysis`（共 6 处，含接口/实现/provider/import 清理）。
4. 全部迁移完成后执行 FE-CONTEXT-REMOVE：删除 `syncInterviews` / `syncJobs` / `syncExperiences` 镜像与 context 只读镜像。

## 测试

- `mappers.test.ts`：2 主要 mapper（patch 派生 / review 构建）边界与兜底。
- `review-query.test.tsx`：CreateReview 创建（analyze 走 fallback → 双 cache + 双镜像 + 返回 interviewId；分析失败容忍；缺 interview 抛错）；ReviewDetail 应用反馈（EXPERIENCES cache + versionHistory + 镜像 + feedback.applied 标记）。通过 `vi.mock` auth/job/interview/tasks/experience 隔离后端。