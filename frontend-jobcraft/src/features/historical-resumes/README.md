# features/historical-resumes — 历史简历管理

底座简历（`base_resume`）历史版本域的查询层封装：`useHistoricalResumesQuery`、
新增/删除/设为默认三个 mutation 与完整上传链 `useUploadResumeMutation`，
映射逻辑收敛在 `mappers.ts`。

## 当前状态
- 已迁移（FE-HISTORICAL-RESUMES-01）。消费方：
  - `src/components/user/UserProfileView.tsx`（列表渲染 + 上传 + 删除 + 设默认）
  - `src/pages/CreateInterview.tsx`（简历上传 + 默认底座读取）
  - `src/components/interview/ResumeStep.tsx`（向导内上传，走 `useUploadResumeMutation`）
- `JobCraftContext` 已移除 `historicalResumes` 域（state / `loadHistoricalResumes` / 三个 action / provider value）。
- 测试：`src/test/historical-resumes-query.test.tsx`（列表、删除成功/失败、设默认迁移、
  新增落库回填与失败上抛、`useUploadResumeMutation` 成功链与两段断网失败）；
  `src/test/resume-step.test.tsx`（向导上传：浏览文件接线、非法文件、断网两段）。

## hooks / mappers
- `HISTORICAL_RESUMES_QUERY_KEY = ['historical-resumes']`
- `baseResumeToHistoricalResume(r)`：后端 `BaseResumeRecord` → 前端 `HistoricalResume`，单一事实来源。
- `useHistoricalResumesQuery`：`jobApi.listBaseResumes()` → map；失败返回 `[]` 兜底。
- `useAddHistoricalResumeMutation`（FE-UPLOAD-01 硬化）：`jobApi.createBaseResume(...)`
  成功后以 `hr-<serverId>` 入列（与 `baseResumeToHistoricalResume` 回源一致，选中态不悬空）；
  **失败上抛**，由视图层报错——不再静默容忍假成功。
- `useUploadResumeMutation`（FE-UPLOAD-01）：`previewResume`（真实解析）→
  `confirmUpload`（真实入库）→ `createBaseResume`（元数据），任一步失败上抛。
- `resumeFileError(file)`：与后端 `/experience/upload/preview` 同契约的格式/体积校验
  （PDF / DOCX / MD / TXT，≤10MB）。
- `useDeleteHistoricalResumeMutation` / `useSetDefaultHistoricalResumeMutation`：
  后端成功后再写 cache（对齐 experiences delete 模式）；无 serverId 条目仅做本地操作；失败保留条目。

## 设计取舍
- 不在 hook 写 `console` / 不写 `activities`（`ActivityLog` 无消费方，随 FE-CONTEXT-REMOVE 处理）。
- legacy 上传后 `selectedResumeId` 用 `hr-upload-{ts}` 而列表 id 为 `hr-{serverId}` 的
  quirk 已随 FE-UPLOAD-01 修复（上传成功后统一用回源 id）。

## 红线
- 不新增后端 endpoint，仅复用 `base_resumes` / `experience/upload` 既有接口。
