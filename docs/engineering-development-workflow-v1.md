# JobCraft Engineering Development Workflow v1

## 1. 核心目标

JobCraft 所有开发任务统一遵循：

```
读文档
  ↓
分析现状
  ↓
建立 Task
  ↓
设计方案
  ↓
修改代码
  ↓
测试验证
  ↓
更新文档
  ↓
Git Commit
  ↓
记录 Progress
  ↓
下一 Task
```

核心原则：

> **先理解，再修改；先建立边界，再写代码；一个 Task 一个闭环；每次修改都有测试、文档和 Git 回溯点。**

------

# 2. 第一阶段：Read Docs

任何新任务开始前，Coding Agent 必须先读取：

```
AGENTS.md
PRODUCT.md
ARCHITECTURE.md
TODO.md
PROGRESS.md
```

涉及前端 / 后端 / 数据库 / AI 时，再读取：

```
docs/frontend-backend-contract-audit-v1.md
docs/domain-model-v2.md
docs/database-schema-v2.md
docs/api-contract-v2.md
docs/ai-architecture-v2.md
docs/state-machine.md
```

### 原则

**文档是上下文，不是代码替代品。**

Agent 必须继续检查真实代码。

不能只看：

```
Domain Model
```

就直接修改：

```
Database
```

------

# 3. 第二阶段：Analyze

读取文档后，先分析当前实现。

Agent 必须回答：

```
当前功能是什么？

入口页面在哪里？

当前用户行为是什么？

前端现在使用什么数据？

调用哪个 API？

后端是否已经有这个能力？

后端对应哪个 Router？

哪个 Service / Workflow？

哪个数据库表？

哪些部分是 Mock？

哪些部分是真的？

哪些部分缺失？

哪些部分只是技术债？

哪些内容属于当前 Task？

哪些应该留给后续 Task？
```

------

# 4. 给每个需求打标签

统一使用：

```
[EXISTS]
```

已有能力，可以直接复用。

```
[ADAPT]
```

已有能力，但要适配新 UI。

```
[MISSING]
```

前端需要，但后端没有。

```
[REFACTOR]
```

存在架构问题，但暂时不阻塞功能。

```
[DEPRECATED]
```

旧能力，未来应淘汰。

例如：

```
JD Analysis
[ADAPT]

Experience Version
[EXISTS]

AI Task
[MISSING]

api.ts 拆分
[REFACTOR]
```

------

# 5. 第三阶段：建立 Task

任何代码修改前，都要先有 Task。

推荐：

```
tasks/
├── TASK-EXP-001.md
├── TASK-JD-001.md
├── TASK-SUB-001.md
└── TASK-REVIEW-001.md
```

每个 Task 必须包括：

```
# TASK-XXX

## Title

## Context

## Current State

## Goal

## Scope

## Non-goals

## Affected Files

## API Impact

## Database Impact

## AI Impact

## Acceptance Criteria

## Test Plan

## Documentation

## Expected Commit
```

------

# 6. Task 必须足够小

一个好的 Task：

```
可以独立理解
可以独立实现
可以独立测试
可以独立提交
可以独立回滚
```

例如：

```
TASK-JD-002
实现 JD 历史记录分页
```

是合理的。

而：

```
TASK-ALL-001
完成整个 JobCraft 后端
```

不合理。

------

# 7. Scope Lock

Task 开始以后，Scope 默认锁定。

例如当前 Task：

```
实现 Experience Update API
```

过程中发现：

```
api.ts 很乱
数据库可以迁 PostgreSQL
Repository 命名不好
```

不要顺手全部处理。

应该：

```
发现问题
   ↓
记录 TODO
   ↓
必要时建立 REFACTOR Task
```

这样 Git 历史才能真正可读。

------

# 8. 第四阶段：Design

写代码之前，先完成设计。

必须明确：

```
Input
Output
Business Rule
Data Ownership
API Contract
Database Impact
Transaction
Permission
AI Dependency
Cache
Async
Error Handling
```

------

# 9. Backend 标准分层

JobCraft 推荐：

```
Controller
    ↓
Application Service
    ↓
Domain Service
    ↓
Repository
    ↓
Database
```

AI：

