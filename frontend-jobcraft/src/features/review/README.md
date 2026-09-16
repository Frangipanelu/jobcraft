# features/review — 面试复盘

规划归属（FE-REVIEW-01，尚未迁移）。

## 当前状态
- 无业务代码。复盘视图仍在 `src/components/review/`，状态与动作仍在 `JobCraftContext`。

## 目标边界
- 复盘中心、复盘详情（`/review/:reviewId`）、复盘生成、反馈落地到经历。
- 依赖 `interview` domain（复盘对象）与 `experiences` domain（反馈同步）。

## 红线
- 不实现后端 endpoint；复盘由后端任务接口生成。