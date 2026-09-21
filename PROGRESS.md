# PROGRESS.md — JobCraft 求职助手 · 状态与进度记忆

> 本文件用于追踪项目整体进度。AI 在每次会话结束或完成子任务时，必须更新本文件的对应板块。

## 生产评分策略 max + polish prompt 收口（2026-09-21，commits `8eba56b`/`1051877`）

- [x] **EVAL-PROD-001 生产评分策略切换 max(Local, LLM)**：依据 evaluation 消融结论（0.4/0.6 加权把 local 校准问题传染给 LLM 分——0 分 local 把 80 分 LLM 拉到 48；max 结构性等同纯 LLM 且保留零成本本地兜底）。`app/tools/jobcraft_analyze.py` 移除 `LOCAL_WEIGHT=0.4/LLM_WEIGHT=0.6`，新增 `FUSION_MODE="max"` + `_fuse_score()`，`compute_match`/`fuse_gap_scores` 改取两者较大者；`fuse_gap_scores` 返回 `score_weights` 改 `{"mode":"max"}`（对应端点已下线、无消费者）；`evaluation/strategies.py` Hybrid 镜像同步为 max；`evaluation/README.md`/`fusion.py` 标注生产已切换、hybrid_a 标记为历史权重。**单测锁定 max 语义**：`test_compute_match_uses_max_fusion`（local 100+llm 10→100 保本地分 / local 0+llm 80→80 不拉低 LLM）+ `fuse_gap_scores` 断言更新（card1 100 / card2 50 / unknown 70）。重测（中文真实 JD 回测、LLM 抖动量化、Regression 基线 v1.json，TASK-EVAL-018）按用户决策**待整体重构完成后统一做**
- [x] **EXP-POLISH-001 experience_polish prompt 修复**：`prompts/experience/polish_v1.txt` 指示"直接输出润色后的经历文本"（纯文本）与 `invoke_structured` 期望 schema JSON 不符（P0-2 保留风险）→ 新增 `polish_v2.txt`（明确输出单对象 JSON `{"polished_text": ...}`，禁止解释/前缀/Markdown 代码块）+ `polish_experience` 切 `load_prompt(version=2)`；新增单测 `test_polish_uses_json_structured_prompt_v2`（断言 prompt 含 polished_text/JSON、v1 纯文本指示消失）。真实模型验证待整体重构后统一回测
- [x] **验证**：`python scripts/check_encoding.py`（312 文件 0 warning）+ `ruff check/format` 全绿 + pytest **545 passed / 11 skipped**（+2 新增）+ 前端 tsc 0 错 + vitest **22 files / 124 passed** + `npm run build` ✅

## 已完成事项

### Phase B P1 收口 全部完成（2026-09-20，commits `31ef8d4`..`b66c5a7`）

- [x] **B-1（`31ef8d4`）**：合并双 QueryClient——删除 `App.tsx` 内嵌 QueryClientProvider，统一用 `main.tsx` 的 QueryProvider（消除 createQueryClient 双实例导致的缓存分叉）
- [x] **B-2（`766078b`）**：删除 `src/services/api` 死树；`InterviewPrepRecord` 收敛为 `api/types` 单一类型源
- [x] **B-3（`f44f87f`）**：后端 `db.py` 新增 `transaction()` 助手并覆盖 6 处多语句写（delete_submission/delete_job_analysis/soft-delete 等），原子提交/回滚
- [x] **B-4（`4f0e327`）**：投递/岗位删除改软删（`is_active` 标记），先 V0006 迁移，删除路径不再级联删 QA/records/preps（孤儿数据保留原件，前端列表过滤）
- [x] **B-5（`a317bca`）**：运行时 `_ensure_*` DDL 固化为正式迁移 + 防漂移单测（`test_migrations_runner_unit.py`，冻结 V0007 软删 SQL），防止逐请求 ALTER
- [x] **B-6（`b66c5a7`，FE-CONTEXT-REMOVE 清账）**：context 删除 4 域 state（jobs/experiences/jdAnalyses/interviews）+ 4 个 sync 镜像 + `createJob`/`loadExperiences`；navigateTo 不再由 jobId 推导 jdId（所有调用方显式传参）；9 组件 + MockInterviewModal + UserProfileView 全部迁移至 feature hooks（`useJobsQuery`/`useInterviewsQuery`/`useJdAnalysesQuery`/`useExperiencesQuery`，NewInterviewModal 用 `useCreateJobMutation`、UserProfileView 用 `refetchExperiences`）；hooks 移除 onSync 机制 + 空 `MutationOptions` 接口；5 个 query 测试改写为 cache 断言（CacheSpy/Seeder+CacheReader，删除 Mirror*）。context 现仅保留 auth + 导航过渡态 + 瞬态 UI
- [x] **验证（Phase B 全绿）**：后端 pytest 581 passed / 11 skipped + ruff 全绿（B-4 后）；前端 tsc 0 错 + vitest 20 files / **112 tests** + `npm run build` ✅ + `python scripts/check_encoding.py` 305 files 0 warning
- [x] **待办**：B-1..B-6 已推 origin/main（`427d585..936048f`，commit `936048f` 含本记录）
- [x] 留白已转 **Phase C P2 专项**（见下，2026-09-21 启动：C-2 已完成，C-1/C-3/C-4 待做）

### Phase C P2 专项（2026-09-21 启动，四个候选 → 见 TODO.md P3 区）

- [x] **C-2 FE-TOAST-CLEANUP-01 showToast setTimeout/cleanup**：auto-dismiss 从 context `showToast`（`JobCraftContext.tsx:170` 无清理 setTimeout）下沉到 `Toast.tsx` 新增 `ToastItem` 组件 `useEffect`（挂载 4s 计时 + 卸载 clearTimeout，`onDismiss` 用 ref 避免计时因引用变化重置）；context `showToast` 只入队；关闭按钮补 `aria-label="关闭通知"`。新增 `src/test/toast.test.tsx` 4 条单测（4s 自动消失 / 卸载后推进计时器不 setState 泄漏 / 点关闭立即消失 / 空态不渲染容器）。验证：vitest **21 files / 116 tests** 通过 + `npm run lint`（tsc 0 错）✅ + `npm run build` 通过 + check_encoding ✅。commit `4d820bc`
- [x] **C-3 FE-CONTEXT-MEMO-01 context 零 memo**（commit `f61f751`）：拆 `ToastProvider`（ToastState + ToastActions 双 context，`useToasts`/`useToastActions`，showToast/dismissToast `useCallback` 稳定化）；`JobCraftContext` 删 toast key，value 全量 `useMemo`（依赖表=state/action 引用），login/register/logout/navigateTo/saveInterviewDraft/clearInterviewDraft 全部 `useCallback`；16 个 showToast 消费者迁移 `useToastActions`；`App.tsx`（ToastProvider ⊃ JobCraftProvider）与 `test-utils` 同步包裹；新增 memo 隔离单测（触发 toast 不重渲染 useJobCraft 消费者）。验证：vitest **21 files / 117 tests** + tsc 0 错 + build + check_encoding ✅
- [x] **C-1 FE-NEWINTERVIEW-SPLIT-01 NewInterviewModal(1122→~500 行) 拆分**（commit `6f33d89`）：shell（状态编排+弹窗壳+stepper+footer）+ 4 个 Step 子组件——`JobSelectionStep`（岗位下拉 + 新建岗位内联表单含 JD 分析双写回填）、`InterviewDetailsStep`、`ResumeStep`、`AdditionalInfoStep`；草稿读写下沉 `interviewModalDraft.ts`（load 容错/读后删除/save/clear，收敛 `DRAFT_KEY`）；**ResumeStep 弃硬编码假简历（resume-1/2/3）**，接真实底座简历 `useHistoricalResumesQuery`（真实名称 + 上传时间 + 标签）；渲染样式与交互行为完全保持。新增 `src/test/resume-step.test.tsx` 3 条（真实列表渲染（断言无硬编码假简历）/ 选中详情 + 变更回调 / 无关联提示）。验证：vitest **22 files / 120 tests** + tsc 0 错 + build + check_encoding ✅
- [x] **C-4 FE-ENDPOINT-WIRE-01 9 个未接线端点清账（逐端点裁决）**（commit `f137c78` 后端 + `866de10` 前端）：**下线 10 端点**——`job/step1-ats-recommend`、`job/step2-gap-polish`（被 POST /analyze 取代）、`job/save-card-version`、`job/analyze-ats`（被 save-resume + analyze-ats-structured/split-jd 取代）、`job/{id}/resume-preview`（无前端预览接线）、`job/{id}/selected-cards`、`experience/export`（与 profile/export 重叠）、`experience/cards/batch`（前端单卡操作）、`experience/cards/{id}/versions` GET/POST（版本历史纯前端演进）；**保留** `experience/cards/search`（DEFERRED，DB-03 安全收口）。同步删除死 Workflow（run_step1/step2/analyze_ats/resume_preview 及其 State/schema；AtsRecommendAgent/GapPolishAgent 保留）与前端 4 个死 wrapper（step1AtsRecommend/step2GapPolish/saveCardVersion/getJobSelectedCards）+ 清理类型导入。测试删除对应用例。验证：ruff + pytest **543 passed/11 skipped**（净删 ~40 用例）+ tsc/vitest **120 passed**/build + check_encoding ✅

### 结构化 JD 报告降级展示 FE-JD-REPORT-01（2026-09-21，commit `422a312`）

- [x] **背景**：TODO「结构化结果报告视图」遗留——`analyze-ats-structured` 只产出 ATS 画像（岗位理解/技能/暗话），不产出匹配类字段（matchScore=0、whyMatch=''、skillGaps=[]、recommendedExperiences=[]、合成 id `jd-{ts}` 无真实 `job_analysis_id`），报告页需如实降级而非误导。
- [x] **修复（`JDReportDetailView.tsx` 3 处）**：
  - 结论卡片 `matchLabel`：`whyMatch || 'MATCH'` → `whyMatch || (hasMatchScore ? 'MATCH' : '待分析')`（matchScore=0 不再显示 MATCH）
  - 星标行条件渲染：有真实分数=金色满星 `data-filled="true"`，无分数=灰色占位星 `data-filled="false"`（`data-testid="verdict-stars"`）
  - `handleGoToResume` 加 `parseInt` NaN 守卫：结构化合成 id 不向 `/job/save-resume` 发 `job_analysis_id: NaN`，toast「暂无法生成简历，请先完成完整 JD 分析」并返回
- [x] **已确认的既有降级路径**（无需改动）：能力匹配/推荐经历/ATS 空区块占位文案、暗话解析正常展示、goal/risk「待分析」
- [x] **测试**：`src/test/jd-query.test.tsx` 新增 4 条（结论卡片降级：待分析·—·无 MATCH·无金色满星 / 区块降级占位+暗话正常 / 定制简历守卫不调 saveResume+toast / 有真实分数仍显示 MATCH 与金色满星）；全量 vitest **22 files / 124 tests** 通过 + `npm run lint`（tsc 0 错）+ `npm run build` + `python scripts/check_encoding.py`（312 文件 0 warning）✅

### 技术债收口 P1/P2（2026-09-20，commits `e29216a`/`88e76fb`/`731db68`/`27a51f0`/`1d45def`）

- [x] **FE-CONTEXT-REMOVE 首切（`e29216a`）**：删除孤立 `app/legacy/MainLayout.tsx` + `router/LegacyPageWrapper.tsx`；删除 context 死 surface（`user`/`updateUserProfile`/`nextActions`/`activities`/`aiSuggestions`/`terminateJob`/`resumeJob`/`deleteJob`/`deleteJDAnalysis`/`updateQuestionAnswer`/`addCustomQuestion`/经历域 4 writer/`loadJdAnalyses` 外部入口）；`WorkbenchView` `user`→`useProfileQuery`（`useProfileQuery` 为权威 profile 源）；删除死类型 ActivityLog/NextActionItem/AISuggestionCard。context 2324→461 行。验证：tsc/`npm run build`（616.60 kB）✅、113 tests ✅、check_encoding（307 文件）✅。**剩余范围**：4 域 state+4 sync 镜像（jobs/experiences/jdAnalyses/interviews 仍被未迁移视图读取）、`currentTab`/`navigateTo`/`selected*` 待 URL 驱动化后移除
- [x] **P1-1（`88e76fb`）**：`job_analysis_flow.py` legacy 单节点 3 次 LLM → 4 节点 StateGraph（`_run_legacy_ats`→`_run_legacy_score`→`_run_legacy_suggestions`→`_run_legacy_collate`），`JobAnalysisState` 增 cards/ats/jd_req/match/suggestions；行为不变。验证 `/job/analyze` + `resume_generate`（`tasks/handlers.py:43-66`）为存活路径（前端 `useCreateJdAnalysisMutation` runTaskOrSync fallback `analyzeJob`），仅重构不删端点。12 workflow + 22 api 测试 ✅，ruff ✅
- [x] **P1-2（`731db68`）**：`extract_flow.py` backfill LLM 循环 → `MAX_BACKFILL_CARDS=10` 上限 + 单卡失败容忍（结果增 `failed` 列表，向后兼容）。新增 tolerance/cap 单测 2；test_workflows_unit.py 31 ✅
- [x] **P2-1+P2-2（`27a51f0`）**：删除 `api/job.ts` 死 `uploadResume`（零消费者，`api/index.ts` re-export experience.ts 版）；**JD 分析列表 N+1 消除**——后端 `db_job.py` 新增 `_job_analysis_to_dict` 归一化（`get_job_analysis` 复用 + 补 `job_analysis_id` 双键修复潜伏契约 bug，`list_job_analyses` 单次 SQL 返回全量详情 + `_ensure_job_analysis_columns()`）；前端 `JobAnalysisDetail` 类型 + `useJdAnalysesQuery`/`loadJdAnalyses` 直接映射列表不再逐条 `getJobAnalysis`；`jd-query.test.tsx` 断言改 list 单次（`getJobAnalysis` 不被调）。`loadDashboard` 确认为单次 `getDashboard`（非 N+1）。前端 21 文件/113 tests ✅，build ✅，后端 TestJobList 18 ✅
- [x] **P2-3（`1d45def`）**：`GET /resume/download` 错误返回从 200+`{"error":...}` 改为统一错误中间件契约（403/404 + `error.code/message`，无前端消费者零风险）；`JobAnalyzePayload`/`GapPolishPayload`/`SaveResumePayload`/`InterviewPrepPayload` 的 `card_ids`/`selected_card_ids` 统一 `Field(default_factory=list)`，缺键不再 pydantic 422、交 handler 统一友好 400（`/export` 可选过滤参数语义保留；card_ids vs selected_card_ids 命名方差为各端点绑定单消费者，保留）。test_api_routes_unit.py 103 ✅
- [ ] 留白：`NewInterviewModal`(1056 行) 过大、context 零 memo 专项、`showToast` setTimeout/cleanup、9 个后端端点前端未接线、FE-CONTEXT-REMOVE 剩余（4 域镜像 + currentTab/navigateTo/selected*）

### 整体健康审查 + v2 Spec 差距分析（2026-09-20）

- [x] **审查结论落盘**：`docs/health-review-and-v2-gap-2026-09-20.md`——现状梳理/对标差距/P0-P2 问题+证据/三阶段解决方案。对照基线 `design-v2.0/`（14 份）+ `domain-model-v2` + `frontend-backend-contract-audit-v1` + `implementation-roadmap-v1`。
- [x] **验证**：后端 575 passed/11 skip、ruff 全绿、check_encoding 307 OK、前端 tsc/build/113 tests（会话内实测）
- [x] **关键结论**：架构分层/AI 审计链/迁移驱动 = 最强项；3 处 P0 规范违背（`mappers.ts:51` 已投递自动推导、`job_analysis_flow.py:435` 非 StateGraph 入口、`experience_polish.py:38` 绕道 llm_json）
- [x] **Phase A P0 修复（3 项完成，commits `0b58c34`/`bd8a9b4`/`ff0a8fc`）**：P0-1/P0-2/P0-3 详见下方"Phase A P0 修复"章节 → Phase B P1 收口 → Phase C P2（详见报告）

### Phase A P0 修复（2026-09-20，commits `0b58c34`/`bd8a9b4`/`ff0a8fc`）

- [x] **P0-2（`0b58c34`）**：`experience_polish.py` 从 `llm_json.invoke_structured` 直连改为统一出口 `experience_polish.invoke_structured` 的 `PolishOutput` 结构化（审计/缓存/观测链补齐）；新增 `TestExperiencePolish` 单测 3（结构化 schema、空输出兜错、LLM 失败兜错）。**原保留风险已解除（2026-09-21，EXP-POLISH-001）**：`polish_v1.txt` 纯文本指示与 `invoke_structured` JSON 期望不符 → 新增 `polish_v2.txt`（JSON 指示）+ 切 `load_prompt(version=2)`；真实模型验证待整体重构后统一回测
- [x] **P0-3（`bd8a9b4`）**：`job_analysis_flow.py` 新增 `StructuredATSState`（forward）并以 `conda_edge` 把 3 阶段节点拼接为 StateGraph `run_structured_ats_workflow`；`run_structured_ats` 保持兼容包装，行为不变；相关 workflow/api 测试通过
- [x] **P0-1（`ff0a8fc`）**：已投递改为用户确认（规范 §9.3：投递状态不得自动推导）。后端 `migrations/versions/V0006__submission_delivered.sql` 新增 `delivered TINYINT(1) DEFAULT 0`（仅加列，前向兼容）；`db_submission.py` ensure/insert/get/get_by_analysis/update/`get_dashboard` 全链 `delivered`；`api/submission.py` `UpdateSubmissionPayload.delivered` + 手动录入投递置 `delivered=1`。前端 `types/jobcraft.ts` JobStatus 新增 `'submitted'`（已投递）；`mappers.ts` `applied: sub.delivered ?? false` + `backendId`，`deriveJobStatus` 优先级 `terminated>prepStage>reviewStage>applied(submitted)>jdAnalysis(delivered)>pending`；`hooks.ts` 新增 `useSetDeliveredMutation`（先 PATCH 后端、失败仅本地乐观、写 cache `steps.applied` + `deriveJobStatus` + onSync 镜像）；`useTerminateJobMutation` 不再自动置 `applied:true`（避免误标已投递）；JobsListView 行内"标记已投递/取消已投递"、JobWorkspaceView header "标记已投递"、submitted 徽标/文案/过滤药丸。验证：后端 581 passed/11 skip、`ruff check`/`format` 全绿、check_encoding 307 OK、前端 tsc + vitest **115 tests** + `npm run build` ✅

### FE-HISTORICAL-RESUMES-01 历史简历域迁移（2026-09-19，commit `7eece93`/`c0c3d72`）

- [x] **`features/historical-resumes/mappers.ts`**：`HISTORICAL_RESUMES_QUERY_KEY = ['historical-resumes']` + `baseResumeToHistoricalResume`（自 context 内联映射提取，单一事实来源）
- [x] **`features/historical-resumes/hooks.ts`**：`useHistoricalResumesQuery`（listBaseResumes → map，失败 `[]` 兜底）；`useAddHistoricalResumeMutation`（createBaseResume 成功回填 `serverId` 后前置入列，失败仅内存保留，toast 归视图层、无 console / 不写零消费者 activities）；`useDeleteHistoricalResumeMutation` / `useSetDefaultHistoricalResumeMutation`（后端成功后再写 cache，对齐 experiences delete 模式；无 serverId 仅本地操作）
- [x] **视图迁移**：`UserProfileView`（query 读 + 3 mutation，删除/设默认 await 后各自的成功/失败 toast）；`CreateInterview`（query 读 + add mutation，`handleFileUpload`/`handleSimulatedDrop` 两路径；`hr-upload-{ts}` 选择器 quirk 保留）
- [x] **context 清理**：删除 `historicalResumes` 域全部 key（`HistoricalResume` 导入 / interface 成员 / state / `loadHistoricalResumes` 与启动水合 / 3 action / provider value）
- [x] **测试**：`src/test/historical-resumes-query.test.tsx`（6：列表渲染/计数/默认徽标、删除成功移除（断言 `deleteBaseResume(serverId)`）、删除失败保留、设默认徽标迁移（断言 `setDefaultBaseResume`）、新增落库回填 serverId 入列、落库失败内存兜底）；全量 **21 文件 / 113 测试全绿**，`npm run lint`（tsc）、`npm run build`、`python scripts/check_encoding.py` 通过
- [x] **文档**：重写 `features/historical-resumes/README.md`；更新 `features/resume/README.md` 边界
- [x] 已提交（commit `7eece93`/`c0c3d72`）；已 push
- [ ] 留白：FE-CONTEXT-REMOVE（删 syncJobs/syncExperiences/syncJdAnalyses/syncInterviews 镜像与双写）+ `activities`/`nextActions`（零消费者）

### FE-RESUME-01 简历编辑域迁移（2026-09-19，commit `b34268d`/`52b3afe`）

- [x] **`features/resume/mappers.ts`**：`RESUMES_QUERY_KEY = ['resumes']`（`Record<submissionId, ResumeVersion>` 键控对象）
- [x] **`features/resume/hooks.ts`**：`useResumesQuery`（getCurrentUser → getDashboard → has_resume 逐条 getSubmission → markdownToResume，单条失败容忍、无 console）；9 个 mutation——AI 建议 apply/reject/applyAll、bullet 编辑（updateText/add/delete）为**纯 cache 操作**；`useSaveResumeMutation`（合法 id → updateSubmission；NaN id → `{saved:false,reason:'local'}` 供视图 warning）；`useUpsertResumeMutation`（纯 cache 写，替换 `setResumes`）；React Query v5 下 7 个纯 mutation 全部 async
- [x] **视图迁移**：`ResumeEditorView`（读 `useJobsQuery`/`useResumesQuery`/`useExperiencesQuery`，`activeResumeId` 改局部 state，apply/reject/applyAll/edit/delete 走 mutation，save 按 `result.saved` 分支 toast）；`JDReportDetailView`（删死 `resumes` 解构，改 `useUpsertResumeMutation`）
- [x] **context 清理（本域零消费者 → 无 onSync 镜像）**：删除 `Submission`/`ResumeVersion`/`resumeParser` 导入、interface `resumes`/`setResumes` + resume actions 块、state 声明、loadDashboard 内联简历水合（含 `console.error('Load resume failed...')`）、L697–971 方法块、provider value 11 个 key；grep 验证残留 "resumes" 仅 tab 名
- [x] **测试**：`src/test/resume-query.test.tsx`（9：空态/水合渲染/应用单条/忽略/全部应用/编辑要点/删除要点/保存草稿/upsert）；修复建议注入标题精确匹配（渲染为带序号前缀，改正则）；全量 **20 文件 / 107 测试全绿**，`npm run lint`（tsc）、`npm run build`、`python scripts/check_encoding.py` 通过
- [x] **文档**：重写 `features/resume/README.md`（数据流/hooks API/边界）
- [x] 已提交（commit 待填）；已 push
- [ ] 留白：FE-CONTEXT-REMOVE（删 syncJobs/syncExperiences/syncJdAnalyses/syncInterviews 镜像与双写）

### FE-REVIEW-01 面试复盘域写入迁移（2026-09-19，commit `a1d1d8a`）

