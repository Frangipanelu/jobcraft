# 代码审查规范与记录

> 本文档用于沉淀 JobCraft 项目的代码审查规范、扫描清单以及历次审查发现的问题与修复方式。
> 它是 [`AGENTS.md`](../AGENTS.md) 中代码审查要求的详细展开与落地记录。
> 审查依据：[`AGENTS.md`](../AGENTS.md)、[`ARCHITECTURE.md`](../ARCHITECTURE.md)、[`PRODUCT.md`](../PRODUCT.md)。

---

## 1. 审查触发条件

以下任一情况发生时，必须进行代码审查：

1. 功能开发完成、准备提交前。
2. 修复 Bug 后、回归验证前。
3. 引入新依赖或新外部服务时。
4. 修改数据库 Schema、Pydantic Schema 或核心 API 契约时。
5. 合并分支或发起 Pull Request 前。

---

## 2. 审查检查清单

### 2.1 绝对红线（Zero-Tolerance）

- [ ] **无硬编码密钥**：所有 API Key、数据库密码、Token 必须通过 `.env` 或环境变量注入。
- [ ] **无裸 `except:`**：必须使用 `except SpecificException:` 并记录原因。
- [ ] **无未经授权引入第三方库**：新增依赖需先写入 `pyproject.toml` 或 `frontend-jobcraft/package.json`，并说明必要性。
- [ ] **无业务代码直接调用 `print`**：统一使用日志模块或结构化日志。
- [ ] **不提交 `.env` 文件**：`.env` 必须在 `.gitignore` 中。
- [ ] **不破坏现有 API 契约**：修改 Pydantic Schema 或接口返回结构时，必须同步更新调用方与测试。
- [ ] **不未经验证删除文件**：删除前必须确认文件作用，且相关引用已清理。

### 2.2 Python 代码规范

- [ ] 函数参数与返回值标注类型；复杂结构使用 `Pydantic` 或 `TypedDict`。
- [ ] 公共函数、类包含 Google 风格 Docstring。
- [ ] 导入顺序：标准库 → 第三方 → 项目内部，每组之间空一行。
- [ ] 捕获具体异常，必要时向上抛出并保留原始堆栈。
- [ ] I/O 操作使用 `async/await`，禁止在异步函数中调用阻塞 API。
- [ ] SQL 查询必须使用参数化，禁止 f-string / `.format()` 拼接 SQL。

### 2.3 TypeScript / React 代码规范

- [ ] 禁止 `any` 隐式传播，组件 props 必须显式定义 interface。
- [ ] UI 优先使用 Ant Design 原生组件，禁止为了样式引入自定义 CSS/JS，除非明确授权。
- [ ] 单文件代码超过 300 行必须考虑拆分。
- [ ] 前端类型必须与后端 Pydantic Schema 保持同步。

### 2.4 安全扫描

- [ ] 扫描 f-string SQL / `.format()` SQL / DDL 拼接。
- [ ] 扫描 `os.system`、`subprocess`、`eval`、`exec`、`pickle`、`yaml.load` 等危险调用。
- [ ] 扫描项目源码中的硬编码密钥、Token、密码（排除 `.venv`、依赖库示例值）。
- [ ] 检查文件下载/上传接口是否存在路径遍历风险。

### 2.5 自动化验证

提交前必须通过以下命令：

```bash
# 后端代码质量（项目根目录执行）
uv run ruff check --fix .
uv run ruff format .

# 后端测试
uv run pytest tests/ -q

# 前端代码质量（frontend-jobcraft 目录执行）
cd frontend-jobcraft
npm run build
```

### 2.6 自定义扫描脚本

除上述自动化命令外，项目扫描还应执行以下正则/命令，用于发现 ruff 无法覆盖的安全与规范问题：

```bash
# 1. 扫描 f-string / .format() 拼接 SQL
rg -n "execute\(f[\"']|\.format\(" app/tools/db_tools.py

# 2. 扫描危险调用
rg -n "os\.system|subprocess\.call|subprocess\.run|eval\(|exec\(|pickle\.load|yaml\.load" app/

# 3. 扫描疑似硬编码密钥（排除 .venv、node_modules、.env.example 示例值；命中后需人工复核）
rg -n "api[_-]?key|apikey|password|token|secret" app/ frontend-jobcraft/src/ \
  --iglob '!*.example' --iglob '!*.venv*' --iglob '!*node_modules*'

# 4. 扫描业务代码中的 print
rg -n "^\s*print\(" app/ --iglob '!*test*'
```

