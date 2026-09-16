# features/jd-analysis — JD 解析与报告

规划归属（FE-JD-01，尚未迁移）。

## 当前状态
- 无业务代码。JD 分析视图仍在 `src/components/jd/`，状态与动作仍在 `JobCraftContext`。

## 目标边界
- JD 上报 / 解析、分析中心、分析报告详情（`/jobs/:jobId/jd/:jdId`）、AI 生成检索记录。
- 依赖 `jobs` domain（jobId 归属）与 `resume` domain（定制简历入口）。

## 红线
- 不实现后端 endpoint；解析由后端完成，前端只展示与交互。