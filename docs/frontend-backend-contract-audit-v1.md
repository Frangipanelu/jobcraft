# JobCraft Frontend ↔ Backend Contract Audit v1

> **文档版本**：v1.0
> **审计对象**：`Frangipanelu/jobcraft` `main` 分支
> **前端目录**：`frontend-jobcraft/`
> **后端目录**：`app/`
> **数据库**：`docker/mysql/jobcraft.sql`
> **审计日期**：2026-09-02
>
> 本文不是重新设计一套后端，而是以当前仓库的真实代码为事实来源，核对：
>
> **页面 → 用户行为 → 前端 API → Request/Response → 后端 Router/Workflow → 数据库 → AI Workflow**
>
> 并指出当前契约缺口、重复模型、数据归属问题和后续改造优先级。

---

# 1. 执行摘要

## 1.1 当前系统已经具备什么

当前 JobCraft 已经是一个完整的全栈项目骨架，而不是只有 UI：

```text
Frontend
React 18 + TypeScript + Vite + Ant Design
        │
        │ HTTP /api
        ▼
Backend
FastAPI
        │
        ▼
Workflow
LangGraph
        │
        ▼
Agent
LangChain / LLM
        │
        ▼
Tool
DB / File / Search / Rules
        │
        ▼
MySQL
```

仓库同时包含：

- `frontend-jobcraft/`
- `app/api/`
- `app/workflows/`
- `app/agents/`
- `app/tools/`
- `app/schemas/`
- `app/tasks/`
- `app/auth/`
- `docker/mysql/`
- `tests/`
- `AGENTS.md`
- `ARCHITECTURE.md`
- `PRODUCT.md`
- `PROGRESS.md`
- `TODO.md`

项目 README 已明确采用：

```text
Controller → Workflow → Agent → Tool
```

的四层 AI 应用架构。

---

## 1.2 新前端已经不是纯 UI

当前新前端 `frontend-jobcraft/src` 已经：

1. 定义页面路由；
2. 定义 TypeScript API Contract；
3. 调用真实 FastAPI 接口；
4. 使用后端 Pydantic Schema 同步生成/维护前端类型；
5. 实现经历卡、JD 分析、投递、面试准备、面试复盘等真实数据流。

因此：

> **现在的主要任务不是"把 UI 接一个后端"，而是"把现有前端与既有后端做一次契约对齐和架构收口"。**

---

## 1.3 当前最大问题

当前不是"没有后端"，而是存在四类不一致：

### A. Resource Model 与 Product Model 尚未完全统一

例如：

```text
resume_submission
```

实际承载的是：

```text
一次求职投递 Application / Submission
```

而不是单纯 Resume。

---

### B. 一部分页面仍然直接 `fetch`

大多数请求走 `src/api.ts`，但部分页面仍直接使用：

```ts
fetch(...)
```

会导致：

```text
组件 → api.ts
组件 → fetch
```

两个 API 出口。

---

### C. `user_id` 仍由前端部分接口显式传入

例如：

```text
?user_id=...
body.user_id
```

生产系统应逐步改成：

```text
Authorization
    ↓
Current User
    ↓
Backend 自动绑定 user_id
```

---

### D. AI 结果、业务数据和 AI Task 还没有完全统一

目前部分 AI 接口是：

```text
POST → 等 AI 完成 → 返回 Result
```

而复杂的 Interview Review 已经天然需要：

```text
Create Task
    ↓
Parse
    ↓
Question Table
    ↓
Analyze
    ↓
Result
```

下一阶段应统一 AI Task、缓存、重试、模型信息、Prompt Version、Schema Version。

---

# 2. 审计事实来源

本次审计主要对照以下源码：

```text
frontend-jobcraft/src/App.tsx
frontend-jobcraft/src/api.ts
frontend-jobcraft/src/types.ts
frontend-jobcraft/src/useRoute.ts
frontend-jobcraft/src/pages/CareerRoutePage.tsx
frontend-jobcraft/src/pages/ExperiencePage.tsx
frontend-jobcraft/src/pages/JDAnalysisPage.tsx
frontend-jobcraft/src/pages/JobPage.tsx
frontend-jobcraft/src/pages/InterviewPrepPage.tsx
frontend-jobcraft/src/pages/InterviewReviewPage.tsx

app/api/server.py
app/schemas/jobcraft.py
docker/mysql/jobcraft.sql
AGENTS.md
ARCHITECTURE.md
PRODUCT.md
```

当前仓库 README 还明确记录了前端页面与业务能力：

```text
#/dashboard       求职路线
#/experience      经历卡
#/jd-analysis     JD 分析库
#/prep/:id        面试准备
#/review/:id      面试复盘
```

以及核心业务链：

```text
经历梳理
→ JD 分析
→ 简历定制
→ 投递
→ 面试准备
→ 面试复盘
```

---

# 3. 前端总体结构审计

当前 `src/`：

```text
frontend-jobcraft/src/
├── components/
├── pages/
├── App.tsx
├── api.ts
├── index.css
├── main.tsx
├── types.ts
└── useRoute.ts
```

页面入口：

```text
dashboard      → CareerRoutePage
experience     → ExperiencePage
jd-analysis    → JDAnalysisPage
job            → JobPage
prep/:id       → InterviewPrepPage
review/:id     → InterviewReviewPage
```

`App.tsx` 采用 lazy import，因此页面级代码分块是合理的。

---

# 4. 页面 → 后端映射总表

| 页面 | 当前前端入口 | 数据来源 | 用户操作 | 当前 API | 持久化 | AI | 优先级 |
|---|---|---|---|---|---|---|---|
| 求职路线 | `CareerRoutePage` | API | 查看/更新投递状态/删除投递 | dashboard + submission | ✅ | 间接 | P0 |
| 经历卡 | `ExperiencePage` | API | 新建/编辑/删除/上传/结构化/标签 | experience APIs | ✅ | ✅ | P0 |
| JD 分析库 | `JDAnalysisPage` | API | 新建分析/查看历史/删除 | job analysis APIs | ✅ | ✅ | P0 |
| 定制简历 | `JobPage` | API | 选择经历/版本/生成简历 | job/resume APIs | ✅ | ✅ | P1 |
| 面试准备 | `InterviewPrepPage` | API | 选择轮次/经历/生成准备 | submission + prep APIs | ✅ | ✅ | P1 |
| 面试复盘 | `InterviewReviewPage` | API | 上传/解析/配对/选择题目/分析/删除 | review APIs | ✅ | ✅ | P1 |

