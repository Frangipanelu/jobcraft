# JobCraft 前后端映射关系文档

> 基于代码扫描生成，用于指导后续开发。
> 扫描日期：2026-09-02

## 1. 前端架构概览

### 1.1 组件结构
```
frontend-jobcraft/src/
├── components/
│   ├── workbench/WorkbenchView.tsx      # 求职路线仪表盘
│   ├── experiences/ExperiencesView.tsx   # 经历卡管理
│   ├── jobs/JobsListView.tsx           # 投递列表
│   ├── jobs/JobWorkspaceView.tsx       # 投递工作台
│   ├── jd/JDAnalysisCenterView.tsx     # JD分析中心
│   ├── jd/JDReportDetailView.tsx       # JD分析详情
│   ├── resume/ResumeEditorView.tsx     # 简历编辑器
│   ├── interview/InterviewPrepCenterView.tsx    # 面试准备中心
│   ├── interview/InterviewPrepWorkspaceView.tsx # 面试准备工作台
│   ├── review/InterviewReviewCenterView.tsx     # 面试复盘中心
│   ├── review/InterviewReviewDetailView.tsx     # 面试复盘详情
│   └── user/UserProfileView.tsx        # 用户中心
├── context/JobCraftContext.tsx          # 全局状态管理
├── api/                                # API调用层
│   ├── client.ts                       # HTTP客户端
│   ├── experience.ts                   # 经历卡API
│   ├── job.ts                          # 岗位/投递API
│   ├── interview.ts                    # 面试API
│   └── auth.ts                         # 认证API
└── types/
    ├── jobcraft.ts                     # 前端业务类型
    └── api/types.ts                    # API响应类型
```

### 1.2 状态管理
- 使用React Context + useState管理全局状态
- 所有API调用集中在`JobCraftContext.tsx`
- 组件通过`useJobCraft()` hook访问状态

---

## 2. 页面 → 组件 → API 映射

### 2.1 求职路线 (WorkbenchView)
| 层级 | 文件 | 说明 |
|------|------|------|
| 组件 | `components/workbench/WorkbenchView.tsx` | 仪表盘视图 |
| API | `api/job.ts::getDashboard()` | 获取投递列表 |
| 后端 | `app/api/submission.py::jobcraft_dashboard()` | `/api/jobcraft/dashboard` |
| 数据库 | `resume_submission` | 投递记录表 |
| 状态 | **[EXISTS]** | 已存在，可直接复用 |

### 2.2 经历卡 (ExperiencesView)
| 层级 | 文件 | 说明 |
|------|------|------|
| 组件 | `components/experiences/ExperiencesView.tsx` | 经历卡列表 |
| API | `api/experience.ts::listCards()` | 获取经历卡列表 |
| 后端 | `app/api/experience.py::jobcraft_experience_list()` | `/api/jobcraft/experience/cards` |
| 数据库 | `experience_card` | 经历卡表 |
| 状态 | **[EXISTS]** | 已存在，可直接复用 |

**CRUD操作：**
- 创建：`createCard()` → `POST /api/jobcraft/experience/cards`
- 更新：`updateCard()` → `PATCH /api/jobcraft/experience/cards/{id}`
- 删除：`deleteCard()` → `DELETE /api/jobcraft/experience/cards/{id}`
- 结构化：`structureCard()` → `POST /api/jobcraft/experience/cards/{id}/structure`
- 标签推荐：`recommendTags()` → `POST /api/jobcraft/experience/cards/{id}/recommend-tags`

### 2.3 JD分析 (JDAnalysisCenterView)
| 层级 | 文件 | 说明 |
|------|------|------|
| 组件 | `components/jd/JDAnalysisCenterView.tsx` | JD分析中心 |
| API | `api/job.ts::listJobAnalyses()` | 获取分析列表 |
| 后端 | `app/api/job_analysis.py::jobcraft_job_list()` | `/api/jobcraft/job/analyses` |
| 数据库 | `job_analysis` | 岗位分析表 |
| 状态 | **[EXISTS]** | 已存在，可直接复用 |

