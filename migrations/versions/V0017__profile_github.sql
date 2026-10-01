-- FE-RESUME-03：user_profiles 增加 github 列（个人资料 GitHub 主页，简历头部同步用）
--
-- 背景：ResumePersonalInfo 已支持 github，profile 表缺该字段；
--   产品裁决「profile 补 github」，补齐资料 → 简历同步链路。
-- 前向兼容约束（AGENTS §4.4）：只加列，不改/删列；旧代码不读该列，未迁移环境不受影响。
-- 迁移编号：V0014 继续预留给 BE-INDEX-01 / T-M7-4 批次，本迁移取 V0017
--   （沿用 V0015/V0016 跳号先例；runner 按文件名排序应用，不强制版本号连续）。
-- 幂等性（DB-02）：MySQL 8 无 ADD COLUMN IF NOT EXISTS，采用
--   information_schema 探测 + PREPARE/EXECUTE 动态执行，重复执行安全；
--   运行时 db_profile._ensure_user_profiles_table 带同款守卫补列，
--   两路径可共存（守卫探测相同，先到先得）。
--
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）。

SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'user_profiles'
              AND COLUMN_NAME = 'github')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE user_profiles ADD COLUMN github VARCHAR(255) DEFAULT ''''',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_104 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_104
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_104
;--SPLIT--
