# features/jobs — 岗位推进

规划归属（FE-JOBS-01，尚未迁移）。

## 当前状态
- 无业务代码。岗位相关视图仍在 `src/components/jobs/`，状态与动作仍在 `JobCraftContext`。

## 目标边界
- 岗位列表、岗位空间（JD 分析 / 定制简历 / 模拟面试入口）、岗位元数据 CRUD。
- 挂载阶段规划：
  1. 迁移后 AppRouter 的 `/jobs/:jobId` 直接渲染本 domain 页面（移除 LegacyPageWrapper 桥接）。
  2. 数据获取迁移至 `#queries` 域 hooks。

## 红线
- 不实现后端 endpoint；不复制 `JobCraftContext` 内部实现。