**分析流程：**
- Step1 ATS：`step1AtsRecommend()` → `POST /api/jobcraft/job/step1-ats-recommend`
- Step2 Gap：`step2GapPolish()` → `POST /api/jobcraft/job/step2-gap-polish`
- 完整分析：`analyzeJob()` → `POST /api/jobcraft/job/analyze`

### 2.4 投递工作台 (JobWorkspaceView)
| 层级 | 文件 | 说明 |
|------|------|------|
| 组件 | `components/jobs/JobWorkspaceView.tsx` | 投递工作台 |
| API | `api/job.ts::getSubmission()` | 获取投递详情 |
| 后端 | `app/api/submission.py::jobcraft_submission_get()` | `/api/jobcraft/submission/{id}` |
| 数据库 | `resume_submission` | 投递记录表 |
| 状态 | **[EXISTS]** | 已存在，可直接复用 |

**投递操作：**
- 创建投递：`createSubmission()` → `POST /api/jobcraft/submission`
- 更新状态：`updateSubmission()` → `PATCH /api/jobcraft/submission/{id}`
- 删除投递：`deleteSubmission()` → `DELETE /api/jobcraft/submission/{id}`

### 2.5 面试准备 (InterviewPrepWorkspaceView)
| 层级 | 文件 | 说明 |
|------|------|------|
| 组件 | `components/interview/InterviewPrepWorkspaceView.tsx` | 面试准备工作台 |
| API | `api/interview.ts::generateInterviewPrep()` | 生成面试准备 |
| 后端 | `app/api/interview_prep.py::jobcraft_job_interview_prep()` | `/api/jobcraft/job/{id}/interview-prep` |
| 数据库 | `interview_preps` | 面试准备稿表 |
| 状态 | **[EXISTS]** | 已存在，可直接复用 |

### 2.6 面试复盘 (InterviewReviewDetailView)
| 层级 | 文件 | 说明 |
|------|------|------|
| 组件 | `components/review/InterviewReviewDetailView.tsx` | 面试复盘详情 |
| API | `api/interview.ts::analyzeInterviewReview()` | 分析面试复盘 |
| 后端 | `app/api/interview_review.py::jobcraft_interview_review_analyze()` | `/api/jobcraft/interview-review/{id}/analyze` |
| 数据库 | `interview_records` + `interview_qa_pairs` | 面试记录表 + QA对表 |
| 状态 | **[EXISTS]** | 已存在，可直接复用 |

**复盘流程：**
- 上传：`uploadInterviewReview()` → `POST /api/jobcraft/interview-review/upload`
- 解析预览：`parseInterviewReviewPreview()` → `POST /api/jobcraft/interview-review/parse-preview`
- 问题表：`generateInterviewReviewQuestionTable()` → `POST /api/jobcraft/interview-review/{id}/question-table`
- 分析：`analyzeInterviewReview()` → `POST /api/jobcraft/interview-review/{id}/analyze`

---

## 3. API端点映射表

### 3.1 经历卡 API
| 前端函数 | HTTP方法 | 后端端点 | 数据库表 | 状态 |
|----------|----------|----------|----------|------|
| `listCards()` | GET | `/api/jobcraft/experience/cards` | `experience_card` | **[EXISTS]** |
| `createCard()` | POST | `/api/jobcraft/experience/cards` | `experience_card` | **[EXISTS]** |
| `updateCard()` | PATCH | `/api/jobcraft/experience/cards/{id}` | `experience_card` | **[EXISTS]** |
| `deleteCard()` | DELETE | `/api/jobcraft/experience/cards/{id}` | `experience_card` | **[EXISTS]** |
| `uploadResume()` | POST | `/api/jobcraft/experience/upload` | `experience_card` | **[EXISTS]** |
| `structureCard()` | POST | `/api/jobcraft/experience/cards/{id}/structure` | `experience_card` | **[EXISTS]** |
| `recommendTags()` | POST | `/api/jobcraft/experience/cards/{id}/recommend-tags` | `experience_card` | **[EXISTS]** |
| `backfillCards()` | POST | `/api/jobcraft/experience/cards/backfill` | `experience_card` | **[EXISTS]** |

