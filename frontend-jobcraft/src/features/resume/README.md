# features/resume — 简历与定制

## 当前状态
- FE-RESUME-01 已迁移：`useResumesQuery` + 9 个 mutation 与 `ResumeEditorView` / `JDReportDetailView` 读写切到查询层；context 删除简历域 key（`resumes`/`setResumes` 与 resume 动作，零消费者后删除，**无 onSync 镜像**）。
- FE-RESUME-02 已闭环：AI 建议「生成 → 存储 → 应用 → 落库」全链路接通（生成器此前不存在、6 个 mutation 纯 cache 刷新即丢、「要点已保存」为假 toast，三个缺陷一并修复）。
- **T-M6-2 已切换**：简历域读写源从 `resume_submission` 切到 `resume_version`（V0022 存量快照迁 v1），resumeId 语义 = 版本 id 字符串；**AI 建议链暂挂空**（版本表无 `resume_suggestions` 列，见下方「建议域债务」）。

## 数据流
- **cache 权威**：`RESUMES_QUERY_KEY = ['resumes']`（`Record<versionId, ResumeVersion>` 键控对象，键为 resume_version id 字符串）。
- **水合**：`useResumesQuery` → `listResumeVersions()`（`GET /api/jobcraft/resume-version`，version_no DESC）→ 按 `job_analysis_id` 归组取最新（缺失回退 `job_id`，再回退版本 id）→ `markdownToResume` 解析（id 兜底元数据 = 版本 id）。**不再走 dashboard/getSubmission，也不再水合存量 `resume_suggestions`**（M6-3 接回）。
- **落库单一写入点**：`persistResumePatch(resumeId, patch)` → `PATCH /api/jobcraft/resume-version/{id}`；patch 中的 `resume_suggestions` 被剥离（版本表无此列），剥离后为空则跳过 API 返回 `false`；本地示例（id 非数字）跳过 API 返回 `false`，PATCH 失败上抛（视图 error toast）。
- **权威与镜像**：`jobs` 与 `prep`/`review` 等跨域依赖读各自 query，不读简历 cache；`useJobsQuery` 拉 `listResumeVersions` 按 analysis 归组，把 submission 行的 `customResume`/`resumeId` 重映射为版本 id（失败容忍，退回 dashboard `has_resume`）。

## 索引契约（`utils/resumeSuggestionMapper.ts`）
- `item_index` = `sections→items` 展平后的卡片全局序号；`bullet_index` = item 内要点序号；生成（`buildSuggestionBullets`）与水合（`hydrateResumeSuggestions`）共用同一套展平。
- 定位策略：index 命中且 `original_text`（trim）一致 → 应用可用；否则全文检索兜底；双不中 → `stale:true`（pending 展示「已失效」徽标、应用按钮禁用）。applied/rejected 历史照常展示不判 stale。
- `suggestionsToWire` 反向序列化落库（缺索引按 `targetBulletId` 反查，仍无则 0/0 交由下次水合判定）。

## hooks API
- `useResumesQuery()`：全量简历映射 `Record<versionId, ResumeVersion>`（aiSuggestions 恒为空，待 M6-3 按版本维度接回）。
- `useGenerateResumeSuggestionsMutation()`：**T-M6-2 暂停**，固定返回 `{generated:false, count:0, reason:'unavailable', synced:false}`（服务端 `resume_suggest` 链仍以 submission id 取数，直接调用会打错 id）；视图 toast「AI 建议待接入」。M6-3 以版本维度重构后接回。
- 变更（React Query v5，mutationFn 均为 async；返回 `{synced}`，失败上抛由视图 toast）：
  - `useApplyResumeAiSuggestionMutation`：改写 bullet + PATCH `{resume_markdown}`（`resume_suggestions` 被 persist 剥离）；运行时防错位（目标已删/原文已变 → 抛错提示重新生成，不覆盖用户编辑）。
  - `useRejectResumeAiSuggestionMutation`：仅含 `resume_suggestions` → 被剥离后无有效字段，**不打 PATCH** 返回 `synced:false`（视图提示「本地标记，改版后支持同步」）。
  - `useApplyAllResumeAiSuggestionsMutation`：批量改写（rejected/stale 跳过，目标失效条目标记 stale 不阻断），返回 `{synced, appliedCount}`，PATCH `{resume_markdown}`。
  - `useUpdateResumeBulletTextMutation` / `useDeleteResumeBulletMutation`：PATCH `{resume_markdown}`（**编辑即落库**），并把指向该要点的 pending 建议标 `stale`。
  - `useAddResumeBulletMutation`：PATCH `{resume_markdown}`；存量建议靠 `original_text` 全文兜底重定位（索引后移不判 stale）。
  - `useSaveResumeMutation`：id 合法 → `updateResumeVersion(versionId, { resume_markdown })`；NaN id（本地示例/未落库）→ 返回 `{saved:false, reason:'local'}`。
  - `useUpsertResumeMutation`：纯 cache 写（原 `setResumes` 的替换品），供 `JDReportDetailView` 写回；resumeId 来自 `saveResume` 返回的 `resume_version_id`。
  - `useGenerateResumeFromJdMutation`：`saveResume()` → `{resumeId: String(resume_version_id), resume}`（端点未回版本 id 或解析失败返回 null）。
- 所有 mutation 接受本地参数（不依赖当前 cache 快照）。

## 边界
- AI 简历生成由后端 `save-resume` 端点完成（写 resume_version，返回 `resume_version_id`），前端不实现 endpoint；suggest 链路（任务 + 同步端点）**暂挂空**，落库一律走 PATCH resume-version。
- **建议域债务（M6-3）**：`resume_suggestions` 无处持久化（V0021 无此列）、`suggestResume`/`resume_suggest` 任务仍打 submission id、存量 v1 无水合；矩阵已排「下线/重构 aiSuggestions 空壳 6 mutation」。
- 建议上限 12 条/次（后端清洗 + prompt 双侧约束）、wire 列表 ≤50（PATCH Schema 校验）。
- 历史简历域（底座简历 `base_resume`）已在 FE-HISTORICAL-RESUMES-01 迁移至 `features/historical-resumes`，Context 中无简历相关残留。
- FE-CONTEXT-REMOVE 时不再有 resume 相关双写可删（本域已零 consumer）。
