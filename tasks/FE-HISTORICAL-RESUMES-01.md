# FE-HISTORICAL-RESUMES-01 · 历史简历域迁移（底座简历）

> 状态：进行中。继承 FE- 系列模式：cache 权威 + 视图读 hooks + 写走 mutations + context 清理。

## 目标
将历史简历域（底座简历 `base_resume`）从 `JobCraftContext` 迁至查询层。消费者仅两处：`UserProfileView`（列表/增删/默认切换）与 `CreateInterview`（读默认简历 + 上传后追加）。迁移完成后从 context 移除 `historicalResumes` 域全部 key。

## 现状
- context 持有：`loadHistoricalResumes`（启动时水合）+ `addHistoricalResume` / `deleteHistoricalResume` / `setDefaultHistoricalResume` 三个 action（各自带 toast、console.error、activities 推送）。
- 后端 API：`listBaseResumes` / `createBaseResume` / `setDefaultBaseResume` / `deleteBaseResume`（`src/api/job.ts`）。

## 设计决策

- **HRC-1 mappers**：`features/historical-resumes/mappers.ts` → `HISTORICAL_RESUMES_QUERY_KEY = ['historical-resumes']`；`baseResumeToHistoricalResume(r)` 从 context 内联映射提取（id `hr-{serverId}`、serverId、name/fileSize/uploadDate/isDefault/parsedExperiencesCount/format/tags 兜底规则单源化）。
- **HRC-2 hooks**：`features/historical-resumes/hooks.ts`
  - `useHistoricalResumesQuery`：listBaseResumes → map。
  - `useAddHistoricalResumeMutation`：`createBaseResume` 落库成功回填 `serverId` → onSuccess 前置插入 cache；落库失败仅保留内存记录（继承 legacy fire-and-forget 容忍，**不打 console**）。不写 activities（零消费者，同 review 结论）；toast 归视图层。
  - `useDeleteHistoricalResumeMutation`：`await deleteBaseResume(serverId)` 成功后再从 cache 过滤（对齐 experiences delete 模式：失败保留条目 + 视图 error toast，优于 legacy 无条件删除+console）。
  - `useSetDefaultHistoricalResumeMutation`：`await setDefaultBaseResume(serverId)` 成功后 cache 置唯一 `isDefault`。
- **HRC-3 UserProfileView 迁移**：读 `useHistoricalResumesQuery`；三条写路径走 mutation，视图层补 toast（沿用原文案：`历史简历已删除` / `默认底座简历已设置`；上传确认保留 `简历导入成功` + `loadExperiences`）。
- **HRC-4 CreateInterview 迁移**：读 `useHistoricalResumesQuery`（初始默认简历选择逻辑不变）；两处 `addHistoricalResume` → mutation.mutate；上传为模拟解析（legacy 行为，不调 preview，保持）。
- **HRC-5 context 清理**：删 `HistoricalResume` 导入、`historicalResumes` state、`loadHistoricalResumes`（含启动水合）、三个 action、interface 成员与 provider value。`activities`/`nextActions` 零消费者保留待 FE-CONTEXT-REMOVE。
- **HRC-6 测试**：`src/test/historical-resumes-query.test.tsx`（列表渲染+计数/删除后端成功+缓存过滤/删除后端失败保留/设为默认/新增落库回填 serverId 入列/CreateInterview 下拉读默认）。
- **HRC-7 commits**：feat(historical-resumes) + refactor(context)；docs 记录。

## 验收
- [ ] `npx vitest run src/test/historical-resumes-query.test.tsx` 全绿
- [ ] `npm run lint` / `npm run build` / `npx vitest run` 全量绿 / `python scripts/check_encoding.py`
- [ ] grep 验证 context 无 historicalResumes 残留
- [ ] 提 2 commits 并 push；更新 PROGRESS.md / TODO.md / 两个 README

## 留白
- `activities` / `nextActions` 零消费者，随 FE-CONTEXT-REMOVE 一并清理。
- UserProfileView 简历卡「下载」按钮仅 toast、无真实下载（legacy 行为保留）。
- CreateInterview 上传为本地模拟（不经 previewResume/confirmUpload，legacy 行为保留）。