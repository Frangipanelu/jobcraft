-- JobCraft 求职助手数据库初始化脚本
-- 包含：经历卡、岗位分析、面试准备稿、经历-岗位关联、公司背调

SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS jobcraft
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;
USE jobcraft;

-- 1. 经历卡表 (Experience Card)
-- 存储候选人每段工作经历/项目经历的五段式 STAR 结构
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
    tags JSON,
    metrics JSON,
    dimensions JSON,
    industry VARCHAR(100),
    role_type VARCHAR(100),
    source VARCHAR(50) DEFAULT 'manual',
    version INT DEFAULT 1,
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_user_active (user_id, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. 岗位分析表 (Job Analysis)
-- 存储每次岗位分析的结果，包括 JD 需求、匹配分数、缺口分析、8维能力要求
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. 经历-岗位关联表 (Experience Job Mapping)
-- 记录岗位分析时选中的经历卡
CREATE TABLE IF NOT EXISTS experience_job_mapping (
    experience_id INT NOT NULL,
    job_analysis_id INT NOT NULL,
    selected TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (experience_id, job_analysis_id),
    KEY idx_job (job_analysis_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. 面试准备稿表 (Interview Preparations)
-- 存储基于岗位分析生成的面试逐字稿
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_job (job_analysis_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. 公司背调缓存表 (Company Research Cache)
-- 缓存公司搜索结果，7 天新鲜度校验由业务层控制
CREATE TABLE IF NOT EXISTS company_research (
    company VARCHAR(200) NOT NULL PRIMARY KEY,
    info JSON,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_cached_at (cached_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. 投递记录表 (Resume Submission)
-- pipeline 核心实体，每一条投递对应一次实际求职动作
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
    status           VARCHAR(32) DEFAULT '已投递',
    notes            TEXT,
    is_manual        TINYINT(1) DEFAULT 0,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_user_status (user_id, status),
    KEY idx_job_analysis (job_analysis_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. 面试记录表 (Interview Records)
-- 面试复盘原始记录，按投递/岗位分析关联
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8. 面试 QA 对表 (Interview QA Pairs)
-- 问题表中的逐条问题，可关联经历卡
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 9. 经历卡版本表 (Card Versions)
-- 定制文本快照：润色/复盘精修版本，不修改原卡
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
