# AGENTS.md — JobCraft 求职助手 · AI 协作行为规范

> 本文件定义所有 AI Agent（编码、架构、测试、Review）在本项目中的角色、行为准则、绝对红线与自动化验证要求。任何 AI 会话开始前必须先读取本文件。

## 0. AI 工作流（必读）

### 0.1 启动流程

当opencode开始新会话时，必须按以下步骤执行：

```
1. 读取上下文
   ├── AGENTS.md        → 了解行为规范
   ├── PRODUCT.md       → 了解产品定义
   ├── ARCHITECTURE.md  → 了解技术架构
   └── PROGRESS.md      → 了解当前进度

2. 检查任务
   └── TODO.md          → 查看未完成任务

3. 建立任务（如有新需求）
   └── 更新 TODO.md     → 创建任务清单

4. 执行任务
   ├── 完成一个任务 → 更新 TODO.md
   ├── 提交代码 → 记录 commit_id
   └── 更新 PROGRESS.md

5. 完成后
   ├── 确保所有任务完成
   ├── 更新 PROGRESS.md
   └── git push origin main
```

### 0.2 文档更新规则

| 时机 | 更新文件 | 内容 |
|------|----------|------|
| 开始任务 | TODO.md | 创建任务清单 |
| 完成任务 | TODO.md | 标记为完成 |
| 提交代码 | PROGRESS.md | 记录 commit_id |
| 发布版本 | PROGRESS.md | 更新版本号 |

### 0.3 Commit Message 规范

```
feat: 新功能
fix: 修复bug
refactor: 重构
docs: 文档更新
chore: 杂项
```

## 1. 角色与行为准则

### 1.1 角色定义

| 角色 | 职责 |
|------|------|
| **Coder** | 完成需求实现、Bug 修复、单测补充，优先编辑现有文件，避免不必要的创建。 |
| **Architect** | 审查架构一致性，评估技术债务，禁止引入与现有栈冲突的方案。 |
| **Reviewer** | 执行代码审查，确保红线、规范、性能约束被满足；具体操作见 [`docs/CODE_REVIEW.md`](docs/CODE_REVIEW.md)。 |
| **Debugger** | 在静态分析无法定位时，通过日志/复现脚本收集运行时证据。 |

### 1.2 Agent 节点开发规范

所有 `app/agents/` 中的 Agent 节点必须遵守：

1. **单一职责**：每个 Agent 只做一件事（如 `tech_analyzer` 只分析技术题，`router_agent` 只做分类）。
2. **无状态**：Agent 节点不持有状态，所有输入输出通过 State 传递。
3. **可独立测试**：给定相同输入，必须返回相同输出（或符合 schema 约束的输出）。
4. **类型标注**：所有输入/输出必须使用 Pydantic 模型标注。
5. **LLM 调用限制**：单次节点内最多 1 次 LLM 调用，不循环、不递归。如需多次调用，拆分为多个节点。

### 1.3 Workflow 开发规范

1. **Workflow = StateGraph**：每个功能对应一个 Workflow 文件，定义状态模型、节点和边。
2. **简单功能用单节点**：直接封装 1 次 LLM 调用，不增加不必要的节点。
3. **复杂功能用多节点**：节点之间通过条件边分派，并行节点用 `add_edge` 不设置顺序。
4. **可观测**：所有 Workflow 必须经过测试验证，错误必须有明确的日志。

### 1.2 通用行为准则

1. **先读后写**：修改任何文件前必须先读取完整上下文，禁止基于猜测 patch。
2. **最小改动**：优先编辑现有文件，仅在必要时创建新文件；禁止一次性重写无关模块。
3. **可验证性**：任何非纯 UI 的改动必须附带可运行的验证方式（pytest / curl / 脚本）。
4. **中文优先**：面向用户的文案、注释、文档使用中文；代码中的变量名、函数名使用英文。
5. **暴露问题而非隐藏**：测试失败、lint 错误、接口异常必须如实汇报，禁止虚构成功结果。

## 2. 绝对红线（Zero-Tolerance）

以下行为一经发现必须立即回滚或拒绝合并：

- **禁止硬编码密钥**：所有 API Key、数据库密码、Token 必须通过 `.env` 或环境变量注入。
- **禁止裸 `except:`**：必须使用 `except SpecificException:` 并记录原因。
- **禁止未经授权引入第三方库**：新增依赖需先写入 `pyproject.toml` 或 `frontend-jobcraft/package.json`，并说明必要性。
- **禁止在业务代码中直接调用 `print`**：统一使用日志模块或结构化日志。
- **禁止提交 `.env` 文件**：`.env` 必须在 `.gitignore` 中。
- **禁止破坏现有 API 契约**：修改 Pydantic Schema 或接口返回结构时，必须同步更新调用方与测试。
- **禁止未经验证直接删除文件**：删除前必须确认文件作用，且相关引用已清理。

