-- JobCraft AI 缓存迁移
-- TASK-AI-003：为 ai_tasks 增加缓存命中标记列（只加不改，前向兼容）。
--
-- 遵循 AGENTS.md 前向兼容（只加列/表，不改/删列）。
-- from_cache: 1 = 本次结果来自 AI 热缓存（未实际调用 LLM），0/NULL = 实际调用。

ALTER TABLE ai_tasks
    ADD COLUMN from_cache TINYINT NULL DEFAULT NULL
    AFTER total_tokens;
;--SPLIT--
