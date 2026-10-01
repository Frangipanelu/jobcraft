-- BE-INDEX-01：未索引逻辑外键补索引 + job_analysis.updated_at
--
-- 背景：
--   1. 4 个逻辑外键列无索引，反查/关联时全表扫描：
--      job.raw_jd_id、job.job_analysis_id（V0013 建表时仅 3 个业务索引）、
--      interview_records.job_analysis_id（V0001 仅 user/ submission 索引）、
--      interview_qa_pairs.related_card_id（V0001 仅 record/sequence 索引）。
--   2. job_analysis 独有 created_at 无 updated_at，列表只能按创建时间排序。
--
-- 前向兼容约束（AGENTS §4.4）：只加索引 / 只加列，不改/删既有列；
--   旧代码不读 updated_at，未迁移环境不受影响。
--
-- 幂等性（DB-02）：MySQL 8 无 ADD KEY IF NOT EXISTS，采用
--   information_schema.STATISTICS / COLUMNS 探测 + PREPARE/EXECUTE 动态执行，
--   重复执行安全；三处创建路径（本迁移 / docker 基线 / 运行时 _ensure CREATE）
--   同款 DDL 收敛，先到先得（见 test_migrations_runner_unit V0014 用例）。
--
-- 迁移编号：V0014 为预留位（TODO 注记），补占后 runner 按文件名排序应用。
--
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）。

-- 1. job.raw_jd_id（岗位挂 RawJD 快照，V0012 逻辑外键）
SET @cnt = (SELECT COUNT(*) FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'job'
              AND INDEX_NAME = 'idx_job_raw_jd')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE job ADD KEY idx_job_raw_jd (raw_jd_id)',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_141 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_141
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_141
;--SPLIT--

-- 2. job.job_analysis_id（岗位挂分析记录）
SET @cnt = (SELECT COUNT(*) FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'job'
              AND INDEX_NAME = 'idx_job_analysis')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE job ADD KEY idx_job_analysis (job_analysis_id)',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_142 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_142
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_142
;--SPLIT--

-- 3. interview_records.job_analysis_id（复盘记录挂岗位分析）
SET @cnt = (SELECT COUNT(*) FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'interview_records'
              AND INDEX_NAME = 'idx_job_analysis')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE interview_records ADD KEY idx_job_analysis (job_analysis_id)',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_143 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_143
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_143
;--SPLIT--

-- 4. interview_qa_pairs.related_card_id（问题回链经历卡）
SET @cnt = (SELECT COUNT(*) FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'interview_qa_pairs'
              AND INDEX_NAME = 'idx_related_card')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE interview_qa_pairs ADD KEY idx_related_card (related_card_id)',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_144 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_144
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_144
;--SPLIT--

-- 5. job_analysis.updated_at（自动维护：写入即刷新）
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'job_analysis'
              AND COLUMN_NAME = 'updated_at')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE job_analysis ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_145 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_145
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_145
;--SPLIT--
