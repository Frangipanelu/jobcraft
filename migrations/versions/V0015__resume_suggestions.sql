-- FE-RESUME-02：resume_submission 增加 resume_suggestions JSON 列（简历 AI 优化建议存储）
--
-- 背景：简历编辑器「AI 针对性优化」需要跨刷新保留生成结果与 applied/rejected 状态，
--   resume_markdown 只承载正文，无法承载结构化建议列表。
-- 前向兼容约束（AGENTS §4.4）：只加列，不改/删列；旧代码不读该列，未迁移的旧版本不受影响。
-- 迁移编号：V0014 预留给 BE-INDEX-01 / T-M7-4 等共享批次，本迁移取 V0015
--   （runner 按文件名排序应用，不强制版本号连续）。
-- 幂等性（DB-02 / DB-VERIFY-02）：MySQL 8 无 ADD COLUMN IF NOT EXISTS，采用
--   information_schema.COLUMNS 探测 + PREPARE/EXECUTE 动态执行（同 V0014/V0017 惯例）；
--   存量库（列已由运行时守卫建成、schema_migrations 无记录）全量重放安全。
--
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）。

SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'resume_submission'
              AND COLUMN_NAME = 'resume_suggestions')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE resume_submission ADD COLUMN resume_suggestions JSON',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_151 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_151
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_151
;--SPLIT--
