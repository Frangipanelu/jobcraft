-- P4-1：job_analysis 持久化分析物（Job 分析物不落库缺口收敛）
--
-- 背景：run_job_analysis_workflow 的 collate 节点已产出 ats_profile /
--   match_level / per_card_scores / suggestions 并随 JobAnalysisResult 返回前端，
--   但 insert_job_analysis 只落 jd_requirements / match_score / gap_analysis /
--   dimension_requirements；历史记录（list_job_analyses）再读取时这四项全部丢失，
--   刷新页面后 JD 报告退化为空壳。同时分析物无版本标记，无法回溯是哪版 Prompt 产出。
--
-- 新增列（均只加不改，AGENTS §4.4 前向兼容）：
--   ats_profile       JSON      ATS 岗位画像
--   suggestions       JSON      简历/投递优化建议列表
--   per_card_scores   JSON      逐经历卡匹配得分
--   match_level       VARCHAR   匹配等级（值得投递/可以尝试/谨慎评估）
--   analysis_version  VARCHAR   分析产物版本（Prompt 版本化，AGENTS §7）
--
-- 幂等性（DB-02）：MySQL 8 无 ADD COLUMN IF NOT EXISTS，采用
-- information_schema 探测 + PREPARE/EXECUTE 动态执行，重复执行安全。
--
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）。

-- 1. ats_profile
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'job_analysis'
              AND COLUMN_NAME = 'ats_profile')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE job_analysis ADD COLUMN ats_profile JSON',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_111 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_111
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_111
;--SPLIT--

-- 2. suggestions
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'job_analysis'
              AND COLUMN_NAME = 'suggestions')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE job_analysis ADD COLUMN suggestions JSON',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_112 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_112
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_112
;--SPLIT--

-- 3. per_card_scores
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'job_analysis'
              AND COLUMN_NAME = 'per_card_scores')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE job_analysis ADD COLUMN per_card_scores JSON',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_113 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_113
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_113
;--SPLIT--

-- 4. match_level
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'job_analysis'
              AND COLUMN_NAME = 'match_level')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE job_analysis ADD COLUMN match_level VARCHAR(32)',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_114 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_114
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_114
;--SPLIT--

-- 5. analysis_version
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'job_analysis'
              AND COLUMN_NAME = 'analysis_version')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE job_analysis ADD COLUMN analysis_version VARCHAR(32)',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_115 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_115
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_115
;--SPLIT--