### 3.2 JD分析 API
| 前端函数 | HTTP方法 | 后端端点 | 数据库表 | 状态 |
|----------|----------|----------|----------|------|
| `analyzeJob()` | POST | `/api/jobcraft/job/analyze` | `job_analysis` | **[EXISTS]** |
| `listJobAnalyses()` | GET | `/api/jobcraft/job/analyses` | `job_analysis` | **[EXISTS]** |
| `step1AtsRecommend()` | POST | `/api/jobcraft/job/step1-ats-recommend` | `job_analysis` | **[EXISTS]** |
| `step2GapPolish()` | POST | `/api/jobcraft/job/step2-gap-polish` | `job_analysis` | **[EXISTS]** |
| `saveCardVersion()` | POST | `/api/jobcraft/job/save-card-version` | `card_versions` | **[EXISTS]** |
| `saveResume()` | POST | `/api/jobcraft/job/save-resume` | `resume_submission` | **[EXISTS]** |

### 3.3 投递 API
| 前端函数 | HTTP方法 | 后端端点 | 数据库表 | 状态 |
|----------|----------|----------|----------|------|
| `createSubmission()` | POST | `/api/jobcraft/submission` | `resume_submission` | **[EXISTS]** |
| `getSubmission()` | GET | `/api/jobcraft/submission/{id}` | `resume_submission` | **[EXISTS]** |
| `updateSubmission()` | PATCH | `/api/jobcraft/submission/{id}` | `resume_submission` | **[EXISTS]** |
| `deleteSubmission()` | DELETE | `/api/jobcraft/submission/{id}` | `resume_submission` | **[EXISTS]** |
| `getDashboard()` | GET | `/api/jobcraft/dashboard` | `resume_submission` | **[EXISTS]** |
| `createManualSubmission()` | POST | `/api/jobcraft/submission/manual` | `resume_submission` | **[EXISTS]** |

### 3.4 面试准备 API
| 前端函数 | HTTP方法 | 后端端点 | 数据库表 | 状态 |
|----------|----------|----------|----------|------|
| `generateInterviewPrep()` | POST | `/api/jobcraft/job/{id}/interview-prep` | `interview_preps` | **[EXISTS]** |
| `getInterviewPrep()` | GET | `/api/jobcraft/job/{id}/interview-prep` | `interview_preps` | **[EXISTS]** |
| `getJobSelectedCards()` | GET | `/api/jobcraft/job/{id}/selected-cards` | `experience_job_mapping` | **[EXISTS]** |

### 3.5 面试复盘 API
| 前端函数 | HTTP方法 | 后端端点 | 数据库表 | 状态 |
|----------|----------|----------|----------|------|
| `listInterviewReviews()` | GET | `/api/jobcraft/interview-review` | `interview_records` | **[EXISTS]** |
| `createInterviewReview()` | POST | `/api/jobcraft/interview-review` | `interview_records` | **[EXISTS]** |
| `getInterviewReviewDetail()` | GET | `/api/jobcraft/interview-review/{id}` | `interview_records` + `interview_qa_pairs` | **[EXISTS]** |
| `deleteInterviewReview()` | DELETE | `/api/jobcraft/interview-review/{id}` | `interview_records` | **[EXISTS]** |
| `uploadInterviewReview()` | POST | `/api/jobcraft/interview-review/upload` | `interview_records` | **[EXISTS]** |
| `parseInterviewReviewPreview()` | POST | `/api/jobcraft/interview-review/parse-preview` | - | **[EXISTS]** |
| `generateInterviewReviewQuestionTable()` | POST | `/api/jobcraft/interview-review/{id}/question-table` | `interview_qa_pairs` | **[EXISTS]** |
| `analyzeInterviewReview()` | POST | `/api/jobcraft/interview-review/{id}/analyze` | `interview_qa_pairs` | **[EXISTS]** |

