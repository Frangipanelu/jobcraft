-- FE-PREP-01：interview_preps 增加 drafts JSON 列（备战应答草稿持久化）
--
-- 背景：备战工作台「保存草稿」原先只弹 toast，answerDrafts 纯本地随导航丢失；
--   本列按 interview_preps 行存「题号 -> 草稿文本」映射，整体覆盖写入。
-- 前向兼容约束（AGENTS §4.4）：只加列，不改/删列；旧代码不读该列，未迁移环境不受影响。
-- 迁移编号：V0014 预留给 BE-INDEX-01 / T-M7-4 等共享批次，本迁移取 V0016
--   （沿用 V0015 跳号先例；runner 按文件名排序应用，不强制版本号连续）。
-- 幂等性（DB-02）：MySQL 8 无 ADD COLUMN IF NOT EXISTS，采用
--   information_schema 探测 + PREPARE/EXECUTE 动态执行，重复执行安全；
--   运行时 db_interview._ensure_interview_preps_table 带同款守卫补列，
--   两路径可共存（守卫探测相同，先到先得）。
--
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）。

SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'interview_preps'
              AND COLUMN_NAME = 'drafts')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE interview_preps ADD COLUMN drafts JSON',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_103 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_103
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_103
;--SPLIT--
