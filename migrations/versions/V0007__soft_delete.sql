-- B-4：删除改软删（is_active）——为 resume_submission / job_analysis 增加活跃标记
--
-- 背景：design-v2.0（DMV2 §54/§55、JOBCRAFT_SYSTEM_SPEC 删除应优先归档而非物理删除、
-- JOBCRAFT_DATA_MODEL 保留历史引用）主张删除数据时保留历史，防止投递/复盘断链。
-- experience_card 已有 is_active（V0001），本迁移补齐 resume_submission / job_analysis。
-- 查询侧一律过滤 is_active=1，删除接口改为 UPDATE is_active=0（软删）。
--
-- 前向兼容约束（AGENTS §4.4）：只加列，不改/删列；旧代码不读 is_active，
-- 未运行迁移的旧版本删除/查询行为不受影响（DEFAULT 1 对所有存量行有效）。
ALTER TABLE resume_submission ADD COLUMN is_active TINYINT(1) DEFAULT 1;--SPLIT--
ALTER TABLE job_analysis ADD COLUMN is_active TINYINT(1) DEFAULT 1;--SPLIT--