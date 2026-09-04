-- JobCraft AI 审计持久化迁移
-- TASK-AI-002：为 AI 调用建立元数据审计（ai_tasks / ai_outputs，Domain v2 §29-31）。
--
-- 遵循 AGENTS.md 前向兼容（只加不改）：本迁移只新增表，不修改/删除现有表或列。
-- ai_tasks 记录每次结构化 LLM 调用的元数据；ai_outputs 存结构化输出 JSON。
-- token 用量列为可空（预留 AI-003 usage 记录使用，本任务只写核心元数据）。

CREATE TABLE IF NOT EXISTS ai_tasks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    feature VARCHAR(64) NOT NULL DEFAULT '',
    model VARCHAR(128) NOT NULL DEFAULT '',
    schema_name VARCHAR(128) NOT NULL DEFAULT '',
    prompt_version VARCHAR(32) NOT NULL DEFAULT '',
    input_hash CHAR(64) NOT NULL DEFAULT '',
    prompt_hash CHAR(64) NOT NULL DEFAULT '',
    status VARCHAR(16) NOT NULL DEFAULT 'running',
    error TEXT NULL,
    prompt_tokens INT NULL,
    completion_tokens INT NULL,
    total_tokens INT NULL,
    latency_ms INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    KEY idx_ai_tasks_status (status),
    KEY idx_ai_tasks_feature (feature),
    KEY idx_ai_tasks_created (created_at),
    KEY idx_ai_tasks_input_hash (input_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--

CREATE TABLE IF NOT EXISTS ai_outputs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id BIGINT NOT NULL,
    schema_name VARCHAR(128) NOT NULL DEFAULT '',
    schema_version VARCHAR(32) NOT NULL DEFAULT '',
    output_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ai_outputs_task FOREIGN KEY (task_id) REFERENCES ai_tasks (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--
