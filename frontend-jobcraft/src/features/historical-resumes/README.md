# features/historical-resumes — 历史简历管理

规划归属（用户中心迁移，暂对应 FE-CONTEXT-* 的一部分，尚未迁移）。

## 当前状态
- 无业务代码。历史简历上传/管理在 `src/components/user/UserProfileView.tsx` 内，状态与动作仍在 `JobCraftContext`。

## 目标边界
- 底座简历上传（PDF/Word 解析预览）、历史版本列表、默认底座切换、删除。
- 与 `resume` domain 关系密切，建议随 FE-CONTEXT-REMOVE 一并权衡归属。

## 红线
- 不实现后端 endpoint；文件上传沿用后端已有多媒体/解析接口。