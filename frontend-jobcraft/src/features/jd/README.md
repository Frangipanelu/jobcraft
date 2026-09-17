# features/jd — JD 分析域

FE-JD-01 已迁移读/删路径（spec `tasks/FE-JD-01.md`）。

## 数据流（过渡期）

```
login → loadJdAnalyses（legacy）→ listJobAnalyses(userId) → N× getJobAnalysis → analysisDetailToJD
                                                                                 ├→ context.jdAnalyses
                                                                                 └→ query cache（双写）
JDAnalysisCenterView / JDReportDetailView 读：useJdAnalysesQuery（cache 权威）
JDAnalysisCenterView 删：useDeleteJdAnalysisMutation → cache → onSync → context 镜像
createJDAnalysis / createStructuredJDAnalysis（legacy，仍走 context）→ analysisToJD → setJdAnalyses → 双写 cache
```

- **权威与镜像**：react-query cache 是迁移后视图的读源；`context.jdAnalyses` 为只读镜像
  （`JobWorkspaceView` / `NewInterviewModal` / `MainLayout` 仍读 context），由 hooks 的 `onSync` 与 legacy writers 双向同步。
- **hooks API**：
  - `useJdAnalysesQuery`：`authApi.getCurrentUser` → `listJobAnalyses` → 逐条 `getJobAnalysis` → `analysisDetailToJD`（与 legacy load 一致，保持 N+1；单条失败跳过）。
  - `useDeleteJdAnalysisMutation`：仅本地移除；id 形如 `sub-{number}` 时尝试 `deleteSubmission`（失败忽略）。**后端无 JD 分析删除端点**，真实分析 id 不发删除请求。
  - `onSync` 由消费方注入 `useJobCraft().syncJdAnalyses`。
- **创建仍为 legacy（非目标）**：`createJDAnalysis` / `createStructuredJDAnalysis` 跨域自动创建 Job、经
  `tasksApi.runTaskOrSync` 异步分析、并同步返回本地 id 供 `navigateTo`；迁移需拆分 jobs 域与任务编排，留待后续 task。
- **映射单源**：`analysisToJD`（分析结果 → JDAnalysis）与 `analysisDetailToJD`（详情 → JDAnalysis）均在此，
  context 改 import，杜绝双份漂移。
- 移除触发器：FE-CONTEXT-REMOVE 删除 `context.jdAnalyses` / legacy 动作 / `syncJdAnalyses`。

## 目标边界

- JD 分析中心（`JDAnalysisCenterView`）、分析报告详情（`JDReportDetailView`）、`selectedJDId` 落地页。
- 依赖 `jobs` domain（jobId 归属）与 `resume` domain（定制简历入口）。

## 红线

- 不实现后端 endpoint；解析由后端完成，前端只展示与交互。