---

# 5. 数据分类总规则

当前前端数据必须划分成四类。

## 5.1 A 类：核心业务数据

必须持久化：

```text
ExperienceCard
CardVersion
JobAnalysis
Submission
InterviewPreparation
InterviewReview
CompanyResearch
Resume
```

---

## 5.2 B 类：AI 派生数据

由 AI / Workflow 产生，应保存，但必须标记来源：

```text
ai_structured
ats
gap_analysis
subtext_decoded
dimension_requirements
interview questions
interview analysis
review diagnosis
```

关键字段：

```text
model
prompt_version
schema_version
source_task_id
created_at
```

---

## 5.3 C 类：页面临时状态

不要保存数据库：

```text
loading
analyzing
searchText
selectedRowKeys
activeTab
modalOpen
selectedSequences
analyzeElapsed
dimensionFilter
```

---

## 5.4 D 类：缓存

优先 Redis：

```text
company research
AI result cache
task status
rate limit
temporary upload state
```

---

# 6. App / Routing 审计

## 6.1 当前路由

当前路由：

```text
#/dashboard
#/experience
#/jd-analysis
#/job/:id
#/prep/:id
#/review/:id
```

`useRoute.ts` 是自实现 hash routing。

### 评价

MVP 可继续使用。

### 风险

如果业务继续增长：

```text
/query params
nested resource
404
auth guard
permission
redirect
```

会逐渐需要独立 router。

### 当前建议

**P2，不要现在换。**

---

# 7. API Client 审计

`src/api.ts` 已经是当前前端最重要的契约入口。

当前特点：

```text
BASE_URL = ''
request<T>()
requestFormData<T>()
parseUnifiedError()
```

并且接口集中在一个文件中。

---

## 7.1 当前优势

统一调用：

```ts
request<T>()
```

统一错误解析：

```ts
{ code, msg, data }
```

前端 TypeScript 类型与后端 Schema 有明确同步关系。

这是应该保留的设计。

---

## 7.2 当前问题

`api.ts` 已经超过单文件 API 层适合的规模。

建议后续拆：

```text
src/api/
├── client.ts
├── experience.ts
├── jobs.ts
├── jd.ts
├── submission.ts
├── resume.ts
├── interview.ts
├── review.ts
└── dashboard.ts
```

统一：

```text
src/api/client.ts
```

处理：

- base URL
- auth
- JSON
- FormData
- 错误
- requestId

---

# 8. Experience 页面审计

文件：

```text
pages/ExperiencePage.tsx
```

这是目前前端与后端契合度较高的页面之一。

---

## 8.1 当前状态

```ts
cards
loading
modalOpen
uploading
backfilling
structuring
structuringElapsed
initialValues
detailCard
detailOpen
```

这些基本全部属于 UI / request state。

不应进入数据库。

---

## 8.2 当前 API

```text
GET    /api/jobcraft/experience/cards
POST   /api/jobcraft/experience/cards
PATCH  /api/jobcraft/experience/cards/{id}
DELETE /api/jobcraft/experience/cards/{id}

POST   /api/jobcraft/experience/upload

POST   /api/jobcraft/experience/cards/backfill

POST   /api/jobcraft/experience/cards/{id}/structure

POST   /api/jobcraft/experience/cards/{id}/recommend-tags
```

---

## 8.3 当前业务流程

### 新建

```text
Form
 ↓
parseFormState()
 ↓
createCard()
 ↓
API
 ↓
DB
 ↓
load()
```

正确。

---

### 上传简历

```text
File
 ↓
uploadResume()
 ↓
Backend
 ↓
Resume Parse / AI
 ↓
Experience Cards
```

正确。

但后续应该拆成：

```text
Upload
→ File Created
→ Parse Task
→ Candidate Cards
→ User Confirm
```

避免上传一次就自动永久生成全部经历。

---

### AI 结构化

```text
structureCard(cardId)
```

当前是同步等待。

建议长期改为：

```text
POST /experience/cards/:id/structure
      ↓
AI Task
      ↓
202 Accepted
      ↓
Task status
      ↓
Result
```

---

## 8.4 当前重要问题：DetailModal 使用 `Record<string, any>`

代码中存在：

```ts
onSave: (payload: Record<string, any>) => void
```

以及：

```ts
Record<string, any>
```

这违反当前工程规则中"禁止 any 隐式传播"的方向。

### 建议

建立：

```ts
ExperienceCardUpdate
CardStructuredCache
Achievement
AchievementAction
```

严格类型。

---

# 9. Experience 数据模型建议

当前后端已有：

```text
experience_card
```

字段包括：

```text
id
user_id
company
role
period
title
summary
background
problem
solution
execution
result
content
tags
metrics
dimensions
industry
role_type
source
card_type
version
is_active
created_at
updated_at
```

另外前端使用：

```text
raw_text
ai_structured
```

以及兼容字段：

```text
summary
content
company
role
period
```

### 当前判断

这是历史模型与新模型并存。

---

## 9.1 建议最终方向

保留：

```text
experience_card
```

作为事实主对象：

```text
raw_text
tags
company
role
period
card_type
```

AI 投影：

```text
ai_structured JSON
```

版本：

```text
card_versions
```

形成：

```text
ExperienceCard
  ├── raw facts
  ├── AI projection
  └── versions
```

---

# 10. JD Analysis 页面审计

文件：

```text
pages/JDAnalysisPage.tsx
```

---

## 10.1 页面状态

```text
analyses
searchText
selectedRowKeys
loading
position
company
jdText
analyzing
analyzeElapsed
result
analysisId
```

其中：

### UI state

```text
searchText
selectedRowKeys
loading
analyzing
analyzeElapsed
```

### Request form state

```text
position
company
jdText
```

### Server state

```text
analyses
result
analysisId
```

这部分后续应通过 Query Cache 管理，而不是手工全部 `useState`。

---

# 11. JD Analysis 当前 API

```text
GET  /api/jobcraft/job/analyses
POST /api/jobcraft/job/step1-ats-recommend
POST /api/jobcraft/job/analyze
GET  /api/jobcraft/job/analyze/{id}
DELETE /api/jobcraft/job/analyze/{id}
POST /api/jobcraft/job/step2-gap-polish
```

