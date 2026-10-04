-- T-M8-1：复盘反馈闸门（feedback_candidates 决策台账）
--
-- 背景：复盘候选建议的**内容**已随 T-M8-5 落在 interview_records.analysis_json
--   （patch.experienceFeedbacks），前端据此渲染「经历资产反哺」提案。但决策状态
--   （是否已确认沉淀）此前只存在于前端 query cache 的 applied 标记：
--   - 刷新页面即丢失，用户无法看到「哪些已确认」；
--   - 重复点击会重复写卡，无幂等（SPEC §"Running Review again MUST NOT
--     duplicate permanent feedback"）；
--   - spec §5 状态机的 awaiting_confirmation 无落库载体。
--
-- 设计取舍：本表**不复制候选内容**，只做「决策台账」——
--   候选正文仍以 analysis_json 为唯一来源，本表按
--   (interview_record_id, target_type, target_ref) 唯一定位一条候选并记录决策。
--   避免同一建议两处存储产生漂移。
--
-- target_type 取值预留 SPEC §W12 的 8 类候选
--   （experience / standardized_expression / direction_expression /
--     job_expression / self_introduction / answer_drill /
--     expression_strategy / direction_knowledge），
--   当前仅落地 experience（唯一有写卡通路的类型），其余类型先不写入。
--
-- 前向兼容约束（AGENTS §4.4）：只新增表，不改/删既有列与表；
--   旧代码不读该表，回滚代码即可，不动 DB。
--
-- 幂等性（DB-02）：CREATE TABLE IF NOT EXISTS，重复执行安全。
--
-- 语句分隔：多条语句间用 --SPLIT-- 标记（分号加短横线）。
CREATE TABLE IF NOT EXISTS feedback_candidates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL DEFAULT 1,
    interview_record_id INT NOT NULL,
    target_type VARCHAR(32) NOT NULL DEFAULT 'experience',
    target_ref VARCHAR(64) NOT NULL,
    analysis_run_id VARCHAR(64) NOT NULL DEFAULT '',
    decision VARCHAR(16) NOT NULL DEFAULT 'pending',
    card_version INT NULL,
    decided_at TIMESTAMP NULL DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_feedback_candidate (interview_record_id, target_type, target_ref),
    KEY idx_feedback_candidates_record (interview_record_id, decision),
    KEY idx_feedback_candidates_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4