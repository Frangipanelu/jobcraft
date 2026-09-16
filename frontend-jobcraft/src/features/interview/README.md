# features/interview — 面试准备与模拟

规划归属（FE-INTERVIEW-01，尚未迁移）。

## 当前状态
- 无业务代码。面试视图仍在 `src/components/interview/`，状态与动作仍在 `JobCraftContext`。

## 目标边界
- 面试准备中心、面试准备空间（`/prep/:interviewId`）、模拟面试、面试创建。
- 由内部路由 `/prep/:interviewId` 承载可分享落地页。

## 红线
- 不实现后端 endpoint；面试准备内容由后端任务接口生成。