```
Application Service
    ↓
AI Task
    ↓
Workflow
    ↓
Agent
    ↓
LLM Provider
```

禁止：

```
Controller → Database
Controller → LLM
React → Database
React → LLM
```

------

# 10. Frontend 标准分层

推荐：

```
Page
 ↓
Feature Component
 ↓
Hook / Query / Mutation
 ↓
API Client
 ↓
Backend
```

所有 HTTP 请求统一从：

```
src/api/
```

出去。

不要出现：

```
Page → fetch()
```

这种散落式调用。

------

# 11. Server State 与 UI State 分开

## UI State

留在 React：

```
activeTab
modalOpen
searchQuery
selectedIds
loading
formDraft
```

## Server State

来自后端：

```
experiences
jobs
submissions
jdAnalyses
resumes
interviews
reviews
```

不要把同一个服务器数据复制到：

```
Context
useState
localStorage
多个组件
```

形成多份真相源。

------

# 12. Database 规则

数据库变化必须走：

```
Schema
 ↓
Migration
 ↓
Repository
 ↓
Service
 ↓
API
 ↓
Frontend
```

禁止：

```
直接修改生产数据库
```

------

# 13. Database Migration 策略

统一采用：

```
Expand
 ↓
Migrate
 ↓
Verify
 ↓
Switch
 ↓
Contract
```

例如增加：

```
submission_card_versions
```

先新增表：

```
Expand
```

再从旧：

```
card_version_ids JSON
```

迁移：

```
Migrate
```

验证：

```
Verify
```

应用切换到新表：

```
Switch
```

确认稳定后再删除旧字段：

```
Contract
```

------

# 14. AI 开发规则

AI 是基础设施，不是业务层。

标准链路：

```
Business Service
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
Validation
      ↓
Domain Result
```

------

# 15. AI Prompt 必须版本化

禁止：

```
prompt = """
一大段 Prompt
"""
```

散落在业务代码中。

建议：

```
prompts/
├── experience/
├── jd/
├── resume/
├── interview/
└── review/
```

版本：

```
jd_ats_v1
jd_ats_v2
jd_ats_v3
```

历史版本不能直接覆盖。

------

# 16. AI Output 必须结构化

不要让：

```
LLM → Markdown → 前端自己解析
```

成为正式业务链路。

应该：

```
LLM
 ↓
JSON
 ↓
Pydantic
 ↓
Validation
 ↓
Domain Result
```

例如：

```
{
  "score": 82,
  "skills": [],
  "gaps": [],
  "recommendedExperiences": []
}
```

必须经过 Schema 验证。

------

# 17. AI 不得直接修改用户事实

例如 Experience：

```
用户原始经历
      ↓
AI 分析
      ↓
AI Proposal
      ↓
用户确认
      ↓
New Version
```

不要：

```
AI
 ↓
直接 UPDATE experience raw text
```

------

# 18. AI Cache

AI Cache Key 至少包含：

```
feature
model
prompt_version
schema_version
input_hash
```

例如：

```
jd-analysis:gemini:prompt-v3:schema-v2:8f9a...
```

推荐：

```
Redis
```

作为热缓存。

数据库负责：

```
最终业务结果
历史
审计
追溯
```

------

# 19. 第五阶段：Implementation

推荐普通业务功能：

```
Schema
 ↓
Repository
 ↓
Domain / Service
 ↓
API
 ↓
Frontend API Client
 ↓
Frontend
```

AI 功能：

```
AI Schema
 ↓
Prompt
 ↓
Agent
 ↓
Workflow
 ↓
AI Task
 ↓
Persistence
 ↓
API
 ↓
Frontend
```

------

# 20. 第六阶段：Testing

代码完成后不能直接提交。

根据功能选择：

```
Unit Test
Integration Test
API Test
Component Test
E2E Test
AI Regression Test
```

------

# 21. Test Pyramid

推荐：

```
             E2E
            /   \
        API / Integration
          /       \
        Unit       Unit
```

大量基础逻辑用 Unit Test。

关键 API 用 Integration Test。

关键用户路径用 E2E。

------

# 22. AI 测试不能只检查 HTTP 200

必须检查：

```
Schema
Required fields
Enum
Range
Array constraints
Business invariants
```

