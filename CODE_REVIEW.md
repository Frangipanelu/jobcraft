# CODE_REVIEW.md — 代码审查标准

> 本文件为版本控制中的权威代码规范，适用于所有贡献者（含 AI Agent）。
> 内容从 `AGENTS.md` 中提取并补充，确保团队可共享。

## 绝对红线（Zero-Tolerance）

以下行为一经发现必须立即回滚或拒绝合并：

1. **禁止硬编码密钥**：所有 API Key、数据库密码、Token 必须通过 `.env` 或环境变量注入。
2. **禁止裸 `except:`**：必须使用 `except SpecificException:` 并记录原因。
3. **禁止未经授权引入第三方库**：新增依赖需先写入 `pyproject.toml` 或 `frontend-jobcraft/package.json`，并说明必要性。
4. **禁止在业务代码中直接调用 `print`**：统一使用日志模块或结构化日志。
5. **禁止提交 `.env` 文件**：`.env` 必须在 `.gitignore` 中。
6. **禁止破坏现有 API 契约**：修改 Pydantic Schema 或接口返回结构时，必须同步更新调用方与测试。
7. **禁止未经验证直接删除文件**：删除前必须确认文件作用，且相关引用已清理。

## 文件编码规范（FE-ROUTE-03 后新增）

### 规则

源文件**必须**为 UTF-8（无 BOM）编码。禁止用 PowerShell 文本 cmdlet（`Set-Content` / `Out-File` / `>` / `>>` / `Add-Content`）写入含中文的文件，因为 Windows PowerShell 5.1 默认按 ANSI（GBK）编码写入，会导致 mojibake 且仍能通过编译，极难发现。

### 正确做法

| 操作 | 正确 | 错误 |
|------|------|------|
| 读写源文件 | 使用 Read / Write / Edit 工具（VS Code、opencode 等） | `Set-Content` / `Out-File` |
| 脚本处理 | Python（UTF-8 默认） | PowerShell 文本 cmdlet |
| 检测问题 | `python scripts/check_encoding.py` | 无（依赖肉眼） |

### 检测脚本

```bash
python scripts/check_encoding.py
```

检查项：
- **非 UTF-8 编码**（`UnicodeDecodeError`）：源文件被 ANSI/GBK 重写
- **替换字符 U+FFFD**：编码损坏残留
- **mojibake 片段**：`锟斤拷`、`ï¿½`、`â€`、`Ã©` 等双重编码特征

CI 已配置强制执行（`.github/workflows/ci.yml`）。

## Python 规范

- **强制类型提示**：函数参数与返回值必须标注类型；复杂结构使用 `Pydantic` 或 `TypedDict`。
- **强制 Docstring**：所有公共函数、类必须包含 Google 风格 Docstring。
- **导入顺序**：标准库 → 第三方 → 项目内部，每组之间空一行。
- **异常处理**：捕获具体异常，必要时向上抛出并保留原始堆栈。
- **异步规范**：I/O 操作使用 `async/await`，禁止在异步函数中调用阻塞 API。

## TypeScript / React 规范

- **强制类型**：禁止 `any` 隐式传播，组件 props 必须显式定义 interface。
- **纯原生 Ant Design**：UI 优先使用 Ant Design 原生组件，禁止为了样式引入自定义 CSS/JS，除非明确授权。
- **组件拆分**：单文件代码超过 300 行必须考虑拆分。

## 文件与命名

- Python 模块：`snake_case.py`
- React 组件：`PascalCase.tsx`
- 常量/配置：`UPPER_SNAKE_CASE`
- 测试文件：`test_*.py` 或 `*.test.tsx`
- Workflow 文件：`*_flow.py`
- Agent 节点文件：`*_agent.py`

## 提交前验证命令

```bash
# 文件编码扫描
python scripts/check_encoding.py

# 后端代码质量
uv run ruff check --fix .
uv run ruff format .

# 后端测试
uv run pytest tests/ -q

# 前端代码质量
cd frontend-jobcraft
npm run build
```

若上述命令失败，禁止提交。CI 已配置强制执行（`.github/workflows/ci.yml`）。

## 问题记录

| 日期 | 问题 | 根因 | 修复 |
|------|------|------|------|
| 2026-09-17 | `WorkbenchView.tsx` CJK 损坏 | PowerShell `Set-Content` 默认 ANSI 编码 | `git checkout` 还原 + 全程改用 Edit 工具 |
| 2026-09-17 | `tasks/FE-ROUTE-03.md` 自我追加乱码 | `Get-Content | Add-Content` 管道编码问题 | 还原 + Edit 工具追加 |

修复后建立了检测防线：`scripts/check_encoding.py` + CI 强制。
