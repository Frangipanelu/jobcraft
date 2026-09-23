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
ALTER TABLE experience_card ADD COLUMN is_confirmed TINYINT(1) NOT NULL DEFAULT 1;--SPLIT--
ALTER TABLE experience_card ADD COLUMN fields JSON;--SPLIT--