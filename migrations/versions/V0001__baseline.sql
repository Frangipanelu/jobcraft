-- JobCraft 数据库 baseline（当前完整 schema 固化）
-- TASK-DB-MIG-001：把原本散落在 app/tools/db_*.py 的运行时 _ensure_* DDL
-- 固化为迁移基线。此后新 schema 变更一律走 migrations/versions 新增版本，
-- 不再新增运行时 DDL。
--
-- 表清单（10 张）：
--   users / experience_card / experience_job_mapping / job_analysis /
--   company_research / resume_submission / interview_preps /
--   interview_records / interview_qa_pairs / card_versions
--
-- 语句分隔：多条语句间用 `;--SPLIT--` 分隔，runner 会逐条执行。

-- 1. 用户表（db_user._ensure_users_table）
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(200),
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--

-- 2. 经历卡表（docker/mysql/jobcraft.sql + db_experience._ensure_experience_card_columns）
CREATE TABLE IF NOT EXISTS experience_card (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT DEFAULT 1,
    company VARCHAR(200),
    role VARCHAR(100),
    period VARCHAR(100),
    title VARCHAR(200) NOT NULL,
    summary TEXT NOT NULL,
    background TEXT,
    problem TEXT,
    solution TEXT,
    execution TEXT,
    result TEXT,
    content TEXT,
    raw_text LONGTEXT,
    ai_structured JSON,
    tags JSON,
    metrics JSON,
    dimensions JSON,
    industry VARCHAR(100),
    role_type VARCHAR(100),
    source VARCHAR(50) DEFAULT 'manual',
    card_type VARCHAR(32) DEFAULT 'work',
    version INT DEFAULT 1,
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_user_active (user_id, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--

-- 3. 经历-岗位关联表（docker/mysql/jobcraft.sql）
CREATE TABLE IF NOT EXISTS experience_job_mapping (
    experience_id INT NOT NULL,
    job_analysis_id INT NOT NULL,
    selected TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (experience_id, job_analysis_id),
    KEY idx_job (job_analysis_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--

-- 4. 岗位分析表（docker/mysql/jobcraft.sql + db_job._ensure_job_analysis_columns）
CREATE TABLE IF NOT EXISTS job_analysis (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT DEFAULT 1,
    company VARCHAR(200),
    position VARCHAR(200),
    jd_text TEXT NOT NULL,
    jd_requirements JSON,
    match_score DECIMAL(5,2),
    gap_analysis TEXT,
    dimension_requirements JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--

-- 5. 公司背调缓存表（docker/mysql/jobcraft.sql）
CREATE TABLE IF NOT EXISTS company_research (
    company VARCHAR(200) NOT NULL PRIMARY KEY,
    info JSON,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_cached_at (cached_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--

-- 6. 投递记录表（docker/mysql/jobcraft.sql + db_submission._ensure_resume_submission_table）
CREATE TABLE IF NOT EXISTS resume_submission (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    user_id          INT DEFAULT 1,
    job_analysis_id  INT,
    position         VARCHAR(200) NOT NULL,
    company          VARCHAR(200) DEFAULT '',
    jd_text          LONGTEXT,
    resume_markdown  LONGTEXT,
    resume_file_path VARCHAR(500),
    card_version_ids JSON,
    status           VARCHAR(32) DEFAULT 'APPLIED',
    notes            TEXT,
    is_manual        TINYINT(1) DEFAULT 0,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_user_status (user_id, status),
    KEY idx_job_analysis (job_analysis_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--

-- 7. 面试准备稿表（docker/mysql/jobcraft.sql + db_submission._ensure_interview_submission_columns）
CREATE TABLE IF NOT EXISTS interview_preps (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_analysis_id INT NOT NULL,
    user_id INT DEFAULT 1,
    round_type VARCHAR(32) NOT NULL,
    duration VARCHAR(32) NOT NULL,
    elevator_pitch TEXT,
    standard_version_json JSON,
    extended_version_json JSON,
    ability_matrix_json JSON,
    html_content LONGTEXT,
    submission_id INT,
    company_research_json JSON,
    company_research_at DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_job (job_analysis_id),
    KEY idx_submission (submission_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--

-- 8. 面试记录表（docker/mysql/jobcraft.sql + db_submission._ensure_interview_submission_columns）
CREATE TABLE IF NOT EXISTS interview_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT DEFAULT 1,
    title VARCHAR(300),
    company VARCHAR(200),
    position VARCHAR(200),
    round_type VARCHAR(50),
    job_analysis_id INT,
    submission_id INT,
    round_label VARCHAR(32) DEFAULT '',
    raw_text LONGTEXT,
    parsed_dialogue_json JSON,
    analysis_json JSON,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_user_created (user_id, created_at),
    KEY idx_submission (submission_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--

-- 9. 面试 QA 对表（docker/mysql/jobcraft.sql）
CREATE TABLE IF NOT EXISTS interview_qa_pairs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    record_id INT NOT NULL,
    user_id INT DEFAULT 1,
    sequence INT DEFAULT 0,
    speaker VARCHAR(50),
    start_time VARCHAR(20),
    content TEXT,
    is_question TINYINT DEFAULT 0,
    question_text TEXT,
    dimension VARCHAR(50),
    level VARCHAR(10),
    intent TEXT,
    expected_answer TEXT,
    my_answer TEXT,
    feedback_json JSON,
    suggestions_json JSON,
    score INT DEFAULT 0,
    related_card_id INT,
    related_card_title VARCHAR(300),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_record (record_id),
    KEY idx_sequence (record_id, sequence)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--

-- 10. 经历卡版本表（docker/mysql/jobcraft.sql + db_experience._ensure_card_versions_table）
CREATE TABLE IF NOT EXISTS card_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    card_id INT NOT NULL,
    version_type VARCHAR(32) NOT NULL COMMENT 'polished | review_refined',
    source_type VARCHAR(32) NOT NULL COMMENT 'job_analysis | interview_review',
    source_id INT NOT NULL,
    title VARCHAR(300),
    raw_text LONGTEXT NOT NULL,
    tags JSON,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_card (card_id),
    KEY idx_source (source_type, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--