- [x] **`features/review/mappers.ts`**：6 个纯映射 helper（`buildReviewPatchFromAnalysis` / `buildReviewFromPatch` / `nextExperienceVersion` / `applyProposedChanges` / `applyFeedbackSuggestions` / `buildVersionRecord`），score 一律来自真实分析数据，无伪造评分
- [x] **`features/review/hooks.ts`**：`useCreateInterviewReviewMutation`（legacy `createReviewFromTranscript` 等价：cache 解析面试 → `createInterviewReview` 落库 → `runTaskOrSync('interview_review_analyze')` 降级 `analyzeInterviewReview` 180s；分析失败容忍保 base patch；onSuccess 写 INTERVIEWS cache + 跨域 JOBS cache steps done + 双镜像）；`useApplyReviewFeedbackMutation`（legacy `applyReviewFeedback` 等价，**修复漂移 bug**：写 EXPERIENCES cache + 镜像，不再只 setExperiences；不写零消费者 activities）
- [x] **视图迁移**：`InterviewReviewCenterView`（读 `useInterviewsQuery`）、`InterviewReviewDetailView`（`useApplyReviewFeedbackMutation` + 镜像注入 + await + toast + 按钮 pending 态）、`CreateReview`（`useJobsQuery`/`useInterviewsQuery`/`useCreateInterviewReviewMutation`，await 后 `navigateTo('interview_review_detail')`，失败停留 + toast）
- [x] **context 清理**：删除 `addInterviewReview` / `applyReviewFeedback` / `syncReviewToExperience` / `createReviewFromTranscript` / `commitExperienceDiff`（接口+实现+provider）与 `buildReviewPatchFromAnalysis`；收敛 import（去 `tasksApi` / `InterviewReviewResult` / `InterviewReview` / `InterviewQA`）
- [x] **测试**：`features/review/mappers.test.ts`（11）+ `src/test/review-query.test.tsx`（6：create 双写双镜像/分析失败容忍/缺面试抛错、apply 缓存+镜像（漂移修复断言）/suggestions 兜底、Center 读路径过滤）；全量 **19 文件 / 98 测试全绿**，`npm run lint`（tsc）、`npm run build`、`python scripts/check_encoding.py` 通过
- [x] **文档**：新增 `features/review/README.md`；更新 `features/interview/README.md` / `features/experiences/README.md` 镜像数据流
- [x] 已提交（commit `a1d1d8a`），已 push

### FE-ROUTE-03 E2E 路由验证测试（2026-09-18，commit `c94f574`）

- [x] **基础设施**：安装 `@playwright/test` + chromium 浏览器；新增 `playwright.config.ts`（webServer 启动 Vite E2E 模式、chromium only）+ `vite.e2e.config.ts`（端口 5174、CORS 宽松）
- [x] **`e2e/helpers.ts`**：`loginWithTestUser` — localStorage 注入 Supabase session + user，绕过真实 OAuth 流程
- [x] **`e2e/routes.spec.ts`**（15 用例全绿）：认证与重定向（2）、侧边栏导航（5：我的经历/我的岗位/JD分析/面试准备/面试复盘）、工作台卡片跳转（2）、详情路由直连（4：经历/JD报告/简历/复盘详情）、刷新保持路由（1）、AppShell 内两步跳转（1）
- [x] **测试命令**：`npm run test:e2e`（`npx playwright test --project=chromium`）
- [x] 已提交（commit `c94f574`）

### 编码防线：`scripts/check_encoding.py` + CI 强制（2026-09-17，commit `01d8f26`/`0ce6f20`）

- [x] **`scripts/check_encoding.py`**：全仓扫描 `UnicodeDecodeError`（ANSI/GBK 重写）、`U+FFFD`、常见 mojibake 片段（`锟斤拷`/`ï¿½`/`â€`/`Ã©` 等）；跳过 `.git`/`node_modules`/`dist`/`venv`/`output` 等目录与锁文件；BOM 仅对代码/配置类文件告警；错误退出码 1
- [x] **`.pre-commit-config.yaml`**：新增 `check-encoding` local hook（`always_run`）；**注意**：`pre-commit` 未安装到项目环境，hook 目前不自动生效，需 `pre-commit install` 或依赖 CI
- [x] **CI 强制**：`.github/workflows/ci.yml` 在 lint 前新增 `Check file encoding` 步骤（推送/PR 即校验）
- [x] **`AGENTS.md`（本地 gitignored）**：§2 绝对红线补「禁止用 PowerShell 文本 cmdlet 写源文件」；§5 验证命令补 `python scripts/check_encoding.py`
- [x] **验证**：Guard 自测（GBK 写入 CJK → 捕获并 exit 1，探针已清理）；全仓 350 文件 0 error / 0 warn；`uv run ruff check scripts/` 通过
- [x] **顺带修复**：剥离 `frontend-jobcraft/src/test/jobs-route.test.tsx` 的冗余 UTF-8 BOM（commit `3eb72f4`），该测试回归通过

### FE-ROUTE-03 剩余 tab 路由补全 + 导航收敛（2026-09-17，commit `1201afa`）

- [x] **`src/router/tabPaths.ts`**：`tabToPath(tab, params)` 作为 tab→URL 单一映射（全 `NavigationTab` 覆盖）+ `useTabNavigate()`（签名对齐 legacy `navigateTo`，只做导航，选中项副作用交 `useSyncRouteTab`）
- [x] **路由表补全**：新增 AppShell 真实路由页 `/experiences(/:experienceId)`、`/prep/:interviewId`、`/review/:interviewId`、`/jd-report/:jdId`（+ `/jobs/:jobId/jd/:jdId` 别名）；补齐 legacy URL `/jd-analysis`、`/resume(/:jobId)`、`/prep`、`/interview/new`、`/review`、`/review/new`；`*` 兜底改 `<Navigate to="/workbench" replace/>`
- [x] **新增页面**：`features/experiences/pages/ExperiencesPage.tsx`、`features/interview/pages/InterviewPrepPage.tsx`、`features/review/pages/InterviewReviewPage.tsx`、`features/jd/pages/JdReportPage.tsx`（均 `useSyncRouteTab` + Outlet modal openers）
- [x] **导航收敛（修复 AppShell 内 `navigateTo` 静默失效）**：`WorkbenchView`(4)、`TopHeader`(3)、`Sidebar`(navItems)、`NewInterviewModal`(2)、`MockInterviewModal`(1)、`JDReportDetailView`(7)、`ExperiencesView`(1)、`InterviewPrepWorkspaceView`(1)、`InterviewReviewDetailView`(1)、`MainLayout`(2) 改用 `useTabNavigate`
- [x] **`ExperiencesView.initialSelectedExpId` 接线**：`/experiences/:experienceId` 命中时自动打开对应经历编辑弹窗（一次性 ref 防重复）
- [x] **测试**：新增 `src/test/routes-03.test.tsx`（15：tabToPath 全映射、各新路由渲染、未知路径重定向、AppShell 内两处跳转生效）；全量 `npm test` **15 文件 / 63 测试全绿**，`npm run lint`（tsc）、`npm run build` 通过
- [x] **文档**：新增 `src/router/README.md`（路由表 + 两宿主职责 + tab→URL 约定）
- [x] 已提交（commit `1201afa`）；未 push
- [ ] 留白：legacy 中心 / 创建 / 简历编辑视图（`JDAnalysisCenterView`/`CreateInterview`/`CreateReview`/`ResumeEditorView`/`UserProfileView`/`InterviewPrepCenterView`/`InterviewReviewCenterView`）内部 `navigateTo` 未收敛（context 驱动仍生效，URL 滞后）；`currentTab` / `LegacyPageWrapper` / `MainLayout` 保留待 FE-CONTEXT-REMOVE

### FE-JD-01 JD 分析域数据层迁移（2026-09-17，commit `3d777f7`）

- [x] **`features/jd/mappers.ts`**：`analysisToJD`（分析结果→JDAnalysis）自 context 移出 + `analysisDetailToJD`（getJobAnalysis 详情→JDAnalysis，含 dimension_requirements→skillGaps/goal）从 `loadJdAnalyses` 内联映射提取 + `JD_ANALYSES_QUERY_KEY`；context 改 import（映射单源，消除两套构造）
- [x] **`features/jd/hooks.ts`**：`useJdAnalysesQuery`（getCurrentUser → listJobAnalyses → 逐条 getJobAnalysis → analysisDetailToJD，保持 legacy N+1 语义、单条失败跳过）；`useDeleteJdAnalysisMutation`（仅 cache 过滤 + `sub-{number}` 时尝试 deleteSubmission；`onSync` 注入镜像）
- [x] **context 改造**：`syncJdAnalyses` 镜像写入；`loadJdAnalyses`/createJDAnalysis/createStructuredJDAnalysis/deleteJDAnalysis 五处单向双写 cache（`setJdAnalyses` + `setQueryData`）
- [x] **视图迁移**：`JDAnalysisCenterView`（历史列表/搜索/计数读 query，删除走 mutation + 视图层补 toast）与 `JDReportDetailView`（按 analysisId 从 query 命中，`isLoading` 改用 query）读写切 hooks；**创建（createStructuredJDAnalysis）与非目标消费者保持 legacy**
- [x] **测试**：`features/jd/mappers.test.ts`（4：analysisToJD 映射/兜底、analysisDetailToJD skillGaps/goal）+ `src/test/jd-query.test.tsx`（4：历史列表+搜索+镜像、删除 cache 过滤且真实 id 不请求后端、sub-N 触发 deleteSubmission、报告页按 id 命中）；全量 `npm test` **14 文件 / 48 测试全绿**，`npm run lint`（tsc）、`npm run build` 通过
- [x] **文档**：新增 `src/features/jd/README.md`（数据流/权威与镜像/hooks API/create 边界）；`features/jd-analysis/README.md` 改为指向 `features/jd`
- [x] 已提交（commit `3d777f7`）；未 push
- [ ] 留白：JD create 编排（自动建 Job + runTaskOrSync + 同步返回 id）仍 legacy（FE-JD-01 遗留/后续 task）；`JobWorkspaceView`/`NewInterviewModal`/`MainLayout` 仍读 context 镜像；FE-CONTEXT-REMOVE 时删除 `syncJdAnalyses` 与双写

### FE-EXPERIENCES-01 经历域数据层迁移（2026-09-17，commit `ffbc9b1`）

- [x] **`features/experiences/mappers.ts`**：`cardToExperience`（achievements→actions/results、tags→capabilityTags、version→currentVersion）+ `EXPERIENCES_QUERY_KEY`；context 原私有实现删除、改 import（映射单源）
- [x] **`features/experiences/hooks.ts`**：`useExperiencesQuery`（getCurrentUser → listCards → cardToExperience）；create/update/delete mutations（后端调用成功→cache 更新→`onSync` 镜像）；`useAddExperienceVersionMutation`（纯本地 cache 内 versionHistory 演进，不发网络请求）
- [x] **context 改造**：`syncExperiences` 镜像写入；`loadExperiences`/create/update/delete/addExperienceVersion 单点双向双写 cache；review 落盘写入方（syncReviewToExperience/commitExperienceDiff）保持 context 直写（过期偏差窗口接受）
- [x] **视图迁移**：`ExperiencesView`（含行内 EditExperienceModal）+ `NewExperienceModal` 读写切 hooks；toast 归位视图层（消除 legacy 双重 toast，删除补 `经历已移除`）
- [x] **测试**：`mappers.test.ts`（3）+ `experiences-query.test.tsx`（5：渲染/分类/搜索、create 前置+镜像、update patch+镜像、delete 过滤+镜像、本地版本演进）；全量 `npm test` **12 文件 / 40 测试全绿**，lint（tsc）、build 通过
- [ ] 留白：`ResumeEditorView`/`JDReportDetailView`/`UserProfileView` 仍读 context 镜像；review→经历落盘走 context 直写双写；`/experiences` 路由待 FE-ROUTE-03

### FE-ROUTE-02 工作台/岗位列表/岗位空间真实路由迁移（2026-09-17，commit `1b49e8c`）

- [x] **路由表**：`/workbench`、`/jobs`、`/jobs/:jobId` 改走 `<AppShell/>` 真实路由（页面：`src/features/jobs/pages/{WorkbenchPage,JobsPage,JobWorkspacePage}.tsx`），移除对应 LegacyPageWrapper；`jd_report`/`prep`/`review`/`experiences` 保持 legacy
- [x] **`useSyncRouteTab(tab)`**（`src/router/useSyncRouteTab.ts`）：URL→context `navigateTo` 同步钩子，LegacyPageWrapper 与三个新页面共用（sidebar 高亮/面包屑/selectedJobId 跟 URL 走）
- [x] **AppShell `<Outlet context>`**：`AppShellOutletContext`（onOpenNewJob/onOpenMockInterview/onOpenNewInterview）+ `useAppShellOutlet`；补齐 MockInterview/NewInterview modal openers
- [x] **导航收敛到 react-router**：WorkbenchView（6 处）、JobsListView（1 处）、NewJobModal（创建后 `/jobs/{id}?tab=jd`）、JobWorkspaceView（返回 `/jobs`、复盘 `/review/{id}`、准备 `/prep/{id}`）、TopHeader 面包屑（3 处）、Sidebar（workbench/jobs 2 项）
- [x] **测试**：router.test 升级为真实路由断言（AppShell 壳 + 视图，5 个用例）；新增 `jobs-route.test.tsx`（工作台/岗位列表点击 → `/jobs/:jobId` 岗位空间直达，2 个用例）；全量 `npm test` **10 文件 / 32 测试全绿**，`npm run lint`（tsc）、`npm run build` 通过
- [x] 已提交（commit `1b49e8c`）；未 push
- [ ] 留白：jobId 变化时子 tab 重置 jd；`?tab=` 仅作初值（深度链接等于 activeTab 初值）；`ResumeEditorView` 嵌入式返回按钮仍走 context（无视觉副作用）；`currentTab` 在真实路由内由 useSyncRouteTab 维护，遗留 navigateTo 依旧不改 URL（FE-ROUTE-01 同款过渡行为）

### FE-JOBS-01 岗位领域查询层迁移（2026-09-17，commit `e29df4c`）

