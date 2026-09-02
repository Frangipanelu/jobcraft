# PROGRESS.md — JobCraft 求职助手 · 状态与进度记忆

> 本文件用于追踪项目整体进度。AI 在每次会话结束或完成子任务时，必须更新本文件的对应板块。

## 已完成事项

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

---

**更新规则**：每次会话结束时，AI 必须根据本次实际完成的工作，移动或新增上述列表中的条目，并简要描述进展。