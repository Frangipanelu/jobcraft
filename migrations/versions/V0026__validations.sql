-- T-M9-1：Validation 验证信号表（validations）
--
-- 背景：「某表达/知识对象在现实中获得了什么验证证据」此前无落库载体，
--   expression.validation_level 只能靠单一 usage_count 推断，且复盘 accept
--   的用户一手确认（API_SPEC §17.3 user confirmation）无处记录。本表按
--   DATA_MODEL §24 建立 append-only 证据账本，供 GET
--   /api/jobcraft/validation-summary 做读时 Level 投影（§17.4）。
--
-- 裁决依据（Q1-A，docs/feature-alignment-matrix-2026-09-28.md:526）：
--   本期只落 L0（默认无信号）/ L1（usage_count + user_confirmed）；
--   L2-L4 自动信号（successful_use / follow_up 等）后置，不在本期写入。
--   user_confirmed 由 Feedback Accept 的同一事务创建（§31 / §17.3），
--   不允许客户端直造 Validation。
--
-- 字段（§24.1，append-only：只追加，不覆盖、不更新，故无 updated_at、无 FK）：
--   user_id       归属用户（供 §30 建议索引 (user_id) 与投影按用户过滤）
--   target_type / target_id   被验证对象（枚举见下）
--   source_type / source_id   证据来源（本期固定 user_confirmation +
--                             interview_record_id；不同 source 各追加一行）
--   signal_type               信号类型（本期仅 user_confirmed，其余枚举预留）
--   strength                  证据强度（用户一手确认 = moderate，strong 预留
--                             给 L2+ 跨场正向信号）
--   evidence_refs             SourceRef[] JSON（§3.2，含 fc:<台账id> 回指）
--   notes                     备注（可空）
--   created_at                追加时间
--
-- 枚举（§24.1）：
--   target_type   expression / self_introduction / answer_drill /
--                 direction_knowledge
--   source_type   interview / review / job_outcome / user_confirmation
--   signal_type   successful_use / follow_up / repeated_acceptance /
--                 contradiction / user_confirmed
--   strength      weak / moderate / strong
--
-- experience 扩展注记：§24.1 的 targetType 枚举未含 experience，但 W12 复盘
--   反哺候选当前唯一落地类型就是 experience（feedback_candidates.target_type，
--   V0025），accept 第 4 步的 user_confirmed 必须落点于此（TODO:232 /
--   PROGRESS:134 预留承诺）。本扩展仅此一个，迁移与
--   app/tools/db_validation.py 的白名单/ docstring 同步注记。
--
-- 幂等（DB-02）：CREATE TABLE IF NOT EXISTS，重复执行安全；写入侧另以
--   uk_validation 唯一键 + DAO 的 INSERT ... WHERE NOT EXISTS 双保险，
--   保证「同一证据不重复追加」而「不同 source 仍可各自追加一行」。
--   不变量：uk_validation 不含 user_id，依赖 source_id（interview_record_id
--   全局自增 PK）天然用户内唯一；未来换 source 形态需重评。
--
-- 前向兼容（AGENTS §4.4）：只新增表，不改/删既有表与列；旧代码不读该表，
--   回滚代码即可，不动 DB。
--
-- 语句分隔：单语句，无 --SPLIT-- 标记。
CREATE TABLE IF NOT EXISTS validations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL DEFAULT 1,
    target_type VARCHAR(32) NOT NULL,
    target_id VARCHAR(64) NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    source_id VARCHAR(64) NOT NULL,
    signal_type VARCHAR(32) NOT NULL,
    strength VARCHAR(16) NOT NULL DEFAULT 'moderate',
    evidence_refs JSON NULL,
    notes VARCHAR(500) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_validation (source_type, source_id, target_type, target_id, signal_type),
    KEY idx_validation_target (target_type, target_id),
    KEY idx_validation_user (user_id),
    KEY idx_validation_source (source_type, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
