# features/experiences — 经历资产库

规划归属（FE-EXPERIENCES-01，尚未迁移）。

## 当前状态
- 无业务代码。经历相关视图仍在 `src/components/experiences/`，状态与动作仍在 `JobCraftContext`。

## 目标边界
- 经历卡片列表、经历创建/编辑/删除、版本历史、`/experiences/:experienceId` 落地页。
- 与 `resume` / `jd-analysis` 存在数据耦合，迁移时按依赖方向排序。

## 红线
- 不实现后端 endpoint；不复制 `JobCraftContext` 内部实现。