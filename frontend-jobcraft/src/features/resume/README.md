# features/resume — 简历与定制

## 当前状态
- FE-RESUME-01 已迁移：`useResumesQuery` + mutation 集合与 `ResumeEditorView` / `JDReportDetailView` 读写切到查询层；context 删除简历域 key（`resumes`/`setResumes` 与 resume 动作，零消费者后删除，**无 onSync 镜像**）。
- FE-RESUME-02 旧建议链（生成→存储→应用→落库）已在 **T-M6-3** 整体下线：`aiSuggestions`/`AISuggestion` 类型、4 个建议 mutation（apply/reject/applyAll/generate）、建议面板、`resumeSuggestionMapper`、`suggestResume` API 全部删除；BE `resume-suggest` 端点与 `resume_suggest` 任务同步删除。
- **T-M6-3 新能力**：编辑器左栏 =「缺口任务」列，消费 JD 分析 `capability_gaps`（T-M4-2）：`rewrite` 缺口点「AI 改写」按中栏选中要点改写；`evidence` 缺口按 `card_id` 跳经历资产库补强。
- **T-M6-4 新能力**：中栏 =「结构化编辑器」（`components/resume/ResumeSectionsEditor.tsx`）：两级拖拽（原生 HTML5 零依赖）+ ↑↓ 备用、条目增删改名（删除经 `confirm`）、模块显隐开关、**双击直编**（单击=选中改写目标，双击=textarea 内联编辑）；落库双写 `{sections, resume_markdown}`。
- **T-M6-2 已切换**：简历域读写源从 `resume_submission` 切到 `resume_version`（V0022 存量快照迁 v1），resumeId 语义 = 版本 id 字符串。

## 数据流
- **cache 权威**：`RESUMES_QUERY_KEY = ['resumes']`（`Record<versionId, ResumeVersion>` 键控对象，键为 resume_version id 字符串）。
- **水合（T-M6-4：sections JSON 优先）**：`useResumesQuery` → `listResumeVersions()` → 按 `job_analysis_id` 归组取最新 → `markdownToResume` 解析头部；`normalizeStructuredSections(wire.sections)` 存在即**覆盖解析出的 sections**（顺序/显隐/id 稳定），不可回读时以最小头部 + 结构化兜底；`jobAnalysisId` 挂到简历上（T-M6-3 缺口任务列取数键）。
- **落库单一写入点（T-M6-4 双写）**：`persistResumePatch(resumeId, { resume_markdown, sections })` → `PATCH /api/jobcraft/resume-version/{id}`；`sections` = 结构化编辑权威（BE JSON 列不解释内容），`resume_markdown` = 派生导出（`resumeToMarkdown`：**hidden 模块跳过**、多模块全部落盘、全隐藏保底空骨架）；本地示例（id 非数字）跳过 API 返回 `false`，PATCH 失败上抛（视图 error toast）。
- **权威与镜像**：`jobs` 与 `prep`/`review` 等跨域依赖读各自 query，不读简历 cache；`useJobsQuery` 拉 `listResumeVersions` 按 analysis 归组，把 submission 行的 `customResume`/`resumeId` 重映射为版本 id（失败容忍，退回 dashboard `has_resume`）。

## 缺口任务列（T-M6-3 / M6-Q2 裁决）
- 取数：`resume.jobAnalysisId` → `useJdAnalysesQuery()` 找分析 → `capabilityGaps`（`JDAnalysis.capabilityGaps`，缺省归空）。
- `kind=rewrite`：点「AI 改写选中要点」→ `useRewriteResumeBulletMutation` → `POST /api/jobcraft/resume-version/{id}/rewrite`（1 次 LLM，缺口字段入参）→ 替换中栏选中 bullet → PATCH `{resume_markdown}` 落库；未点选要点 → info toast「请先点选要点」。
- `kind=evidence`：点「去经历资产库补强」→ `navigateTo('experiences', { expId: gap.cardId })`；无 `cardId` 按钮禁用。
- 严重度徽标：high=高/warning、medium=中/sage、low=低/faint（`SEVERITY_BADGE`）。

