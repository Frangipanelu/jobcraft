-- 批次 C1：把运行时 runtime DDL 收编进迁移基线（DB-01 防漂移收敛）
--
-- 背景：V0001-V0009 已把核心表固化为迁移，但存在两个 runtime-only 补列场景：
--   1. 由旧版 docker/mysql/jobcraft.sql 初始化的历史库，experience_card 无
--      raw_text / ai_structured 列（旧初始化脚本只到 content + tags/metrics）；
--   2. 该历史表因 V0001 采用 CREATE TABLE IF NOT EXISTS，不会对"已存在的旧表"
--      补新列，此前唯一补救是 db_experience._ensure_experience_card_columns 的
--      运行时 SHOW COLUMNS + ALTER。
--      * 其余 runtime `_ensure_*` 补列（experience_card.is_confirmed/fields、
--        resume_submission.delivered/is_active、job_analysis.is_active、
--        interview_preps/records 的 submission_id/company_research_json/round_label）
--        均已由 V0008/V0006/V0007/V0001 覆盖，无需重复收编。
--
-- 本迁移把这唯一的迁移缺口补上，使 `migrate` 单独执行即可收敛任一来源的库；
-- runtime `_ensure_*` 仍保留为未迁移环境的降级兜底（行为不变，仅去掉 MODIFY）。
--
-- 前向兼容约束（AGENTS §4.4）：只加列，不改/删列；禁止 MODIFY/DROP。
--
-- 幂等性（DB-02）：MySQL 8 无 ADD COLUMN IF NOT EXISTS，采用
-- information_schema 探测 + PREPARE/EXECUTE 动态执行，重复执行安全。
--
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）。

-- 1. experience_card.raw_text（历史 docker 初始化的 experience_card 缺此列）
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'experience_card'
              AND COLUMN_NAME = 'raw_text')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE experience_card ADD COLUMN raw_text LONGTEXT',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_101 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_101
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_101
;--SPLIT--

-- 2. experience_card.ai_structured（同上，历史库缺结构化 AI 结果列）
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'experience_card'
              AND COLUMN_NAME = 'ai_structured')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE experience_card ADD COLUMN ai_structured JSON',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_102 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_102
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_102
;--SPLIT--