此外：

```text
GET /api/jobcraft/job/{job_analysis_id}/selected-cards
```

用于面试准备。

---

# 12. JD Analysis 当前存在"模型重复"

`api.ts` 里存在：

```text
Step1AtsProfile
AtsProfile
AnalyzeJobResult
GapItem
PerCardScore
DimensionRequirement
DimensionQuestion
SuggestionItem
```

而 `types.ts` 又定义：

```text
JDRequirements
ATSProfile
JobAnalysisResult
```

### 问题

存在两套数据模型：

```text
api.ts domain types
+
types.ts backend synced types
```

这会逐渐产生：

```text
相似字段
命名不一致
nullable 不一致
Schema 漂移
```

---

## 12.1 建议

最终形成：

```text
src/types/
├── common.ts
├── experience.ts
├── jd.ts
├── submission.ts
├── resume.ts
├── interview.ts
└── review.ts
```

`api.ts` 不再重复定义业务 Interface。

只：

```text
import type
```

。

---

# 13. JD Analysis AI Workflow 建议

当前产品设计：

```text
JD
 ↓
ATS / Requirement
 ↓
Experience Match
 ↓
Gap Analysis
 ↓
Polish
 ↓
Resume
```

已经非常合理。

不要改成一个巨大 Prompt。

---

# 14. JD Analysis API 合约建议

## 14.1 当前保持兼容

```http
POST /api/jobcraft/job/step1-ats-recommend
```

请求：

```json
{
  "company": "xxx",
  "position": "AI Product Manager",
  "jd_text": "..."
}
```

返回：

```json
{
  "job_analysis_id": 123,
  "ats": {},
  "recommended_cards": [],
  "all_cards": []
}
```

---

## 14.2 下一版本建议

逐步演进：

```http
POST /api/v1/jd-analyses
GET  /api/v1/jd-analyses
GET  /api/v1/jd-analyses/{id}
DELETE /api/v1/jd-analyses/{id}
POST /api/v1/jd-analyses/{id}/reanalyze
```

而复杂 AI 子步骤：

```text
POST /api/v1/jd-analyses/{id}/ats
POST /api/v1/jd-analyses/{id}/match
POST /api/v1/jd-analyses/{id}/gap
```

内部可以继续调用现有 Workflow。

---

# 15. JobPage 审计

文件：

```text
pages/JobPage.tsx
```

当前承担的实际功能已经不只是"Job"。

实际上是：

```text
JD → 经历版本 → 简历生成 → 投递
```

这说明它更准确的业务名称应该是：

```text
Application Workspace
```

或：

```text
Submission Workspace
```

而不是单纯 Job。

---

# 16. Job 与 Submission 的模型问题

当前后端已有：

```text
job_analysis
resume_submission
```

而新 UI 的核心数据接口：

```ts
Submission
```

字段：

```text
id
user_id
job_analysis_id
position
company
jd_text
resume_markdown
resume_file_path
card_version_ids
status
notes
created_at
updated_at
```

这非常接近：

```text
Application
```

---

# 17. 建议确定三个层次

不要把三者混淆：

```text
Job Opportunity
    ↓
Job Analysis
    ↓
Application / Submission
```

推荐：

### Job Opportunity

描述：

```text
公司
岗位
部门
地点
薪资
```

### Job Analysis

描述：

```text
这份 JD 的结构化理解
```

### Submission

描述：

```text
用户实际投递这次岗位时使用了什么
```

例如：

```text
Submission
 ├── job_analysis_id
 ├── card_version_ids
 ├── resume_snapshot
 ├── submitted_at
 └── status
```

---

# 18. Submission 应该成为 Pipeline 核心

产品 README 已经明确把：

```text
resume_submission
```

定义为：

> 投递记录（pipeline 核心）

这个产品决策建议保留。

业务关系：

```text
User
 ↓
Submission
 ├── Job Analysis
 ├── Experience Versions
 ├── Resume Snapshot
 ├── Interview Preparations
 └── Interview Reviews
```

---

# 19. CareerRoutePage 审计

页面：

```text
CareerRoutePage.tsx
```

它实际上就是：

> Application Pipeline Dashboard

---

## 19.1 当前主要 API

```text
getDashboard()
getSubmission()
updateSubmission()
deleteSubmission()
createSubmission()
```

以及部分场景的：

```text
fetch(...)
```

---

## 19.2 当前严重问题：组件直接 fetch

如果页面里直接：

```ts
fetch('/api/jobcraft/submission/...')
```

那么应该改成：

```ts
deleteSubmission(id)
```

所有 HTTP 必须通过：

```text
src/api/*
```

---

# 20. Dashboard 应该区分"原始数据"和"派生统计"

当前：

```text
DashboardItem
```

包含：

```text
has_analysis
card_version_count
card_count
has_resume
is_manual
prep_count
review_count
```

这些并非全部是原始业务事实。

### 建议分成：

```text
Submission
```

与：

```text
SubmissionProgress
```

例如：

```json
{
  "submission": {},
  "progress": {
    "hasAnalysis": true,
    "cardVersionCount": 3,
    "cardCount": 4,
    "hasResume": true,
    "prepCount": 1,
    "reviewCount": 0
  }
}
```

Dashboard 可以继续由 SQL 聚合产生。

---

# 21. 求职状态机

当前产品状态：

```text
已投递
面试邀约
一面
二面
Offer
已关闭
```

这是领域规则。

不能只在前端判断。

---

## 21.1 建议后端统一状态机

```text
APPLIED
INVITED
ROUND_1
ROUND_2
OFFER
CLOSED
```

显示层：

```text
已投递
面试邀约
一面
二面
Offer
已关闭
```

这样代码不会把中文状态散落在前后端。

---

# 22. 当前状态规则冲突

前端产品语义：

```text
复盘
需 ≥ 一面
```

但当前部分页面判断是：

```text
status !== 已投递
```

所以：

```text
面试邀约
```

也可能开启复盘。

### P0 修复

建立：

```text
can_prepare_interview(status)
can_review_interview(status)
```

作为统一业务规则。

---

# 23. InterviewPrepPage 审计

当前数据链：

```text
submission
 ↓
job_analysis
 ↓
selected cards
 ↓
roundType
 ↓
generateInterviewPrep
```

这个链路是正确的。

---

## 23.1 当前状态

```text
submission
initialLoading
roundType
cards
selectedCardIds
loading
result
```

