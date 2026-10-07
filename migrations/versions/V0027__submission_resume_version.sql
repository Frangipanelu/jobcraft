-- T-M6-7：resume_submission 增加 resume_version_id 归档列（投递时快照所选简历版本）
--
-- 背景：投递归档咬合——用户「标记已投递」时需把选中的简历版本快照 ID
--   一并写入 submission，保证投递记录可回溯当时投出的简历版本。
-- 前向兼容约束（AGENTS §4.4）：本迁移只加列/索引，不改/删既有列；
--   未迁移旧代码不读该列，不受影响。
-- 幂等性（DB-02 / DB-VERIFY-02）：MySQL 8 无 ADD COLUMN IF NOT EXISTS，采用
--   information_schema.COLUMNS / STATISTICS 探测 + PREPARE/EXECUTE 动态执行
--   （同 V0015/V0022 惯例），重复执行安全；
--   运行时 db_submission._ensure_resume_submission_table 带同款守卫补列，
--   两路径可共存（守卫探测相同，先到先得）。
--
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）。
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'resume_submission'
              AND COLUMN_NAME = 'resume_version_id')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE resume_submission ADD COLUMN resume_version_id INT NULL, ADD KEY idx_resume_version (resume_version_id)',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_271 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_271
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_271
;--SPLIT--
SET @cnt2 = (SELECT COUNT(*) FROM information_schema.STATISTICS
             WHERE TABLE_SCHEMA = DATABASE()
               AND TABLE_NAME = 'resume_submission'
               AND INDEX_NAME = 'idx_resume_version')
;--SPLIT--
SET @ddl2 = IF(@cnt2 = 0,
               'ALTER TABLE resume_submission ADD KEY idx_resume_version (resume_version_id)',
               'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_272 FROM @ddl2
;--SPLIT--
EXECUTE _mig_stmt_272
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_272
;--SPLIT--