## 中栏结构化编辑（T-M6-4 / M6-Q6 裁决 A）
- 组件 `components/resume/ResumeSectionsEditor.tsx`（从 `ResumeEditorView` 拆出，业务变更与 toast 仍在视图层）。
- 交互：单击要点 = 选中（T-M6-3 AI 改写目标）；**双击文字 / 铅笔 = textarea 直编**（规避 contenteditable IME 坑）；模块与条目**两级原生 HTML5 拖拽**（grip 把手起拖、条目仅限同模块内）+ ↑↓ 备用按钮；条目删除经 `window.confirm`、条目标题双击内联改名、模块尾部「+ 添加条目」行。
- 模块显隐：`ResumeSection.hidden === true` → 编辑器灰色折叠卡 +「已隐藏」徽标（可恢复）；**导出 markdown 跳过隐藏模块**（prep/下载天然干净），全隐藏时保底空骨架保持可回读。
- 落库：全部经 `persistResumePatch` 双写 `{sections, resume_markdown}`；`resumeToMarkdown` 自 T-M6-4 起导出全部可见模块（核心能力由 summary 承载）。

## hooks API
- `useResumesQuery()`：全量简历映射 `Record<versionId, ResumeVersion>`（含 `jobAnalysisId`；sections JSON 优先水合）。
- `useRewriteResumeBulletMutation()`：`{resumeId, bulletId, gap}` → rewrite 端点拿 `rewritten_text` → cache 替换 → PATCH 双写；返回 `{synced, rewrittenText}`（本地示例/要点已不存在 → 抛错）。
- 变更（React Query v5，mutationFn 均为 async；返回 `{synced}`，失败上抛由视图 toast）：
  - `useUpdateResumeBulletTextMutation` / `useDeleteResumeBulletMutation`：PATCH 双写（**编辑即落库**）。
  - `useAddResumeBulletMutation`：PATCH 双写（追加 bullet，域能力）。
  - `useReorderResumeMutation`（T-M6-4）：两级重排，`scope:'section'|'item'`，id 定位（任一缺失抛错不静默乱序）；拖拽 drop 与 ↑↓ 共用。
  - `useToggleSectionHiddenMutation`（T-M6-4）：hidden 翻转，返回 `{synced, hidden}`。
  - `useAddResumeItemMutation` / `useRenameResumeItemMutation` / `useDeleteResumeItemMutation`（T-M6-4）：条目增删改名（标题空抛错；删除视图先 `confirm`）。
  - `useSaveResumeMutation`：id 合法 → `updateResumeVersion(versionId, { resume_markdown, sections })`；NaN id（本地示例/未落库）→ 返回 `{saved:false, reason:'local'}`。
  - `useUpsertResumeMutation`：纯 cache 写，供 `JDReportDetailView` 写回；resumeId 来自 `saveResume` 返回的 `resume_version_id`。
  - `useGenerateResumeFromJdMutation`：`saveResume()` → `{resumeId, resume}` 并挂 `jobAnalysisId`（端点未回版本 id 或解析失败返回 null）。
  - `useSyncResumePersonalInfoMutation`：profile 非空字段覆盖简历头部，PATCH 双写。
- 所有 mutation 接受本地参数（不依赖当前 cache 快照）。

## 边界
- AI 简历生成由后端 `save-resume` 端点完成（写 resume_version，返回 `resume_version_id`），前端不实现 endpoint。
- 旧建议 wire/列（`ResumeSuggestionWire`、`resume_suggestions` PATCH 字段、DB V0015 列与 Schema）**保留但 FE 不再读写**（DB 前向兼容只加不删）；FE 侧消费者已全部下线。
- 历史简历域（底座简历 `base_resume`）已在 FE-HISTORICAL-RESUMES-01 迁移至 `features/historical-resumes`，Context 中无简历相关残留。
- FE-CONTEXT-REMOVE 时不再有 resume 相关双写可删（本域已零 consumer）。
