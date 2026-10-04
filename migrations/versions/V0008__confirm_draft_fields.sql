-- EXP-P1-03：草稿确认（is_confirmed）与自定义结构字段（fields）
--
-- 背景：JOBCRAFT_SYSTEM_SPEC §25.1/§27/§34.7 —— 简历确认（confirmUpload）只入库草稿
-- （is_confirmed=0），定稿 = 卡片页保存（version=1 + card_versions 哨兵基线
-- source_type='original'/source_id=0 + is_confirmed=1）。card_versions 取值扩展
-- （version_type='original'）无需 DDL（§29/§31）。
--
-- 说明：direction / expression 评估专用表延后至 P2 的 V0009（EXP-P2-01）；
-- V0008 本期只补 P1 所需的 experience_card 两列，避免提前建空表。
--
-- 前向兼容约束（AGENTS §4.4）：只加列，不改/删列；is_confirmed DEFAULT 1 对全部
-- 存量行有效，旧代码不读 is_confirmed/fields，未运行迁移的旧版本行为不受影响。
--
-- 幂等性（DB-02 / DB-VERIFY-02）：MySQL 8 无 ADD COLUMN IF NOT EXISTS，采用
--   information_schema.COLUMNS 探测 + PREPARE/EXECUTE 动态执行（同 V0014/V0017 惯例）；
--   存量库（列已由运行时 _ensure_experience_card_columns 建成、无迁移记录）重放安全。
--
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）。

SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'experience_card'
              AND COLUMN_NAME = 'is_confirmed')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE experience_card ADD COLUMN is_confirmed TINYINT(1) NOT NULL DEFAULT 1',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_81 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_81
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_81
;--SPLIT--
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'experience_card'
              AND COLUMN_NAME = 'fields')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE experience_card ADD COLUMN fields JSON',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_82 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_82
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_82
;--SPLIT--
