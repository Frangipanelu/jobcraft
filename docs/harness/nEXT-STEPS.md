# 下一步计划

## P0 - 缺口分析深度改进

### 1.1 暗话分析中间步骤 ✅ 已完成（2026-07-31）
- [x] 新增 `SubtextDecode` schema（surface_requirement / hidden_meaning / key_ability / how_to_prove）
- [x] `ATSProfile` 增加 `subtext_decoded` 字段
- [x] `ats_and_recommend()` 任务三：JD 潜台词解码（3-6 条），同步写入 ats.subtext_decoded
- [x] `gap_and_polish()` 把暗话作为评估维度，规则：卡片可推导出能力则给 'polish' 建议显性化，不直接判缺失
- [x] 前端 JobPage + JDAnalysisPage 展示暗话分析卡片（橙色标识）
- [x] api.ts 增加 `SubtextDecode` 类型 + step1 返回类型收紧

### 1.2 改进匹配度评估维度
当前缺口分析主要依赖 `required_skills` / `preferred_skills`，需改为：
- 专业技能匹配（原有）
- 业务/领域经验匹配（新增）
- 可迁移通用能力匹配（新增）
- 量化成果对标（新增，对比 key_metrics）
- 文化/协作风格匹配（新增）
- **暗话能力显性化**（✅ 已完成，gap_and_polish 规则 4）

### 1.3 教育/年限过滤
- 在 gap analysis 入口处过滤掉 `education` 字段（本科以上等不可通过经历卡补充的信息）
- `years_of_experience` 应作为参考指标而非匹配依据

### 1.4 接口流程调整
当前 `JobPage.tsx` step 1/2/3/4 的流程可能需对齐：
1. Step 1: ATS分析（JD 解析，已有）
2. Step 2: 暗话分析 + 匹配度 + 修改建议（新增暗话分析，合并或分步）
3. Step 3: 面试准备（已有）
4. Step 4: 简历生成（见下方）

## P1 - 简历生成模块

### 2.1 模板预设 ✅ 已完成（2026-07-31）
- [x] `generate_resume_html()`：预设 A4 排版（深蓝主题 header + 核心能力标签 + 经历条目）
- [x] 每条经历渲染为「公司 · 职位 · 时间段」标题行 + 要点列表（自动从文本拆 bullets）
- [x] 内容源优先 card_versions（用户编辑终稿）→ ai_structured.achievements → raw_text

### 2.2 个人信息补充 ✅ 已完成
- [x] `ResumePersonalInfo` schema（name/phone/email/city/github/education/years）
- [x] `SaveResumePayload.personal_info` + `generate_resume()` 透传
- [x] 前端「补充个人信息」Modal 表单，保存至 localStorage（`jobcraft_personal_info`）
- [x] Markdown 与 HTML 头部均使用个人信息替换占位符

### 2.3 HTML 预览 ✅ 已完成
- [x] `save-resume` 返回 `resume_html`
- [x] JobPage「简历预览」Tab 用 iframe `srcDoc` 渲染 HTML（`.jc-iframe`）
- [x] 同时落盘 .md + .html 到 `output/job_resume/`

### 2.4 PDF 下载 ✅ 已完成
- [x] 「导出 PDF」按钮：新窗口写入 resume_html → `window.print()` → 浏览器另存为 PDF
- [x] 不新增 html2canvas/jspdf 依赖（符合 AGENTS.md 禁止未经授权引入第三方库）
- [x] HTML 内置 `@page { size: A4 }` 打印样式

### 2.5 一键静默下载 ✅ 已完成（v0.9）
- [x] 引入 html2canvas + jspdf（依赖已写入 package.json），「一键下载 PDF」离屏容器截图 → A4 多页切分
- [x] 原「导出 PDF」按钮改「打印」

## P2 - 代码/文档清理

### 3.1 恢复之前版本的缺口分析能力 ✅ 已关闭（2026-08-03）
- git 调查确认：历史上不存在被删的更完善缺口分析，当前 `gap_and_polish()` 已是超集（D1-D8 / 暗话解码 / 溢出启发式）
- 旧版已导出到 `D:\我的文档\环境变量\TEMP\opencode\jobcraft_analyze_orig.py` 供对照，无需恢复

### 3.2 卡片内容回填 ✅ 已完成（v0.9）
- 旧数据单卡含整份简历 raw_text 的拆分功能（`backfill_resume_cards` + 「拆分历史整卡」按钮）

### 3.3 UI 设计系统落地 ✅ 已完成（v0.10，2026-08-03）
- 新建 `docs/UI_DESIGN.md`（设计唯一事实来源）
- hallmark audit 全量修复：C1 token 化、C2 响应式、M1 Fraunces、M2 对比度、M3 图标、M4 去嵌套卡、M5 可点击语义化
- 详见 `docs/harness/session-2026-08-03.md`

### 3.4 完善测试覆盖
- 为 gap analysis 补充 pytest 测试（mock LLM 返回）
- 为 resume upload parsing 补充测试
- 为 `_looks_like_full_resume` / `_rebuild_entry_text` 补充测试 ✅（v0.9 已加）

## 文件变更预测

| 文件 | 预计改动 |
|------|----------|
| `app/tools/jobcraft_analyze.py` | 新增暗话分析函数；增强 gap_and_polish prompt；过滤 education ✅ |
| `app/tools/jobcraft_jd_ats.py` | 新增 `decode_jd_subtext()` 暗话分析函数 ✅（合并进 ats_and_recommend 任务三） |
| `frontend-jobcraft/src/pages/JobPage.tsx` | Step 2 展示调优；Step 4 简历生成 UI ✅ |
| `frontend-jobcraft/src/components/ResumeTemplate*.tsx` | 简历模板组件（未采用，改由后端生成 HTML） |
| `frontend-jobcraft/src/components/ResumePreview.tsx` | 简历预览组件（未采用，用 iframe srcDoc） |
| `frontend-jobcraft/package.json` | 新增 html2canvas + jspdf 依赖（未采用，window.print 方案） |
| `app/tools/jobcraft_resume_gen.py` | ✅ 新增 `generate_resume_html()` + `_split_bullets()` + 个人信息支持 |
| `app/tools/jobcraft_resume.py` | ✅ `generate_resume()` 返回 resume_html，落盘 .html |
| `app/schemas/jobcraft.py` | ✅ 新增 `ResumePersonalInfo` |

## 排查记录

### `_card_text_blob` 是否返回整份简历？
- 当前 `_card_text_blob()` 处理单卡时构造：`title + tags + raw_text[:300] + summary + achievements 列表`
- 如果卡片的 `raw_text` 存的是整份简历原文（旧上传逻辑），则 `[:300]` 也带回整份简历的开头
- 新上传逻辑 (`parse_resume_entries()`) 已确保每张卡只存自己那条经历的 raw_text
- **结论**：对旧数据需要迁移或"重新拆卡"功能；新数据无此问题
