# features/experiences — 经历资产库

FE-EXPERIENCES-01 已迁移（commit `1b49e8c` 前序路由；本域 commit 见 PROGRESS.md）。

## 数据流（过度期）

```
login → loadExperiences（legacy）→ listCards(userId) → cardToExperience → context.experiences
                                                                              └→ query cache（双写）
ExperiencesView / NewExperienceModal 读：useExperiencesQuery（cache 权威）
ExperiencesView / NewExperienceModal 写：useCreate/Update/DeleteExperienceMutation → cache → onSync → context 镜像
context 内部写入方（review 落盘 syncReviewToExperience / commitExperienceDiff）→ setExperiences → 双写 cache
```

- **权威与镜像**：react-query cache 是 views 的读源；`context.experiences` 为只读镜像（ResumeEditorView /
  JDReportDetailView / UserProfileView 仍读 context），由两侧写入方双向同步。
- **hooks API**：`useExperiencesQuery`、`useCreateExperienceMutation`、`useUpdateExperienceMutation`、
  `useDeleteExperienceMutation`、`useAddExperienceVersionMutation`（onSync 由消费方注入 `syncExperiences`）。
- **版本演进为纯本地**：后端无经历版本端点，`useAddExperienceVersionMutation` 仅更新 cache 内
  `currentVersion` / `versionHistory`，不发网络请求。
- 移除触发器：FE-CONTEXT-REMOVE 删除 `context.experiences` / legacy 动作 / `syncExperiences`。

## 目标边界

- 经历卡片列表、经历创建/编辑/删除、版本历史、`/experiences/:experienceId` 落地页。
- 与 `resume` / `jd-analysis` 存在数据耦合，迁移时按依赖方向排序。

## 红线

- 不实现后端 endpoint；不复制 `JobCraftContext` 内部实现。