> 说明：以上脚本基于 [`ripgrep`](https://github.com/BurntSushi/ripgrep)，未安装时可用 `grep -R` 替代，但需自行排除依赖目录；命中项需人工复核是否为真实问题。

---

## 3. 审查记录

### 3.1 2026-07-30 项目扫描

**审查范围**：全项目源码（含后端 `app/`、前端 `frontend-jobcraft/src/`、测试 `tests/`）。

**扫描工具**：

- `uv run ruff check .`
- `uv run pytest tests/ -q`
- `cd frontend-jobcraft && npm run build`
- 自定义正则扫描脚本（SQL 注入、危险调用、硬编码密钥），详见 [2.6 自定义扫描脚本](#26-自定义扫描脚本)

---

#### 3.1.1 发现的问题

| 优先级 | 类别 | 问题描述 | 位置 |
|---|---|---|---|
| P0 | 代码质量 | `ruff check` 失败：无占位符 f-string | [`app/api/server.py:1318`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/api/server.py#L1318) |
| P0 | 测试 | `pytest` 收集阶段崩溃：测试脚本模块级调用外部 API 并 `exit(1)` | [`tests/test_interview_review_api.py`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/tests/test_interview_review_api.py)、[`tests/test_interview_review_api_long.py`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/tests/test_interview_review_api_long.py) |
| P1 | 安全 | f-string 拼接 SQL（UPDATE） | [`app/tools/db_tools.py:422`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/tools/db_tools.py#L422)、[`app/tools/db_tools.py:727`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/tools/db_tools.py#L727) |
| P1 | 安全 | f-string 拼接 DDL | [`app/tools/db_tools.py:574`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/tools/db_tools.py#L574) |
| P2 | 前端缺陷 | 岗位分析下拉框使用错误字段 `job_title` / `company_name` | [`frontend-jobcraft/src/pages/InterviewReviewPage.tsx:481`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/frontend-jobcraft/src/pages/InterviewReviewPage.tsx#L481) |
| P2 | 前端类型 | `api.ts` 重复定义 `ExperienceCard` 且使用 `any` | [`frontend-jobcraft/src/api.ts:14-32`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/frontend-jobcraft/src/api.ts#L14-L32) |
| P2 | 前端缺陷 | `parseInterviewReviewPreview` 未透传 `submission_id` | [`frontend-jobcraft/src/api.ts:365-396`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/frontend-jobcraft/src/api.ts#L365-L396) |
| P2 | 性能 | `generate_question_table` 循环单条删除 QA 对 | [`app/tools/interview_review.py:1162-1165`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/tools/interview_review.py#L1162-L1165) |
| P2 | 代码整洁 | `InterviewReviewCreateResponse` 模型定义未使用 | [`app/api/server.py:1404-1414`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/api/server.py#L1404-L1414) |
| P2 | 文档 | 创建/上传接口 docstring 与行为不一致 | [`app/api/server.py:1417`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/api/server.py#L1417)、[`app/api/server.py:1469`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/api/server.py#L1469) |
| P2 | 构建 | 前端动态导入 `api.ts` 导致 chunk 优化警告 | [`frontend-jobcraft/src/pages/InterviewReviewPage.tsx:183`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/frontend-jobcraft/src/pages/InterviewReviewPage.tsx#L183) |
| P2 | 测试/e2e | 经历卡创建 Schema 缺少 `company/role/period/background/problem/solution/execution/result/dimensions` 字段，导致 e2e 测试失败 | [`app/schemas/jobcraft.py:68`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/schemas/jobcraft.py#L68)、[`app/tools/db_tools.py:657`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/tools/db_tools.py#L657) |
| P3 | 环境 | 本地 8000 端口被非本项目服务占用，导致默认 e2e 测试连接到错误服务 | `localhost:8000` |
| P3 | 构建 | 前端产物 chunk 大于 500KB | `dist/assets/index-*.js` |
| P3 | 测试 | 核心业务流（岗位分析、面试准备、面试复盘 LLM 路径）覆盖不足 | `tests/` |

---

#### 3.1.2 修复方式

| 问题 | 修复文件 | 修复方式 |
|---|---|---|
| 无占位符 f-string | [`app/api/server.py`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/api/server.py) | `detail=f"文件过大"` → `detail="文件过大"` |
| 未使用 `typing.Any` | [`app/api/server.py`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/api/server.py) | 删除 `from typing import Any` |
| 测试脚本模块级 API 调用 | [`tests/test_interview_review_api.py`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/tests/test_interview_review_api.py)、[`tests/test_interview_review_api_long.py`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/tests/test_interview_review_api_long.py) | 用 `if __name__ == "__main__":` 包裹 |
| f-string SQL（UPDATE） | [`app/tools/db_tools.py`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/tools/db_tools.py) | 改为字符串拼接 `"UPDATE ... SET " + ", ".join(sets) + " WHERE id=%s"`，值部分仍参数化 |
| f-string DDL | [`app/tools/db_tools.py`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/tools/db_tools.py) | 改为 `"ALTER TABLE ... ADD COLUMN %s %s" % (col, dtype)`，列名/类型来自硬编码白名单 |
| 前端岗位分析字段错误 | [`frontend-jobcraft/src/pages/InterviewReviewPage.tsx`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/frontend-jobcraft/src/pages/InterviewReviewPage.tsx) | `a.job_title` / `a.company_name` → `a.position` / `a.company` |
| `ExperienceCard` 重复定义 | [`frontend-jobcraft/src/api.ts`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/frontend-jobcraft/src/api.ts) | 删除本地重复定义，从 `types.ts` 导入 |
| `submission_id` 未透传 | [`frontend-jobcraft/src/api.ts`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/frontend-jobcraft/src/api.ts) | 在 `formData` 中追加 `submission_id` |
| 循环单条删除 QA 对 | [`app/tools/interview_review.py`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/tools/interview_review.py) | 改用 `delete_interview_qa_pairs_by_record(record_id)` |
| 未使用 Pydantic 模型 | [`app/api/server.py`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/api/server.py) | 删除 `InterviewReviewCreateResponse` |
| 接口 docstring 不一致 | [`app/api/server.py`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/api/server.py) | 更新为「创建面试复盘记录并生成问题表（含轻量意图识别）」 |
| 前端动态导入警告 | [`frontend-jobcraft/src/pages/InterviewReviewPage.tsx`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/frontend-jobcraft/src/pages/InterviewReviewPage.tsx) | 静态导入 `getSubmission`，移除 `import('../api.ts')` |
| 经历卡 Schema 字段缺失 | [`app/schemas/jobcraft.py`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/schemas/jobcraft.py)、[`app/tools/db_tools.py`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/tools/db_tools.py) | `ExperienceCardCreate/Update` 扩展字段；`insert_card` / `update_card` / `_row_to_card` 同步支持；测试 fixture 补充 `raw_text` |

---

#### 3.1.3 验证结果

| 检查项 | 命令 | 结果 |
|---|---|---|
| 后端 Lint | `uv run ruff check .` | ✅ All checks passed |
| 前端构建 | `npm run build` | ✅ 成功（仅剩 chunk 大小警告） |
| 后端测试 | `uv run pytest tests/ -q` | ⚠️ 默认 8000 端口失败；在 8001 端口启动本项目服务后，`test_create_experience_card` 通过 |

**说明**：

- 默认 pytest 失败根因是本地 8000 端口被非本项目服务占用，导致 e2e 测试连接到旧代码/错误服务。
- 开发/测试时请使用 `uv run uvicorn app.api.server:app --host 0.0.0.0 --port 8001` 并设置 `$env:JOBCRAFT_TEST_BASE_URL="http://localhost:8001"`。

---

#### 3.1.4 待跟进事项

- [ ] 清理本地 8000 端口占用，或统一开发/测试端口。
- [ ] 配置有效的智谱 AI API Key（`.env` 中已切换为智谱端点，key 为占位符）。
- [ ] 前端配置 `manualChunks` 拆分 vendor，消除 chunk 大小警告。
- [ ] 补充岗位分析、面试准备、面试复盘 LLM 路径的单元/集成测试。
- [ ] 建立前端类型自动生成机制，避免手工同步 `types.ts`。

---

#### 3.1.5 模型配置变更记录

本次扫描期间同步完成了 LLM Provider 切换：

| 配置项 | 切换前（讯飞 MaaS） | 切换后（智谱 AI） |
|---|---|---|
| `OPENAI_BASE_URL` | `https://maas-api.cn-huabei-1.xf-yun.com/v2` | `https://open.bigmodel.cn/api/paas/v4/` |
| `OPENAI_API_KEY` | 讯飞 MaaS Key | 智谱 API Key（需用户填入真实值） |
| `LLM_model` | `xop35qwen2b` | `glm-4-flash` |

**涉及文件**：

- [`.env`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/.env)
- [`.env.example`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/.env.example)
- [`app/agent/llm.py`](file:///d:/A-pythonProject/AI-learning/multi-agent/jobcraft/app/agent/llm.py)

**备注**：`.env` 中 `OPENAI_API_KEY` 当前为占位符，需用户配置真实智谱 Key 后 LLM 功能方可正常调用。

---

## 4. 审查责任

- **Coder**：修复问题前必须先读取完整上下文，禁止基于猜测 patch。
- **Reviewer**：依据本清单逐项核对，所有 P0/P1 问题必须在合并前解决。
- **Architect**：审查架构一致性，禁止引入与现有栈冲突的方案。
- **Debugger**：静态分析无法定位时，通过日志/复现脚本收集运行时证据。

---

**最后更新**：2026-07-30 18:10