其中 server state：

```text
submission
cards
result
```

UI/request state：

```text
initialLoading
roundType
selectedCardIds
loading
```

---

# 24. 面试准备 API

当前：

```text
GET  /api/jobcraft/submission/{id}

GET  /api/jobcraft/job/{job_analysis_id}/selected-cards

GET  /api/jobcraft/job/{job_id}/interview-prep

POST /api/jobcraft/job/{job_id}/interview-prep
```

生成请求：

```json
{
  "round_type": "技术面",
  "card_ids": [1, 2, 3],
  "submission_id": 123
}
```

---

# 25. Interview Preparation 的领域关系

建议以后不要只：

```text
job_analysis_id
```

而应该以：

```text
submission_id
```

作为核心关联。

因为面试准备基于：

```text
JD
+
实际投出的简历
+
实际使用的经历版本
+
面试轮次
```

所以：

```text
InterviewPreparation
    ↓
Submission
```

更自然。

---

# 26. Company Research

当前存在：

```text
company_research
```

以及：

```text
cached_at
```

产品规则是：

```text
7 天缓存
```

这非常适合缓存层。

建议：

```text
DB = 持久化最近成功结果
Redis = 热缓存
TTL = 7d
```

Cache Key：

```text
company_research:{normalized_company}
```

未来可增加：

```text
company_research:{company}:{locale}
```

---

# 27. 面试准备的 AI 结果建议分层

不要把全部结果只塞到一列。

建议逻辑：

```text
InterviewPreparation
├── metadata
├── company_research_snapshot
├── strategy
├── questions
└── generated_content
```

其中：

```text
questions
```

建议单独实体。

---

# 28. InterviewReviewPage 是整个前端最复杂的页面

代码超过 1000 行。

当前流程已经包含：

```text
列表
 ↓
创建
 ↓
上传
 ↓
解析 Preview
 ↓
说话人拆分
 ↓
QA Pairing
 ↓
问题表
 ↓
选择最多 8 题
 ↓
详细 AI 分析
 ↓
结果
```

这是合理的产品流程。

---

# 29. Interview Review 的状态机

建议明确写成：

```text
DRAFT
 ↓
UPLOADED
 ↓
PARSED
 ↓
QA_READY
 ↓
ANALYZING
 ↓
DONE

异常：
FAILED
```

不要只依赖页面：

```text
analysisStep
```

因为：

```text
analysisStep
```

目前只是 UI state。

后端应该拥有真正 Task 状态。

---

# 30. 当前 Review API

```text
GET    /api/jobcraft/interview-review

POST   /api/jobcraft/interview-review

POST   /api/jobcraft/interview-review/upload

GET    /api/jobcraft/interview-review/{id}

DELETE /api/jobcraft/interview-review/{id}

POST   /api/jobcraft/interview-review/parse-preview

POST   /api/jobcraft/interview-review/{id}/question-table

POST   /api/jobcraft/interview-review/{id}/analyze
```

这套 API 已经基本能覆盖 UI。

---

# 31. Review 的两个阶段应该明确成为两个 AI Task

## Task A

```text
Parse Interview
```

输入：

```text
raw_text / file
```

输出：

```text
speaker_segments
qa_pairs
```

---

## Task B

```text
Analyze Selected Questions
```

输入：

```text
record_id
selected_sequences[]
```

输出：

```text
overall_score
strengths
weaknesses
dimension_stats
question analyses
action_items
```

这样天然支持：

```text
重试
部分失败
任务日志
限流
成本统计
```

---

# 32. 当前 Review 页面"最多 8 题"

前端限制：

```text
selectedSequences.length >= 8
```

这个不能只在前端限制。

后端也必须验证：

```text
1 <= selected_sequences.length <= 8
```

否则可以绕过前端直接请求接口。

---

# 33. Review 数据模型建议

当前已有：

```text
interview_records
interview_qa_pairs
```

建议增加/完善：

```text
interview_review_analyses
interview_review_question_results
```

关系：

```text
InterviewReview
 ├── raw transcript
 ├── parsed segments
 ├── QA pairs
 └── analysis
      ├── overall
      ├── dimensions
      ├── questions
      └── actions
```

---

# 34. AI Output 必须结构化

当前前端已经定义很多结构化 Type，这很好。

原则：

```text
LLM
 ↓
Structured Output
 ↓
Pydantic Validation
 ↓
Domain Result
 ↓
DB
 ↓
API
 ↓
TypeScript
```

不要：

```text
LLM
 ↓
一整段 Markdown
 ↓
前端自己 parse
```

---

# 35. `types.ts` 是目前一个非常关键的桥梁

文件开头明确约定：

> 后端 Pydantic Schema 变化时同步更新。

这是正确方向。

但当前仍存在：

```text
APIResponse<T = any>
```

建议改：

```ts
export interface APIResponse<T> {
  code: number
  msg: string
  data: T
}
```

并彻底减少：

```text
Record<string, any>
any[]
```

---

# 36. API Response 当前规范

README 规定：

```json
{
  "code": 0,
  "msg": "success",
  "data": {}
}
```

这是目前项目统一响应约定。

### 建议保留。

但要补充：

```text
request_id
error
pagination
```

推荐：

成功：

```json
{
  "code": 0,
  "msg": "success",
  "data": {},
  "meta": {
    "request_id": "req_xxx"
  }
}
```

列表：

```json
{
  "code": 0,
  "msg": "success",
  "data": [],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 120,
    "request_id": "req_xxx"
  }
}
```

---

# 37. `user_id` 处理问题

当前多处 API：

```text
listCards(userId?)
listInterviewReviews(userId?)
createInterviewReview({ user_id? })
getDashboard(userId?)
```

这更像单用户 MVP。

生产方案应该：

```text
Authorization: Bearer <token>
             ↓
get_current_user()
             ↓
user.id
```

前端 API 调用：

```ts
listCards()
```

而不是：

```ts
listCards(userId)
```

---

# 38. Auth 应该在当前后端基础上逐步加强

当前 `app/auth/` 已存在。

建议：

```text
Auth Middleware
 ↓
Current User
 ↓
Router
 ↓
Service
```

而所有 Query 必须默认附带：

```text
WHERE user_id = current_user.id
```

并禁止客户端覆盖。

---

# 39. 数据库现状

当前 DB 是：

```text
MySQL 8.4
```

