-- P4-2：RawJD 不可变快照表（Job 对象模型 rawJDId 的落地）
--
-- 背景：岗位对象的 RawJD 应为不可变快照（Job.rawJDId 指向），但现状
--   1. 无 raw_jd 表，原始 JD 只散落在 job_analysis.jd_text / resume_submission.jd_text；
--   2. PATCH /api/jobcraft/submission 允许覆写 resume_submission.jd_text，
--      原始 JD 一旦被改写即无法回溯（分析结果失去可复核依据）。
--   本迁移新建 raw_jd 快照表；jd_text 防覆写由 db_submission.update_submission /
--   api/submission 两层移除 jd_text 更新路径实现（代码侧，不在本迁移内）。
--
-- 前向兼容约束（AGENTS §4.4）：只新建表，不改/删既有表列。
--
-- 幂等性（DB-02）：CREATE TABLE IF NOT EXISTS，重复执行安全。
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）。

CREATE TABLE IF NOT EXISTS raw_jd (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    user_id          INT DEFAULT 1,
    job_analysis_id  INT,
    source           VARCHAR(32) DEFAULT 'job_analysis',
    jd_text          LONGTEXT NOT NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_raw_jd_job (job_analysis_id),
    KEY idx_raw_jd_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--
