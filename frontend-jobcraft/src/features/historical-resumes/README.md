# features/historical-resumes — 历史简历管理

底座简历（`base_resume`）历史版本域的查询层封装：`useHistoricalResumesQuery` 与
新增/删除/设为默认三个 mutation，映射逻辑收敛在 `mappers.ts`。

## 当前状态
- 已迁移（FE-HISTORICAL-RESUMES-01）。消费方：
  - `src/components/user/UserProfileView.tsx`（列表渲染 + 上传 + 删除 + 设默认）
  - `src/pages/CreateInterview.tsx`（简历上传 + 默认底座读取）
- `JobCraftContext` 已移除 `historicalResumes` 域（state / `loadHistoricalResumes` / 三个 action / provider value）。
- 测试：`src/test/historical-resumes-query.test.tsx`（列表、删除成功/失败、设默认迁移、新增落库回填 serverId 与失败兜底）。

## hooks / mappers
- `HISTORICAL_RESUMES_QUERY_KEY = ['historical-resumes']`
- `baseResumeToHistoricalResume(r)`：后端 `BaseResumeRecord` → 前端 `HistoricalResume`，单一事实来源。
- `useHistoricalResumesQuery`：`jobApi.listBaseResumes()` → map；失败返回 `[]` 兜底。
- `useAddHistoricalResumeMutation`：`jobApi.createBaseResume(...)` 成功回填 `serverId` 后前置入列；
  失败仅保留本地内存记录（继承 legacy fire-and-forget 容忍）。toast 由视图层负责。
- `useDeleteHistoricalResumeMutation` / `useSetDefaultHistoricalResumeMutation`：
  后端成功后再写 cache（对齐 experiences delete 模式）；无 serverId 条目仅做本地操作；失败保留条目。

## 设计取舍
- 不在 hook 内写 `console` / 不写 `activities`（`ActivityLog` 无消费方，随 FE-CONTEXT-REMOVE 处理）。
- legacy 上传后视图 `selectedResumeId` 使用 `hr-upload-{ts}` 而列表 id 为 `hr-{ts}` 的既有 quirk 予以保留，不在此任务修复。

## 红线
- 不新增后端 endpoint，仅复用 `base_resumes` 既有接口。