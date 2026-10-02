# features/experiences — 经历资产库

FE-EXPERIENCES-01 已迁移（commit `1b49e8c` 前序路由；本域 commit 见 PROGRESS.md）。

## 数据流（过度期）

```
login → loadExperiences（legacy）→ listCards(userId) → cardToExperience → context.experiences
                                                                              └→ query cache（双写）
ExperiencesView / NewExperienceModal 读：useExperiencesQuery（cache 权威）
ExperiencesView / NewExperienceModal 写：useCreate/Update/DeleteExperienceMutation → cache → onSync → context 镜像
context 内部写入方（review 落盘已迁 FE-REVIEW-01：useApplyReviewFeedbackMutation → cache → onSyncExperiences → context 镜像）
```

- **权威与镜像**：react-query cache 是 views 的读源；`context.experiences` 为只读镜像（ResumeEditorView /
  JDReportDetailView / UserProfileView 仍读 context），由两侧写入方双向同步。
- **hooks API**：`useExperiencesQuery`、`useCreateExperienceMutation`、`useUpdateExperienceMutation`、
  `useDeleteExperienceMutation`、`useAddExperienceVersionMutation`（onSync 由消费方注入 `syncExperiences`）、
  `useStructureExperienceMutation`（T-M1-1 重试）、`useCardVersionsQuery`（T-M1-2 懒加载）。
- **列表摘要内嵌、版本明细懒加载（T-M1-2 / 矩阵 Q3）**：首屏只打 `listCards(userId)`，
  `current_version` / `version_count` / `expression_summary` 由 `GET /cards` 内嵌（原逐卡
  `listCardVersions` 的 N+1 已移除）；`card_versions` 明细由 `useCardVersionsQuery` 在「版本演进」
  面板挂载时才请求，失败回落 cache 内写路径回流的历史。
- **写路径仍走后端版本化**：`useUpdate/AddExperienceVersionMutation` → `updateCard` 落库（服务端
  `version+1` + `card_versions` 快照）→ `loadVersionMeta` 回流明细，成功后同时失效列表与明细缓存。
- 移除触发器：FE-CONTEXT-REMOVE 删除 `context.experiences` / legacy 动作 / `syncExperiences`。

## 目标边界

- 经历卡片列表、经历创建/编辑/删除、版本历史、`/experiences/:experienceId` 落地页。
- 与 `resume` / `jd-analysis` 存在数据耦合，迁移时按依赖方向排序。

## 红线

- 不实现后端 endpoint；不复制 `JobCraftContext` 内部实现。