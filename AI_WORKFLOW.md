# AI工作流启动指令

当opencode开始新的会话时，请按以下步骤执行：

## 第一步：读取项目上下文

```
必读文件（按顺序）：
1. AGENTS.md        - AI行为规范
2. PRODUCT.md       - 产品定义
3. ARCHITECTURE.md  - 技术架构
4. PROGRESS.md      - 当前进度
```

## 第二步：建立任务

根据用户需求，在 `TODO.md` 中创建任务列表：

```markdown
# TODO - [功能名称]

## 目标
[简述用户需求]

## 任务清单
- [ ] 任务1
- [ ] 任务2
- [ ] 任务3

## 开始时间: YYYY-MM-DD HH:MM
```

## 第三步：记录过程

每完成一个任务，自动更新：

### PROGRESS.md
```markdown
## v0.X.0 (YYYY-MM-DD)

### 完成
- [x] 任务名称 - commit_id
```

### TODO.md
```markdown
- [x] 任务1 ✅ HH:MM
- [ ] 任务2
```

## 第四步：完成后提交

```bash
# 1. 更新版本号（如有必要）
# 2. 提交代码
git add .
git commit -m "feat/fix: 功能描述"

# 3. 推送
git push origin main

# 4. 更新PROGRESS.md中的commit_id
```

## 会话结束时

确保：
- [ ] 所有任务已完成或标记为进行中
- [ ] PROGRESS.md已更新
- [ ] 代码已提交并推送
- [ ] TODO.md反映当前状态
