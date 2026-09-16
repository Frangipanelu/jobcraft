-- JobCraft AI 缓存迁移
-- TASK-AI-003：为 ai_tasks 增加缓存命中标记列（只加不改，前向兼容）。
--
-- 遵循 AGENTS.md 前向兼容（只加列/表，不改/删列）。
-- from_cache: 1 = 本次结果来自 AI 热缓存（未实际调用 LLM），0/NULL = 实际调用。
--
-- 幂等性（DB-02）：MySQL 8 无 ADD COLUMN IF NOT EXISTS，采用
-- information_schema 探测 + PREPARE/EXECUTE 动态执行，重复执行安全。

SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'ai_tasks'
              AND COLUMN_NAME = 'from_cache')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE ai_tasks ADD COLUMN from_cache TINYINT NULL DEFAULT NULL AFTER total_tokens',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt
;--SPLIT--