---

## 4. 数据库表映射

### 4.1 核心业务表
| 数据库表 | Domain实体 | 前端对应 | 状态 |
|----------|------------|----------|------|
| `experience_card` | ExperienceCard | Experience | **[EXISTS]** |
| `card_versions` | ExperienceCardVersion | ExperienceVersionRecord | **[EXISTS]** |
| `job_analysis` | JobAnalysis | JDAnalysis | **[EXISTS]** |
| `experience_job_mapping` | ExperienceJobMatch | recommendedExperiences | **[EXISTS]** |
| `resume_submission` | Submission | Job | **[EXISTS]** |
| `interview_preps` | InterviewPreparation | InterviewPreparation | **[EXISTS]** |
| `interview_records` | Interview + InterviewReview | Interview + InterviewReview | **[EXISTS]** |
| `interview_qa_pairs` | InterviewQAPair | InterviewQuestion | **[EXISTS]** |
| `company_research` | CompanyResearch | companyResearch | **[EXISTS]** |

### 4.2 缺失表 (v2 Domain Model)
| 数据库表 | Domain实体 | 前端对应 | 状态 |
|----------|------------|----------|------|
| `users` | User | UserProfile | **[MISSING]** |
| `user_preferences` | UserPreference | preferences | **[MISSING]** |
| `submission_card_versions` | SubmissionCardVersion | - | **[MISSING]** |
| `resume_versions` | ResumeVersion | ResumeVersion | **[MISSING]** |
| `resume_items` | ResumeItem | ResumeSection | **[MISSING]** |
| `ai_tasks` | AITask | - | **[MISSING]** |
| `ai_outputs` | AIOutput | - | **[MISSING]** |
| `activities` | Activity | ActivityLog | **[MISSING]** |
| `interview_experience_feedback` | ExperienceFeedback | - | **[MISSING]** |

---

## 5. 状态标记总结

### 5.1 [EXISTS] - 已存在，可直接复用
- 经历卡CRUD API
- JD分析API
- 投递记录API
- 面试准备API
- 面试复盘API
- 所有核心数据库表

### 5.2 [ADAPT] - 已存在，但需要适配新前端
| 项目 | 问题 | 适配方案 |
|------|------|----------|
| `user_id` 处理 | 前端部分API仍传`user_id`参数 | 改为从auth token获取 |
| 状态机 | 前端使用中文状态，后端也使用中文 | 统一为英文枚举 |
| 前端类型 | `types/jobcraft.ts`与`api/types.ts`重复 | 统一类型定义 |
| 组件状态 | 组件直接fetch（少数情况） | 统一通过API层 |

### 5.3 [MISSING] - 前端需要，但后端缺失
| 项目 | 说明 | 优先级 |
|------|------|--------|
| User表 | 正式用户身份系统 | P0 |
| Submission状态机 | 后端统一状态流转规则 | P0 |
| 用户权限 | 跨用户数据隔离 | P0 |
| AI Task | AI任务追踪和重试 | P1 |
| Activity日志 | 活动记录 | P1 |
| Resume Version | 简历版本管理 | P1 |

### 5.4 [DEPRECATED] - 旧接口/旧结构
| 项目 | 说明 |
|------|------|
| `experience_card`旧字段 | `summary`, `background`, `problem`等旧字段保留兼容 |
| `job_analysis.jd_text` | JD原文直接存储，后续应拆分为`job_descriptions`表 |

### 5.5 [REFACTOR] - 后续应该重构，但当前不要阻塞
| 项目 | 说明 |
|------|------|
| `api.ts`拆分 | 已拆分为多个模块，但可以进一步优化 |
| Server State管理 | 可引入TanStack Query管理缓存 |
| API版本化 | 当前使用`/api/jobcraft/`，后续可迁移至`/api/v1/` |
| 类型自动生成 | 从Pydantic Schema自动生成TypeScript类型 |

---

