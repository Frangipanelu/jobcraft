-- B-4：删除改软删（is_active）——为 resume_submission / job_analysis 增加活跃标记
--
-- 背景：design-v2.0（DMV2 §54/§55、JOBCRAFT_SYSTEM_SPEC 删除应优先归档而非物理删除、
-- JOBCRAFT_DATA_MODEL 保留历史引用）主张删除数据时保留历史，防止投递/复盘断链。
-- experience_card 已有 is_active（V0001），本迁移补齐 resume_submission / job_analysis。
-- 查询侧一律过滤 is_active=1，删除接口改为 UPDATE is_active=0（软删）。
--
-- 前向兼容约束（AGENTS §4.4）：只加列，不改/删列；旧代码不读 is_active，
-- 未运行迁移的旧版本删除/查询行为不受影响（DEFAULT 1 对所有存量行有效）。
--
-- 幂等性（DB-02 / DB-VERIFY-02）：MySQL 8 无 ADD COLUMN IF NOT EXISTS，采用
--   information_schema.COLUMNS 探测 + PREPARE/EXECUTE 动态执行（同 V0014/V0017 惯例）；
--   存量库（列已由运行时 DDL 建成、schema_migrations 无记录）全量重放安全。
--
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）。

SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'resume_submission'
              AND COLUMN_NAME = 'is_active')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE resume_submission ADD COLUMN is_active TINYINT(1) DEFAULT 1',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_71 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_71
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_71
;--SPLIT--
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'job_analysis'
              AND COLUMN_NAME = 'is_active')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE job_analysis ADD COLUMN is_active TINYINT(1) DEFAULT 1',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_72 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_72
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_72
;--SPLIT--
