# features/resume — 简历与定制

## 当前状态
- FE-RESUME-01 已迁移：`useResumesQuery` + 9 个 mutation 与 `ResumeEditorView` / `JDReportDetailView` 读写切到查询层；context 删除简历域 key（`resumes`/`setResumes` 与 resume 动作，零消费者后删除，**无 onSync 镜像**）。
- FE-RESUME-02 已闭环：AI 建议「生成 → 存储 → 应用 → 落库」全链路接通（生成器此前不存在、6 个 mutation 纯 cache 刷新即丢、「要点已保存」为假 toast，三个缺陷一并修复）。

## 数据流
- **cache 权威**：`RESUMES_QUERY_KEY = ['resumes']`（`Record<submissionId, ResumeVersion>` 键控对象，键为投递 id 字符串）。
- **水合**：`useResumesQuery` → `getCurrentUser` → `getDashboard` → 对有 `has_resume` 的投递逐条 `getSubmission` → `markdownToResume` 解析 → `hydrateResumeSuggestions(resume, detail.resume_suggestions)` 挂载存量建议（定位失败的 pending → `stale`）；单条失败容忍（该键缺失），无 console 输出。
- **落库单一写入点**：`persistResumePatch(resumeId, patch)` → `PATCH /api/jobcraft/submission/{id}`；本地示例（id 非数字）跳过 API 并返回 `synced:false`（视图 warning toast），PATCH 失败上抛（视图 error toast）。
- **权威与镜像**：`jobs` 与 `prep`/`review` 等跨域依赖读各自 query，不读简历 cache。

## 索引契约（`utils/resumeSuggestionMapper.ts`）
- `item_index` = `sections→items` 展平后的卡片全局序号；`bullet_index` = item 内要点序号；生成（`buildSuggestionBullets`）与水合（`hydrateResumeSuggestions`）共用同一套展平。
- 定位策略：index 命中且 `original_text`（trim）一致 → 应用可用；否则全文检索兜底；双不中 → `stale:true`（pending 展示「已失效」徽标、应用按钮禁用）。applied/rejected 历史照常展示不判 stale。
- `suggestionsToWire` 反向序列化落库（缺索引按 `targetBulletId` 反查，仍无则 0/0 交由下次水合判定）。

## hooks API
- `useResumesQuery()`：全量简历映射 `Record<submissionId, ResumeVersion>`（含水合后的 `aiSuggestions`）。
- `useGenerateResumeSuggestionsMutation()`：**生成/重生成**。bullets 前端结构化传入，JD 上下文服务端自取（前端不传 JD）；`runTaskOrSync('resume_suggest', {submission_id, user_id, bullets})`，任务系统不可用降级 `suggestResume` 同步端点；结果替换 pending、保留 applied/rejected 历史，PATCH `resume_suggestions` 落库。返回 `{generated, count, reason?: 'local'|'empty', synced}`。触发点：JD 报告「定制简历」生成成功后自动 fire（不阻塞跳转，失败仅 toast）+ 编辑器空态 CTA /「重新生成」按钮（编辑器打开不自动触发，省 token）。
- 变更（React Query v5，mutationFn 均为 async；返回 `{synced}`，失败上抛由视图 toast）：
  - `useApplyResumeAiSuggestionMutation`：改写 bullet + PATCH `{resume_markdown, resume_suggestions}`；运行时防错位（目标已删/原文已变 → 抛错提示重新生成，不覆盖用户编辑）。
  - `useRejectResumeAiSuggestionMutation`：仅 PATCH `{resume_suggestions}`（status=rejected）。
  - `useApplyAllResumeAiSuggestionsMutation`：批量改写（rejected/stale 跳过，目标失效条目标记 stale 不阻断），返回 `{synced, appliedCount}`，PATCH 两字段。
  - `useUpdateResumeBulletTextMutation` / `useDeleteResumeBulletMutation`：PATCH `{resume_markdown}`（**编辑即落库**），并把指向该要点的 pending 建议标 `stale`。
  - `useAddResumeBulletMutation`：PATCH `{resume_markdown}`；存量建议靠 `original_text` 全文兜底重定位（索引后移不判 stale）。
  - `useSaveResumeMutation`：id 合法 → `updateSubmission(submissionId, { resume_markdown })`；NaN id（本地示例/未落库）→ 返回 `{saved:false, reason:'local'}`。
  - `useUpsertResumeMutation`：纯 cache 写（原 `setResumes` 的替换品），供 `JDReportDetailView` 写回。
- 所有 mutation 接受本地参数（不依赖当前 cache 快照）。

## 边界
- AI 简历生成由后端任务接口（提交任务→轮询）完成；**建议生成同理**（`resume_suggest` 任务 + 同步端点兜底），前端不实现 endpoint；suggest 链路只算不写，落库一律走 PATCH。
- 建议上限 12 条/次（后端清洗 + prompt 双侧约束）、wire 列表 ≤50（PATCH Schema 校验）。
- 历史简历域（底座简历 `base_resume`）已在 FE-HISTORICAL-RESUMES-01 迁移至 `features/historical-resumes`，Context 中无简历相关残留。
- FE-CONTEXT-REMOVE 时不再有 resume 相关双写可删（本域已零 consumer）。
