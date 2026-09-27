-- P4-4a：Job 实体表（岗位对象落地）+ job_analysis.job_id 归属
--
-- 背景：岗位对象模型要求存在独立 Job 实体（company/role/rawJDId/jdAnalysisId/
--   submissionId 等），但现状由 `job_analysis` + `resume_submission` 二分替代，
--   没有「岗位」这一聚合根：
--   1. 同一岗位重复分析会产生多条 job_analysis，彼此无归属关系；
--   2. 前端创建岗位时只拿到 submission_id，无 job 概念可缓存；
--   3. P4-2 的 RawJD 快照无法挂到岗位上（当前仅挂 job_analysis_id）。
--
-- 本迁移：
--   1. 新建 job 表（岗位聚合根，find-or-create 键：user_id + company + position）；
--      不加唯一键约束——键策略（submission_id vs company+position）
--      仍属批次 B 待定项，此处只加普通索引，避免提前锁死。
--   2. job_analysis 增加 job_id 列（只加不改，AGENTS §4.4 前向兼容），
--      使分析记录反向可归到岗位。
--
-- 幂等性（DB-02）：CREATE TABLE IF NOT EXISTS + information_schema 探测 +
-- PREPARE/EXECUTE 动态执行，重复执行安全。
--
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）。

-- 1. job 表（岗位聚合根）
CREATE TABLE IF NOT EXISTS job (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    user_id          INT DEFAULT 1,
    company          VARCHAR(200) DEFAULT '',
    position         VARCHAR(200) NOT NULL,
    raw_jd_id        INT,
    job_analysis_id  INT,
    submission_id    INT,
    status           VARCHAR(32) DEFAULT 'PREPARED',
    is_active        TINYINT(1) DEFAULT 1,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_job_owner (user_id),
    KEY idx_job_lookup (user_id, company, position),
    KEY idx_job_submission (submission_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--

-- 2. job_analysis.job_id（分析记录归属岗位）
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'job_analysis'
              AND COLUMN_NAME = 'job_id')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE job_analysis ADD COLUMN job_id INT, ADD KEY idx_job_analysis_job (job_id)',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_113 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_113
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_113
;--SPLIT--