## 6. 前端类型映射

### 6.1 前端类型 → 后端Schema
| 前端类型 | 后端Schema | 说明 |
|----------|------------|------|
| `Experience` | `ExperienceCardSchema` | 经历卡 |
| `JDAnalysis` | `JobAnalysisResult` | JD分析结果 |
| `Job` | `DashboardItem` | 投递记录 |
| `InterviewPreparation` | `InterviewPrepResult` | 面试准备 |
| `InterviewReview` | `InterviewReviewResult` | 面试复盘 |
| `InterviewQuestion` | `DimensionQuestion` | 面试问题 |
| `ResumeVersion` | - | 简历版本（缺失） |

### 6.2 类型转换函数
前端`JobCraftContext.tsx`中已有转换函数：
- `cardToExperience()`: ExperienceCard → Experience
- `analysisToJD()`: JobAnalysisResult → JDAnalysis
- `submissionToJob()`: DashboardItem → Job

---

## 7. 开发优先级建议

### 7.1 第一阶段：契约对齐 (P0)
1. **统一user_id处理**
   - 移除前端API调用中的`user_id`参数
   - 后端从auth token获取user_id
   - 涉及文件：`api/experience.ts`, `api/job.ts`, `api/interview.ts`

2. **统一状态机**
   - 后端定义状态枚举：`APPLIED`, `INVITED`, `ROUND_1`, `ROUND_2`, `OFFER`, `CLOSED`
   - 前端显示层转译为中文
   - 涉及文件：`app/api/submission.py`, `frontend-jobcraft/src/types/jobcraft.ts`

3. **清理any类型**
   - 移除`api/types.ts`中的`any`类型
   - 完善TypeScript类型定义
   - 涉及文件：`frontend-jobcraft/src/api/types.ts`

### 7.2 第二阶段：功能补全 (P1)
1. **User表实现**
   - 创建`users`表
   - 实现用户注册/登录
   - 涉及文件：`app/tools/db_user.py`, `app/api/auth.py`

2. **Submission状态机**
   - 实现状态流转规则
   - 添加状态变更验证
   - 涉及文件：`app/tools/db_submission.py`

3. **AI Task基础**
   - 创建`ai_tasks`和`ai_outputs`表
   - 实现任务追踪
   - 涉及文件：`app/workflows/`

### 7.3 第三阶段：架构优化 (P2)
1. **API版本化**
   - 创建`/api/v1/`路由
   - 保持旧API兼容
   - 涉及文件：`app/api/`

2. **类型自动生成**
   - 从Pydantic Schema生成TypeScript类型
   - 涉及文件：`scripts/`

3. **Server State优化**
   - 引入TanStack Query
   - 优化缓存策略
   - 涉及文件：`frontend-jobcraft/src/`

---

## 8. 关键发现

### 8.1 优势
1. **API层完整**：所有核心业务都有对应的API端点
2. **数据库表完整**：核心业务表已存在
3. **前后端对齐**：类型定义基本一致
4. **状态管理清晰**：使用Context集中管理状态

### 8.2 问题
1. **user_id硬编码**：部分API仍使用默认`user_id=1`
2. **状态机缺失**：后端没有统一的状态流转规则
3. **类型重复**：`types/jobcraft.ts`和`api/types.ts`有重复定义
4. **权限缺失**：没有用户权限隔离

### 8.3 建议
1. **优先处理P0问题**：user_id、状态机、权限
2. **保持现有架构**：不推倒重来
3. **增量改进**：每次只改一个模块
4. **测试覆盖**：每个改动都要有测试

---

## 9. 下一步行动

### 9.1 立即执行
1. 检查所有`user_id=1`的硬编码
2. 审查状态机实现
3. 清理any类型

### 9.2 本周完成
1. 实现User表
2. 统一状态枚举
3. 完善类型定义

### 9.3 本月完成
1. 用户权限系统
2. AI Task基础
3. API版本化规划

---

*文档生成时间：2026-09-02*
*基于代码版本：v0.14*