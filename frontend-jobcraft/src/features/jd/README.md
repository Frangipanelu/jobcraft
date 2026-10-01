# features/jd — JD 分析域

FE-JD-01 已迁移读/删路径（spec `tasks/FE-JD-01.md`）；create 已由 FE-JD-02 迁移（`tasks/FE-JD-02.md`）。

## 数据流

```
useJdAnalysesQuery → authApi.getCurrentUser → listJobAnalyses(userId)（单次返回完整详情）→ analysisDetailToJD → query cache
JDAnalysisCenterView / JDReportDetailView 读：useJdAnalysesQuery（cache 权威）
JDAnalysisCenterView 删：useDeleteJdAnalysisMutation → cache（id 形如 sub-{number} 时尝试 deleteSubmission）
create：useCreateJdAnalysisMutation / useCreateStructuredJdAnalysisMutation
        → resolveTargetJob（find-or-create 岗位）→ runTaskOrSync → analysisToJD → 写 jd + jobs 双 cache
```

- **权威**：react-query cache 是唯一读源（`context.jdAnalyses` 已由 FE-CONTEXT-REMOVE 删除，无镜像）。
- **hooks API**：
  - `useJdAnalysesQuery`：`authApi.getCurrentUser` → `listJobAnalyses` 单次返回完整详情 → `analysisDetailToJD`（无逐条 GET，N+1 已消除）。
  - `useDeleteJdAnalysisMutation`：仅本地移除；id 形如 `sub-{number}` 时尝试 `deleteSubmission`（失败忽略）。**后端无 JD 分析删除端点**，真实分析 id 不发删除请求。
  - `useCreateJdAnalysisMutation` / `useCreateStructuredJdAnalysisMutation`：find-or-create 岗位 → `tasksApi.runTaskOrSync` 异步分析（降级同步端点）→ 同步返回本地 id 供 `navigateTo`。
- **映射单源**：`analysisToJD`（分析结果 → JDAnalysis）与 `analysisDetailToJD`（详情 → JDAnalysis）均在此，杜绝双份漂移。

## 目标边界

- JD 分析中心（`JDAnalysisCenterView`）、分析报告详情（`JDReportDetailView`）、`selectedJDId` 落地页。
- 依赖 `jobs` domain（jobId 归属）与 `resume` domain（定制简历入口）。

## 红线

- 不实现后端 endpoint；解析由后端完成，前端只展示与交互。