## 3. 代码规范

### 3.1 Python

- **强制类型提示**：函数参数与返回值必须标注类型；复杂结构使用 `Pydantic` 或 `TypedDict`。
- **强制 Docstring**：所有公共函数、类必须包含 Google 风格 Docstring。
- **导入顺序**：标准库 → 第三方 → 项目内部，每组之间空一行。
- **异常处理**：捕获具体异常，必要时向上抛出并保留原始堆栈。
- **异步规范**：I/O 操作使用 `async/await`，禁止在异步函数中调用阻塞 API。

### 3.2 TypeScript / React

- **强制类型**：禁止 `any` 隐式传播，组件 props 必须显式定义 interface。
- **纯原生 Ant Design**：UI 优先使用 Ant Design 原生组件，禁止为了样式引入自定义 CSS/JS，除非明确授权。
- **组件拆分**：单文件代码超过 300 行必须考虑拆分。

### 3.3 文件与命名

- Python 模块：`snake_case.py`
- React 组件：`PascalCase.tsx`
- 常量/配置：`UPPER_SNAKE_CASE`
- 测试文件：`test_*.py` 或 `*.test.tsx`
- Workflow 文件：`*_flow.py`（如 `interview_review_flow.py`）
- Agent 节点文件：`*_agent.py`（如 `tech_analyzer_agent.py`）
- Workflow 类名：`*Workflow`（如 `InterviewReviewWorkflow`）
- Agent 节点类名：`*Agent`（如 `TechAnalyzerAgent`）

## 4. Git 提交与回滚策略

### 4.1 提交粒度

一个 commit 必须是一个**可独立回滚的逻辑单元**：

| 场景 | 做法 |
|------|------|
| 改了文件里两个无关函数 | 分两个 commit（`git add -p` 交互选择）|
| 一个完整功能涉及后端+前端 | 后端先 commit，前端再 commit |
| 改到一半发现 bug | `git stash` → 修 bug 单独 commit → `git stash pop` |
| 修 bug | 修完即 commit，越早越好 |
| 改命名/格式 | 单独 commit，跟功能分开 |

### 4.2 禁止做的事

- ❌ 一次 commit 改 5+ 个概念无关的文件
- ❌ commit 消息写"修改了一些内容"（必须有 prefix: `feat/fix/docs/refactor/chore`）
- ❌ 提交包含调试代码、console.log、print、TODO 注释
- ❌ 提交损坏的构建（`npm run build` 必须通过）

### 4.3 回滚方式

按需选择：

```bash
# 回滚单个 commit（不影响其他）
git revert <commit-hash> --no-edit

# 回滚多个（按时间倒序）
git revert <最新> <次新> --no-edit

# 本地硬回退（丢失未推送的 commit）
git reset --hard <目标-hash>
```

### 4.4 DB 前向兼容原则

回滚时只回滚代码，DB 不动：

```
规则：只加列/表，不改/删列
示例：加 is_manual  ✓（旧代码不读它）
      把 VARCHAR 改成 INT  ✗（旧代码直接炸）
```

**AI 必须确保所有 DDL 变更满足前向兼容，否则需要双写兼容代码。**

## 5. 自动化验证命令

任何提交前必须通过以下命令（已配置 pre-commit）：

```bash
# 后端代码质量
uv run ruff check --fix .
uv run ruff format .

# 后端测试
uv run pytest tests/ -q

# 前端代码质量（如已配置 eslint/prettier）
cd frontend-jobcraft
npm run build
```

若上述命令失败，禁止提交；CI 失败时优先修复而非绕过。

审查的详细清单、扫描脚本与历次问题记录归档于 [`docs/CODE_REVIEW.md`](docs/CODE_REVIEW.md)。

## 6. 会话工作流

1. **读取上下文**：先读取 `AGENTS.md`、`PRODUCT.md`、`ARCHITECTURE.md`、`PROGRESS.md`。
2. **明确范围**：与用户确认需求边界，避免过度设计。
3. **方案先行**：对于非 trivial 改动，先给出变更方案再执行。
4. **更新进度**：完成子任务后立即更新 `PROGRESS.md`。
5. **关闭会话**：简要汇报完成项、待办事项。

## 7. Engineering Development Workflow

所有开发任务必须遵循：

`docs/engineering-development-workflow-v1.md`

标准流程：

```
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
```

Agent 不得跳过分析、测试、文档或 Git 回溯阶段。

Agent 不得未经 Task Scope 允许进行大范围重构。

Frontend-first：优先复用已有前端需求与后端能力；仅在确认后端缺失时新增后端能力。

所有数据库变更必须通过 Migration。

所有 AI 输出必须经过 Schema Validation。

所有 AI Prompt 必须版本化。

所有独立 Task 必须有明确的 Git Commit。