不是 PostgreSQL。

当前初始化脚本已有：

```text
experience_card
job_analysis
experience_job_mapping
...
```

因此：

> **不建议为了"理论上更先进"而现在迁 PostgreSQL。**

保持 MySQL，先把模型和迁移流程做好。

---

# 40. 数据库当前关键问题

当前 `experience_card` 同时存在：

```text
summary
background
problem
solution
execution
result
content
tags JSON
metrics JSON
dimensions JSON
```

同时前端新模型又使用：

```text
raw_text
ai_structured
```

这说明存在历史兼容层。

---

# 41. 不建议一次性删除兼容字段

正确策略：

```text
Legacy fields
       ↓
兼容读取
       ↓
新 API Schema
       ↓
新字段
       ↓
迁移
       ↓
删除旧字段
```

而不是：

```text
直接 DROP
```

否则历史数据有风险。

---

# 42. 推荐的数据模型 v2

```text
users
user_preferences

experience_cards
experience_card_versions
experience_card_version_changes

job_opportunities
job_descriptions
job_analyses
job_analysis_matches
job_analysis_gaps

submissions
submission_card_versions
submission_resume_versions

resumes
resume_versions
resume_items
resume_ai_suggestions

interviews
interview_preparations
interview_questions
interview_answers

interview_reviews
interview_transcript_segments
interview_qa_pairs
interview_question_analyses
interview_experience_feedback

company_research

ai_tasks
ai_outputs
ai_usage
activities
files
```

不要求第一天全部建完。

---

# 43. 推荐核心关系

```text
User
 │
 ├────────────── ExperienceCard
 │                   │
 │                   └── CardVersion
 │
 └────────────── Submission
                       │
                       ├── JobAnalysis
                       │      ├── Requirements
                       │      ├── Matches
                       │      └── Gaps
                       │
                       ├── ResumeVersion
                       │
                       ├── InterviewPreparation
                       │      └── Questions
                       │
                       └── InterviewReview
                              ├── Transcript
                              ├── QA
                              ├── Analysis
                              └── ExperienceFeedback
                                        │
                                        ▼
                                  CardVersion
```

这是 JobCraft 最核心的数据闭环。

---

# 44. Job Analysis 与 Experience Match

当前有：

```text
experience_job_mapping
```

这是正确方向。

但建议关系语义明确：

```text
JobAnalysis
      │
      ▼
ExperienceMatch
      ├── experience_id
      ├── local_score
      ├── llm_score
      ├── final_score
      ├── matched[]
      ├── missing[]
      └── reason
```

这样：

```text
match_score
```

不是一个黑盒数字，而是可以解释的。

---

# 45. Match Score 建议保留两层

当前接口已经返回：

```text
local_score
llm_score
score
```

这是好设计。

建议：

```text
algorithm_score
+
llm_score
→
final_score
```

同时记录：

```text
algorithm_version
prompt_version
model
```

这样之后才能调优算法而不破坏历史结果。

---

# 46. AI Cache 设计

建议所有可缓存 AI 请求形成：

```text
normalized_input
+
prompt_version
+
model
+
schema_version
+
parameter_version
```

然后：

```text
SHA256(...)
```

得到：

```text
input_hash
```

Redis：

```text
ai:{feature}:{input_hash}
```

例如：

```text
ai:jd-analysis:8f8a...
ai:company-research:9e2a...
```

---

# 47. AI Task 数据模型

推荐：

```text
ai_tasks
```

字段：

```text
id
user_id
feature
business_type
business_id
status
provider
model
prompt_version
schema_version
input_hash
started_at
completed_at
error_code
error_message
retry_count
created_at
updated_at
```

状态：

```text
PENDING
RUNNING
SUCCESS
FAILED
CANCELLED
```

---

# 48. AI Output 数据模型

推荐：

```text
ai_outputs
```

字段：

```text
id
task_id
output_type
schema_version
content_json
created_at
```

作用：

> 让 AI Task 与最终业务实体解耦。

---

# 49. AI Usage / 成本控制

推荐：

```text
ai_usage
```

记录：

```text
task_id
user_id
provider
model
input_tokens
output_tokens
total_tokens
latency_ms
estimated_cost
created_at
```

后面才能知道：

```text
JD 分析一次多少钱
一次面试复盘多少钱
哪个 Prompt 最费 Token
哪个模型性价比最高
```

---

# 50. Prompt 工程

建议：

```text
app/ai/prompts/
├── jd/
│   ├── ats_v1.md
│   ├── match_v1.md
│   ├── gap_v1.md
│   └── subtext_v1.md
├── resume/
├── interview/
└── review/
```

不要把长 Prompt 分散在 Python 业务函数中。

---

# 51. Prompt Contract

每一个 AI 功能至少定义：

```text
Role
Objective
Input
Rules
Constraints
Output Schema
Examples
```

且版本化：

```text
jd_ats_v1
jd_ats_v2
```

数据库保存：

```text
prompt_version
```

---

# 52. AI 输出不要直接覆盖事实

尤其是：

```text
ExperienceCard
Resume
InterviewReview
```

AI 应该产生：

```text
Proposal
```

用户确认以后：

```text
Commit
```

例如：

```text
AI Refine
 ↓
Proposed Version
 ↓
User Approve
 ↓
Card Version
```

而不是：

```text
AI
 ↓
UPDATE experience_card
```

---

# 53. Company Research 的缓存策略

当前规则：

```text
7 天
```

推荐：

```text
L1 Redis
TTL 7 days

L2 MySQL
last_successful_snapshot
```

失败时：

```text
Redis miss
+
DB snapshot still fresh enough
→
返回旧数据
```

这比一次搜索失败就整个页面不可用更稳。

---

# 54. File Storage

当前：

```text
resume_file_path
```

以及：

```text
output/
updated/
```

属于本地文件系统方案。

MVP 可以保留。

后期应该抽象：

```text
FileStorage
├── LocalStorage
└── ObjectStorage
```

这样以后可以换：

```text
S3
OSS
R2
MinIO
```

而业务代码不变。

---

# 55. Resume 下载

当前：

```text
getResumeDownloadUrl(path)
```

直接把：

```text path
```

放到 URL 中。

生产环境不建议暴露实际文件路径。

推荐：

```text
GET /api/v1/resumes/:id/download
```

后端再生成：

```text
signed URL
```

或流式下载。

---

