# AI工作流配置

## 启动时自动执行

当opencode开始新会话时，请按以下步骤执行：

### 1. 读取项目上下文
```bash
# 必读文件
cat AGENTS.md
cat PRODUCT.md
cat ARCHITECTURE.md
cat PROGRESS.md
```

### 2. 检查当前任务
```bash
# 检查是否有未完成任务
cat TODO.md
```

### 3. 根据用户需求建立任务

在 `TODO.md` 中创建任务列表：

```markdown
# TODO - [功能名称]

## 目标
[用户需求]

## 任务清单
- [ ] 任务1
- [ ] 任务2

## 状态
开始时间: YYYY-MM-DD HH:MM
```

### 4. 执行任务并记录

每完成一个任务：
- 更新 `TODO.md` 标记为完成
- 更新 `PROGRESS.md` 添加记录
- 提交代码并记录commit_id

### 5. 完成后提交

```bash
git add .
git commit -m "feat: 功能描述"
git push origin main
```

## 文档更新规则

| 时机 | 更新文件 |
|------|----------|
| 开始任务 | TODO.md |
| 完成任务 | TODO.md + PROGRESS.md |
| 提交代码 | PROGRESS.md (记录commit_id) |
| 发布版本 | PROGRESS.md (版本号) |

## Commit Message规范

```
feat: 新功能
fix: 修复bug
refactor: 重构
docs: 文档更新
chore: 杂项
```
