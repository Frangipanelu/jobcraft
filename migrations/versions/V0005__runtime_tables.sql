-- JobCraft 运行时表固化（TASK-P1-10）
-- base_resume / user_profiles 此前仅靠运行时 _ensure_* 创建（无迁移版本），
-- 本次固化为迁移，使 `python -m migrations.runner` 完整覆盖全库 schema。
-- 遵循 AGENTS.md 前向兼容（只加不改）：CREATE TABLE IF NOT EXISTS，已存在则无操作。
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）分隔。

CREATE TABLE IF NOT EXISTS base_resume (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    user_id          INT NOT NULL,
    name             VARCHAR(255) NOT NULL,
    file_size        VARCHAR(50) DEFAULT '',
    format           VARCHAR(16) DEFAULT 'docx',
    parsed_count     INT DEFAULT 0,
    tags             JSON,
    is_default       TINYINT(1) DEFAULT 0,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id INT NOT NULL PRIMARY KEY,
    display_name VARCHAR(100) DEFAULT '',
    role VARCHAR(100) DEFAULT '求职者',
    target_salary VARCHAR(50) DEFAULT '',
    years_of_exp INT DEFAULT 0,
    city VARCHAR(100) DEFAULT '',
    phone VARCHAR(30) DEFAULT '',
    summary TEXT,
    target_cities JSON,
    target_companies JSON,
    target_roles JSON,
    avatar_url VARCHAR(500) DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--