# 56. Pagination

JD 分析库已经有历史记录设计。

推荐所有列表 API 统一：

```text
page
page_size
sort
order
q
```

响应：

```json
{
  "data": [],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 100
  }
}
```

不要不同模块一套分页协议。

---

# 57. 错误处理

当前前端：

```text
parseUnifiedError()
```

已经有基础。

建议增加错误码：

```text
AUTH_REQUIRED
FORBIDDEN
RESOURCE_NOT_FOUND
VALIDATION_ERROR
BUSINESS_RULE_VIOLATION
AI_PROVIDER_ERROR
AI_SCHEMA_ERROR
AI_TIMEOUT
FILE_PARSE_ERROR
RATE_LIMITED
```

前端根据：

```text
error.code
```

决定 UI。

不要根据：

```text
message.includes("xxx")
```

判断业务。

---

# 58. 前端 API 层最终结构建议

当前：

```text
src/api.ts
```

改成：

```text
src/api/
├── client.ts
├── dashboard.ts
├── experience.ts
├── jd-analysis.ts
├── submission.ts
├── resume.ts
├── interview-prep.ts
├── interview-review.ts
└── index.ts
```

---

# 59. 前端 Server State 建议

现在大量使用：

```text
useEffect
useState
load()
```

随着 API 增多，建议引入：

```text
TanStack Query
```

或者保持轻量自定义 Query 层。

目标：

```text
GET
→ cache
→ stale
→ invalidate
→ mutation
```

例如：

```text
updateCard()
→ invalidate experiences
```

而不是：

```text
await updateCard()
await load()
```

到处重复。

---

# 60. 页面与 Server State 的最终职责

页面：

```text
Form
UI state
User interaction
```

Query：

```text
GET
cache
loading
error
```

Mutation：

```text
POST
PATCH
DELETE
```

Backend：

```text
Business Logic
```

AI：

```text
AI Logic
```

---

# 61. Backend 目录建议

你现有架构可以继续，不必推倒。

建议演进成：

```text
app/
├── api/
│   ├── experience.py
│   ├── job_analysis.py
│   ├── submission.py
│   ├── interview_prep.py
│   └── interview_review.py
│
├── domain/
│   ├── experience/
│   ├── job/
│   ├── submission/
│   ├── interview/
│   └── resume/
│
├── services/
│   ├── experience_service.py
│   ├── submission_service.py
│   └── ...
│
├── workflows/
├── agents/
├── tools/
├── schemas/
├── repositories/
├── tasks/
├── auth/
└── core/
```

当前 `Controller → Workflow → Agent → Tool` 可以继续保留。

只是在复杂业务上补：

```text
Controller → Application Service → Workflow
```

---

# 62. Controller 不能承担业务规则

Controller 只负责：

```text
HTTP
Parse
Validate
Call Service
Response
```

不要把：

```text
状态机
权限
事务
AI Prompt
```

写进 Router。

---

# 63. Workflow 与 Domain 的边界

建议：

### Workflow

负责：

```text
AI orchestration
```

### Domain Service

负责：

```text
business rules
```

例如：

```text
can_review_submission()
can_generate_prep()
can_move_status()
```

不要让这些判断存在于：

```text
React
```

或者：

```text
LLM
```

---

# 64. Transaction 边界

以下操作应该考虑数据库事务：

## 新建 Submission

```text
create submission
+
attach cards
+
attach analysis
```

## 保存 Resume

```text
resume version
+
submission snapshot
```

## Experience 回流

```text
feedback
+
new version
+
activity
```

避免半成功状态。

---

# 65. Activity Log

当前项目已经有 Activity 思路。

建议正式化：

```text
activities
```

event type：

```text
SUBMISSION_CREATED
STATUS_CHANGED
JD_ANALYSIS_COMPLETED
RESUME_GENERATED
INTERVIEW_PREP_CREATED
INTERVIEW_REVIEW_COMPLETED
EXPERIENCE_VERSION_CREATED
```

Activity 应来自业务事件，而不是页面自己手动拼。

---

# 66. Event → Activity

例如：

```text
POST /submission
       ↓
SubmissionCreated
       ↓
ActivityService
       ↓
activities
```

这样未来：

```text
Notification
Analytics
Timeline
```

都可以复用。

---

# 67. API 版本化策略

当前：

```text
/api/jobcraft/*
```

继续作为兼容层。

新 API 建议：

```text
/api/v1/*
```

迁移：

```text
Legacy API
     ↓
Adapter
     ↓
Application Service
```

而不是复制一整套业务逻辑。

---

# 68. 推荐的 API v1 资源结构

```text
/api/v1/me

/api/v1/experiences
/api/v1/experiences/{id}
/api/v1/experiences/{id}/versions

/api/v1/jobs
/api/v1/jobs/{id}

/api/v1/jd-analyses
/api/v1/jd-analyses/{id}

/api/v1/submissions
/api/v1/submissions/{id}
/api/v1/submissions/{id}/workspace

/api/v1/resumes
/api/v1/resumes/{id}

/api/v1/interviews
/api/v1/interviews/{id}

/api/v1/interviews/{id}/preparation
/api/v1/interviews/{id}/review

/api/v1/ai-tasks/{id}
```

---

# 69. 旧 API 到新 API 映射

| 当前 API | 推荐 v1 |
|---|---|
| `/experience/cards` | `/experiences` |
| `/job/analyze` | `/jd-analyses` |
| `/job/step1-ats-recommend` | `/jd-analyses/{id}/ats` |
| `/job/step2-gap-polish` | `/jd-analyses/{id}/gap` |
| `/submission` | `/submissions` |
| `/dashboard` | `/dashboard` 或 `/me/dashboard` |
| `/job/{id}/interview-prep` | `/interviews/{id}/preparation` |
| `/interview-review` | `/interviews/{id}/review` |

**注意：这不是要求现在全部重命名。**

优先保持兼容，然后逐步迁移。

---

# 70. 前后端契约的"唯一真相源"

建议：

```text
Backend Pydantic
        ↓
OpenAPI
        ↓
TypeScript generated types
        ↓
Frontend
```

最终目标：

```text
不要手工维护两套类型。
```

如果暂时做不到完整自动生成，也至少保持：

```text app/schemas/jobcraft.py
        ↓
frontend/src/types.ts
```

这一条单向规则。

---

# 71. 当前 `types.ts` 自动同步策略建议