例如：

```
score ∈ [0,100]
selectedQuestions <= 8
```

------

# 23. AI Regression Test

建立：

```
tests/fixtures/ai/
```

例如：

```
jd_001.json
jd_002.json
experience_001.json
interview_001.txt
```

修改 Prompt 后：

```
Old Prompt
   vs
New Prompt
```

至少验证：

```
Schema Valid
Required Fields
Field Coverage
Business Constraints
```

------

# 24. 第七阶段：Documentation

Task 完成后检查：

```
API 是否变化？
Database 是否变化？
Domain 是否变化？
AI 是否变化？
State Machine 是否变化？
用户流程是否变化？
```

需要的时候分别更新：

```
API Contract
Database Schema
Domain Model
AI Architecture
State Machine
TODO
PROGRESS
```

------

# 25. 文档记录什么

不要把代码重新抄进文档。

文档主要记录：

```
What
Why
Boundary
Decision
Contract
Migration
Known Limitations
```

------

# 26. ADR

出现这些变化时建立 ADR：

```
数据库迁移
引入 Redis
引入 Queue
AI Provider 更换
核心状态机修改
Domain Model 修改
API Breaking Change
新增架构层
```

例如：

```
docs/decisions/
ADR-001-ai-task.md
ADR-002-submission-status.md
ADR-003-cache.md
```

------

# 27. 第八阶段：Git Commit

一个独立 Task 至少有一个主要 Git Commit。

推荐格式：

```
feat(experience): add update card api
feat(jd): integrate ats analysis
fix(submission): enforce review status rule
refactor(api): split frontend api clients
test(review): add review contract tests
docs(contract): update jd api contract
chore(db): add migration
```

------

# 28. Commit 的标准

一个 Commit 要做到：

```
可理解
可验证
可回滚
```

不要：

```
update
fix
final
test
aaa
```

------

# 29. Commit 前 Checklist

```
[ ] Task Scope 完成
[ ] 无无关修改
[ ] Test 通过
[ ] Lint 通过
[ ] Typecheck 通过
[ ] 文档更新
[ ] TODO 更新
[ ] PROGRESS 更新
[ ] Commit Message 合规范
```

------

# 30. 第九阶段：PROGRESS

完成后记录：

```
## 2026-09-02

### TASK-JD-002

Status: DONE

Completed:
- JD history pagination
- API integration
- Backend tests

Commit:
abc1234
```

这样以后你可以直接知道：

```
某个功能什么时候实现？
谁改的？
为什么改？
哪个 Commit？
```

------

# 31. TODO

开发前：

```
- [ ] TASK-JD-002 JD History Pagination
```

完成：

```
- [x] TASK-JD-002 JD History Pagination
```

中途发现新问题：

```
- [ ] TASK-REF-003 Split frontend API clients
```

不要隐藏问题。

------

# 32. Task 状态机

```
BACKLOG
   ↓
READY
   ↓
ANALYZING
   ↓
IN_PROGRESS
   ↓
TESTING
   ↓
DOCS
   ↓
READY_TO_COMMIT
   ↓
DONE
```

异常：

```
BLOCKED
```

------

# 33. 状态定义

### BACKLOG

任务存在，但还没开始。

### READY

前置条件已经满足。

### ANALYZING

阅读代码、文档并确定实现方案。

### IN_PROGRESS

正在修改。

### TESTING

功能已经实现，正在验证。

### DOCS

更新工程文档。

### READY_TO_COMMIT

所有检查通过。

### DONE

Git Commit 完成，Progress 已记录。

### BLOCKED

存在外部依赖或技术阻塞。

------

# 34. 禁止状态跳跃

不允许：

```
BACKLOG → DONE
```

也不允许：

```
IN_PROGRESS → COMMIT
```

必须：

```
IN_PROGRESS
 ↓
TESTING
 ↓
DOCS
 ↓
READY_TO_COMMIT
 ↓
DONE
```

------

# 35. Agent 标准行为

OpenCode / Claude Code / Codex 等 Coding Agent 必须遵循：

```
Observe
 ↓
Plan
 ↓
Implement
 ↓
Verify
 ↓
Document
 ↓
Commit
```

而不是：

