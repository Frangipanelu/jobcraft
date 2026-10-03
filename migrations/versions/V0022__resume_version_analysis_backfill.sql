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
-- 幂等：runner 以 schema_migrations 保证只执行一次；INSERT 的 NOT EXISTS
--   按 (user_id, job_analysis_id) 防重复迁入（同岗位已有版本则跳过）。
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）。

ALTER TABLE resume_version
    ADD COLUMN job_analysis_id INT NULL,
    ADD KEY idx_resume_version_analysis (job_analysis_id)
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