当前注释说：

> 由 `app/schemas/jobcraft.py` 自动生成/维护。

下一阶段应真正自动化：

```text
FastAPI OpenAPI
      ↓
openapi.json
      ↓
TypeScript generator
      ↓
src/api/generated.ts
```

手工 TypeScript Type 只保留真正前端独有模型。

---

# 72. Contract Test

建议新增：

```text
tests/contract/
```

测试：

```text
Backend response
matches OpenAPI schema
```

以及：

```text
Frontend mock
matches generated schema
```

这样避免：

```text
后端改 field
↓
前端运行时才发现
```

---

# 73. 测试矩阵

## Experience

```text
create
update
delete
structure
recommend tags
upload
```

## JD

```text
create analysis
list
detail
ATS
gap
match
delete
```

## Submission

```text
create
update status
delete
workspace
```

## Interview Prep

```text
generate
get
round type
submission linkage
```

## Interview Review

```text
upload
parse
QA
limit 8
analyze
delete
```

---

# 74. AI 测试不要只测"HTTP 200"

应该测试：

```text
schema valid
required fields
score ranges
enum values
array lengths
business invariants
```

例如：

```text
overall_score ∈ [0,100]
```

```text
selected_sequences.length <= 8
```

---

# 75. AI Prompt Regression Test

建立固定测试样例：

```text
tests/fixtures/ai/
├── jd_001.json
├── jd_002.json
├── interview_001.txt
└── experience_001.txt
```

每次 Prompt 修改：

```text
Prompt V1
vs
Prompt V2
```

跑：

```text
schema validity
field coverage
basic semantic checks
```

避免"Prompt 改完，页面悄悄坏掉"。

---

# 76. 当前前端主要技术债清单

## P0

```text
1. 统一 API 出口
2. user_id 不再由客户端决定
3. 统一状态机
4. JD 模型去重
5. API Response 类型去 any
6. Review / Prep AI Task 化
7. 后端权限校验
```

## P1

```text
8. api.ts 模块化
9. Server State Query 化
10. Submission 正式成为 Pipeline Aggregate
11. Experience Version 标准化
12. File Storage abstraction
13. Activity Event
```

## P2

```text
14. /api/v1 migration
15. OpenAPI 自动生成 TS types
16. Observability
17. AI cost accounting
18. Redis unified cache
19. Object storage
```

---

# 77. 推荐开发顺序

不要一次修改全部。

建议按以下 Phase。

## Phase 0 — Contract Freeze

输出：

```text
domain-model.md
api-contract.md
frontend-backend-mapping.md
state-machine.md
```

Git：

```text
docs(contract): freeze frontend backend contract v1
```

---

## Phase 1 — Experience

```text
Experience API
DB cleanup
Version API
Frontend API refactor
Tests
```

Git：

```text
feat(experience): align experience contract
```

---

## Phase 2 — Submission / Pipeline

```text
Submission model
Status machine
Dashboard
Workspace
```

Git：

```text
feat(submission): establish application pipeline
```

---

## Phase 3 — JD

```text
JD Analysis
ATS
Match
Gap
History
Pagination
```

Git：

```text
feat(jd): align jd analysis contract
```

---

## Phase 4 — AI Infrastructure

```text
AI Task
Prompt Version
Cache
Retry
Usage
Validation
```

Git：

```text
feat(ai): introduce unified ai task infrastructure
```

---

## Phase 5 — Resume

```text
ResumeVersion
Experience snapshots
AI Suggestions
PDF
```

Git：

```text
feat(resume): integrate resume pipeline
```

---

## Phase 6 — Interview Prep

```text
Interview
Preparation
Questions
Company Research Cache
```

Git：

```text
feat(interview-prep): integrate preparation workflow
```

---

## Phase 7 — Interview Review

```text
Upload
Parse
QA
Selected Questions
Multi-Agent Analysis
```

Git：

```text
feat(interview-review): integrate review workflow
```

---

## Phase 8 — Feedback Loop

```text
Review
 ↓
Experience Feedback
 ↓
Experience Version
```

Git：

```text
feat(feedback): close interview-to-experience loop
```

---

# 78. 推荐每个 Task 的开发模板

每次让 Coding Agent 开工前，先写：

```markdown
## Task

实现 Experience Update API。

## Context

参考：
- docs/frontend-backend-contract-audit-v1.md
- app/schemas/jobcraft.py
- frontend-jobcraft/src/pages/ExperiencePage.tsx

## Scope

- PATCH /experiences/{id}
- Pydantic request schema
- repository
- service
- tests
- frontend api client

## Non-goals

- 不修改 AI Workflow
- 不修改数据库旧字段
- 不重构其他模块

## Acceptance Criteria

- API 200
- 未授权不能访问
- 不属于当前用户返回 404/403
- Schema test passed
- ruff passed
- pytest passed

## Documentation

更新：
- PROGRESS.md
- API contract
```

---

# 79. Git Commit 规则

每个可独立验证的 Task 一个 commit。

推荐：

```text
feat(experience): add update card api
fix(jd): prevent cross-user analysis access
refactor(api): split frontend api clients
test(review): add question selection contract tests
docs(contract): update submission schema
```

禁止：

```text
update
modify
test
new
final
```

---

# 80. 代码审查 Checklist

## Frontend

```text
[ ] 没有直接 fetch
[ ] 没有新增 any
[ ] API 类型来自统一 schema
[ ] UI state 与 server state 分离
[ ] loading/error/empty 都有处理
```

## Backend

```text
[ ] Controller 无业务逻辑
[ ] Service 有权限校验
[ ] Repository 负责 DB
[ ] Schema 已定义
[ ] 有测试
[ ] 有事务边界
```

## AI

```text
[ ] Prompt versioned
[ ] Structured output
[ ] Pydantic validation
[ ] Task state
[ ] Retry
[ ] Cache key
[ ] Usage logging
```

---

# 81. 最终推荐架构

