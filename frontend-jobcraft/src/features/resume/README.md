# features/resume — 简历与定制

规划归属（FE-RESUME-01，尚未迁移）。

## 当前状态
- 无业务代码。简历编辑/建议视图仍在 `src/components/resume/`，状态与动作仍在 `JobCraftContext`。

## 目标边界
- AI 简历生成、简历建议（apply/reject）、简历结构化编辑、版本管理。
- 依赖 `jd-analysis`（针对岗位定制）与 `experiences`（经历素材）。

## 红线
- 不实现后端 endpoint；AI 简历生成由后端任务接口（提交任务→轮询）完成。