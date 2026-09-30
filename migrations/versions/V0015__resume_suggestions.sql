-- FE-RESUME-02：resume_submission 增加 resume_suggestions JSON 列（简历 AI 优化建议存储）
--
-- 背景：简历编辑器「AI 针对性优化」需要跨刷新保留生成结果与 applied/rejected 状态，
--   resume_markdown 只承载正文，无法承载结构化建议列表。
-- 前向兼容约束（AGENTS §4.4）：只加列，不改/删列；旧代码不读该列，未迁移的旧版本不受影响。
-- 迁移编号：V0014 预留给 BE-INDEX-01 / T-M7-4 等共享批次，本迁移取 V0015
--   （runner 按文件名排序应用，不强制版本号连续）。
ALTER TABLE resume_submission ADD COLUMN resume_suggestions JSON;