```text
                         JobCraft
                            │
             ┌──────────────┴──────────────┐
             │                             │
         Frontend                       Backend
             │                             │
      React + TypeScript                FastAPI
             │                             │
         API Client                    Router
             │                             │
       Query / Mutation             Application Service
             │                             │
             └──────── HTTP ───────────────┘
                                           │
                          ┌────────────────┼─────────────────┐
                          ▼                ▼                 ▼
                       Domain           Workflow         Repository
                          │                │                 │
                          │                ▼                 ▼
                          │              Agent             MySQL
                          │                │
                          │                ▼
                          │               LLM
                          │
              ┌───────────┼───────────────┐
              ▼           ▼               ▼
         Experience   Submission       Interview
              │           │               │
              │           ├── Resume      ├── Prep
              │           ├── JD          └── Review
              │           └── Card Versions
              │
              └────────────── Feedback Loop ──────────────┐
                                                           ▼
                                                   Experience Version
```

---

# 82. 最终数据流

```text
用户
 ↓
Experience
 ↓
JD
 ↓
JD Analysis
 ↓
Experience Match
 ↓
Card Version
 ↓
Resume
 ↓
Submission
 ↓
Interview Preparation
 ↓
Interview
 ↓
Interview Review
 ↓
Experience Feedback
 ↓
New Experience Version
 ↓
Experience Library
```

这条链路是整个 JobCraft 的核心。

---

# 83. 本次审计最重要的结论

### 结论 1

**不用重写后端。**

现在的 FastAPI + LangGraph + MySQL + Pydantic 架构可以继续。

---

### 结论 2

**不要为了"看起来高级"现在迁 PostgreSQL。**

先把已有 MySQL 模型、事务、迁移和关系搞正确。

---

### 结论 3

**新 UI 已经可以作为真实前端。**

它不是单纯设计稿，而是已经调用现有后端 API。

---

### 结论 4

现在最需要的是：

```text
Contract Alignment
```

不是：

```text
Rewrite
```

---

### 结论 5

产品真正的核心聚合应逐步统一为：

```text
Submission / Application
```

因为它连接：

```text
JD
Resume
Experience Versions
Interview Prep
Interview Review
```

---

### 结论 6

Experience 是第二个核心资产：

```text
Experience
 ↓
Version
 ↓
Match
 ↓
Resume
 ↓
Interview
 ↓
Review Feedback
```

---

### 结论 7

AI 应该是基础设施，而不是业务实体本身：

```text
Business
 ↓
AI Task
 ↓
Workflow
 ↓
Agent
 ↓
LLM
 ↓
Structured Output
 ↓
Validator
 ↓
Business Result
```

---

# 84. 下一阶段执行清单

按照实际开发顺序：

```text
[ ] 01 冻结 Domain Model
[ ] 02 冻结 Status Machine
[ ] 03 冻结 API Contract
[ ] 04 统一 user identity
[ ] 05 统一前端 API Client
[ ] 06 清理 any
[ ] 07 Experience API 对齐
[ ] 08 Submission/Pipeline 对齐
[ ] 09 JD API 对齐
[ ] 10 Resume API 对齐
[ ] 11 Interview Prep 对齐
[ ] 12 Interview Review 对齐
[ ] 13 AI Task
[ ] 14 AI Cache
[ ] 15 AI Usage
[ ] 16 Prompt Version
[ ] 17 File Storage
[ ] 18 Contract Tests
[ ] 19 E2E Tests
[ ] 20 CI
```

---

# 85. 给 OpenCode / Claude Code 的开发原则

把以下规则视为当前项目的强约束：

```text
1. 不推倒现有后端。
2. 不未经说明迁移数据库。
3. 不直接在 React Component 中写 fetch。
4. 不让前端决定 user_id。
5. 不让 Controller 承担业务逻辑。
6. 不让业务代码直接调用 LLM Provider。
7. 不让 AI 直接覆盖用户事实数据。
8. 所有 AI 输出必须经过 Schema Validation。
9. 所有数据库变更必须通过 migration。
10. 每完成一个独立 Task 必须：
   - 更新文档
   - 更新 TODO / PROGRESS
   - 运行测试
   - Git commit
11. 修改 Backend Schema 时同步前端类型。
12. 新增业务规则时必须更新状态机 / Domain 文档。
13. 不因为"重构更漂亮"而扩大 Task Scope。
14. 优先兼容当前 API，再逐步迁移 `/api/v1`。
```

---

# 86. Audit Status

| 项目 | 状态 |
|---|---|
| 前端页面识别 | ✅ |
| 页面 → API 映射 | ✅ |
| 当前 API 入口识别 | ✅ |
| 核心数据对象识别 | ✅ |
| AI 数据流识别 | ✅ |
| 数据库现状识别 | ✅ |
| 契约冲突识别 | ✅ |
| 代码技术债识别 | ✅ |
| Domain v2 初步建议 | ✅ |
| API v1 演进建议 | ✅ |
| AI Task / Cache 建议 | ✅ |
| 实际代码修改 | ❌ 本文仅做审计，不直接修改仓库 |

---

# 87. 参考源码

- GitHub Repository: `https://github.com/Frangipanelu/jobcraft`
- Frontend source: `frontend-jobcraft/src`
- API client: `frontend-jobcraft/src/api.ts`
- Frontend schema types: `frontend-jobcraft/src/types.ts`
- Routes: `frontend-jobcraft/src/App.tsx`
- Career route: `frontend-jobcraft/src/pages/CareerRoutePage.tsx`
- Experience: `frontend-jobcraft/src/pages/ExperiencePage.tsx`
- JD Analysis: `frontend-jobcraft/src/pages/JDAnalysisPage.tsx`
- Job / Resume: `frontend-jobcraft/src/pages/JobPage.tsx`
- Interview Prep: `frontend-jobcraft/src/pages/InterviewPrepPage.tsx`
- Interview Review: `frontend-jobcraft/src/pages/InterviewReviewPage.tsx`
- Backend API: `app/api/server.py`
- Backend schemas: `app/schemas/jobcraft.py`
- Database: `docker/mysql/jobcraft.sql`
- Engineering rules: `AGENTS.md`
- Architecture: `ARCHITECTURE.md`

---

# 88. 后续文档链

本审计文档之后，建议形成以下正式工程文档：

```text
01_frontend_backend_contract_audit.md   ← 本文
02_domain_model_v2.md
03_api_contract_v2.md
04_database_schema_v2.md
05_ai_architecture_v2.md
06_state_machine.md
07_development_plan.md
08_agent_coding_rules.md
```

最终由：

```text
01 Audit
   ↓
02 Domain
   ↓
03 API
   ↓
04 Database
   ↓
05 AI
   ↓
06 State
   ↓
07 Development Tasks
```

形成完整的 JobCraft 软件工程基线。