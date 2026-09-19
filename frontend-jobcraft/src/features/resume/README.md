# features/resume — 简历与定制

## 当前状态
- FE-RESUME-01 已迁移：`useResumesQuery` + 9 个 mutation 与 `ResumeEditorView` / `JDReportDetailView` 读写切到查询层；context 删除简历域 key（`resumes`/`setResumes` 与 resume 动作，零消费者后删除，**无 onSync 镜像**）。

## 数据流
- **cache 权威**：`RESUMES_QUERY_KEY = ['resumes']`（`Record<submissionId, ResumeVersion>` 键控对象，键为投递 id 字符串）。
- **水合**：`useResumesQuery` → `getCurrentUser` → `getDashboard` → 对有 `has_resume` 的投递逐条 `getSubmission` → `markdownToResume` 解析；单条失败容忍（该键缺失），无 console 输出。
- **权威与镜像**：`jobs` 与 `prep`/`review` 等跨域依赖读各自 query，不读简历 cache。

## hooks API
- `useResumesQuery()`：全量简历映射 `Record<submissionId, ResumeVersion>`。
- 变更（React Query v5，mutationFn 均为 async）：
  - `useApplyResumeAiSuggestionMutation` / `useRejectResumeAiSuggestionMutation` / `useApplyAllResumeAiSuggestionsMutation`：AI 建议 apply/reject（**纯 cache 操作**，不落库）。
  - `useUpdateResumeBulletTextMutation` / `useAddResumeBulletMutation` / `useDeleteResumeBulletMutation`：结构编辑，纯 cache。
  - `useSaveResumeMutation`：id 合法 → `updateSubmission(submissionId, { resume_markdown })`；NaN id（本地示例/未落库）→ 返回 `{saved:false, reason:'local'}`，由视图提示"本地示例不落库"。
  - `useUpsertResumeMutation`：纯 cache 写（原 `setResumes` 的替换品），供 `JDReportDetailView` 写回。
- 所有 "suggestion/bullet" 类 mutation 接受本地参数（不依赖当前 cache 快照），失败静默。

## 边界
- AI 简历生成由后端任务接口（提交任务→轮询）完成，前端不实现 endpoint。
- 历史简历域（底座简历 `base_resume`）已在 FE-HISTORICAL-RESUMES-01 迁移至 `features/historical-resumes`，Context 中无简历相关残留。
- FE-CONTEXT-REMOVE 时不再有 resume 相关双写可删（本域已零 consumer）。