- [x] **`src/features/jobs/mappers.ts`**：`JOBS_QUERY_KEY`、`submissionToJob`（DashboardItem → Job 归一）、`deriveJobStatus`（steps → status 单一事实源），context 与 hooks 共用，删除 context 内重复实现
- [x] **`src/features/jobs/hooks.ts`**：`useJobsQuery`（getCurrentUser → getDashboard → submissionToJob）；`useCreateJobMutation`（本地乐观 Job → createSubmission 回填 id/backendId，失败静默；mutateAsync 返回最终 Job 供跳转）；`useLocalJobPatchMutation` 基类 + `useTerminateJobMutation`/`useResumeJobMutation`（纯本地 steps 更新，重新 `deriveJobStatus`）
- [x] **三视图迁移**：`JobsListView` / `NewJobModal` / `WorkbenchView` 改读 hooks（loading 态、terminate/resume 走 mutation + 保留 toast、create 成功 toast + 用回填 id 跳转 job_workspace）；删除对 context `jobs/terminateJob/resumeJob/createJob` 的依赖
- [x] **context 过渡镜像**：`syncJobs`（hooks 变更 → context），legacy writers（loadDashboard/createJob/terminateJob/resumeJob/deleteJob）反向 `setQueryData` 双写 cache；`JobCraftProvider` 内持 `queryClient`
- [x] **实测修复回归**：`App.tsx` 原缺 `QueryClientProvider`（context 加了 `useQueryClient` 后未登录即崩溃，app.test 捕获；已包 provider）；`useLocalJobPatchMutation` 原先只改 steps 不重算 status → 补 `deriveJobStatus(steps)`；legacy-pages 两用例改异步（query loading 态）
- [x] **测试**：`mappers.test.ts`（映射/优先级，5）＋ `jobs-query.test.tsx`（list 渲染、create 前置写入 + 镜像同步、terminate/resume 乐观更新、workbench 统计，4）；全量 `npm test` **9 文件 / 29 测试全绿**，`npm run lint`、`npm run build` 通过
- [x] `src/features/jobs/README.md`：数据流（cache 权威 + context 镜像）、hooks API、新视图迁移清单
- [x] 已提交（commit `e29df4c`，11 文件 +610/-71）；未 push（等待用户指示）
- [ ] 留白：`deleteJob` 未迁 hooks（无调用方）；活动列表新增项原 createJob 行为在 NewJobModal 迁移后小偏差；JobWorkspace/JD/Interview/*Create 仍读 context 镜像（FE-ROUTE-02 / FE-JOBS-02 等后续任务）；FE-CONTEXT-REMOVE 时删除 `syncJobs` 与双写

### FE-ROUTE-01 路由迁移试点 Profile（2026-09-17，commit `f0b8151`）

- [x] 实机验证（Playwright + 本地后端 8000 / vite 5173，测试账号 `pw_verify_2026`）：
  - 注册登录 → 自动进入 `/workbench`（legacy MainLayout）✓
  - 直接访问 `/profile`：AppShell 壳 + UserProfileView 正常（`账号设置`/`职业资产`/`求职中 · 积极沟通`），无需 LegacyPageWrapper ✓
  - `/profile?tab=preferences`：偏好子 tab 打开（`意向职位方向`）✓
  - 头像下拉点「求职偏好」→ URL 变 `/profile?tab=preferences` 且子 tab 切换 ✓
  - `/workbench` 回归正常（不渲染 profile banner）✓
- [x] **实测发现并修复**：SPA 客户端内从 `/profile` 跳 `/profile?tab=preferences` 时元素复用不重挂载，`initialTab` 不生效 → `UserProfileView` 增加 `initialTab` 变化同步 effect（commit `3ad1a13`）；直接 URL 加载回归正常
- [x] 遗留说明：新用户登录后 `loadHistoricalResumes` 请求返回 404（历史简历接口对空数据行为，JobCraftContext 遗留逻辑，非本次回归）；验证用临时 vite 配置（proxy→8000，因 vite.config 代理指向 AI Studio 的 8001）已删除，未入库

- [x] **`src/app/AppShell.tsx`**：应用壳（Sidebar + TopHeader + `<Outlet/>` + 3 全局 Modal + Toast），与遗留 `MainLayout` 并行存在，互斥渲染
- [x] **`/profile` 真实路由**：`<Route path="/profile" element={<AppShell/>}>` → `ProfilePage`（`?tab=` 解析 → `UserProfileView.initialTab`），移除该路由的 `LegacyPageWrapper`
- [x] **入口 router 驱动**：TopHeader 头像下拉四子项由 `navigateTo('user_profile',{profileTab})` 改为 `navigate('/profile?tab=...')`；spec 偏差说明：profile 入口实际在 TopHeader（Sidebar 无此项），双模导航落点随入口调整，已同步更新 `tasks/FE-ROUTE-01.md`
- [x] **测试**：router.test `/profile` 断言升级（AppShell 壳 + UserProfileView 直接渲染 + `?tab=preferences` 打开求职偏好）；全量 `npm test` **7 文件 / 20 测试全绿**，`npm run lint`、`npm run build` 通过
- [x] 已知留白：/profile 真实路由后 TopHeader 面包屑不再显示「个人中心」（过渡期接受）；`UserProfileView.initialTab` 为最小 prop 扩展，遗留 `userProfileTab` 仍作兜底

### FE-QUERY-01 查询层试点 Profile（2026-09-17，commit `368cfdb`）

- [x] **`src/features/profile/hooks.ts`**：`useProfileQuery`（queryKey `['profile']`，合并 `getCurrentUser`+`getProfile` 映射领域 `UserProfile`，getProfile 失败降级 auth 侧）；`useUpdateProfileMutation`（`toApiProfilePatch` snake_case 映射 → `authApi.updateProfile`，成功后 `setQueryData` 乐观合并缓存，不整页 refetch）；`EMPTY_PROFILE` 空态与 context 对齐
- [x] **组件迁移**：`TopHeader`（头像/姓名/角色）与 `UserProfileView`（banner + 资料表单 + 求职偏好 chips）改读 hooks，不再从 context 读取 `user`；保存/增删 chip 走 `saveProfile()`（成功/失败 toast 保持原 UX）
- [x] **测试**：`hooks.test.tsx`（合并映射/降级/mutation 缓存断言/字段映射，4）＋ `src/test/profile-query.test.tsx`（TopHeader 渲染 + 保存调用断言，2）；全量 `npm test` **7 文件 / 19 测试全绿**，`npm run lint`、`npm run build` 通过
- [x] 明确留白：读/写字段映射与 context `updateUserProfile` 内联实现重复 → FE-CONTEXT-REMOVE 收敛唯一 mapper；`authApi.getProfile/updateProfile` 的 `Record<string,unknown>` 弱类型保留
- [x] 无后端 / DB / AI 改动；未删 context `user` / `updateUserProfile`

### FE-ARCH-00 前端架构基础设施（2026-09-17，commit `dce9933`）

- [x] **路由与查询层**：`@tanstack/react-query` Query Provider；`src/router/AppRouter.tsx` 路由表（`/workbench`、`/jobs/:jobId`、`/jobs/:jobId/jd/:jdId`、`/prep/:interviewId`、`/review/:reviewId`、`/experiences(/:experienceId)`、`/profile`）+ `LegacyPageWrapper` 桥接遗留 `navigateTo`
- [x] **API 客户端骨架**：`src/services/api/{client,errors,types}.ts`，token 注入/超时/`{error:{code,message,details,requestId}}` 契约对齐，无业务 endpoint
- [x] **过渡层**：`MainLayout` 迁移至 `src/app/legacy/MainLayout.tsx`，旧导航/视图切换保持工作
- [x] **边界占位**：`src/features/{jobs,experiences,jd-analysis,resume,interview,review,historical-resumes}/README.md`
- [x] **测试基础设施**：vitest 4.x + jsdom + testing-library（`npm test`，13 项基础设施测试全绿；`npm run lint`、`npm run build` 通过）
- [x] **遗留类型契约修复**（引入 @types/react 后暴露，纯类型修正）：`setResumes` 补入 context interface/value；`JDReportDetailView`/`ResumeEditorView` 的 navigateTo 参数修正；`createJob`/`createInterview` 异步契约对齐调用方；`ExperienceVersionRecord.source` 补 `'ai_optimization'`

- [x] 项目基础骨架搭建（FastAPI + React + Vite + uv）
- [x] 经历卡抽取与编辑功能
- [x] 岗位分析（JD 解析、匹配评分、优化建议）
- [x] 面试准备稿生成（按维度分类预测题 + 答题要点）
- [x] 面试复盘基础版本（QA 配对、评分、反馈）
- [x] 解析预览功能（说话人拆分 + QA 配对预览）
- [x] QA 配对优化：过滤闲聊/过渡/确认发言，拆分语音转文字错误
- [x] LLM 输出约束：问题/回答/身份由规则 QA 对权威提供，避免身份反调与跳跃
- [x] 详细复盘分析：intent、expected_answer、feedback、suggestions 结构化输出
- [x] 面试复盘三段式流程：解析预览（含意图识别）→ 问题表汇总 → 详细解析
- [x] 问题表生成与落库：`/api/jobcraft/interview-review/{id}/question-table`
- [x] 勾选问题详细解析：`/api/jobcraft/interview-review/{id}/analyze`，结合 JD 与经历卡生成结构化标准答案
- [x] 前端问题表汇总页面：表格展示全部问题，支持调整勾选并触发详细解析
- [x] 前端结果页区分「已详细解析」与「未详细解析」问题
- [x] API 错误统一：FastAPI 全局异常处理返回 `{code, msg, data}` 格式
- [x] 前端类型同步：根据 `app/schemas/jobcraft.py` 生成 `frontend-jobcraft/src/types.ts`，并在 `api.ts` 重新导出
- [x] Harness 工程基线文件：AGENTS.md、PRODUCT.md、ARCHITECTURE.md、PROGRESS.md
- [x] 代码审查规范与记录文档：新增 [`docs/CODE_REVIEW.md`](docs/CODE_REVIEW.md)，沉淀审查触发条件、检查清单、扫描脚本及历次审查问题与修复记录

### v0.2 经历卡架构重构

- [x] **产品设计决议**：保持 REST API + 直接 LLM 调用（非多 Agent 架构）
- [x] **产品设计决议**：裁剪公司背调功能（搜索不准、缺免费 MCP、偏离核心价值）
- [x] **产品设计决议**：经历卡存储模型改为 `raw_text + tags + ai_structured 缓存`，STAR 结构化按需即时抽取
- [x] **产品设计决议**：公司/角色/时间段从经历卡主力字段降级为可选补充信息
- [x] **产品设计决议**：标签平铺扁平（不分类/不层级），由 LLM 推荐 + 用户手动编辑
- [x] 新增 Schema：`Achievement` / `AchievementAction` / `CardStructuredCache`（`app/schemas/jobcraft.py`）
- [x] 新增 Schema：`ExperienceCardCreate` / `ExperienceCardUpdate`（统一请求体验证）
- [x] 重构 `ExperienceCardSchema`：`raw_text` 为主力输入，旧字段降级为兼容存量数据
- [x] 重写 `jobcraft_extract.py`：从「简历→多张卡」改为「raw_text → achievements[] + 标签推荐」
- [x] 新增 `extract_structured()`：单段 raw_text → 结构化缓存（S/A/R 含困难与解决）
- [x] 新增 `recommend_tags()`：raw_text → 3-5 个扁平标签
- [x] DB 迁移：`experience_card` 表新增 `raw_text`（LONGTEXT）与 `ai_structured`（JSON）列
- [x] DB 迁移：自动回填旧数据的 raw_text（从 content/summary 派生）
- [x] 更新 `db_tools._row_to_card()`：新架构优先，旧字段向下兼容

### v0.3 岗位分析模块重构

- [x] **产品设计决议**：ATS 解析 + 推荐卡片合并为一次 LLM 调用
- [x] **产品设计决议**：缺口分析 + 润色建议合并为一次 LLM 调用
- [x] **产品设计决议**：新流程 4 步（ATS+推荐 → 用户审批 → 缺口+润色 → 用户编辑 → 生成简历）
- [x] **产品设计决议**：裁剪公司背调功能，删除独立路由
- [x] **产品设计决议**：简历生成改为纯模板拼装，不再调用 LLM
- [x] **产品设计决议**：定制文本存 `card_versions` 表，不修改原卡
- [x] 新增 `card_versions` 表（`db_tools.py`）：`insert_card_version` / `get_card_version` / `get_card_versions_by_source`
- [x] 新增 `ats_and_recommend()`：ATS 解析 + 推荐卡片（合并一次 LLM 调用）
- [x] 新增 `gap_and_polish()`：缺口分析 + 润色建议（合并一次 LLM 调用）
- [x] 更新 `_card_text_blob()`：匹配源优先 ai_structured → raw_text → tags
- [x] 删除 `_safe_company_context()` 及相关引用
- [x] 新增 3 个 API 路由：`/step1-ats-recommend`、`/step2-gap-polish`、`/save-card-version`
- [x] 删除 `/api/jobcraft/company/search` 路由
- [x] 简历生成器模板化（`jobcraft_resume_gen.py`）：30 行纯模板，无 LLM
- [x] 前端 `JobPage.tsx` 重写为 3 步流程：JD 输入 → 卡片选择 → 缺口编辑+简历
- [x] 前端新增 AI 推荐卡片展示、缺口诊断面板、内联编辑框、版本保存

### v0.4 求职系统 CRM 化重构

- [x] **产品设计决议**：JD 分析改为原子功能，不绑定卡片/流程
- [x] **产品设计决议**：求职路线为主页，投递记录作为 pipeline 核心
- [x] **产品设计决议**：面试准备/复盘改为从投递记录进入，不占导航位
- [x] **产品设计决议**：JD 分析库独立可用，支持不关联投递单独使用
- [x] 新增 `resume_submission` 表 + DAO CRUD（`db_tools.py`）
- [x] `interview_preps` 表新增 `submission_id` 字段
- [x] `interview_records` 表新增 `submission_id` + `round_label` 字段
- [x] 后端新增路由：`/submission`（CRUD）、`/dashboard`、`/selected-cards`
- [x] 后端更新：面试准备/复盘支持 `submission_id` 传入
- [x] `interview_pre.py`：优先读 `card_versions` 润色版本 + `raw_text`
- [x] 前端路由重构：`useRoute.ts` 支持参数化路由（prep/:id / review/:id）
- [x] 导航侧边栏精简为 3 项：🏠求职路线 / 📋经历卡 / 🔍JD 分析库
- [x] 新增 `CareerRoutePage.tsx`：投递时间线，每条含状态 + 5 步按钮矩阵
- [x] 新增 `JDAnalysisPage.tsx`：独立 JD 分析工作台
- [x] 重写 `InterviewPrepPage.tsx`：从投递进入，自动带出岗位/JD/卡片
- [x] 适配 `InterviewReviewPage.tsx`：支持 `submissionId` 传入，预填公司/岗位
- [x] **CRM 流程优化**：投递记录改为简历生成的副产品，不再支持手动新建
- [x] Dashboard 只返回有 `resume_markdown` 的记录，空壳投递自动排除
- [x] `CareerRoutePage.tsx`：移除「新建投递」按钮，空状态引导用户去 JD 分析库
- [x] `JDAnalysisPage.tsx`：「创建投递」→「为该 JD 定制简历」，无经历卡片时自动跳转至创建卡片页
- [x] **简历生成全流程打通**：JD 分析 → 检查卡片 → step2 润色（弹窗展示）→ saveResume → createSubmission（自动带 resume_markdown）→ 跳转首页

### v0.5 面试准备增强 + 手动补录

- [x] **产品设计决议**：主页卡片按钮重排为「📄简历→🔍JD分析→📝润色→🎤面试准备→📝复盘」
- [x] **产品设计决议**：按钮 4 态（todo/done/locked/ready），逐步骤引导
- [x] **产品设计决议**：手动补录为主线操作，不再使用独立向导弹窗
- [x] **产品设计决议**：不支持 Word 导出，仅 MD 下载
- [x] `resume_submission` 表：新增 `is_manual` 字段
- [x] `interview_preps` 表：新增 `company_research_json` + `company_research_at` 字段
- [x] `POST /api/jobcraft/submission/manual`：手动上传简历 → 解析文本 → 抽取经历卡 → 创建投递
- [x] `CareerRoutePage.tsx` 重写：新按钮顺序 + 4 态渲染 + 上传简历弹窗 + 粘贴 JD 弹窗
- [x] `_build_interview_prompt()` 增强：公司调研 + 已投简历 + 上一轮复盘摘要
- [x] 面试准备路由自动加载公司调研（Tavily + 7天缓存）和已投简历
- [x] 多轮衔接：自动提取上一轮复盘摘要传给 prompt
- [x] `list_interview_records_by_submission()`：按投递 ID 查面试记录

## v0.6 Agent Workbench 重构（已完成）

- [x] **Phase 1 基础设施**：创建 `app/core/`、`app/workflows/`、`app/agents/`，实现基类（`base_agent.py`、`structured_caller.py`、`workflows/base.py`）
- [x] **Phase 2 清理**：删除 DeepAgents 系统（`app/agent/`、`app/prompt/`、`app/ragflow/`、`markdown_tools.py`、`pdf_tools.py`、`ragflow_tools.py`、深智能体路由、WebSocket）
- [x] **Phase 3 面试复盘迁移**：拆分规则引擎，实现 Multi-Agent Workflow（Router → Tech/Soft → Gate）
  - Agent 节点：router_agent.py、tech_analyzer.py、soft_analyzer.py、gate_agent.py
  - Workflow：interview_review_flow.py（StateGraph, 6 个节点, 条件边）
  - 入口：run_interview_review_workflow(record_id, selected_sequences, user_id)
  - server.py 路由已接入（/api/jobcraft/interview-review/{id}/analyze）
  - 旧 analyze_selected_questions / _build_analysis_prompt / analyze_interview_record 等函数已清理
- [x] **Phase 4 其余功能迁移**：岗位分析、面试准备、经历卡抽取、问题表迁移为 Workflow + Agent（LLM 全部下沉 agents）
  - 新增 10 个 Agent 节点（单职责、最多 1 次 LLM 调用）：extract_agent（ExtractStructured/ParseResumeEntries/RecommendTags）、jd_ats_agent、ats_recommend_agent（Step1 合并）、score_match_agent、gap_polish_agent（Step2 合并）、sug_agent、interview_prep_agent、question_table_agent、question_intent_agent、company_research_agent
  - `job_analysis_flow.py`：run_step1_workflow / run_step2_workflow（GapPolishAgent + fuse_gap_scores 本地40%+LLM60%）/ 旧版完整分析 / run_analyze_ats_workflow / run_resume_preview_workflow
  - `question_table_flow.py`：3 节点（load_record → generate_intents → persist）
  - `interview_prep_flow.py`：纯函数构建 prompt → InterviewPrepAgent → 落库
  - `extract_flow.py`：extract / recommend_tags / parse_resume_entries / run_backfill_workflow（新拆卡流程）
  - **tools 纯化**：删除 `jobcraft_extract.py`/`jobcraft_jd_ats.py`/`jobcraft_company.py`；`jobcraft_analyze.py` 重写为纯函数（compute_match/fuse_gap_scores/build_rule_suggestions）；`interview_pre.py`/`interview_review.py`/`db_tools.backfill` 的 LLM 逻辑拆到 agents；`app/tools/` 下已无 LLM 调用（唯一例外 llm_json.py 底层封装）
  - server.py 全部路由改走 workflow/agent（/analyze、/analyze-ats、/resume-preview、/step1、/step2、/backfill、/upload、/interview-prep 等）
  - 新增单测：`test_fuse_gap_scores_unit.py`（5 个）+ `test_agents_mock_unit.py`（14 个 mock）
  - ruff check/format ✅ · pytest 65 passed/11 skipped ✅ · npm run build ✅
- [x] **Phase 5 闭环迭代（v0.6 新功能）**：跨JD聚合、跨复盘聚合、反哺经历卡 → 本期裁剪，长期方向记录于此（JD 列表选中生成岗位画像 + To C 埋点），暂不开发

### v0.7 Bug 修复 + 功能补全（本轮）

- [x] **Bug 1 - source 截断**：ENUM→VARCHAR(100) ALTER TABLE + insert_card None-handling
- [x] **Bug 2 - entrypoint 缺失**：5 个 workflow 补 `add_edge(START, ...)`
- [x] **Bug 3 - 无变更弹窗提示**：ExperiencePage 编辑弹窗加 dirty-check
- [x] **Bug 4 - AI 调用全挂**：修正 .env 模型名 `glm-4-flash` + DB 库名 `jobcraft`
- [x] **Bug 5 - company 缺失 422**：payload required + route 校验 + 前端补齐
- [x] **Bug 6 - batch delete 白屏**：注册 `DELETE /api/jobcraft/job/analyze/{job_id}` 路由
- [x] **Bug 7 - JD→工作台白屏**：注册 `#/job/:jobId` 路由
- [x] **Feature A - 加载耗时提示**：JD 分析 + 卡片结构化显示秒数 + 首次提示词
- [x] **Feature B - STAR 编辑弹窗**：DetailModal 支持编辑 summary + S/A/R
- [x] **Feature C - 卡片层级确认**：保持 achievements[] 为工作事项，不拆分表
- [x] **Feature D - JD CRUD**：详情、搜索、批量删除、分页
- [x] **Feature E - JD→卡片导航**："进入定制工作台" → `#/job/:jobId`
- [x] **Feature F - 简历上传 AI 解析**：`parse_resume_entries()` 拆条→多卡
- [x] **Feature G - 卡片简历格式展示**：扁平列表 + 公司/角色/时间段标题
- [x] **Feature H - 缺口分析增强**：过滤学历要求，使用 D1-D8 8 维能力评估
- [x] **匹配评分闭环（评审反馈）**：step2 每卡补算本地关键词分，与 LLM 语义分按 4:6 融合，返回 `overall_score` + `match_level` + 每卡 `local_score/llm_score`；前端展示整体匹配等级与评分对比（本地 X ｜ LLM Y ｜ 融合 Z）
  - `PerCardScore` / `CardGapItem` 增加 `local_score` / `llm_score` 字段（前向兼容，默认 0）
  - 抽取 `_local_score()` helper，`compute_match` 与 `gap_and_polish` 共用

### v0.8 暗话分析 + 简历生成（进行中）

- [x] **暗话分析（JD 潜台词解码）**：`SubtextDecode` schema + `ATSProfile.subtext_decoded` 字段
- [x] `ats_and_recommend()` 任务三：JD 潜台词解码（3-6 条），同步写入 ats.subtext_decoded
- [x] `gap_and_polish()` 把暗话作为评估维度：可推导能力给 'polish' 建议显性化而非判缺失
- [x] 前端 JobPage / JDAnalysisPage 展示暗话分析卡片
- [x] `api.ts` 增加 `SubtextDecode` 类型 + step1 返回类型收紧
- [x] **简历生成预设排版**：`generate_resume_html()` A4 模板（header + 技能标签 + 经历条目）
- [x] **个人信息补充**：`ResumePersonalInfo` schema + 前端 Modal 表单 + localStorage 持久化
- [x] **HTML 预览**：save-resume 返回 `resume_html`，JobPage iframe srcDoc 渲染，落盘 .md + .html
- [x] **PDF 导出**：`window.print()` 方案（新窗口写入 HTML → 打印对话框），无新依赖
- [x] 修复 `npm run build` 失败：清理 ExperiencePage useRef / JDAnalysisPage Modal+selectedAnalysis 未使用导入
- [x] **测试基建修复**：调试脚本重命名 `check_*.py` 避免 pytest 收集报错；e2e 加 `server_available` 跳过保护
- [x] **单元测试扩充**：新增 `test_resume_gen_unit`(10) / `test_jobcraft_analyze_unit`(10) / `test_misc_unit`(9)，共 39 passed（无 LLM/DB 依赖）
- [x] 修复 `_split_bullets` 未过滤 `**背景**：xxx` 加粗行（简历 HTML 混入噪声）
- [x] **前端性能优化**：Vite `manualChunks` 拆分 vendor（react-vendor / antd-vendor / vendor），消除循环 chunk；`chunkSizeWarningLimit` 调至 1000；`App.tsx` 全部 6 个页面改为 `React.lazy()` 懒加载 + `Suspense` fallback，每页独立 chunk（3~18KB）
  - 产物从单一 1.19MB 拆为：入口 5.6KB + react-vendor 144KB + antd-vendor 964KB(300KB gzip) + 各页面 3~18KB
  - 首屏只加载 dashboard，其他 5 页按需加载；vendor chunk 长期缓存
  - React Router 迁移暂缓（用户确认后续再考虑），当前 6 页面自研 hash 路由够用

## 进行中事项

- [x] **缺口分析多维评估**：可迁移能力、领域经验、量化成果对标（v0.9 已完成：`dimension_analysis`/`transferable_skills`/`domain_overlap`/`quantified_note`）
- [x] **卡片内容回填**：旧数据单卡含整份简历 raw_text 的拆分功能（v0.9 已完成，已用真实数据验证）
- [x] **恢复之前版本的缺口分析能力**：git 调查确认无被删旧版，当前为超集（v0.9 已归档结论）
- [x] **PDF 一键下载**：已引入 html2canvas+jspdf 实现静默下载（v0.9 已完成）

### v0.9 极简编辑风格 + 四项待办（本轮）

- [x] **极简编辑视觉风格落地**：`index.css` 重写为 `--jc-*` 设计系统（暖米白底、祖母绿强调色 `#0f6b52`、灰阶文字、hairline 边框、Fraunces 衬线标题、12px 圆角、40px 页边距）；`main.tsx` ConfigProvider 主题 token；`App.tsx` 品牌区（J 方块 + 衬线字标）与返回链接 `jc-back-link`；`CareerRoutePage.tsx` 上传图标改主题色。`npm run build` 通过。
- [x] **卡片内容回填（拆分旧数据整卡）**：
  - `db_tools.py` 新增 `_looks_like_full_resume()`（3 种启发式：时间范围 ×2 / 简历章节标题 ×2 / 素材库 `#### 经历N` 标题 ×2）+ `_rebuild_entry_text()` + `backfill_resume_cards()`
  - 复用 `parse_resume_entries()` 拆条，每段经历新建一卡，原卡归档（`is_active=0` 可恢复）
  - 新路由 `POST /api/jobcraft/experience/cards/backfill`；前端 ExperiencePage 新增「拆分历史整卡」按钮
  - 已用真实库数据验证：4 张「素材库」整卡拆为 4 张独立经历卡，原卡归档，无数据丢失
- [x] **缺口分析多维评估 + 恢复旧版能力**：
  - git 调查结论：历史上不存在被删的更完善缺口分析，当前 `gap_and_polish` 已是超集（D1-D8/暗话解码/溢出启发式）
  - `CardGapItem` 新增 `dimension_analysis`（D1-D8 逐维打分+证据）、`transferable_skills`、`domain_overlap`、`quantified_note`（前向兼容默认空）
  - prompt 增补多维评估输出指令；前端 JobPage 新增「多维评估」面板（维度分/可迁移能力/领域契合/量化对标）
- [x] **PDF 一键静默下载**：引入 `html2canvas` + `jspdf`（新增依赖已写入 package.json），`JobPage.tsx` 新增「一键下载 PDF」（离屏容器 → 截图 → A4 多页切分）；保留 `window.print()` 打印入口，原「导出 PDF」按钮改为「打印」
- [x] 测试与规范：新增 5 个回填单测（`_looks_like_full_resume` / `_rebuild_entry_text`）；`uv run pytest tests/ -q` 45 passed、11 skipped；`ruff check/format` 通过；前端 `npm run build` 通过

### v0.10 hallmark audit 落地（本轮）

- [x] **建立设计文档**：新建 `docs/UI_DESIGN.md`，记录「极简编辑」设计系统唯一事实来源（token/字体/圆角/间距/布局/响应式/无障碍/版本历史）
- [x] **C1 token 化**：`index.css` 扩充语义 token（success/warn/info/danger 及浅底、`--jc-bg-3`、`--jc-muted` 加深至 `#6f6c63`）；6 个页面全部内联裸色值改 `var(--jc-*)`（仅 PDF 离屏容器保留 `#ffffff` 以保 A4 白底）
- [x] **C2 响应式**：`html,body{overflow-x:clip}`；`.jc-card-grid` 改 `minmax(min(320px,100%),1fr)`；CareerRoute 动作按钮 `Space wrap`；页面头行 `flex-wrap`；复盘双栏抽成 `.jc-review-cols` 并在 ≤768px 折叠单列
- [x] **M1 字体**：`index.css` 顶部 `@import` Google Fonts 加载 Fraunces（离线回退 Georgia/Songti）
- [x] **M2 对比度**：`--jc-muted` 由 `#8a877e`（≈3.3:1）加深为 `#6f6c63`（≈4.5:1）；`main.tsx` 菜单/表头辅助色同步
- [x] **M3 图标**：`🎤`→`AudioOutlined`、`📝`→`FormOutlined`、`◀`→`ArrowLeftOutlined`、`📌` 移除（`CareerRoutePage/App/ExperiencePage`）
- [x] **M4 去嵌套卡**：JobPage/JDAnalysisPage 暗话、多维评估、改写/补充建议等子 `Card` 全部改带背景的 div 块
- [x] **M5 可点击语义化**：`App.tsx` 返回链接 span→`Button type="link"`；InterviewReview 维度筛选 Tag→`Button`
- [x] **m3/m5 细节**：`.jc-card` 动效加 `prefers-reduced-motion` 降级；补圆角/间距 token（`--jc-radius-sm/xs`、`--jc-space-*`）
- [x] 验证：`npm run build` 通过（tsc 严格）；`uv run ruff check .` 通过；`uv run pytest tests/ -q` 51 passed、6 skipped

### v0.11 UI 迭代（本轮）

- [x] **重复标题修复**：`App.tsx` 主页面（dashboard/experience/jd-analysis）不再渲染全局 Header，仅子页面渲染含返回按钮的 Header；三个主页面内部统一用 `.jc-page-header` 标题，6 条路由均无重复标题（Playwright 实测）
- [x] **经历卡分类分组**：后端 `experience_card` 新增 `card_type`（work/intern/project），Schema/DAO/SQL/前端类型/表单全链路打通；列表按「工作经历（含实习）」与「项目经历」分组展示
- [x] **列表收敛**：经历卡列表只显示 `renderSummary` 摘要，STAR 要点收进详情弹窗
- [x] **删除后停留**：Collapse 分组用稳定 key + `defaultActiveKey`，删除卡片后分组保持展开、停留卡片页
- [x] **编辑/详情合一**：经历卡卡片操作按钮去掉独立「编辑」，只留「详情」；详情弹窗基础字段（类型/标题/描述/标签）+ S/A/R 结构化字段全部可编辑，一次 PATCH 保存（`updateCard` 已支持）
- [x] **求职路线视觉化**：`CareerRoutePage` 重写为路线流卡片——每条投递一张 `.jc-route-card`，5 步流程（简历→JD 分析→润色→面试准备→复盘）以圆形状态节点 + 连接线呈现（done/todo/ready/locked 四种状态配色），小屏自动折叠为纵向；按钮去掉内联 style 改用 `.jc-route-*` token 类
- [x] 验证：`npm run build` 通过（tsc 严格）；`uv run ruff check .` 通过；`uv run pytest tests/ -q` 65 passed、11 skipped

### v0.12 求职路线 + 经历卡 + JD 库体验优化（本轮）

- [x] **需求1 - 求职路线空态 UI + 简历可查看**：`CareerRoutePage` 空态不再用 `Empty`，改为固定 5 步流程面板（简历→JD分析→润色→面试准备→复盘，`.jc-route-*` 圆形节点+连接线），顶部提供「上传已投简历」入口（原有上传逻辑不变，新记录自动添加）；已投简历的投递记录上点击「简历」按钮可查看简历原文弹窗（`getSubmission` → `resume_markdown`，复用 `.jc-resume-preview` 样式）
- [x] **需求2 - 经历卡上传拆分 + 公司聚合**：
  - 后端 `upload` 与 `submission/manual` 路由：逐段解析简历 → 每段重建原文（`_rebuild_entry_text`，不再整份简历存 raw_text）、识别 `card_type`（work/intern/project）、保留 parse 出的 `ai_structured{summary,achievements}` 缓存、同公司+同岗位去重（`find_card_by_company_role` + 内存 seen 集合）
  - `ParseResumeEntriesAgent` prompt 增加 card_type 判定规则；`ResumeExperience` schema 加 `card_type` 字段；`split_resume_card_by_entries` 回填同步加 card_type + 去重
  - 前端 `ExperiencePage` 改为**按公司分组**（同公司一个折叠组、组内不同岗位并列），组内同公司+同岗位兼容去重（老数据），标题旁展示「项目/实习」类型 Tag；卡片保留「详情/AI 分析/标签/删除」
- [x] **需求3 - JD 列表去掉多余「查看」按钮**：`JDAnalysisPage` 岗位名称可点击查看详情，删除操作列的「查看」按钮（保留删除）
- [x] **需求4 - 缺口分析与简历拼接用 STAR + 一页纸原则**：
  - 缺口分析匹配源 `_card_text_blob` 已优先 `ai_structured.achievements`（S/A/R 拼接），无 STAR 才回退原文——需求本体已满足
  - 简历拼接 `generate_resume_html` 每张经历卡 bullet 截断为最多 4 条，控制 A4 一页篇幅
- [x] 验证：`npm run build` 通过；`uv run ruff check .` 通过；`uv run pytest tests/ -q` 70 passed、6 skipped；上传接口实测 3 段简历拆 3 卡（不同公司/岗位）、raw_text 逐段、去重生效

### v0.13 技术债清理（本轮）

- [x] **CI 修复**：`frontend-ci.yml` 移除不存在的 `npm run lint` 步骤；`ci.yml` 移除无效的 DB 环境变量（e2e 测试通过 `server_available` fixture 自动跳过）
- [x] **api.ts 统一错误处理**：新增 `requestFormData<T>()` 函数复用 `request<T>` 的错误解析逻辑；`uploadResume`/`uploadInterviewReview`/`parseInterviewReviewPreview`/`createManualSubmission` 四个 FormData 函数改为调用 `requestFormData`，消除重复手写错误处理
- [x] **ExperiencePage 去 raw fetch**：`handleStructure`/`handleRecommendTags` 改为调用 `api.ts` 的 `structureCard()`/`recommendTags()`，统一走 `request<T>` 错误处理链路
- [x] **全局 ErrorBoundary**：新增 `components/ErrorBoundary.tsx`，在 `App.tsx` 的 Suspense 外层包裹，捕获 JS 渲染错误并展示友好降级 UI
- [x] **初始 loading 状态**：ExperiencePage / InterviewPrepPage / JobPage 补全局 `Spin` spinning 状态，消除数据加载期间的空白闪烁
- [x] **评分权重常量化**：`jobcraft_analyze.py` 提取 `LOCAL_WEIGHT = 0.4`、`LLM_WEIGHT = 0.6` 常量，`compute_match`/`fuse_gap_scores` 两处引用统一
- [x] **前后端阈值对齐**：`JobPage.tsx` 匹配等级颜色阈值从 70/40 改为 80/60/40，与后端 `_match_level()` 一致；评分构成文案改用常量计算
- [x] **PDF 库动态 import**：`html2canvas`/`jspdf` 从静态 `import` 改为 `handleDownloadPdf` 内 `import()` 动态加载，减少主 bundle 体积
- [x] **类型清理**：`api.ts` 新增 `SuggestionItem`/`JobAnalysisRecord`/`Step1AtsProfile` 接口；`analyzeJob` 参数类型从 `any` 改为具体类型；`listJobAnalyses` 返回类型从 `any[]` 改为 `JobAnalysisRecord[]`；`JDAnalysisPage` 的 `analyses`/`result`/table 列全部消除 `any`；`JobPage` 的 `ats` 从 `any` 改为 `Step1AtsProfile`
- [x] 验证：`uv run ruff check .` 通过；`uv run ruff format .` 通过；`uv run pytest tests/ -q` 65 passed、11 skipped；`npm run build` 通过（tsc 严格）

### v0.14 项目结构重新梳理（本轮）

- [x] **.gitignore 清理**：移除过时的 `app/output`、`app/updated`、`frontend/` 等路径，统一为 `/output/`、`/updated/`、`/_preview_test.txt`
- [x] **tests/ 调试脚本归类**：13 个 `check_*.py` / `parse_*.py` 调试脚本移入 `tests/debug/` 子目录，pytest 不再收集
- [x] **docs/ 历史文档归档**：7 个历史文档（ACCEPTANCE_CRITERIA / EXECUTION_PLAN / SUMMARY / PROJECT_MINDMAP / REVIEW / REFACTORING_*）移入 `docs/archive/`
- [x] **server.py 拆分**：2086 行 → 222 行（App 初始化 + health/tasks），业务路由拆为 5 个 APIRouter 模块：
  - `experience.py`（494 行）：12 个经历卡路由
  - `job_analysis.py`（236 行）：10 个岗位分析路由
  - `submission.py`（174 行）：6 个投递记录 + dashboard 路由
  - `interview_prep.py`（104 行）：3 个面试准备路由
  - `interview_review.py`（323 行）：8 个面试复盘路由
- [x] **db_tools.py 拆分**：1960 行 → 220 行（连接配置 + re-export），业务 CRUD 拆为 5 个实体模块：
  - `db_experience.py`（658 行）：经历卡 + card_versions + company_research
  - `db_interview.py`（360 行）：面试准备/复盘 CRUD
  - `db_submission.py`（275 行）：投递记录 + dashboard
  - `db_job.py`（125 行）：岗位分析 CRUD
  - `db_user.py`（121 行）：用户 CRUD
  - 向后兼容：`from app.tools.db_tools import insert_card` 仍然可用
- [x] 验证：`uv run ruff check .` 通过；`uv run ruff format .` 通过；`uv run pytest tests/ -q` 65 passed、11 skipped；`npm run build` 通过

## 待办事项（v0.6 之后）

- [ ] 面试复盘长文本稳定性优化（Groq TPM 限制下的平衡）— Multi-Agent 重构后单 Agent prompt 降至 1500~2000 tokens，显著缓解
- [ ] 经历卡与 JD 匹配的 LLM 评分校准
- [ ] 用户注册/登录（Non-Goal，排期在 MVP 之后）

## 已知问题 / 技术债

- [ ] **LLM TPM 限制**：面试复盘长文本当前仅分析前 8 个核心 QA 对，需在详细度与分析数量之间继续平衡。
- [ ] **语音转写错误处理**：部分复杂反问/插话（如“对吧？对，然后...”）切分仍有边界 case。
- [x] **API 错误统一**：`app/api/server.py` 已添加全局异常处理器，所有接口统一返回 `{code, msg, data}`；工具层异常由 Controller 层兜底转换。
- [x] **前端类型同步**：当前版本已根据 `app/schemas/jobcraft.py` 手工生成 `frontend-jobcraft/src/types.ts`，并在 `api.ts` 重新导出；长期仍待建立自动生成机制。
- [x] **代码质量工具**：已将 `ruff` 加入 `pyproject.toml` 的 dev 依赖组，ruff check / format 通过。
- [x] **pytest 环境问题**：已清理模块级 API 调用导致的 pytest 收集崩溃；`uv run pytest tests/ -q` 当前在正确端口下可运行（7 passed, 6 skipped, 3 errors 源于 8000 端口被非本项目服务占用，非代码问题）。
- [x] **ruff 失败**：已修复 `app/api/server.py:1318` 无占位符 f-string 与未使用 `typing.Any` 导入。
- [x] **SQL 拼接风险**：`app/tools/db_tools.py` 中 `UPDATE resume_submission` / `UPDATE experience_card` / `ALTER TABLE experience_card` 已改为非 f-string 形式（DDL 列名来自硬编码白名单）。
- [x] **前端类型不一致**：`frontend-jobcraft/src/api.ts` 已删除重复的 `ExperienceCard`，改为从 `types.ts` 导入；`parseInterviewReviewPreview` 已透传 `submission_id`。
- [x] **前端字段错误**：`InterviewReviewPage.tsx` 岗位分析下拉框已改用后端真实字段 `position` / `company`。
- [x] **批量删除 QA 对**：`interview_review.py` 生成问题表时已改用 `delete_interview_qa_pairs_by_record()`。
- [x] **经历卡创建字段缺失**：`ExperienceCardCreate/Update` 已扩展 `company/role/period/background/problem/solution/execution/result/dimensions`；`db_tools.insert_card/update_card/_row_to_card` 已同步支持。
- [x] **LLM Provider 切换**：`.env` 与 `.env.example` 已从讯飞 MaaS 切换为智谱 AI OpenAI 兼容端点（`https://open.bigmodel.cn/api/paas/v4/`），默认模型 `glm-4-flash`；`app/agent/llm.py` 已补充智谱模型示例注释。
- [ ] **端口占用**：本地 8000 端口被其他服务占用，导致默认 e2e 测试连接到非本项目服务；开发/测试时请使用 `uv run uvicorn app.api.server:app --port 8001` 并设置 `JOBCRAFT_TEST_BASE_URL=http://localhost:8001`。
- [ ] **大 chunk 警告**：前端构建产物仍大于 500KB，需配置 `manualChunks` 拆分 vendor。
- [x] **测试覆盖不足**：已补充 `test_fuse_gap_scores_unit.py`（融合评分纯函数）与 `test_agents_mock_unit.py`（14 个 Agent mock 单测），覆盖岗位分析/抽取/面试准备核心路径；LLM 真实调用路径仍依赖 e2e（标记 slow，需真实 DB）。

---

### v0.15 认证闭环：强制 JWT + 登录/注册（本轮）

- [x] **产品设计决议**：认证闭环采用方案 A——所有业务端点强制 JWT + 注册加固 + 移除 `default-login` 后门；保留公开端点仅 4 个（register/login/health×2）
- [x] **后端强制认证**：`experience/job_analysis/submission/interview_prep/interview_review` 全部端点改为 `user_id: int = Depends(get_current_user)`（token 中的 user_id），移除 payload/Form 里的 user_id 入参；`server.py` tasks 4 端点同步加认证
- [x] **注册加固**：密码强度校验（≥8 位含字母+数字）、邮箱格式正则（不引入 email-validator 第三方库）、用户名/邮箱唯一性校验
- [x] **契约调整（前向兼容）**：`ExperienceCardCreate.user_id` 移除；question-table 端点去掉空 body 参数（前端多余字段被 FastAPI 忽略）
- [x] `db_user.py` 新增 `get_user_by_email` 并 re-export
- [x] **测试**：`test_auth_security.py`（56 用例：401 参数化、token 注入用户身份、公开端点、注册校验、登录成败）；`test_api_routes_unit.py` 用 `_AuthedClient` 包装器；e2e 自动注册一次性用户拿 token；修 e2e 陈旧断言 `cards`→`items`
- [x] **前端认证闭环**：`auth.ts` 新增 `login/register`、`autoLogin` 改为仅校验已有 token（无 token/失效返回 null 进登录页）；Context 暴露 `isAuthenticated/login/register/logout` 并修 `loadDashboard/loadExperiences` 传显式 user_id（防新用户加载错数据）；新增 `src/pages/AuthPage.tsx`；App 认证门 + loading gate；TopHeader 登出实连
- [x] **移除后门**：删除 `POST /api/auth/default-login`（commit 2 随前端一起提交），并同步删除前端对该端点的唯一引用
- [x] **验证**：工作区 `ruff check .` 绿；`uv run pytest tests/ -q` 315 passed、6 skipped；提交快照（worktree）同样 315 passed/6 skipped；前端 `npm run build` + `npx tsc --noEmit` 通过
- [x] **commits**：`8599e80` feat(auth): enforce JWT on business endpoints and harden registration（14 文件）；`6a0f121` feat(frontend): add login and register flow; remove default-login（60 文件，含既有前端重构 WIP 一并落库）
- [x] **过程信息**：main 下存在大量与本任务无关的既有 WIP（前端重构、db_config 迁移、mock-chat 端点、docs 删除等），通过 hunk 级暂存 + git plumbing 只纳入认证相关改动；`db_tools.py` 曾因 `ruff --fix` 误删 WIP 的 `_jc_config` re-export 导致既有单测失败，已按文件 re-export 模式恢复

---

### v0.16 安全基线收尾：所有权过滤 + 注入收敛 + 移除默认凭据（本轮）

- [x] **R2 所有权过滤（TASK-OWN-001）**：`get_card/update_card/delete_card`（db_experience）、`get_job_analysis/delete_job_analysis`（db_job）、`get_submission/update_submission/delete_submission`（db_submission）、`get_interview_prep_by_job/get_interview_record/delete_interview_record`（db_interview）全部增加可选 `user_id` 参数，传入时 WHERE 追加 `AND user_id=%s`；Controller/工具/工作流全部透传 `current_user`；另补 `list_interview_records_by_submission` 的 user_id 过滤（复盘摘要泄漏路径）
- [x] **新增越权测试**：`tests/test_ownership_filtering.py`（15 passed）——DAO 层验证 SQL 含 `AND user_id=%s` + 参数含 user_id；无 user_id 时不强制过滤；API 层验证 Controller 把 current_user 传入 get_card/get_job_analysis/get_submission
- [x] **R3 注入收敛（TASK-INJ-001）**：确认 `list_sql_tables/get_table_data/execute_sql_query` 三个 `@tool` 无调用方（死代码）后下线；`db_tools.py` 自重写为自包含兼容层（本地定义 `get_db_config/_jc_config/JOBCRAFT_DB`、保留 `connect` 与各 `db_*` re-export），提交快照不引用未跟踪的 `db_config.py`
- [x] **R4 移除默认凭据（TASK-AUTH-002）**：`auth/__init__.py` `load_dotenv(override=True)` 后强制要求 `JWT_SECRET_KEY`（缺失即 `RuntimeError`），移除硬编码 dev secret 兜底；`db/config.py` 移除 `root/root` 默认用户/密码，`MYSQL_USER/MYSQL_PASSWORD` 必须由 env 注入（已验证缺失时启动即失败）
- [x] **修复既有测试回归**：`test_workflows_unit.py` 29 个失败源于 DAO 加 `user_id` 参数后 mock lambda 参数不匹配，统一改为接受 `user_id=None` 可选参；`test_tools_extra_unit.py` 11 个失败源于 WIP `db_tools.py` 丢失 `connect/get_db_config`，随 INJ-001 自包含重构修复
- [x] **验证**：工作区全量 `uv run pytest tests/ -q` 330 passed、6 skipped；`ruff check .` 绿；OWN-001/AUTH-002 提交快照经独立 worktree 验证 `ruff` 绿 + 相关测试通过；INJ-001 提交后 `test_tools_extra_unit.py` 53 passed
- [x] **commits**：`b681f2c` refactor(security): remove SQL injection tools（INJ-001）；`09aa805` feat(security): owner scoping for by-id DAO + tests（OWN-001，18 文件）；`8878459` fix(security): require JWT secret and DB credentials via env（AUTH-002）

---

### v0.17 阶段 1 Contract 对齐：roadmap 校准 + 类型收紧（TASK-TYPE-001）（本轮）

- [x] **roadmap 重新校准（`82bf6c3`）**：按实际代码全面扫描 24 个 task——
  - 修正过时前提：`TASK-TYPE-001` 两层类型确认为**有意架构**（api/types.ts=后端 DTO / types/jobcraft.ts=camelCase 领域模型，10 组件消费），从「删除 camelCase+mapper」重定位为「收紧 any + 文档化」；`TASK-FETCH-001` 已核验唯一 fetch 出口（client.ts）→仅需文档固化
  - 精化 3 个 REAL-DATA 任务范围（Workbench/JDReport 硬编码、mock-chat 后端已就绪但前端零接线、复盘/向导 Math.random 假评分）
  - 新增 3 个经代码证实的新任务：`TASK-INTERVIEW-001`（interviews 永不从后端加载）、`TASK-TASK-SYS-001`（后端 4 个 task 路由前端零接线）、`TASK-CLEANUP-WIP-001`（18+ 未提交 WIP 清理）
  - 同步更新依赖图、优先清单（11 行）、退出标准（11 条）
- [x] **核验 step2-gap-polish 返回结构**：`per_card` 元素 = CardGapItem{card_id, score, local_score, llm_score, matched[], missing[], action, rewrite_suggestion?, supplement_suggestion?, supplement_steps[], dimension_analysis[], transferable_skills[], domain_overlap, quantified_note}；`global_suggestions` 元素 = GlobalSuggestion{missing_ability, priority, action, steps[]}（`app/agents/gap_polish_agent.py:25-62`、`app/tools/jobcraft_analyze.py:243-256`）；step1 的 `ats`=ATSProfile、`all_cards`=ExperienceCard[]（`app/api/job_analysis.py:69,88-93`）
- [x] **收紧 api 层 7 处 any（TASK-TYPE-001）**：
  - `api/types.ts`：`APIResponse<T = any>`→`Record<string, unknown>`；`company_context: Record<string, any>`→`Record<string, string|number|boolean|null>`；`parsed_dialogue?: any[]`→`InterviewReviewParsePreviewItem[]`；新增 `CardGapItem`/`GlobalSuggestion`（对齐后端 schema）
  - `api/job.ts`：`ats: any`→`ATSProfile`；`all_cards: any[]`→`ExperienceCard[]`；`per_card: any[]`→`CardGapItem[]`；`global_suggestions: any[]`→`GlobalSuggestion[]`；step2 补 `score_weights: {local,llm}`
  - **文档**：`types.ts` 顶部加双层类型架构 JSDoc；`client.ts` 顶部加「唯一 fetch 出口 + auth 注入」JSDoc（TASK-FETCH-001 文档固化项，随本 commit）
- [x] **验证**：`npm run lint`（tsc --noEmit）通过；`npm run build`（vite）成功——1701 modules，仅有既有 CSS @import 顺序 warning（与本次改动无关）；确认 step1/step2 API 函数无组件调用点（收紧不破坏现有 UI）
- [x] **commits**：`82bf6c3` docs: recalibrate roadmap to actual code（已本地，未 push，待与后续任务一起推送）；`4e0d14e` refactor(frontend): tighten api layer any types, document type architecture（TASK-TYPE-001，4 文件：3 前端 + roadmap Verify 记录，未 push）
- [x] **过程信息**：工作区仍有大量既有 WIP（前端重构、db_config.py、mock-chat、docs 删除、docker、frontend-jobcraft-backup/ 等），全部通过显式 `git add <file>` 只纳入本任务文件；roadmap 上一轮整体校准已在 `82bf6c3` 提交，本轮仅提交 Verify 字段修正 3 行

### v0.18 阶段 1 Contract 对齐：Workbench 接真实数据（TASK-REAL-DATA-001）（本轮）

- [x] **范围确认**：与用户对齐后，本轮只做 `WorkbenchView` 去硬编码；`JDReportDetailView` 的 `FALLBACK_DATA` 假模板拆为独立后续任务 `TASK-REAL-DATA-004`（此前分析确认其细节区块受 mapper `analysisToJD` 未填充字段限制——`subtextAnalysis=[]`、`skillGaps` 的 evidence/requirement 为空占位）
- [x] **roadmap 更新**：`TASK-REAL-DATA-001` 收窄为 Workbench-only；新增 `TASK-REAL-DATA-004 JD 报告去 FALLBACK`；优先清单加第 12 行、退出标准拆为两条
- [x] **WorkbenchView 去硬编码（核心）**：
  - 计数：`deliveredCount=12/interviewing=3/pending=5/finished=2` → 从真实 `jobs` 按 `status` 派生；`activeCount`/`appliedThisWeekCount`（本周新增）同步数据化
  - 6 步管线：`getJobSteps(index)` 硬编码三份假数据 → `getJobSteps(job)` 用 `job.steps`（jdAnalysis/expMatched/customResume/applied/prepStage/reviewStage），首个未 done 标记为 active
  - 卡片：公司/角色/状态徽章/匹配度从 `job.company`/`job.role`/`job.status`/`job.matchScore` 读取；匹配度因后端 mapper 恒为 0 显示 `—`（不造数）
  - 下一步行动：改为 `nextUpJobs`（未 finished 按状态优先级排序取前 3）渲染；最近活动：改为 `recentEvents`（从真实 applyDate/lastUpdated 派生相对时间）；AI 建议：改为数据驱动文案（无数据/待处理/正常三态），删除「3 条经历」假声明
  - 空状态：无 jobs 时展示引导卡而非假数据
- [x] **验证**：`npm run lint`（tsc --noEmit）通过；`npm run build` 成功——1701 modules，仅有既有 CSS @import 顺序 warning（与本次改动无关）
- [x] **commits**：`3c03cde` feat(frontend): drive workbench from real dashboard data（2 文件：WorkbenchView.tsx + roadmap；未 push，待用户确认后与 `82bf6c3`/`4e0d14e`/`52fab9f` 一起推送）
- [x] **过程信息**：工作区既有 WIP 依旧通过显式 `git add` 只纳入本任务文件（WorkbenchView.tsx + roadmap）；匹配度 `matchScore` 恒为 0 为 mapper `submissionToJob` 硬编码所致（后端 dashboard 无 match_score 字段），诚实显示 `—`，后续如需真分数需后端补充返回

### v0.19 阶段 1 Contract 对齐：JD 报告去 FALLBACK_DATA（TASK-REAL-DATA-004）（本轮）

- [x] **TASK-REAL-DATA-004**：移除 `JDReportDetailView.tsx` 的 `FALLBACK_DATA`（字节跳动模板），改为真实 `currentAnalysis` 渲染 + 空态占位
  - 核心字段：`company/position/createdAt/matchScore` 已有真实来源 → 直接渲染（匹配度 0 时显示「—」）
  - 岗位理解（职责）：从 `coreRequirements` 实时派生，删除硬编码的 4 条职责
  - 关键词匹配（ATS）：从 `atsKeywords.hardSkills/softSkills/expKeywords` 实时派生（high/partial/unmatched 三组），全空时显示空态占位
  - 能力匹配表：从 `skillGaps` 实时派生，evidence/requirement 为空时显示「待分析」；删除 `ScoreDots` 组件（不再造假分数）
  - 推荐经历：从 `recommendedExperiences` + `experiences` 标题查找实时派生，tags 为空时不渲染
  - 隐含要求：从 `subtextAnalysis` 实时派生，后端未填时显示「暂无」空态占位
  - 岗位目标/verdict.risk/verdict.why：分别映射到 `verdictSummary`/`keyRisks`/`whyMatch`（或「待分析」占位）
  - 底部行动指引：从 `verdictScore` 派生文案（不再硬编码「92%」）
  - 无分析数据时：早期 return 友好空态引导，不渲染假报告
- [x] **CI 修复**：`uv run ruff format .` 修复 `experience.py` / `test_ownership_filtering.py` 格式（pre-commit 问题，非本次改动）→ commit `fdf2cde`
- [x] **验证**：`npm run lint`（tsc --noEmit）通过；`npm run build` 成功——1701 modules；`rg` 确认无 `字节跳动/腾讯/FALLBACK_DATA/as any` 残留
- [x] **commits**：`8870c26` feat(frontend): remove fallback mock data from JD report detail

---

### v0.20 阶段 1 面试准备接真实数据（TASK-INTERVIEW-001，部分完成）（本轮）

> **概念纠正**：与用户对齐后确认——面试准备应接后端 `interview_preps`（面试准备稿），**不是** `interview_records`（复盘 review）。用户业务逻辑为：公司调研 → JD 分析 → 简历分析 → 面试逐字稿（电梯式演讲 + 几维度题 + 问题），保留公司调研环节，问题准备 UI 保留。UI 板块重组（合并 JD/简历、新增完整逐字稿报告）放下一步。

- [x] **后端：`get_interview_prep_by_job` 补出 `company_research`**——`db_interview.py` 从 `company_research_json` 列读出并返回（此前漏带）；`InterviewPrepResult` schema 新增 `company_research: Optional[Dict] = {}`（前向兼容）；`interview_pre.get_interview_prep` 透传
- [x] **后端：新增列表端点 `GET /api/jobcraft/interview-prep`**——返回当前用户所有面试准备稿，LEFT JOIN `job_analysis` 带出 `company/position`，含 `elevator_pitch/dimension_questions/full_version/html_content/company_research/created_at`；`db_interview.list_interview_preps` + `db_tools` re-export
- [x] **前端：`api/interview.ts` 新增 `listInterviewPreps()`**（调用 `/interview-prep` 列表）；`api/types.ts` 新增 `InterviewPrepRecord`（= InterviewPrepResult + id/company/position/submission_id）
- [x] **前端：`JobCraftContext` 新增 `loadInterviews()`** ——拉 `listInterviewPreps` → `prepRecordToInterview` 映射为 `Interview[]`（填充 `prepSource` 真实数据 + best-effort 填 `preparation`：维度题→highFreqQuestions、companyResearch 扁平化、elevator_pitch）；集成进 `loadUserProfileAndData` 的并行加载，刷新不清空内存中未持久化的本地面试
- [x] **前端：`Interview` 类型新增可选 `prepSource?: InterviewPrepRecord`**——承载后端完整真实结构，供下一步 UI 板块重组消费
- [x] **验证**：`npm run lint`（tsc --noEmit）通过；`npm run build` 成功（1701 modules，仅既有 CSS @import 顺序 + chunk 大小 warning）；后端 `uv run ruff check .` 通过；`uv run pytest tests/ -q` 325 passed、11 skipped；`uv run python -c from app.api.server import app` 正常（新路由已注册）
- `commit_id: a5aa31e`（已推 `origin/main`）

> **第二轮（真实生成 + 持久化）** —— `createInterview` 接后端真实 LLM 生成，删除硬编码假数据
>
> - [x] `createInterview` 改为 **async**（返回 `Promise<string>`）：解析该岗位的 `job_analysis_id`（无则抛错"请先到岗位分析页生成"→ 失败兜底）；调 `POST /interview-prep`（`round_type` 经 `roundTypeToCn` 映射、`card_ids: []` 由后端 `get_selected_card_ids_by_job` 自动回退）；返回结果经 `buildInterviewFromPrep` 映射为 `Interview` 并落本地 state；保留更新 job 状态、nextActions、成功 toast
> - [x] **删除** 硬编码假 `highFreqQuestions`（原 q-new-1/q-new-2）、假 `companyResearch`、假 `recommendedExperiences`
> - [x] 抽取共享映射 `buildInterviewFromPrep`（`prepRecordToInterview` 与创建共用），`roundTypeToCn` 前端 roundType→中文轮次
> - [x] **3 个调用方改造为 await + 失败兜底**：`NewInterviewModal.tsx`、`CreateInterview.tsx`、`NewInterviewPrep.tsx` 的生成完结分支改为 async，成功才 `navigateTo`；失败 `setIsGenerating(false)` + `showToast(error)` 留在表单可重试
> - [x] 验证：`npm run lint` 通过；`npm run build` 成功（504.38 kB，仅既有 chunk 大小 warning）
> - [x] **遗留（下一步）**：UI 板块重组（合并 JD/简历、新增完整版逐字稿报告）——`prepSource` 已承载后端完整结构可供消费
>   - `commit_id: a1558a7`（已推 `origin/main`）

> **第三轮（UI 板块重组，接真实数据）** —— 面试准备工作台从"全硬编码 mock"改为"消费真实 prepSource"
>
> - [x] **工作台板块精简为 5 个**：公司调研 / 本场判断 / 维度题准备 / 面试逐字稿 / 模拟面试
> - [x] **公司调研**：渲染真实 `company_research`(basic/business/funding/team/industry/news)；保留原视觉语言
> - [x] **本场判断**：渲染真实 `round_type`/`duration` + 考察方向(维度题→方向拆解)
> - [x] **维度题准备**：渲染真实 `dimension_questions`(question/type/answer_points→STAR 建议)，左列表右编辑器草稿
> - [x] **面试逐字稿（新增）**：渲染 `elevator_pitch`(电梯式演讲) + `full_version`(完整版报告)，附使用建议
> - [x] **模拟面试**：保留
> - [x] 删除 Workbench 里硬编码的 `companyData`/`initialQuestions`
> - [x] `createInterview` 同步携带 synthesized `prepSource`，使新建的面试也有真实完整数据（此前仅加载项有）
> - [x] 验证：`npm run lint` 通过；`npm run build` 成功（504.33 kB）
> - [x] **说明**：原计划"合并 JD/简历"板块暂未单列（需额外接 JD 文本与简历 markdown 数据源），当前工作台聚焦 4 大真实数据板块 + 模拟面试；如需可后续补充 JD/简历板块
>   - `commit_id: efaca61`（已推 `origin/main`）

> **TASK-REAL-DATA-002 模拟面试去 Mock** —— 由真实后端 mock-chat 驱动
>
> - [x] `api/interview.ts` 新增 `mockChat(payload)` 包装 `POST /interview-review/mock-chat`（返回 `{reply, role:"interviewer"}`）
> - [x] `MockInterviewModal` 改为**多轮真实对话**：打开即向 AI 面试官发起开场（后端 system prompt 自动开场），用户发送回答后带完整历史 POST mock-chat，展示真实 LLM 面试官回复，循环
> - [x] **移除**：`mockQuestions` 硬编码题目、`Math.floor(78+Math.random()*12)` 假评分、`setTimeout` 假录音（含"快速填入参考回答"）
> - [x] **完成时**：调用 `createInterviewReview` 把整场对话落库为复盘，`showToast` + 导航到复盘中心
> - [x] 验证：`npm run lint` 通过；`npm run build` 成功（502.07 kB）
> - [x] 说明：因 mock-chat 端点只返回 `reply`（无逐题四维评分），改为整体完成后生成真实复盘，而非保留逐题假分数卡
>   - `commit_id: 59ab3f0`（已推 `origin/main`）

> **TASK-REAL-DATA-003 复盘/新增向导去 Mock 评分**
>
> - [x] `buildReviewPatchFromAnalysis`（新增 mapper）：把后端 `InterviewReviewResult`（overall_score/summary/strengths/weaknesses/action_items/questions）映射为前端 `InterviewReview`，只使用真实数据（四维诊断沿用每题真实 score 派生，不造随机数）
> - [x] `createReviewFromTranscript`：create + analyze 串联，用真实分析结果填充 review，删除 `Math.random()`、硬编码 competencies/aiDiagnosis，复用 `addInterviewReview` 统一落库
> - [x] `addInterviewReview`：移除 `Math.random()` 与硬编码 passProbability/competencies 默认值，未传真实数据时用 `0`/空兜底（不伪造）
> - [x] `NewReviewModal`：删除 `setTimeout` 假延迟与 hardcoded 数据，改调 `createReviewFromTranscript` 走真实后端
> - [x] **InterviewPrepCenterView createInterview**：经核查已由 TASK-INTERVIEW-001 接通真实后端（`generateInterviewPrep`→`buildInterviewFromPrep`），无硬编码，无需改动
> - [x] 验证：`npm run lint` 通过；`npm run build` 成功
>   - `commit_id: 5eb2810`（已推 `origin/main`）

> **TASK-CLEANUP-WIP-001 清理未提交 WIP**
>
> - [x] 审计工作区 4 类变更，用户确认后处理
> - [x] 归档 7 个旧 docs（内容在 `docs/archive/`，`git rm` 记录）→ `794047b`
> - [x] 提交真实后端 WIP（mock-chat 端点、server.py text()、db_* 配置集中到 db_config）→ `4b64ca3`
> - [x] 提交 docker 部署（compose/Dockerfile×2/nginx）+ 前端 `.env.example`/`.gitignore` → `f69f25c`
> - [x] 删磁盘：`frontend-jobcraft-backup/`（191MB）、`docker/*.sql`（~7MB）、`PROMPT.md`+`metadata.json`
> - [x] restore 11 个仅行尾噪音文件（无内容变更）
> - [x] 验证：`uv run pytest tests/ -q` 通过（325 passed, 11 skipped）；`ruff check` 通过；working tree clean
>   - `commit_id`：`794047b` / `4b64ca3` / `f69f25c`

---

> **TASK-FIX-001 启用 Redis 异步任务消费循环**
>
> - [x] 修复 `execute_interview_prep` 错误 import（`interview_flow` → `interview_prep_flow` 的 `run_interview_prep_workflow`），并对齐真实签名（补 `job_analysis_id` 必填校验 + `submission_id/company_research/resume_markdown/previous_review_summary` 透传）
> - [x] `app/tasks/worker.py` 新增 `_dispatch_one`（按 task_type 分发 handler，未知类型标记 failed）与 `run_worker`（`blpop` 消费循环 + JSON 解析容错 + 单任务失败不终止 daemon + `python -m app.tasks.worker` 启动入口）
> - [x] 4 个 `/tasks/*` 端点对 Redis 不可用优雅降级为 503（原 500）
> - [x] 新增 `redis>=5.0.0` 依赖声明并安装（redis 8.1.0）
> - [x] 新增 `tests/test_tasks_handlers_unit.py`（5 用例：注册表、job_analysis_id 必填、handler 参数对齐、未知类型标记 failed、已知类型分发补 task_id）
> - [x] 验证：`uv run pytest tests/ -q` 330 passed、11 skipped；`ruff check` 通过
>   - `commit_id: d3dee83`（已本地，待推送）

> **TASK-STATUS-001 引入 Submission 状态机**
>
> - [x] 新增 `app/schemas/submission_status.py`：`SUBMISSION_STATUS` 枚举（APPLIED/INVITED/ROUND_1/ROUND_2/OFFER/CLOSED）+ 中文显示映射 + 合法流转校验（§4.2，任意阶段可提前 CLOSED）+ 存量中文字符串读时归一化（前向兼容）
> - [x] `db_submission`：建表默认值 / insert / update 用枚举码；get / list 读取时旧中文自动归一化为枚举码
> - [x] submission API：创建校验状态合法性（非法 400）；更新时校验状态流转（非法流转 400）；manual 端点默认 APPLIED
> - [x] 前端：`SubmissionStatus` 联合类型 + `SUBMISSION_STATUS_CN` 中文映射；`Submission/DashboardItem.status` 收紧为枚举；`submissionToJob.statusMap` 对齐新枚举（APPLIED→delivered / INVITED/ROUND_x→interviewing / OFFER/CLOSED→finished），currentStage 用中文映射
> - [x] 新增 `tests/test_submission_status_unit.py`（9 用例）；更新路由测试（含非法流转 400 用例）
> - [x] 验证：`uv run pytest tests/ -q` 340 passed、11 skipped；`ruff check` 绿；`npm run build` + `tsc --noEmit` 通过
>   - commit：后端 `d3254a8`、前端 `1a16001`（已本地，待推送）

> **TASK-RESUME-001 Resume 编辑接真实数据**
>
> - [x] 新增 `markdownToResume` 解析器 + `resumeToMarkdown` 反序列化器（`src/utils/resumeParser.ts`），与后端 `generate_resume_markdown` 格式互为逆运算；round-trip 验证 item/bullet 分组与内容一致
> - [x] `loadDashboard` 对每个 `has_resume` 投递站 `getSubmission()` 解析 `resume_markdown` → 填充 `resumes`（key=submission id）；`submissionToJob.resumeId` 对齐为 `String(sub.id)`
> - [x] Context 新增 `activeResumeId`/`setActiveResumeId`；6 个编辑动作（apply/reject/applyAll suggestion、update/add/delete bullet）由硬编码 `'res-byte-1'` 改为读写 `activeResumeId`；新增 `saveResume(id)` = `resumeToMarkdown` → `PATCH /submission/{id}`（复用现有字段，无后端改动）
> - [x] `ResumeEditorView` 按 `resumeId ?? job.resumeId ?? 首个简历` 解析当前简历并 `setActiveResumeId`；「保存草稿」接入 `saveResume`；修正中文标识符 `allBullets紧`→`allBullets`、`isEditing迁移`→`isEditing`；无简历时友好空态
> - [x] `JobWorkspaceView` 不再写死 `'res-byte-1'`
> - [x] 验证：round-trip 脚本确认解析↔序列化一致；`tsc --noEmit` + `npm run build` 通过；后端 `uv run pytest tests/ -q` 340 passed/11 skipped 回归通过

> **TASK-INTERVIEW-001 面试记录后端持久化**
>
> - [x] 校准：`loadInterviews`/`buildInterviewFromPrep`/前端 `companyResearch` 等已接后端真实数据；真正缺口是后端生成落库后未返回 `id`，前端 `createInterview` 用假 ID `-Date.now()`，刷新后与真实 `prep-{id}` 重复
> - [x] 后端 `InterviewPrepResult` schema 加 `id: Optional[int]`；`_generate_prep` 捕获 `insert_interview_prep()` 返回的 `record_id` 写入 `result.id`
> - [x] 前端 `api/types.ts` `InterviewPrepResult` 加 `id?: number`；`createInterview` 用 `result.id` 生成 `newId`（`prep-{id}`）并填充 `prepSource.id`，ID 格式与加载路径一致，消除重复
> - [x] 验证：`tsc --noEmit` + `npm run build` 通过；后端 `uv run pytest tests/ -q` 340 passed/11 skipped；`ruff check` 绿

> **TASK-TASK-SYS-001 接线前端任务系统**
>
> - [x] scope 校准：后端仅注册 3 种任务（`resume_generate`/实际为 JD 分析、`interview_prep`、`export_pdf`），无「复盘分析」任务类型；故按最小 scope 接 **面试准备**（有对应 `interview_prep` 任务类型 + Redis 消费循环），其余 AI 调用保持同步、不改 contract
> - [x] 新增 `src/api/tasks.ts`：`submitTask`/`getTask`/`cancelTask`/`listTasks` + `pollTaskUntilDone`（1.5s 间隔 / 120s 超时，回传失败/取消/超时）；`api/types.ts` 补 `TaskStatusName`/`TaskInfo`/`SubmitTaskResult`（commit `081e2ae`）
> - [x] `createInterview`：提交 `interview_prep` 任务 → 轮询 `completed` 读 `result`（`InterviewPrepResult` dict，含 `id`）继续 `buildInterviewFromPrep`；提交失败/Redis 不可用（503）降级为原同步 `generateInterviewPrep` POST，保证功能始终可用（commit `506cd16`）
> - [x] 验证：`tsc --noEmit` + `npm run build` 通过；后端 `ruff check` 绿 + `pytest -q` 340 passed/11 skipped（后端未改动，仅回归）

> **阶段 3 数据库演进（TASK-DB-MIG-001 + TASK-DB-FK-001）**
>
> - [x] MIG-001 `f78d826`：文档化 SQL 迁移目录（非 Alembic——栈为 raw mysql-connector）。`migrations/runner.py` + `schema_migrations` 版本表 + checksum + 幂等逐条执行；`V0001__baseline.sql` 固化 10 表完整 schema；pyproject 增 `jc-migrate` + pytest `pythonpath=["."]`；单测 5 用例（345 passed/11 skipped）。**未对真实库端到端应用**（环境 MySQL :3308 未运行），应用时 `python -m migrations.runner migrate`
> - [x] FK-001 `20641a4`：`V0002__foreign_keys.sql`，先清孤儿数据再 ADD CONSTRAINT：`submission→job_analysis`(SET NULL)、`interview_preps→job_analysis`(CASCADE)、`interview_preps→submission`(SET NULL)、`qa_pairs→record`(CASCADE)、`card_versions→card`(CASCADE)，全 `ON UPDATE CASCADE`、只加不改；单测追加约束覆盖校验（346 passed/11 skipped），`ruff` 绿

> **阶段 4 AI 工程化（TASK-AI-001）**
>
> - [x] AI-001 `77a28f8`：18 个内联 LLM prompt 全部外部化 + 版本化到 `prompts/<域>/<名>_v1.txt`（experience 3 / jd 5 / interview 8 + core 1，另盘点为 18 个含 llm_json 回退后缀）。`app/core/prompts.py` loader 用 `{{name}}` 自定义替换（字面 `{ }` 免转义，规避 str.format 的 `{{var}}`=字面量坑）；14 处调用点重构且保留 `_build_*_prompt` 纯函数签名（兼容既有单测）；rubric 常量作占位符实参传入。新增 `tests/test_prompts.py` 4 用例（占位符一致性/无未闭合花括号/渲染/字面保留）；`pytest tests/ -q` 350 passed/11 skipped、`ruff` 绿。
> - [x] AI-002 `8909def`：AI 调用元数据审计。盘点校准：结构化调用约 20 处全走 `llm_json.invoke_structured` 唯一 chokepoint（roadmap「4 处」过时），2 处非结构化（gate_agent bind_tools、mock 面试 OpenAI SDK）按用户决策首版排除。迁移 `V0003__ai_audit.sql`（ai_tasks + ai_outputs，token 列可空预留 AI-003）；`app/tools/db_ai.py` 局部封装（create/finish，**尽力而为非阻塞**）；`invoke_structured` 内挂钩子记录 status/model/input_hash/prompt_hash/schema_name + 结构化输出 + 耗时，外部行为完全不变。单测 `tests/test_ai_audit.py` 8 用例；`pytest tests/ -q` 358 passed/11 skipped、`ruff` 绿。V0003 未对真实库应用。
> - [x] AI-003 `0aa89d0`：通用 AI Cache + Usage。用户确认：Redis 热缓存（复用 REDIS_URL，零新增依赖）/ 复用 ai_tasks token 列 / 命中即返回。cache key=`ai:{feature}:{model}:{input_hash}`（input_hash 已含 prompt+schema → 版本变更天然失效）。`app/tools/ai_cache.py`（懒 Redis + 短超时快速失败 + `_DISABLED` 哨兵，尽力而为非阻塞，TTL 配 `JC_AI_CACHE_TTL`）；`invoke_structured` 先查缓存命中即返回（审计标记 from_cache=1）→ 未命中跑 LLM + 写缓存 + 从 `usage_metadata`/`response_metadata` 提取 token 用量；内层函数改返 `(result, response)`。迁移 `V0004__ai_cache.sql` 加 `from_cache` 可空列（只加不改）。单测新增 5 用例；`pytest tests/ -q` 363 passed/11 skipped、`ruff` 绿。V0004 未对真实库应用。
> - [x] OBS-001 `cfcf970`：激活 Prometheus 指标。用户决策：DB query 指标后续做（留重构候选），本任务接 **LLM + API**。LLM：`invoke_structured` 增 `_record_llm_observability`（calls_total/duration_seconds/tokens_total，缓存命中不记）；**修 bug**：`llm_tokens_total` 未从 `app.monitoring.__init__` 导出导致 `from app.monitoring import ...` 整体 ImportError 被吞→所有 LLM 指标不记录，改直连 `metrics` 模块并补齐导出。API：`server.py` 加 `@app.middleware("http")` 记 requests_total + duration（endpoint 用路由模板 path）。单测 `tests/test_observability.py` 4 用例（含 /health 集成测试读 registry）；`pytest tests/ -q` 367 passed/11 skipped、`ruff` 绿。

> **阶段 5 工程治理（TASK-CLEAN-001 + TASK-DEPS-001）**
>
> - [x] CLEAN-001 `564019c`：死代码清理。**盘点澄清**：`app/db/config.py` 非无引用——`/api/jobcraft/health` 用其 engine + `SELECT 1`，且 `sqlalchemy` 未声明（传递依赖）。按用户批准，先重写健康检查为原生 `_jc_config()`+`mysql.connector.connect` 再**删除整个 `app/db/`**（消除未声明传递依赖）；整文件删 `app/schemas/common.py`（4 类全零引用）；删 `get_optional_user`（零引用）、`tests/test_qa_pairs.py`（误收集副作用脚本，真测试为 `test_qa_pairs_unit.py`）。删前 grep 确认无残留引用；`pytest` 367 passed/11 skipped、`ruff` 绿。
> - [x] DEPS-001 `f04764f`：依赖清理。后端：删 `aiofiles`、dev `playwright`（均零引用）；`passlib[bcrypt]` → 显式 `bcrypt>=4.0.0`（auth 直接 import bcrypt，防包消失）；`requests` 从 runtime 移 dev（核实 tests 在用，非未用是放错位）。前端：删 `@google/genai`、`express`、devDeps `@types/express`（均零引用）；`vite` 从 dependencies 移出（build 工具，dev 保留）。`uv lock`/`uv sync` 移除 4 包（aiofiles/passlib/playwright/pyee）+ bcrypt 5.0.0 直声明可用；`pytest` 367 passed/11 skipped、`ruff` 绿；前端 `npm install` 移除 120 包 + `npm run build`/`tsc --noEmit` 通过。均未对真实库端到端应用。

> **重构候选推进（TASK-REF-DB-001 + TASK-REF-DB-002）**
>
> - [x] REF-DB-001 `1df3ecc`：DB 访问集中封装（方案 B：封装 + execute/query helper，用户已确认）。新建 `app/tools/db_conn.py`（`_jc_config`/`connect`/`connection`/`query_one`/`query_all`/`query_scalar`/`execute`/`execute_lastrowid`，`import db_config` 避免循环依赖）；6 个 db 模块（db_user/db_job/db_submission/db_interview/db_experience/db_ai）重写为 helper——单语句→execute 族，多语句共享连接（`delete_*` 级联删除、`_ensure_*` 的 SHOW COLUMNS+条件 ALTER+回填）→`connection()`；`db_tools` 改从 db_conn re-export `connect`/helper（永保测试 patch 目标）。**测试迁移**：patch 目标 各模块命名空间 `connect`/`_jc_config` → `app.tools.db_conn.connect`（ownership 5+1 处、tools_extra 9 处、ai_audit 3 处）；新增 `tests/test_db_conn_unit.py` 9 用例。`pytest tests/ -q` 376 passed/11 skipped（+9）、`ruff` 绿。**坑**：PowerShell `Set-Content -Raw` 破坏 UTF-8（U+FFFD）损坏 test_ownership_filtering.py，且 `edit` oldString 缩进须与实际一致（曾误加 8 空格）——已 git checkout + 重做。
> - [x] REF-DB-002 `f1ba745`：DB query 与连接指标接线。在 `db_conn` chokepoint 接线两条指标：`db_query_duration_seconds{operation,table}`（经 `_tracked_connection` 观测 5 个封装函数每次查询耗时）+ `db_connections_active`（`connection()` 建立/释放）。operation/table 由 `_sql_meta()` 启发式推断。设计：`inc()` 放 `connect()` 成功后（连接失败不泄漏 Gauge）；`connection()` 保持返回原始连接（兼容 `c is conn` 单测），仅维护连接 Gauge；多语句内部逐句耗时不观测（v1 声明）。单测新增 4 用例（沿用 test_observability fake metric 模式）；`pytest tests/ -q` 380 passed/11 skipped、`ruff` 绿。

> **重构候选推进（TASK-REF-SPLIT-001 大文件拆分）**
>
> - [x] REF-SPLIT-001 `69b155a`：大文件拆分——拆出 `interview_review.py` 的对话解析层。新建 `app/tools/interview_dialogue.py`（525 行，纯函数零 LLM/DB）：全部解析正则/常量 + `_detect_role`→`_parse_dialogue`→`_build_qa_pairs`/`_is_interviewer_question`；`interview_review.py` 精简为业务层（210 行）：`create_interview_record`/`preview_question_intents`/`_build_question_table_prompt`/`_get_job_context`/`_format_cards_for_prompt`/`_find_my_answer`/`_truncate_text` + 维度 rubric 常量 + `_QuestionIntentItem`/`_QuestionTableOut` schema。**契约保持**：`interview_review` re-export `_parse_dialogue`/`_build_qa_pairs`（`# noqa: F401` 防 ruff 误删），故 3 workflow/agent + api + 测试的既有 import 与 patch 目标零改动。验证：`pytest tests/ -q` 380 passed/11 skipped（与拆前一致，纯移动零行为变化）、`ruff` 绿、逐模块 import 冒烟通过。**坑**：ruff `--fix` 的 F401 会删除「仅 re-export」的名字，须显式 `# noqa: F401` 否则破坏对外契约。

> **手动测试 Bug 修复（TASK-MANUAL-FIX-001）**
>
> - [x] FIX-PROFILE-001：个人资料持久化。新建 `app/api/profile.py`（`GET/PATCH /api/auth/profile`，`user_profiles` 表 upsert）；前端 `api/auth.ts` 加 `getProfile`/`updateProfile`；`JobCraftContext.tsx` 改 `loadUserProfileAndData` 并行调 auth+profile 两个 API，`updateUserProfile` 改为 async 并调 `authApi.updateProfile`；`UserProfileView.tsx` 加 `useEffect` 同步表单 + 城市输入框。DB：`user_profiles` 表已建（display_name/role/target_salary/years_of_exp/city/phone/email/summary/target_cities/target_companies/target_roles/avatar_url）。E2E 验证通过。
> - [x] FIX-JOBCREATE-001：岗位创建持久化。`createJob` 改为 async，调 `jobApi.createSubmission` 持久化到 `resume_submission` 表，返回 ID 回填本地 state。Job 类型加 `backendId?: number` 字段。
> - [x] FIX-DELETE-001：删除 JD 调后端。`deleteJDAnalysis` 改为 async，从 id 提取 submission_id 调 `jobApi.deleteSubmission`。`deleteSubmission` API 已存在于 `api/job.ts`，此前前端从未调用。
> - [x] FIX-CITY-001：地址编辑。`UserProfileView.tsx` 移除硬编码默认值（'北京 / 远程'），改为从 user 状态读取（API 加载后自动填充），加城市输入框 + `useEffect` 同步。
> - [x] FIX-AVATAR-001（此前已完成）：TopHeader 硬编码"菁"→用户首字母。

---

### v0.21 Experience Matching Evaluation v0.1（AI 测评体系搭建，本轮）

> 依据 `docs/evaluation/JobCraft AI Evaluation v1.md`（§21 执行顺序），先做第一个 Evaluation = Experience Matching Benchmark。
>
> **本轮合并了 GitHub 上已推送的 4 个 evaluation commits（`b6ae418`→`4924c89`）与本会话实现**：采用其 model-agnostic 架构（gold 预测文件 + 独立评估器，多经历/ranking/NDCG），保留本会话的现有 Agent 策略对接。

- [x] **架构（合并 remote）**：`run_matching_eval.py` = model-agnostic 评估器（`--gold` + `--pred` 预测文件，指标 Acc/Macro F1/Prec/Rec/Score MAE/NDCG@3）；数据集 = remote `matching_cases.jsonl`（10 case，每 case 1 岗位 + 3 经历 + ranking/relevance/score）
- [x] **evaluation/ 结构**：`README.md` + `datasets/matching_cases.jsonl` + `strategies.py`（预测生成器）+ `generate.py`（CLI 产出预测文件）+ `run_matching_eval.py`（评估器）+ `reports/matching_report.md`（真实结果）+ `__init__.py` + `datasets/__init__.py`
- [x] **3 种策略对接现有代码**：在 `strategies.py` 中复现 Keyword=`_local_score`、LLM=`ScoreMatchAgent`（每 case 一次 LLM 调用）、Hybrid=`LOCAL_WEIGHT=0.4`+`LLM_WEIGHT=0.6` 融合；`score_to_relevance` 阈值与后端 `_match_level` 对齐（80/60/40）
- [x] **CLI**：`python -m evaluation.generate --strategy all`（keyword|llm|hybrid|all）→ `evaluation/predictions/predictions_<strategy>.jsonl`；单 case 失败不影响整体；DB 不可用时优雅降级（实测 MySQL :3308 未起仍可跑）
- [x] **真实结果（10 case · English 数据集 · glm-4-flash）**：Keyword Acc=0.4667/Rec=0.1111/MAE=42.84/NDCG=0.974；**LLM Acc=0.9333/Rec=0.8889/MAE=9.27/NDCG=0.977**；Hybrid Acc=0.5667/Rec=0.2778/MAE=25.63/NDCG=0.959；三者 Precision=1.0
- [x] **Hybrid 权重实验（Fusion Ablation）**：新增 `fusion.py`（纯函数）+ `fuse.py`（CLI），在**同一份** LLM 预测上确定性离线融合，产出 A(0.4/0.6)/B(0.2/0.8)/C(max)；隔离 LLM 非确定性，单测 6 条新增（共 22）
- [x] **实验结果（共享 LLM 分）**：LLM 在 30 实例中 24 次最接近人工分数（A 3 胜/B 2 胜/C 1 胜）；Score MAE：LLM=11.70 ≈ C=11.69 < B=14.68 < A=20.34 < Keyword=42.84；Macro-F1：LLM=0.634 ≈ C=0.634 > B=0.352 > A=0.247
- [x] **结论：Local 未给语义匹配增加价值**。病灶是 `_local_score` 与 LLM 分不同量纲（0 分 local 会把 LLM 80 分拉到 48 掉档），加权混合把校准问题传染给 LLM；max 融合免疫传染（永不低于 LLM）→ 建议生产路径切 `max(Local, LLM)`，到中文真实 JD 回测验证
- [x] 验证：`uv run pytest tests/ -q` 402 passed、11 skipped；`ruff check/format` 通过
- [ ] **后续迭代**：① ~~中文真实 JD 回测 `max(Local, LLM)`~~（v0.2 完成）；② 复测量化 LLM 抖动对 A/B/C 结论稳健性；③ 数据集补齐 30 条 + Regression 基线固化（baseline.json → v1.json）

### v0.22 Experience Matching Evaluation v0.2（中文真实 JD 回测 + 工程维度，本轮）

- [x] **中文数据集**：新增 `evaluation/datasets/chinese_cases.jsonl`（10 case：direct×3 / semantic×2 / partial×2 / negative×2 / transfer×1，中文 JD + 中文经历 + 人工 gold ranking/relevance/score）
- [x] **Usage observer**：`app/tools/llm_json.py` 新增注册式 `register_usage_observer()`（默认零行为，不改变语义），`invoke_structured` 每次调用后广播 duration_s + prompt/completion/total tokens + from_cache，供基准采集 Latency/LLM Calls/Cost
- [x] **runner**：新增 `evaluation/run_chinese_eval.py`（`--gold/--outdir/--report`），复用共享 LLM 预测 + 确定性融合（A 0.4/0.6、C max），实测 Latency 与 token 用量，产出第二份报告 `reports/chinese_matching_report.md`
- [x] **真实结果（10 case · 中文数据集 · glm-4-flash）**：Keyword Acc=0.5667/Rec=0.1875/MAE=40.13；**LLM Acc=0.9000/Rec=0.8125/MAE=13.20/Macro-F1=0.5991**；Hybrid A(0.4) Acc=0.6333/MAE=21.09；**Hybrid C(max) Acc=0.9000/MAE=12.87，与 LLM 完全一致**；LLM A/C 三者 LLM Calls 均=10、成本均≈$0.0011，Keyword=0 调用/0 成本
- [x] **结论（跨语言复现 v0.1）**：max(Local, LLM) 与纯 LLM 质量持平且不减少 LLM 调用 → 其价值是**安全融合**（不改变 LLM 分 + 保留零成本本地兜底），不是性能或成本优化；加权 Hybrid A 在中文数据上同样是质量负贡献；若目标省调用应引入路由/缓存
- [x] 单测：新增 5 条（中文数据集 schema/mix、estimate_cost、UsageCollector、produce_hybrid）；验证 `uv run pytest tests/ -q` 407 passed、11 skipped；`ruff check/format` 通过
- [ ] **后续迭代**：① 复测量化 LLM 抖动；② 数据集补齐 30 条 + Regression 基线固化；③ 若走省调用路线，评估路由/缓存方案（Keyword 前置 + LLM 命中高置信才调用）

### v0.3 Evaluation · JD Extraction（2026-09-09）

- [x] **评测链路第一层**：`JD 原文 → JdAtsAgent → ATSProfile` 结构化抽取，默认模型 `glm-4.7-flash`
- [x] **数据集**：`evaluation/datasets/jd_cases.jsonl`（10 条合成中文 JD），gold 含八维能力要求（D1-D8 level）+ subtext 隐性需求（`surface`/`hidden`）
- [x] **评测模块**：`evaluation/jd_metrics.py`（纯函数：normalize/bigram Dice/单边包含/P-R-F1/聚合/维度命中/Exact Match/隐性需求复核清单）
- [x] **runner**：`evaluation/run_jd_eval.py`（断点续跑：预测 jsonl 缓存，失败条目自动重试；per-case usage + `_sum_usages` 成本汇总；报告生成）
- [x] **真实结果（10 case · glm-4.7-flash）**：Required Skills F1=0.6466、Responsibilities 0.3913、Keywords 0.3158、Preferred Skills 0.7143、Dimension Accuracy 0.4125；Salary 10/10、Location 9/10；Hidden Requirements 各 case 表面覆盖 0-100%（报告逐条列出待人工复核）
- [x] **工程结论**：`glm-4.7-flash` 单次约 20s，10 条全量 ≈200s+；Redis ai_cache 命中后 0 次 LLM 调用/0 成本可复现；冷启动约 10 次调用
- [x] 单测：13 条（test_jd_extraction_unit.py）通过；全量 `uv run pytest tests/ -q` 425 passed、6 skipped；`ruff check/format` 通过
- [x] 已推送：`04dba42`（迁移/测试环境适配）+ `2278d53`（v0.3 JD 评测）
- [ ] **下一层**：Interview Review 评测；JD 侧优化聚焦 Responsibilities/Keywords F1 与 Dimension Accuracy、Han subtext 解析约束
### v0.4 Evaluation · JD Extraction 错误分类 + 数据集扩展 + Prompt C（2026-09-10）
- [x] **E1-E8 错误分类**（`350db1b`，与 v0.3 十条合并）：`jd_metrics.py` 新增 ErrorType/classify_case_errors/error_taxonomy_by_field/summary、`field_completeness`、`critical_error_rate`（required/preferred 的 E3 占比）、e_desc；报告新增「Error Taxonomy」「Field Completeness」「Case-level Errors」章节；31 条单测
- [x] **数据集 10 → 40**（`9ec5e3b`）：新增 20 条真实风格 + 10 条对抗（Required/Preferred 混淆、长职责、职责隐含技能、中英混排、缩写、同义词、模糊学历、多地点、薪资谈判、创业公司隐性要求）
- [x] **v1 基线 40 条实测**：Required F1=0.600、Responsibilities 0.417、Keywords 0.229、Preferred 0.625、Dimension 0.35、Salary 39/40、Location 38/40、**Critical Error Rate 23.14%**（E2 Hallucinated=332、E6 Dimension=184、E1 Missing=181）
- [x] **Prompt C evidence-first**（`fba4406`）：新 Schema `EvidenceItem` + `SubtextDecode.confidence` + `ATSProfile.evidence_items`；提示词 `prompts/jd/jd_ats_analysis_v3.txt`；`app/agents/evidence.py` 确定性校验（列表字段无证据即丢、标量缺失用唯一证据回填、维度必须被 dimension_Dx 证据支撑、缩写/同义不做自动兜底如实计 E2）；agent 按版本分发（v1/v3）；runner 支持 `--prompt-version` 与 `--pace-sec` 节流 + 单 case 150s 超时；报告新增「Prompt Version 对比」章节 + 证据覆盖统计；16 条新单测
- [x] **Issue 5 实测（Prompt C，40 条 · glm-4-flash）**：reconcile 后 Critical Error Rate **23.14% → 20.35%**（幻觉下降、总错误减少），但召回下行：Required F1 0.600→0.458、Salary 39→30/40、Location 38→30/40、Dimension 0.35→0.056（模型几乎无法为 D1-D8 产出证据 → 校验全丢）。**结论：evidence-first 是「防幻觉/安全」杠杆（稳定压 Critical Error 约 3pp），而非召回提升手段；维度判断应回归直接模型输出 + 另行约束**
- [x] **工程注意**：账号级 429 限频（code 1302）连续背对背调用约 8 次后触发 → 评测需 `--pace-sec 30` 节流 + 冷却后断点续跑；LLM 单次无超时会永久卡死评测 → runner 已加 per-case 150s 超时（每次独立 executor，超时即弃）
- [x] 已推送：`350db1b` / `9ec5e3b` / `fba4406` → `origin/main`
- [x] **Issue 4 Prompt B 显式规则版 v2**（`c7253fb`）：新提示词 `prompts/jd/jd_ats_analysis_v2.txt`（禁止编造、required/preferred 归属、职责内含技能、缩写归一、维度按 JD 给级、薪资地点必填、文化/指标禁止推断）；agent `_ATS_PROMPT_VERSIONS={"v1":1,"v2":2,"v3":3}` 分发；runner `--prompt-version` 支持 v1/v2/v3 + `_load_version_preds_latest`（last-wins 去重）+ 通用 A/B/C 对比表（从全部可用 pred 文件组装；证据统计改读 v3 文件）；v2 mock 单测；**实测 40/40 有效**：Critical Error Rate **25.52%**（未跑赢 v1 23.14%、v3 20.35%），Required F1 0.584、Responsibilities 0.423（最佳）、Preferred 0.627（最佳）、Keywords 0.065、Dimension 0.097、Salary 36/40、Location 32/40 → **结论：显式规则不比基线与 evidence-first，Issue 6 坐实「证据优先是唯一稳定安全杠杆」**
- [x] **429 根治**（`8905ee3` + runner 配套）：真根因 = `ChatOpenAI` 默认 `timeout=None`，评测「弃线程」后 HTTP 请求仍在飞，持续占账号并发/速率额度 → llm.py 从 `LLM_REQUEST_TIMEOUT`（默认 180s）注入真实请求超时；runner 外层 150s→200s（让请求先自断）；新增 429/1302 60s×N 退避重试（救回 29→40 有效，无该重试前整轮会写假失败）；残余失败为 **1305 服务端忙**（glm-4.7-flash 空闲额度高峰排队），单条探测可恢复
- [x] **Issue 6 A/B/C 终版报告**（`640a3ba`）：对比表浮点格式化 + 修复「v3 raw 列误读已校验 ats」（现在 raw 与校验两态真实分开）、新增**数据驱动的总结论段**；终版以 v3 为主管线重生成：**C 的 raw 关键错误 27.81%（比基线还差）→ 确定性校验后 20.35% 且错误数 1017→901**，Required F1 0.600(A)→0.5226(raw)→0.458(校验)；结论：提示词堆规则压不住幻觉，「输出+确定性证据校验」是唯一稳定安全杠杆（代价是召回/标量下行，维度全线偏弱建议回归直接输出，Keywords 需单独任务）
- [x] 已提交并推送：`8905ee3`（llm）/ `c7253fb`（Issue 4）/ `640a3ba`（Issue 6）→ `origin/main`（`fba4406..640a3ba`）
- [ ] **下一步**：v0.4 收口（可按需把结论写回 PRODUCT/ARCHITECTURE 文档）；或进入下一个里程碑（如把 evidence-first 落为生产默认 + 维度约束、Keywords 独立任务）

---

**更新规则**：每次会话结束时，AI 必须根据本次实际完成的工作，移动或新增上述列表中的条目，并简要描述进展。

### v0.4 JD 生成四步收口（软校验 + 本体归位 + 职责/技能纠正 + 回归报告）

- [x] **Issue: C' 软校验（ACCEPT/REVIEW/REJECT 三档）** -> 提交 `2587be7`；econcile_evidence 仅丢弃 REJECT、REVIEW 项保留并写入 eview_flagged，	rusted_view 剥离 REVIEW 供信任面；_ACCEPT_THRESHOLD=0.6、_REVIEW_THRESHOLD=0.4。实测：字符 Dice 档位下 REVIEW 队列过窄（40 例仅个位数入队），调阈值无效果，REVIEW 语义门槛 ~0.78 需嵌入相似度（列为 Layer-2 架构迭代）。
- [x] **Issue: 本体归位（教育/年限从技能列表迁出）** -> 提交 `424cf7a`；split_ontology_claims 确定性格式化迁往 education/years_of_experience（含 _EDU_PATTERNS/_YEARS_RE 等常量），混合短语保守不拆；v3/v2 prompt 补归位铁律。
- [x] **Issue: Responsibilities/有限技能纠正** -> 提交 `4a15175`；classify_sentence_role（能力动词→skill / 动作动词→responsibility / 其他→ambiguous）+ eclassify_claims 对称移动动词引导条目；两版朴素端点（全部→技能 / 全部→职责）经验证放弃；v3 铁律5 / v2 规则10。
- [x] **回归报告修复** -> 提交 `5deee6d`；un_jd_eval 增加 ebuild_pipeline：C' 证据校验列与顶部汇总都按 当前管线（本体归位→职责/技能纠正→软校验）从缓存 raw 重建，消除旧 ats 缓存失真。
- [x] 全量验证：uv run pytest tests/ -q 472 passed, 6 skipped；ruff 通过。报告重生成（0 LLM 调用，全部走缓存 raw 重建）。
- [x] 三特征提交（`2587be7`/`424cf7a`/`4a15175` 未推送）+ 报告修复（`5deee6d`）与格式清扫（`1178909`）已提交，待推 origin/main。
- [x] **当前 v3 主管线**：raw -> split_ontology_claims -> eclassify_claims -> econcile_evidence(soft)，返回 {ats, raw, review_flagged}。
- [x] **回归指标（v3 全量 LLM 实测 40/40，2026-09-10，确定性管线）**：Critical (C' 校验) **13.51%** < v1 基线 23.14% < C raw 22.55%；Salary raw 25/40 -> 校验 31/40、Location 23/40 -> 30/40；Required F1 0.5880(raw)->0.5435(校验)、Responsibility 0.4411->0.3586、Preferred 0.5735->0.5920（校验反升）；E1 597 / E2 97 / E3 56 / 总错误 902(raw)->836(校验)；证据命中 32/40、条目 434、REJECT 丢弃 139；结论：软校验把 Critical 压到三类最低并靠标量回填抬升 Salary/Location，职责召回仍是代价（REVIEW 宽度 ~0.78 嵌入相似度升级为 Layer-2 待办），dimension/keywords 偏弱需单独方案；3 例 1305 繁忙补跑成功（jd_015/029/035）。
- [x] **v3 prompt 全量 LLM 实测**：40/40 成功（3 例 1305 补跑），指标见上；push 待用户确认后推送；结论建议落 PRODUCT/ARCHITECTURE 文档。
- [ ] **架构迭代（Layer-2）**：REVIEW 宽度升级到嵌入相似度（~0.78），实操 3 层流水线（Extraction -> Normalization -> Validation）+ A/B/C/C' 实验矩阵。
### v0.5 ATS Pipeline 三层重构（Layer-2 落地，2026-09-12，依据 docs/evaluation/JobCraft ATS Pipeline v0.5.md）

> 目标：把 JdAtsAgent 从"全能解析器"降级为"语义推理器"。原则：能规则→规则，能算法→算法，语义/复杂推理→LLM。

- [x] **评估结论（与 v0.5 文档对齐）**：采纳 L0 元数据直取、L1 纯脚本切分/分类、UNKNOWN→LLM fallback、Evidence 从 Span 构建、Key Metrics 算法化、Keyword=Recruitment Signal、评测分层；对文档的两处调整——ATSProfile 保留现有契约只加可选字段（soft_skills/core_keywords，避免破坏 API），Matching Engine 重构后置不纳入本轮。
- [x] **TASK-P5-01 jd_structurer.py（L1 切分层）**：新增 pp/pipeline/ 包。structure_jd(text) 按标题词典（职责/要求/加分/福利/公司/薪资/地点/概述）做 Section Detection，规则：标题后须跟冒号/换行/行尾（防正文词汇误判）、重叠命中取最长（「任职要求」覆盖「要求」）、「坐标+城市名」无冒号特例（语料即 坐标北京 格式）；Item Split 按换行/分号/句号/列表标记切分并清洗；**Span Extraction 每 item 带原文 [start,end) 偏移**；无标题整段降级 unknown 区块；meta(薪资/地点) 单独收集。单测 9 条（tests/test_jd_structurer_unit.py）全过；ruff clean。
- [x] **TASK-P5-01 语料验证（40 条 jd_cases）**：requirements 40/40、responsibilities 40/40、salary 40/40、location 40/40、preferred 32/32（8 条语料无加分标题或「…是加分项。」行内短语，属正常，其归类交给 jd_classifier）；**40 条全量 items span 零失配**；平均 2.0 items/区块；无标题降级 0 条（语料全部有结构化标题）。诊断脚本 evaluation/run_jd_structurer_stats.py（python -m evaluation.run_jd_structurer_stats）。
- [x] 全量回归：uv run pytest tests/ -q 476 passed, 11 skipped（+9 新单测；skipped 增量来自后端未启动的 5 条 e2e 环境性跳过）。
- [x] **TASK-P5-02 jd_classifier.py（L1 规则分类）**：新增 `app/pipeline/jd_classifier.py` + `app/pipeline/data/{soft_skills,technical_skills}.json`。五类（REQUIRED/PREFERRED/RESPONSIBILITY/SOFT_SKILL/UNKNOWN）由 Section+Trigger+Verb+Context 联合判定：区块先验、显式标记（优先/加分/尤佳/Bonus）、软能力程度语境正则（`沟通能力强`/`较强的业务理解能力`/`执行力强`）、动词首发复用 `classify_sentence_role`（与 reclassifier 词表一致）、学历/年限 gate 复用 `_EDU_PATTERNS/_YEARS_RE`、无动词名词短语靠 requirements 语境兜底为必需；**meta（薪资/地点）区块不参与分类**（L0 处理，不污染 LLM fallback）；把握不足才 UNKNOWN（不硬猜）。单测 15 条；40 语料 span 级近似召回：required 0.702 / preferred 0.833 / responsibility 0.420（gold 为细分短语而条目为整句的粒度差，正式 F1 归 TASK-P5-07）、UNKNOWN 仅 1 条；诊断脚本 `evaluation/run_jd_classifier_stats.py`；ruff clean；pytest 491 passed/11 skipped。
- [x] **TASK-P5-03 evidence_builder.py（Evidence 从 Span 构建）**：新增 `app/pipeline/evidence_builder.py`。`build_source_evidence` 把分类条目固化为证据（span=[start,end)、field 由类标签映射、relation=EXACT 构建即真，不猜证据）；`grade_relation` 五级关系（EXACT/CONTAINED/PARAPHRASE/INFERRED/UNSUPPORTED，阈值 0.6/0.4 与 evidence.py 同源）；`to_verdict` 折算回 ACCEPT/REVIEW/REJECT 三档；`grade_entity` 多 span 择优。**Evidence 不再是主分类器**（归类前移 jd_classifier）。单测 8 条；40 语料组合链路（structurer→classifier→evidence）307 条证据全 EXACT + span 零失配；ruff clean；pytest 500 passed/11 skipped。
- [x] **TASK-P5-04 jd_extractor.py（字段全算法化）**：新增 `app/pipeline/jd_extractor.py`。education/years 复用 `_EDU_PATTERNS/_YEARS_RE`；required_skills 合并职责桶后的 tech-token（gold 同款：职责里出现的技能也算核心要求）＋能力短语兜底（`_capability_parts` 拆「熟悉功能测试、回归测试」并列列表）；preferred/soft 分桶；key_metrics 数字+量词正则（容忍 500+、30 家）；**core_keywords=Recruitment Signal**（§十五/§十六：frequency/section_weight/强调词 → high/medium/low）；salary/location 取 meta 区块；tech 词典补 Spring Cloud/pytest(+2)。gold 命中：required 55.4%（50.4→55.4，+11 via 责任桶/拆列表）、preferred 21.1%（其余为词典外领域词/gold 推理性词 → Task06 L2 LLM；**不针对 gold 扩词典防 eval 泄漏**）；education 9/9、years 38/40。单测 20；ruff clean；pytest 520 passed/11 skipped。
- [x] **TASK-P5-05 ATSProfile 可选字段（契约不变）**：`app/schemas/jobcraft.py` 新增 `KeywordSignal` 模型＋`ATSProfile.soft_skills`／`core_keywords`（均 default_factory，旧 payload 兼容）；KeywordSignal 从 extractor 下沉 schemas（单一来源，无循环导入）。单测可视图 2 条；pytest 522 passed/11 skipped。
- [x] **TASK-P5-06 JdAtsAgent 分层收窄（v0.5 Task06）**：新增 v4 prompt + `AtsInference`/`AmbiguousDecision` schema。`_run_v4` 自包含编排：L1 管道全量先跑，LLM 输入=结构化摘要（needs_review=UNKNOWN/低置信条目透传）＋截断 JD，输出仅 job_title/culture/D1-D8/subtext/歧义裁决；`merge_ats` 确定性合并 ATSProfile（L1 字段全保留、歧义按 item_id 回桶、evidence 从 span 构建、core_keywords 带出）。v1/v2/v3 分支原样保留，默认仍 v3。40 语料 L1 dry-run 无异常。单测 +3；pytest 525 passed/11 skipped。
- [x] **TASK-P5-07 分层评测基线 + 真实 JD 语料框架**：新增 `evaluation/run_pipeline_eval.py`（无 LLM）：L1-1 span 零失配；L1-2 307 条目 UNKNOWN 1；L1-3 gold 近似命中 required 55.4%/preferred 21.1%/responsibility 45.4%、edu 9/40、years 38/40、metrics 32、core_keywords 97/37/8；ATS-Safety（空 inference 合并，逐值证据支撑）accept 323/review 1/reject 0 → **支撑率 100%，L1 无幻觉（无 LLM 故符合设计）**；报告 `evaluation/reports/ats_pipeline_l1_report.md`。新增 `load_real_cases`（`real_jd_cases.jsonl`，`source`/`gold_pending`）＋5 条草稿样例（gold_pending=True 待人工补，管道零 UNKNOWN）。真实 v3/v4 40 语料 LLM 对比延后执行（避免 API 成本，按用户确认）。

- [x] **TASK-P5-08 真实 JD 语料落地（40 条，用户填表生成）**：生成 `real_jd_cases_template.xlsx`（12 列：case_id/source/job_title/jd_text/salary/required_skills/preferred_skills/responsibilities/culture_keywords/dimensions/subtext/notes，双 Sheet 说明+填写，冻结表头+示例行）。用户填完 `real_jd_cases_completed.xlsx`（40 条真实 JD，来源 boss/直聘等；**gold 由 GPT 辅助生成 + 人工粗略核对**，英文外企岗（real_014 等）以 GPT 输出为主、人工只做少量修正）→ `evaluation/build_real_jd_cases.py` 转换：gold 按 逗号/顿号/分号/换行/项目编号 拆分、dimensions/subtext 解析、case_id 自动补号、**gold_pending 自动标记（8 条缺 preferred_skills：real_005/010/011/014/027/037/038/040，用户核对后确认多数确无 preferred 要求，属正常；real_014 job_title 后续手工补为「项目管理（外企·HSBC）」）**、与已有条目合并。`run_pipeline_eval.py` 支持 `python -m evaluation.run_pipeline_eval <数据集>`＋报告 UNKNOWN 占比，真实语料端到端可评测。**真实语料 L1 基线**：span 失配 0；classifier 694 条目 **UNKNOWN 199（28.7%）——40 模板语料训练的 classifier 面对真实长文/表述/英文 JD，是调优信号而非故障**；gold 近似命中 required 17.9%/preferred 17.1%/responsibility 64.4%（gold 为用户粗略填写，real_014 等单元格直接粘贴原文段落；gold_pending 诚实标记不掩盖）；education 35/40、years 13/40（英文/口语化年限表述有待 `_YEARS_RE` 覆盖）；core_keywords 91/66/42；ATS-Safety 支撑率仍 100%。模板 JDs 回归不变（307 条目 UNKNOWN 1/0.3%）。报告 `evaluation/reports/ats_pipeline_real_jd_cases_report.md`。→ commit `b257c5c`（7 文件）。

## v0.5 待办（下一步）
- [ ] TASK-P5-09 运行真实 40 语料 v3 vs v4 对比（F1/token/延迟），达标后切默认 v4；依赖 UNKNOWN 28.7% 的分类器调优或对真实语料放宽
- [x] 真实 JD 语料补齐：已由用户填表落地 40 条（含 gold_pending 8 条待人工/LLM 补 preferred 等）
- [x] 真实语料粗糙 gold 收尾（`29e973c`）：8 条缺 preferred 经用户确认为真实无该节 → gold_pending 全置 false，`build_real_jd_cases.py` 改为重建时保留手工确认标记（不再被自动规则重算覆盖）；real_014 英文 gold 按原文 bullet 精修为 4 required/5 responsibilities（去 Qualifications/you will: 等段首噪声与断词），job_title 上轮已补；`_split` 改为「单元格含换行 → 仅按换行/顿号/分号拆分，保留含逗号/斜杠的整句」防过度切片（英文 Slash 复合词不再断开）。真实 L1 基线随 gold 精修微调：required 19.96%（110/551）、preferred 16.38%（29/177）、responsibility 66.79%（370/554）；UNKNOWN 28.7%、span 0、ATS 支撑 100% 不变。
- [ ] PROGRESS 挂起项：Regression 基线固化（#5）、PDF stub（#6）、文档写回（#16）

### v0.5 收口：v4 preferred 召回规则级修复（2026-09-13，本轮）

- [x] **根因定位（真实 40 语料 + 重标 10 条抽样）**：v4 preferred F1 差距（v4−v3 ≈ −0.34）是真实的，主因在 L1 管道而非 LLM：
  - `jd_structurer` 把正文「者优先考虑 4、」里的「优先考虑」误判为 PREFERRED 标题 → 新 section 剥走条目内「优先」标记 → `classify` 判不出 PREFERRED（real_039 item7 实证 `has_youxian: False`）；
  - 标题词典缺「职责描述」→ real_039 职责整段掉进 JOB_OVERVIEW/UNKNOWN；
  - 条目只按 `；;\n。` 切分、不认序号列表标记 → 长资格段合成一条大条目（real_039 item7 长度 91）；
  - `jd_extractor` 的 preferred 完全依赖技术词典（`_find_tech_tokens`）→ CPA/CFA/FRM、团队管理经验、多模态AI 全丢。
- [x] **修复（rule-based，不动 LLM；单节点仍一次调用）**：
  - `jd_structurer.py`：① PREFERRED 词典移除「优先考虑」（防正文误判）；② RESPONSIBILITIES 词典新增「职责描述」；③ `_split_raw_items` 新增序号列表标记边界（`(?<=\s)` + `\d+[、.．）]`/`（1）`/`①-⑩`/`\d+\.(?!\d)`，兼容 Python 3.9 等版本号，span 偏移保持正确）；
  - `jd_extractor.py`：新增 `_preferred_candidate_parts`（剥尾缀"者优先/优先考虑/加分项/尤佳/持证"与「等…工具」括串 → 去动词 → 按标点拆原子项 → 过滤软词/学历/年限门槛），`_extract_preferred_skills` = 词典 token ∪ 非词典候选去重合并；`merge_ats` 无需改动（preferred 直取自 extraction）。
- [x] **测试**：`test_jd_structurer_unit.py` +9（序号拆条/职责描述标题/正文「优先考虑」不幻生区块/版本号不被拆 + span 校验）、`test_jd_extractor_unit.py` +5（持证/多技能拆分/团队管理经验/多模态AI/噪声与门槛丢弃）；全量 `uv run pytest tests/ -q` **534 passed, 11 skipped**；ruff 通过。
- [x] **验证（真实 40；v4 预测从缓存 raw 确定性重建，0 次 LLM 调用）**：
  - 全量：preferred F1 0.2232 → **0.5767**；responsibilities 0.5612 → 0.5874；required 0.2301 → 0.2363；
  - spot-gold（10 条重标）：v4 preferred 0.1277 → **0.5349**（v4−v3 从 −0.3446 翻转为 **+0.0627**）；required 0.4507 → 0.4615（Δ+0.0118）；responsibilities 0.6667 → **0.8085**（Δ+0.1210）；critical Δ−0.0709（安全优势保留）；
  - 关键 case：real_033 抽出 CPA/CMA/高级会计师、real_039 抽出 Python/SQL/SAS/CPA/CFA/FRM/团队管理经验、real_024 preferred 覆盖 Prompt/Agent/LLM/RAG/大模型/Fine-tuning。
- [x] **结论**：v4 preferred 规则级召回差距已闭合；按 calibrated 口径 v4 在 required/preferred/responsibilities/critical 四项全面 ≥ v3，切默认 v4 前提满足。剩余标题混入（real_024/034）、长句原子拆分（real_033 ERP 系列）为粒度优化项，不阻塞切版。

### v0.5 收口：v3 vs v4 对比产物 + 标题/薪资 stub 修复（2026-09-13，本轮 · 对应 v4 重构 Prompt §16/§17/§22）

- [x] **新增 `evaluation/compare_jd_v3_v4.py`**：`evaluation/results/v3_vs_v4.json`（§17 逐 JD diff：v3/v4 四字段 + only_v3/only_v4/both）+ 聚合指标 + 字段迁移统计；支持 `--spot-gold` 复算校准口径。0 次 LLM 调用。
- [x] **修复① `jd_structurer` 方括号标题**：`_detect_headings` 支持 `【岗位职责】/【任职要求】/【加分项】` 等 `【…】/[…]` 包裹写法（原「加分项」后跟 `】` 不满足标题跟随符 → 区块不切，real_024 加分项误入 required）。
- [x] **修复② `merge_ats` LLM 只裁决 UNKNOWN + 滤 stub**：歧义裁决仅在当前 L1 未定论（UNKNOWN）条目生效，过滤 markdown 标题行（`##Al Builder - 产品`）与全粗体薪资 stub（`欣旺达**生产经理****17-22k**`）；同时隔离缓存远期 raw 陈旧裁决污染重建。
- [x] **修复③ `run_jd_eval` 缓存重建持久化**：v3/v4 重建行写回预测文件（latest-wins），spot/compare 读到新 L1（此前只改内存不写盘）。
- [x] **测试**：`test_jd_structurer_unit.py` +2（`【…】` 区块、行内 `【岗位职责】`）、新增 `tests/test_merge_guard_unit.py` +4（L1 已定论不覆盖 / 标题 stub / 薪资 stub / 真 UNKNOWN 裁决生效）。全量 pytest **540 passed, 11 skipped**；ruff 通过。
- [x] **v4 全量重建**（缓存确定性重建，0 LLM 调用，写盘）：required F1 0.2363→**0.2475**、preferred 0.5767→**0.5864**、responsibilities 0.5874→**0.6139**；real_024/034 required 中 stub 清零。
- [x] **对比结果（40 条真实 JD）**：
  - 官方 gold：v4 在 preferred（0.3557→0.5864，Δ+0.2307）、responsibilities（Δ+0.1466）领先；required（Δ−0.0556）、critical（+0.0579）落后（官方 gold 噪声 + v3 证据误杀被当正确，已记录不修改 gold，§18）；
  - 重标 spot-gold（10 条）：v4 **四项全面 ≥ v3** —— required Δ+0.0430、preferred Δ+0.0992、responsibilities Δ+0.2346、culture +0.0025、critical **Δ−0.0929**（更安全）；
  - 成本：v4 仍 1 call/JD（仅 advanced 字段），total tokens −17.6%、completion −48.6%。
- [x] **归档**：`evaluation/reports/jd_v3_vs_v4_compare.md`（含逐字段迁移表与决策依据）。

### v0.5 结构化 JD 分析（前端分类，2026-09-13，本轮）

> 依据用户方向调整：前端把 JD 拆成 公司/岗位/岗位职责/任职要求（逐条打标签）5 部分，地址与薪资不纳入分析；后端仅对「岗位职责+任职要求」做 1 次 LLM 细节分析。

- [x] **后端契约**：新增 `StructuredRequirementItem`/`StructuredJDAnalyzePayload`（`app/schemas/jobcraft.py`，`ATSProfile` 未动、下游匹配兼容）；`app/api/job_analysis.py` 新增 `/job/analyze-ats-structured`（duties/requirements 全空→400、标签非法→400）与 `/job/split-jd`（粘贴原文→自动拆分 duties/requirements，`_PREF_TAIL_RE` 命中「优先/加分/尤佳」进 preferred，其余 required；meta/job_overview/company_info/benefits 不进入分析）。
- [x] **后端实现**：`app/agents/jd_ats_agent.py` 新增 `analyze_structured_jd`/`_build_structured_from_input`/`_structured_to_text` —— 用户标签确定性生成 `ClassifiedItem`（duty→RESPONSIBILITY/responsibilities；hard/required→REQUIRED/requirements；preferred→PREFERRED/preferred，confidence 恒 1.0 无 UNKNOWN），`merge_ats` 歧义守卫天然阻止 LLM 覆盖用户标签；仍复用 `extract_jd`（学历/年限/指标/技能 token 确定性）+ 1 次窄 LLM（`_build_v4_prompt`）+ `merge_ats`；**salary/location 恒 None**。`app/workflows/job_analysis_flow.py` 新增 `run_structured_ats_workflow`（返回 `{ats_profile, raw, company, position}`）与 `run_structured_ats_split`。
- [x] **前端**：`api/job.ts` 新增 `StructuredRequirementItem`/`analyzeStructuredJd`/`splitJd`；`JobCraftContext.tsx` 新增 `createStructuredJDAnalysis`（调 `analyzeStructuredJd`，把 ats_profile 映射为前端 `JDAnalysis`，自动建 Job 置为 interviewing）；`JDAnalysisCenterView.tsx` 重写为结构化表单：公司/岗位/职责(textarea 每行一条)/任职要求（逐条 + 硬性门槛/必选/加分项 3 档标签）+「粘贴原文自动拆分预填」（调 `splitJd`，可手工微调）。
- [x] **验证**：后端单测 +9（标签映射、复用管线断言 salary/location None、workflow 正常、split preferred 分流、API 空文本/非法标签 400 等）；`uv run pytest tests/ -q` **549 passed, 11 skipped**；ruff 通过；前端 `npm run build` 通过。
- [x] **提交**：`1f19180` feat(api): structured JD analysis from frontend-split duties and tagged requirements；`5ebe32f` feat(frontend): structured JD analysis form with tagged requirements and auto-split prefill。
- [x] **收口（后续小修）**：`af71973` refactor(jd): drop education/years parsing（学历/年限门槛统一由前端 hard 标签表达）；`0686e05` docs(frontend): 任职要求表单下加三档标签说明框（核心一问：不满足直接刷掉？硬性=纯年限/统招本科/证书；必选=核心能力「N年+某领域」；加分=没有也录用）+ 底部说明改为仅分析职责与要求；`804a9d2`/`a0e7f55` ruff 收尾（W292、S101 assert → ValueError 守卫 + 新测试）。全量 pytest 555 passed/6 skipped。
- [ ] **待办**：结构化结果的 `JDAnalysis` 映射为「轻量视图」（当前 matchScore/whyMatch 等匹配类字段为空，报告页按 ATS/子文本展示）。

### 底座简历历史版本持久化（2026-09-14，本轮）

> 修复「底座简历与历史版本管理」刷新后看不到已上传简历：`historicalResumes` 原为纯前端内存 state（无后端表/端点），新增 `base_resume` 表 + CRUD 端点，上传确认后落库、启动时拉回。

- [x] **后端**：新增 `app/tools/db_base_resume.py`（`base_resume` 表：user_id/name/file_size/format/parsed_count/tags/is_default/时间戳；`_ensure_base_resume_table` + create/list/get/delete/set_default，set_default 事务性先清旧默认）；`app/api/experience.py` 新增 4 个端点：`POST /experience/base-resumes`（首条自动 is_default）、`GET /experience/base-resumes`、`PATCH /experience/base-resumes/{id}/default`、`DELETE /experience/base-resumes/{id}`（缺失 404），均 JWT。
- [x] **前端**：`api/job.ts` 新增 `BaseResumeRecord` + create/list/setDefault/delete 四个方法与端点对应；`HistoricalResume` 类型加 `serverId`；`JobCraftContext.tsx` 新增 `loadHistoricalResumes`（并入 `loadUserProfileAndData` 的 Promise.all），`addHistoricalResume` 上传后 POST 落库并用返回值回填 serverId，`deleteHistoricalResume`/`setDefaultHistoricalResume` 同步后端。
- [x] **验证**：路由单测 +6（首条默认/后条非默认/设默认翻转/404 两条）；`uv run pytest tests/ -q` **561 passed, 6 skipped**；ruff check/format/S 全绿；前端 `npm run build` + `tsc --noEmit` 通过。

### 岗位状态模型：steps 派生 + 全生命周期分类（2026-09-14，本轮）

> 用户反馈：新建 JD 后「我的岗位」错误显示「面试中」。根因：新岗位建立时一律硬写 `status: 'interviewing'`（`JobCraftContext.tsx`），且 `steps` 进度标志（jdAnalysis/prepStage/reviewStage）已存在却未驱动状态。改为**状态由 steps 派生（单一事实源），流程只更新 steps**。

- [x] **状态分类**（优先级从高到低）：`steps.terminated → 已结束 finished` > `prepStage === 'in_progress' → 待面试 interviewing` > `reviewStage === 'done' → 已复盘 reviewed` > `jdAnalysis → 待投递 delivered` > 其余 → 待处理 pending。`JobStatus` 类型新增 `'reviewed'`；`Job.steps` 新增可选 `terminated`。
- [x] **派生函数**：`deriveJobStatus(steps)`（`JobCraftContext.tsx` 模块级纯函数）；`submissionToJob` 改为依据 `prep_count vs review_count` 推导 prepStage（prep>review → in_progress 待面试；prep==review → done 已复盘）并派生 status；`createJob` 移除 `status` 入参。
- [x] **流程接线**：`createJDAnalysis`/`createStructuredJDAnalysis` 自动建岗改为 `status: deriveJobStatus(autoSteps)`（JD 分析完成 → 待投递）；`createInterview` 只设 `prepStage: 'in_progress'`（→待面试），不再写 status；`addInterviewReview`/复盘完成时同时设 `reviewStage: 'done'` 与 `prepStage: 'done'`（首次复盘 → 已复盘；**新一轮 prep 会再翻转为待面试，符合"多轮待面试优先"**）。
- [x] **UI**：`JobsListView` 移除手动状态下拉，改为「标记已结束 / 恢复处理」按钮 + 增「已复盘」筛选 tab；`WorkbenchView` 四张统计卡改为 待投递岗位/待面试(+已复盘)/待处理分析；`JobWorkspaceView` 状态徽章；新增 violet 主题色（`--color-violet`/`--color-violet-soft`）用于「已复盘」。`NewJobModal` 移除「初始推进状态」选择器（新建即待处理）。`CreateInterview`/`CreateReview` 依赖 `steps` 的过滤条件无需改动。
- [x] **验证**：前端 `npm run build` + `npm run lint (tsc --noEmit)` 通过。

---

### v0.24 全项目扫描修复：P0/P1 收口（2026-09-16，本轮）

> 依据 TODO.md「全项目扫描」板块清单，按用户选择范围 A 修复 P0/P1（越权契约迁移、PostgreSQL 升级、V1 命名空间等不做）。

- [x] **P0-1 认证对接修复**：`app/auth/router.py` `UserInfo` 新增 `id` 字段（与 `user_id` 同值），`/me` 返回 `UserInfo(id=..., user_id=..., ...)`，前端 `autoLogin()` 的 `profile.id` 恢复可用 → `JobCraftContext` 用户信息不再为 undefined。
- [x] **P0-2 注册规则对齐**：`frontend-jobcraft/src/pages/AuthPage.tsx` 注册表单改为同时校验「长度 ≥8 + 含字母 + 含数字」，与后端一致，避免前端放行后端 400。
- [x] **P1-1 任务参数传递**：`app/tasks/handlers.py` `execute_resume_generate` 从 params 读取 `company`/`position` 传给 `run_job_analysis_workflow`（不再丢参）。
- [x] **P1-2 简历生成参数修复**：`execute_export_pdf` 改用 `selected_card_ids`（向下兼容 `card_ids`）＋必填 `job_analysis_id`＋传 `user_id` 给 `generate_resume`。
- [x] **P1-3 review strengths 恒空**：`app/workflows/interview_review_flow.py` `_assemble_result` 对 score≥80 的分析项推导优势点（如「D1 回答表现良好（85分）」），不再恒回退 `["等待评估"]`。
- [x] **P1-4 上传去重**：`app/api/experience.py` `upload_confirm` 以 company+role 为键做集合去重（`find_card_by_company_role`），防止重复插入。
- [x] **P1-5 四层架构合规（polish）**：`api/experience.py` polish 端点的 LLM 调用提取至 `app/tools/experience_polish.py`（统一 `core.llm.model`），prompt 外部化至 `prompts/experience/polish_v1.txt` 并注册进 `tests/test_prompts.py`。
- [x] **P1-8 四层架构合规（mock_chat）**：`api/interview_review.py` mock-chat 端点的 OpenAI 直接调用提取至 `app/tools/mock_chat.py`（复用 `interview/mock_interview_chat` 模板 + `core.llm.model`），移除未用 `load_prompt` import。
- [x] **P1-9 孤儿数据清理**：`app/tools/db_job.py::delete_job_analysis` 与 `app/tools/db_submission.py::delete_submission` 删除前先清关联 `interview_qa_pairs` / `interview_records`（按 job_analysis_id / submission_id）与 `interview_preps`。
- [x] **P1-10（部分）假事务修复**：上述两个多表删除函数改为 `conn.autocommit = False` + 末尾 `conn.commit()`，保证级联删除原子性；测试桩 `_FakeConn` 补 `commit()`、`test_delete_job_analysis` 补 `fetchall` mock。
- [x] **验证**：`uv run ruff check/format` 全绿；`uv run pytest tests/ -q` **556 passed, 11 skipped**（`test_prompts` 注册新增 polish 模板）；前端 `npm run build` 通过（1705 modules，仅既有 CSS/chunk warning）。
- [x] **延迟项（不阻塞）**：P1-6 `job_analysis_flow.py:181` 单节点 3 次 LLM（legacy 未接线）；P1-7 `extract_flow.py:62` 循环 N 次 LLM（每 entry 独立单次；架构改进需专项）；P1-10 余下 `_ensure_*` 并发 ALTER 收敛为启动一次性 DDL 排入 v0.25。
- [ ] **待办**：P2 技术债（Tool→Agent 循环依赖/静默 except/前端大组件与 N+1 等）按余量后续处理；TASK 延迟项各自立项。
- [x] **提交**：`ff3a098` fix: resolve P0/P1 scan findings across auth, tasks, workflows and data integrity（已推 origin/main）

### v0.25 设计决策对齐：统一错误契约 + 异步化 + 前端真实性修复（2026-09-16，本轮）

> 依据 `docs/design-decisions/design-v2.0` 下 14 个设计文档，按用户确认的 **P0 清单**（不引入 P1/P2 新领域模型、不新增产品功能、不重做 UI）逐项修复，全部 typecheck/test/review 通过后单独 commit。7 个 commit 已推 origin/main；另含 TASK-P1-10 运行时 DDL 启动引导（`48a5f5e`）。

- [x] **P0-5 岗位所有权校验** `5b34213`：`app/api/interview_prep.py` selected-cards 查询校验岗位归属当前用户，防止跨用户读取；新增 `tests/test_api_routes_unit.py::TestSelectedCards`。
- [x] **P0-1 统一错误契约（后端 + 前端）** `785eadc` / `3017973`：FastAPI 全局异常统一返回 `{error:{code,message,details,requestId}}`（对应 spec 契约，替换旧 `{code,msg}`）；前端 `api/client.ts` 新增 `parseUnifiedError` 优先解析 `body.error.message`、兼容旧 `body.msg`；后端测试迁移 + 新契约用例。
- [x] **P0-4 导航与契约缺陷 + InterviewDraft 单一类型源** `5a759b9`：`App.tsx` 增 `settings` 分支→UserProfileView；`InterviewPrepCenterView` 复盘详情路由 `interview_review`→`interview_review_detail`；`CreateReview` 复盘契约修复（`{interviewId, transcript}` + 白名单导航 + 独立模式守卫）；`createReviewFromTranscript` 改 async 返回 `Promise<string|undefined>`；`types/jobcraft.ts` InterviewDraft 补 `resumeMode?`/`selectedResumeId?`，`NewInterviewModal` 统一用 `Partial<InterviewDraft>`（前端唯一类型源）。
- [x] **P0-3 前端真实性修复** `7e731c6`：`InterviewReviewDetailView` 移除伪造默认值（'int-byte-1'/interviews[0] 兜底/硬编码 metricCards/intentItems/competencies/coreProblems/analysisBars/qScore 75/duration），意图项改由真实 mainPoints 派生，缺失显示空态；`CreateReview` 删 demoTranscriptText；`JDAnalysisCenterView.handleUsePreset` 本地正则复刻分类→改调后端 `splitJd`；`JobWorkspaceView` 删 'int-byte-2'；`MockInterviewModal`/`InterviewPrepWorkspaceView` 删 `|| interviews[0]`；readinessPercent 兜底 40→0。
- [x] **P0-2 高耗时 LLM 端点异步化（后端 + 前端）** `1becb76` / `5db36a6`：`app/tasks/handlers.py` 新增 5 类任务（`jd_analyze_structured`/`interview_review_analyze`/`question_table`/`parse_preview`/`experience_polish`）执行器 + 注册表；同步端点保留作降级；前端 `api/tasks.ts` 新增 `runTaskOrSync<T>`（submit+poll，任务系统不可用自动降级同步）；`JobCraftContext` analyzeJob→resume_generate、createStructuredJDAnalysis→jd_analyze_structured、createReviewFromTranscript→interview_review_analyze；ExperiencesView polish→experience_polish。`parse_preview`/`question_table` 无前端活跃调用点，仅注册后端任务类型（commit 内说明）。
- [x] **验证**：单个 P0 任务均跑了后端单测 + 前端 `npm run lint`（tsc --noEmit）+ `npm run build`；本轮收尾全量 `uv run pytest tests/ -q` **566 passed、11 skipped**，`ruff check/format` 全绿；前端 build 通过。
- [x] **已推送**：上述 7 个 commit（`5b34213`..`5db36a6`）已 `git push origin main` 成功（`ff3a098..5db36a6`；推送权限受限疑虑已消除，本地与 origin 同步）。
- [x] **P1-10 运行时 DDL 收敛为启动一次性引导** `48a5f5e`：`app/tools/db_conn.py` 新增 `_schema_ready` 标志 + `is_schema_ready()`/`mark_schema_ready()`/`reset_schema_ready()`；新增 `app/tools/db_bootstrap.py`（`_BOOTSTRAP_STEPS` 11 步按依赖排序 + `run_schema_bootstrap()`，先经 `db_tools` re-export 链加载经典 db_* 模块以规避 `db_experience ↔ db_tools` 循环引用）；11 个 `_ensure_*`（db_user/db_base_resume/db_experience×2/db_job/db_submission×2/db_interview×3/profile）入口加 `if is_schema_ready(): return` 短路；user_profiles DDL 从 `app/api/profile.py`（API 层直写 DDL）下沉至新增 `app/tools/db_profile.py`；`app/api/server.py` lifespan 与 `app/tasks/worker.py` run_worker 启动时调用引导；新增迁移 `migrations/versions/V0005__runtime_tables.sql`（base_resume + user_profiles，前向兼容 CREATE TABLE IF NOT EXISTS）。失败语义：任一 DDL 失败仅记 warning、不置位标志、请求路径退化为改造前逐调用行为（完全兼容）；docstring 记录多进程部署建议先跑 `python -m migrations.runner migrate`。
- [x] **P1-10 验证**：新增 `tests/test_db_bootstrap_unit.py`（7 条：标志往返/步骤顺序/幂等/失败不置位/就绪即短路/未就绪仍执行 DDL/启动钩子接线）+ `tests/conftest.py` autouse 重置夹具；`tests/test_observability.py` 用 monkeypatch 短路 lifespan 引导避免真连 DB；全量 `uv run pytest tests/ -q` **573 passed、11 skipped**（较 P0 收尾 +7），`ruff check` + `ruff format --check` 全绿。
- [x] **db_tools ↔ db_* 循环引用消除** `c2b5e1e`：`_parse_json` 原定义于 `db_tools`，而 `db_tools` 模块级 re-export 全部业务 db_* 模块 → db_experience/db_job/db_submission/db_interview/db_base_resume 从 db_tools 取辅助函数形成**模块级循环引用**（直接 `import app.tools.db_experience` 等必 ImportError，只有先加载 db_tools 才能跑通）。已把 `_parse_json` 下沉到叶子模块 `app/tools/db_conn.py`（仅依赖 db_config + monitoring，无环），5 个消费方改从 db_conn 导入，`db_tools` 保留 re-export 向后兼容（`from app.tools.db_tools import _parse_json` 仍可用、同一对象）。验证：全部 db_* 模块任意顺序直接 import OK、全量 pytest **573 passed/11 skipped**、ruff 全绿。
- [x] **Tool→Agent 循环依赖解除** `552d4ac`：`tools/interview_review`（运行时）→ `agents.question_intent_agent`（模块级）→ `tools/interview_review`（模块级）形成 A→B→A 潜在环；且 `question_table_agent` 同样在模块级从 interview_review 取共享构造。已把问题表意图所需的 schema/prompt/常量（`_QuestionTableOut`/`_QuestionIntentItem`/`_build_question_table_prompt`/`MAX_QUESTION_TABLE_QA_PAIRS`/`RUBRIC_TEXT`/`LEVEL_SCORE_MAP`/`ABILITY_DIMENSIONS`/`DIMENSION_RUBRIC`/`_truncate_text`）下沉到新叶子模块 `app/tools/question_table.py`（仅依赖 core.prompts，无环）；`question_intent_agent`/`question_table_agent` 改从叶子导入，`interview_review` 从叶子导入并 re-export 全部符号保持公开契约（同一对象）；`preview_question_intents` 内唯一的运行时 tools→agent 调用按 AI Boundary 约束保留（其 agent 依赖已不再回指此模块，无环）。验证：4 种引入顺序（agent 先/工具先/表 agent 先/workflow+api）全新进程 import 均 OK、re-export 同对象断言通过、全量 pytest **573 passed/11 skipped**、ruff 全绿。TODO.md P2 该条已勾选。

### v0.23 全项目扫描 + 前端死代码清理（本轮）

- [x] **全项目扫描**：四路并行（后端/前端/DB迁移/API契约）扫描出 ~45 项问题（2 CRITICAL / 10 HIGH / 23 MED / 10+ LOW），写入 TODO.md「全项目扫描」板块
  - CRITICAL：`auth/me` 字段名不匹配（前端 `id` vs 后端 `user_id`）、注册密码规则前后端不一致
  - HIGH 后端：`tasks/handlers.py` 2 处参数错误（TypeError）、`interview_review_flow` strengths 恒空、API 层 3 处直调 LLM（`experience.py:880`/`job_analysis_flow.py:181`/`extract_flow.py:62`，违反四层架构）、`experience.py:790` 重复插入
  - HIGH 数据：删除投递/岗位后 `interview_records` 孤儿；运行时 `_ensure_*` DDL + autocommit 竞态
  - MED 后端：Tool→Agent 循环依赖、`base_resume` 无 migration、V0002/V0004 非幂等、search_cards 无索引
  - MED 前端：组件过大（NewInterviewModal 1056 行 / JobCraftContext 2324 行）、Context 全量重渲染、N+1 查询、详见 TODO.md
- [x] **前端死代码清理（TASK-CLEAN-UI-001）**：删除 3 个未用页面（~1931 行）——`pages/NewInterviewPrep.tsx`（965 行旧版面试准备）、`pages/NewReview.tsx`（758 行旧版复盘）、`components/review/NewReviewModal.tsx`（206 行孤儿弹窗，零引用）；App.tsx 清理 2 个残留 import；保留 `CreateInterview`/`CreateReview`（整页）/`NewInterviewModal`（弹窗）在用
- [x] **验证**：`npx tsc --noEmit` 通过；`npm run build` 通过（1705 modules，仅既有 CSS @import 顺序 + chunk 大小 warning）
- [x] **commit**：`25a9aa8` refactor(frontend): remove dead interview/review UI pages（已推 origin/main）

### v0.25 P2 技术债清理：CLEAN-01/02/03（2026-09-16，本轮）

- [x] **CLEAN-01 — 静默 except 修复** `dd71eef`：AST 审计 45 处候选（去重），修复 8 处静默/缺失观测 handlers（company_research 搜索跳过、monitor stream_writer、interview_pre 公司调研序列化、path_utils 路径校验、experience 批量操作、interview_prep 摘要读取、job_analysis 路径参数、llm_json 审计行创建）；`word_converter:89` 静默 pass 推迟至 CLEAN-02；全量 573 passed/11 skipped，ruff 全绿
- [x] **CLEAN-02 — 零引用模块扫描与删除** `47bc16d`：全仓静态 import + 动态加载 + 字符串字面量扫描，确认 3 个零引用模块（均无隐式引用）：`app/utils/word_converter.py`（299 行，MD→PDF 转换，报告 labs 库未被任何模块引用）、`app/workflows/base.py`（74 行，旧 BaseWorkflow 基类，所有 flow 直接用 StateGraph）、`app/agents/structured_caller.py`（51 行，llm_json 包装，零运行时调用）；同步删除 test_agents_extra_unit.py 中 2 个 structured_caller 用例；571 passed（-2 预期）/11 skipped，ruff 全绿
- [x] **CLEAN-03 — Prometheus 指标审计** `5d246b0`：审计 metrics.py 12 个指标定义 vs 3 个使用点（llm_json/db_conn/server）；发现 4 个业务指标（experience_cards_total/submissions_total/interview_prep_total/interview_review_total）定义后从未 `.inc()`/`.set()`，为死代码；移除；剩余 7 个指标（LLM×3/DB×2/API×2）+ app_info 全部正确接线，无重复，无标签错误；571 passed/11 skipped，ruff 全绿

### v0.25 P2 数据库 migration 收口：DB-01（2026-09-16，本轮）

- [x] **环境核实**：本机 DB 为 Docker MySQL 8.4.9（InnoDB，ngram 插件 ACTIVE，utf8mb4/0900_ai_ci）；15 张表全 InnoDB；4 张深库表的索引/结构已备份（`D:\我的文档\环境变量\TEMP\opencode\*`）
- [x] **DB-01 — base_resume 纳入正式 migration** `9429873`：确认 V0005（commit `48a5f5e`，TASK-P1-10）已含 base_resume + user_profiles，且 create 语句与运行时 `_ensure_base_resume_table` 逐字符一致；此前仅确认"已有迁移"未验证——本轮补齐验证闭环：① 新库初始化（`jobcraft_migverify` 空库全量跑 V0001–V0005 → 15 表，base_resume 结构一致）；② 已有库升级（live jobcraft 0001–0004 → migrate 应用 V0005，0 pending）；③ 迁移重复执行幂等（rerun 0 变更）；④ 前后 schema 对比（fresh vs live：唯一差异为 AUTO_INCREMENT 数据值与合法列序/默认值差异，base_resume 结构零差异）；⑤ 新增防漂移单测 `test_v0005_base_resume_matches_runtime_ddl`（V0005 与运行时 DDL 归一后必须相等，防止迁移与运行时静默分叉）；全量 577 passed/6 skipped，ruff 全绿

### v0.25 P2 数据库 migration 收口：DB-02（2026-09-16，本轮）

- [x] **DB-02 — V0002/V0004 幂等化** `a7c513b`：V0002 原 5 条 `ALTER TABLE ADD CONSTRAINT` 与 V0004 原 1 条 `ALTER TABLE ADD COLUMN` 均非幂等（MySQL 8 无 `ADD COLUMN/CONSTRAINT IF NOT EXISTS`，仅 MariaDB 有）。改造为 **information_schema 探测 + PREPARE/EXECUTE 动态执行** 模式：探测到同名校验存在时执行 `SET @noop = 1`，否则执行动态 DDL；孤儿数据清理保留。验证三场景全过：① 新库初始化（`jobcraft_idem` 空库全量跑 V0001–V0005 两轮，round1==round2 结构完全一致，5 FK + from_cache 全在）；② 已有库升级 + 重复执行（对 live jobcraft 强制重跑新版 V0002/V0004，全部逐条 execute OK 无报错，FK/列已存在时正确 no-op）；③ 单元测试 +1 `test_v0002_and_v0004_are_idempotent`（校验 information_schema/PREPARE/EXECUTE 模式 + 语句块无尾分号可被 runner 拆分）；`python -m migrations.runner status` 中 V0002/V0004 显示 "changed"（文件已变更，语义等价，runner 按版本记录跳过不重放）；全量 578 passed/6 skipped，ruff 全绿

### v0.25 P2 数据库 migration 收口：DB-03 — DEFERRED（2026-09-16，本轮）

- [x] **DB-03 — search_cards FULLTEXT 方案评估 → DEFERRED**：完成引擎/索引能力实证后，按用户决策搁置（方案 C）。
  - **实证结论**（已实测，Docker MySQL 8.4.9 InnoDB）：
    1. 引擎支持 FULLTEXT + nGram（`CREATE TABLE ... FULLTEXT INDEX ... WITH PARSER ngram` 成功）；
    2. **现有 LIKE 查询无法从 FULLTEXT 索引获益**：`EXPLAIN` 显示 `search_cards` 形态查询（user_id + is_active + OR LIKE）仍走 `idx_user_active` + `Using where` 全扫，MySQL 8 不会自动把 LIKE 改写为 nGram MATCH；
    3. **LIKE 与 MATCH...AGAINST(IN NATURAL LANGUAGE MODE) 已实测语义分歧**：`Java` → LIKE 1 行 / MATCH 0 行（ngram 英文切 2-gram + 50% 阈值）；`电商系统` → LIKE 1 行（子串）/ MATCH 2 行（ngram 部分匹配误检 row3"推荐系统"）；
    4. `GET /cards/search` 前端消费者为 0（grep 前端 0 引用），后端唯一调用链为 `app/api/experience.py:467` 端点 → `db_tools.search_cards/count_search_cards`；`count_search_cards` 为分页镜像必须与 `search_cards` 同步改否则 total/items 不一致。
  - **决策（方案 C）**：不创建 V0006、不修改 `search_cards`/`count_search_cards`、不改 API contract、不改数据库技术栈。理由：技术上能做 ≠ 产品上现在该做；当前阶段前端未接线，硬上 FULLTEXT 只增加写入维护成本且带来语义变化风险。
  - **触发条件**：未来前端正式接入搜索并确定全文检索语义后，作为独立 Search Optimization Task 重新评估。届时方案 A = V0006 `ADD FULLTEXT INDEX ... WITH PARSER ngram`（沿用 DB-02 幂等模式）+ `search_cards`/`count_search_cards` 改 `MATCH...AGAINST(IN BOOLEAN MODE)`（需关键词转义、MATCH 列序与索引一致、短词兜底）。本项无代码变更、无 commit。

### FE-INTERVIEW-01 面试域数据层迁移（2026-09-18，commit `99f0a07`）

- [x] **`features/interview/mappers.ts`**：`INTERVIEWS_QUERY_KEY` + `mapRoundType` / `roundTypeToCn` / `prepRecordToInterview` / `buildInterviewFromPrep` 自 context 移出（映射单源，含 legacy `业务`→`product` 分支顺序）；context 删除本地实现
- [x] **`features/interview/hooks.ts`**：`useInterviewsQuery`（getCurrentUser → listInterviewPreps → prepRecordToInterview）；`useCreateInterviewMutation`（JOBS cache 解析 jdAnalysisId 缺失抛错 → runTaskOrSync → 降级 generateInterviewPrep → 构建 Interview → INTERVIEWS cache 前置插入 + 跨域补写 JOBS cache interviewIds/prepStage → onSync + onSyncJobs 双镜像；mutateAsync 返回含 id 的 Interview 供 navigateTo；不内置 toast/nextActions）
- [x] **context 改造**：接口/provider 增 `syncInterviews`、删 `createInterview`；`loadInterviews` 双写 cache（updater 内）；复盘 writers（`addInterviewReview` / `commitExperienceDiff` / `applyReviewFeedback`）改块体 updater（`(int): Interview` 标注）并双写 INTERVIEWS cache；清理未用导入（InterviewPrepRecord/InterviewPrepResult/ApiInterviewPrepRecord）
- [x] **视图迁移**：`InterviewPrepCenterView` / `InterviewPrepWorkspaceView` 读 `useInterviewsQuery`；`NewInterviewModal` / `CreateInterview` 改 `useCreateInterviewMutation`（`mutateAsync(...).id` 导航）；toast 保留视图层
- [x] **测试**：`mappers.test.ts`（5）+ `interview-query.test.tsx`（3：列表+搜索+镜像、创建走 task fallback→generateInterviewPrep＋双镜像＋job.interviewIds、jdAnalysisId 缺失抛错）；全量 `npm test` **17 文件 / 72 测试全绿**，tsc（lint）、build 通过
- [x] **E2E**：全栈（Docker mysql/redis/backend:8000）下 Playwright 15 用例 **14/15 通过**；唯一失败「侧边栏→面试准备」为 beforeEach 偶发登录页未进入工作台（同模式其余用例含「登录后进入工作台」通过），**单独重跑通过（14.7s）**，判定非回归
- [x] 已提交（commit `99f0a07`）
- [ ] 留白：`updateQuestionAnswer` / `addCustomQuestion` / `nextActions`（无消费者）待 FE-CONTEXT-REMOVE 清理；workspace 内复盘叠加写路径保持 context；`syncInterviews` 与双写随 FE-CONTEXT-REMOVE 拆除

### FE-JD-02 JD create 收尾（2026-09-18，本轮）

> 承接 FE-JD-01：把`JDAnalysisCenterView`的`createStructuredJDAnalysis`与`NewInterviewModal`的`createJDAnalysis`两位 legacy 写入迁到 features/jd 数据层，context 删除两个 method。

- [x] **`features/jd/mappers.ts`**：新增 `dutiesText` / `requirementsText` / `StructuredJDAnalysisMeta` / `structuredResultToJD`（自 context 内联映射移出为唯一实现，含 `subtext_decoded`→subtextAnalysis、resumeAdvice=key_metrics、matchScore 0、合成的 `jd-<ts>` id）
- [x] **`features/jd/hooks.ts`**：`JDMutationOptions` 增 `onSyncJobs`；新增 `useCreateJdAnalysisMutation`（`runTaskOrSync('resume_generate', …, fallback=analyzeJob, 180s)` → `analysisToJD`，真实 `job_analysis_id`，岗位写 jdAnalysisId/matchScore/steps）与 `useCreateStructuredJdAnalysisMutation`（`runTaskOrSync('jd_analyze_structured', …, fallback=analyzeStructuredJd, 120s)` → `structuredResultToJD` + 岗位 `jdAnalysisId=合成 id`，cache 前置）；helper `resolveTargetJob`（显式 jobId 复用，否则按公司+岗位 find-or-create，`job-<ts>` 自动 Job 写入 JOBS cache 且 produceJob=true 时同步 `onSyncJobs`，不产生后端提交）；`readJdAnalyses` / `readJobs` 从 cache 读
- [x] **`JDAnalysisCenterView.tsx`**：`useCreateStructuredJdAnalysisMutation` 接管，**await-完成后跳转**（`mutateAsync` resolve 后 `navigateTo('jd_report', { jdId: analysis.id })`，移除 `setTimeout(800)` 假等待 + fire-and-forget），失败留表单页 + error toast，finally `setIsAnalyzing(false)`
- [x] **`NewInterviewModal.tsx`**：`useCreateJdAnalysisMutation` 接管，文本路径保持 fire-and-forget（`mutate(vars, { onSuccess/onError })`），toast 归视图层；destructure 增 `syncJdAnalyses`
- [x] **`JobCraftContext.tsx`**：删除 `createJDAnalysis` / `createStructuredJDAnalysis`（实现 + 接口 + provider 值）、`dutiesText` / `requirementsText` 私有 helpers；收敛 import（`analysisToJD`/`JobAnalysisResult` 移除），仅剩 legacy `deleteJDAnalysis` 待 FE-CONTEXT-REMOVE
- [x] **测试**：`mappers.test.ts` +3 组（dutiesText/requirementsText、structuredResultToJD＋subtext_decoded＋空兜底）；`jd-query.test.tsx` +4（结构化自动建岗、复用显式 jobId、原始文本 fire-and-forget、结构化失败 reject）+ tasks mock + CreateHarness；全量 `npx vitest run` **17 文件 / 81 测试通过**（72→81），`npx tsc --noEmit` exit 0，`npm run build` exit 0，`scripts/check_encoding.py` 0 错误
- [x] spec 落盘 `tasks/FE-JD-02.md`（设计决策 JD-C1..C5、Scope、Non-Goals）
- [ ] **本段标记完成前需执行**：TODO.md 已勾选 FE-JD-02；提交（`feat(jd)` + `docs` 两支，PROGRESS.md 走 `git add -f`）+ 推 origin/main（代理 7890 需开启）
