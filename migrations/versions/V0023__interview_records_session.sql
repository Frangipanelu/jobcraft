-- T-M7-4 面试场次骨架（M7-Q3-A）：interview_records 补场次列
--
-- 背景：矩阵 M7-Q3-A——新建面试即预建 interview_records 行（status=planned），
--   复盘时填充内容；场次维度字段此前无处安放：
--   round_seq      第几轮（1/2/3…，来自向导 roundNumber）
--   occurred_at    场次时间（向导 日期+时间）
--   interviewer    面试官
--   format         形式（onsite/video/phone…，向导 format）
--   resume_version_id  该场次使用的简历版本（M5-Q2 载体，FE 暂不透传，先备列）
-- 前向兼容约束（AGENTS §4.4）：只加列，不改/删列；全部可空，存量行 NULL，
--   旧代码不读这些列，未迁移环境不受影响。
-- 幂等性（DB-02）：MySQL 8 无 ADD COLUMN IF NOT EXISTS，采用
--   information_schema 探测 + PREPARE/EXECUTE 动态执行，重复执行安全；
--   运行时 db_interview._ensure_interview_records_table 带同款守卫补列，
--   两路径可共存（守卫探测相同，先到先得）。
--
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）。

SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'interview_records'
              AND COLUMN_NAME = 'round_seq')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE interview_records ADD COLUMN round_seq INT NULL',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_231 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_231
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_231
;--SPLIT--
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'interview_records'
              AND COLUMN_NAME = 'occurred_at')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE interview_records ADD COLUMN occurred_at DATETIME NULL',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_232 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_232
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_232
;--SPLIT--
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'interview_records'
              AND COLUMN_NAME = 'interviewer')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE interview_records ADD COLUMN interviewer VARCHAR(100) NULL',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_233 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_233
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_233
;--SPLIT--
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'interview_records'
              AND COLUMN_NAME = 'format')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE interview_records ADD COLUMN format VARCHAR(20) NULL',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_234 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_234
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_234
;--SPLIT--
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'interview_records'
              AND COLUMN_NAME = 'resume_version_id')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE interview_records ADD COLUMN resume_version_id INT NULL',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_235 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_235
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_235
;--SPLIT--