```
Generate
 ↓
Hope
```

------

# 36. Agent 开始前必须输出

```
## Task Analysis

### Current State

### Existing Capability

### Gap

### Scope

### Files to Modify

### Files Not to Modify

### API Impact

### DB Impact

### AI Impact

### Validation Plan

### Expected Commit
```

------

# 37. Agent 完成后必须输出

```
## Implementation Result

### Completed

### Tests

### Documentation Updated

### Git Commit

### Remaining Work
```

------

# 38. Frontend-first 原则

JobCraft 当前阶段的开发优先级：

```
Frontend Requirement
        ↓
Existing Backend
        ↓
EXISTS？
 ├── YES → 复用
 │
 └── NO
      ↓
   ADAPT？
      ↓
   MISSING
      ↓
  补 Backend
```

即：

> **前端定义用户需要什么，现有后端优先提供什么，Domain v2 决定后续如何演进。**

------

# 39. Domain-first 原则

页面不等于数据库。

例如：

```
JDAnalysisPage
```

不应该直接对应：

```
jd_analysis_page
```

真正实体：

```
Job
JobDescription
JobAnalysis
Submission
```

------

# 40. Database ≠ API Contract

数据库：

```
jd_text
```

API 可以：

```
{
  "jdText": "..."
}
```

前后端不应该因为数据库字段名而互相绑定。

------

# 41. AI 不等于业务模型

例如：

```
Gemini
```

不应该进入：

```
Submission
```

业务只需要：

```
AI Service
```

AI 基础设施记录：

```
provider
model
prompt_version
schema_version
```

------

# 42. Security Priority

发现冲突时：

```
Security
>
Data Integrity
>
Existing User Behavior
>
Current API Contract
>
Domain Architecture
>
Refactor
>
Code Style
```

不要为了"代码漂亮"破坏当前可用产品。

------

# 43. User Identity 原则

前端：

```
GET /experiences
```

不要：

```
GET /experiences?user_id=123
```

以后应：

```
Authorization
 ↓
Current User
 ↓
Backend
 ↓
WHERE user_id = current_user.id
```

这样才能避免越权。

------

# 44. Bug Workflow

```
Bug
 ↓
Reproduce
 ↓
Root Cause
 ↓
Write Test
 ↓
Fix
 ↓
Regression Test
 ↓
Docs if needed
 ↓
Commit
```

不要：

```
Bug
 ↓
直接改
```

------

# 45. Refactor Workflow

重构前先写：

```
Why now?
What risk?
What benefit?
What is smallest safe scope?
```

如果答案只是：

> "以后可能更好。"

就先进入：

```
TODO
```

------

# 46. API Breaking Change

以下全部视为 Breaking Change：

```
删除字段
修改字段类型
Required → Optional / Optional → Required
修改 Enum
修改 URL
修改 HTTP Method
修改错误码语义
```

必须：

```
更新 Contract
+
Migration Plan
```

------

# 47. Prompt Change

Prompt 修改：

```
Change
 ↓
New Version
 ↓
Regression Test
 ↓
Schema Test
 ↓
Compare Result
 ↓
Docs
 ↓
Commit
```

例如：

```
jd_ats_v2
→
jd_ats_v3
```

不能直接把：

```
v2
```

覆盖掉。

------

# 48. Database Change

数据库修改：

```
Domain Change
 ↓
Schema Change
 ↓
Migration
 ↓
Repository
 ↓
Service
 ↓
API
 ↓
Frontend
 ↓
Test
```

------

# 49. API Change

API 修改：

```
Backend Schema
 ↓
OpenAPI
 ↓
Frontend Type
 ↓
API Client
 ↓
Page
 ↓
Test
 ↓
Docs
```

------

# 50. 一个 Feature 的完整流程

例如：

## JD Analysis

```
用户输入 JD
       ↓
建立 Task
       ↓
检查已有 job analysis API
       ↓
[EXISTS]
       ↓
复用
       ↓
Frontend API Adapter
       ↓
Backend Workflow
       ↓
AI Result
       ↓
Schema Validation
       ↓
DB
       ↓
Frontend
       ↓
Tests
       ↓
Docs
       ↓
Git Commit
```

------

# 51. JobCraft 当前推荐开发顺序

