-- JobCraft 外键与索引迁移
-- TASK-DB-FK-001：为高价值关系补外键，提升引用完整性（当前 schema 0 FK）。
--
-- 遵循 AGENTS.md 前向兼容（只加不改）：本迁移只新增约束，不修改/删除列。
-- 先清理孤儿数据（父表不存在的引用行），再添加约束，否则 FK 创建会失败。
--
-- 外键语义（参照 Domain v2 §49 意图）：
--   resume_submission.job_analysis_id   → job_analysis.id        ON DELETE SET NULL
--   interview_preps.job_analysis_id     → job_analysis.id        ON DELETE CASCADE
--   interview_preps.submission_id       → resume_submission.id   ON DELETE SET NULL
--   interview_qa_pairs.record_id        → interview_records.id   ON DELETE CASCADE
--   card_versions.card_id               → experience_card.id     ON DELETE CASCADE
--
-- 语句分隔：多条语句间用 `;--SPLIT--`。

-- 0. 清理孤儿数据（父表已不存在的引用行）
DELETE FROM resume_submission
WHERE job_analysis_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM job_analysis ja WHERE ja.id = resume_submission.job_analysis_id)
;--SPLIT--

DELETE FROM interview_preps
WHERE NOT EXISTS (SELECT 1 FROM job_analysis ja WHERE ja.id = interview_preps.job_analysis_id)
;--SPLIT--

UPDATE interview_preps
SET submission_id = NULL
WHERE submission_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM resume_submission rs WHERE rs.id = interview_preps.submission_id)
;--SPLIT--

DELETE FROM interview_qa_pairs
WHERE NOT EXISTS (SELECT 1 FROM interview_records ir WHERE ir.id = interview_qa_pairs.record_id)
;--SPLIT--

DELETE FROM card_versions
WHERE NOT EXISTS (SELECT 1 FROM experience_card ec WHERE ec.id = card_versions.card_id)
;--SPLIT--

-- 1. resume_submission → job_analysis
ALTER TABLE resume_submission
    ADD CONSTRAINT fk_submission_job_analysis
    FOREIGN KEY (job_analysis_id) REFERENCES job_analysis (id)
    ON DELETE SET NULL ON UPDATE CASCADE
;--SPLIT--

-- 2. interview_preps → job_analysis
ALTER TABLE interview_preps
    ADD CONSTRAINT fk_preps_job_analysis
    FOREIGN KEY (job_analysis_id) REFERENCES job_analysis (id)
    ON DELETE CASCADE ON UPDATE CASCADE
;--SPLIT--

-- 3. interview_preps → resume_submission（submission 可空）
ALTER TABLE interview_preps
    ADD CONSTRAINT fk_preps_submission
    FOREIGN KEY (submission_id) REFERENCES resume_submission (id)
    ON DELETE SET NULL ON UPDATE CASCADE
;--SPLIT--

-- 4. interview_qa_pairs → interview_records
ALTER TABLE interview_qa_pairs
    ADD CONSTRAINT fk_qa_record
    FOREIGN KEY (record_id) REFERENCES interview_records (id)
    ON DELETE CASCADE ON UPDATE CASCADE
;--SPLIT--

-- 5. card_versions → experience_card
ALTER TABLE card_versions
    ADD CONSTRAINT fk_card_versions_card
    FOREIGN KEY (card_id) REFERENCES experience_card (id)
    ON DELETE CASCADE ON UPDATE CASCADE
;--SPLIT--
