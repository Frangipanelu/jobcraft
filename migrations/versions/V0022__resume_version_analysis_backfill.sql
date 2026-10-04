-- T-M6-2 / M6-Q1-B：resume_version 补 job_analysis_id 列 + 存量快照一次性迁 v1
--
-- 背景（M6 矩阵 T-M6-2，裁决「一次性 SQL」而非读时兼容）：
--   存量岗位的简历正文只存在于 resume_submission.resume_markdown（单点覆盖、
--   无历史），需一次性复制为该岗位的 v1 版本行，此后读版本只看 resume_version。
--   job_analysis_id 列使岗位归属不依赖 M5 job 表是否回填（存量岗位可能尚无
--   job 行）：save-resume 与 FE 地图均以 analysis 维度归组，job_id 有则填。
--
-- 前向兼容（AGENTS §4.4）：只加列 + 插入行，不改/删既有列；旧代码不读新列。
-- 语句顺序：先 ALTER（INSERT 的 NOT EXISTS 要引用新列），后 INSERT。
-- 幂等（DB-02 / DB-VERIFY-02）：加列与加索引走 information_schema.COLUMNS /
--   STATISTICS 探测 + PREPARE/EXECUTE 动态执行（同 V0014/V0017 惯例），存量库
--   （列/索引已由运行时守卫建成、schema_migrations 无记录）重放安全；
--   INSERT 的 NOT EXISTS 按 (user_id, job_analysis_id) 防重复迁入
--   （同岗位已有版本则跳过），重复执行不产生重复行。
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）。

SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'resume_version'
              AND COLUMN_NAME = 'job_analysis_id')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE resume_version ADD COLUMN job_analysis_id INT NULL, ADD KEY idx_resume_version_analysis (job_analysis_id)',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_221 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_221
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_221
;--SPLIT--
SET @cnt = (SELECT COUNT(*) FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'resume_version'
              AND INDEX_NAME = 'idx_resume_version_analysis')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE resume_version ADD KEY idx_resume_version_analysis (job_analysis_id)',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_222 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_222
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_222
;--SPLIT--
INSERT INTO resume_version
    (user_id, job_id, job_analysis_id, version_no, version_name,
     sections, resume_markdown, selected_for_application, source_expression_refs)
SELECT
    s.user_id,
    j.id,
    s.job_analysis_id,
    1,
    'v1（存量快照）',
    NULL,
    s.resume_markdown,
    0,
    NULL
FROM resume_submission s
JOIN job_analysis a
    ON a.id = s.job_analysis_id AND a.user_id = s.user_id
LEFT JOIN job j
    ON j.job_analysis_id = s.job_analysis_id
   AND j.user_id = s.user_id
   AND j.is_active = 1
WHERE s.resume_markdown IS NOT NULL
  AND s.resume_markdown <> ''
  AND NOT EXISTS (
      SELECT 1 FROM resume_version v
      WHERE v.user_id = s.user_id
        AND v.job_analysis_id = s.job_analysis_id
  )
;--SPLIT--