```
Phase 0
Contract Alignment

      ↓

Phase 1
Experience

      ↓

Phase 2
Submission / Pipeline

      ↓

Phase 3
JD Analysis

      ↓

Phase 4
Resume

      ↓

Phase 5
Interview Preparation

      ↓

Phase 6
Interview Review

      ↓

Phase 7
Experience Feedback Loop

      ↓

Phase 8
AI Infrastructure / Observability
```

------

# 52. 第一阶段真正的目标

不是：

> "重构 JobCraft。"

而是：

> **让新的 `jobcraft-ui` 完全由真实后端数据驱动。**

也就是：

```
Mock
 ↓
API
 ↓
Backend
 ↓
Database
```

逐步替换。

------

# 53. 当前项目第一批 Task 推荐

```
TASK-CONTRACT-001
前端 API 全量盘点

TASK-CONTRACT-002
前端 Page → API → Backend 映射

TASK-CONTRACT-003
清理组件直接 fetch

TASK-CONTRACT-004
统一 TypeScript API Types

TASK-EXP-001
Experience API 对齐

TASK-JD-001
JD Analysis API 对齐

TASK-SUB-001
Submission / Career Route 对齐

TASK-PREP-001
Interview Preparation 对齐

TASK-REVIEW-001
Interview Review 对齐
```

完成这些以后才进入：

```
AI Task
AI Cache
AI Usage
```

------

# 54. 最终 JobCraft 开发闭环

```
                  Requirement
                       ↓
                  Read Docs
                       ↓
                 Inspect Code
                       ↓
                  Analyze Gap
                       ↓
                  Create Task
                       ↓
                    Design
                       ↓
                  Implement
                       ↓
                    Test
                       ↓
                 Documentation
                       ↓
                  Git Commit
                       ↓
                   PROGRESS
                       ↓
                  Next Task
                       │
                       └──────────→ Repeat
```

------

# 55. JobCraft Engineering Manifesto

```
1. 先读，再写。
2. 先看真实代码，再相信文档。
3. 前端体验优先。
4. 最大化复用已有后端。
5. 缺失能力才补。
6. 一个 Task 一个完整闭环。
7. Scope 必须可控。
8. Controller 不承担业务逻辑。
9. Domain 不依赖 UI。
10. API 是前后端正式接缝。
11. 数据库通过 Migration 演进。
12. AI 输出必须结构化。
13. AI 不直接覆盖用户事实。
14. Prompt 必须版本化。
15. 测试是完成条件。
16. 文档是工程资产。
17. Git 是正式回溯机制。
18. 新问题建立新 Task。
19. 先正确，再优化。
20. 不为了理论完美破坏当前可用功能。
```

------

# 56. 建议加入 `AGENTS.md`

你现有的 `AGENTS.md` 后面直接增加：

```
## Engineering Development Workflow

所有开发任务必须遵循：

`docs/engineering-development-workflow-v1.md`

标准流程：

Read Docs
→ Analyze
→ Task
→ Design
→ Implement
→ Test
→ Documentation
→ Git Commit
→ PROGRESS
→ Next Task

Agent 不得跳过分析、测试、文档或 Git 回溯阶段。

Agent 不得未经 Task Scope 允许进行大范围重构。

Frontend-first：
优先复用已有前端需求与后端能力；
仅在确认后端缺失时新增后端能力。

所有数据库变更必须通过 Migration。

所有 AI 输出必须经过 Schema Validation。

所有 AI Prompt 必须版本化。

所有独立 Task 必须有明确的 Git Commit。
```

------

## 最终建议

你现在的项目文档体系可以正式变成：

```
AGENTS.md
    ↓
工程规则

PRODUCT.md
    ↓
产品规则

ARCHITECTURE.md
    ↓
当前架构

Frontend ↔ Backend Contract Audit v1
    ↓
现在到底是什么

Domain Model v2
Database Schema v2
API Contract v2
AI Architecture v2
State Machine
    ↓
未来往哪里走

Engineering Development Workflow v1
    ↓
每一次具体怎么开发

TODO.md
    ↓
接下来做什么

PROGRESS.md
    ↓
已经做了什么

Git
    ↓
完整历史
```