-- T-M6-1 / M6-Q1-B：简历版本表 resume_version（核心字段版）
--
-- 背景（M6-Q1 裁决 B）：简历版本必须独立落库——结构化 sections JSON 是
--   版本 diff、来源溯源、左栏缺口任务列（M6-3/4）的前提；且 M5-Q2 Job 先行
--   后「投递前简历」不再有 submission 可存（T-M6-2 将 save-resume 产物写入本表）。
--
-- 本迁移只新建表（AGENTS §4.4 前向兼容，仅 CREATE 不动既有表/列）：
--   Q1-B 核心字段：user_id / job_id / direction_id / version_no / version_name /
--   sections / resume_markdown / selected_for_application / source_expression_refs；
--   factualCheck、userStatus、type、baseResumeId、customizationFocus 按裁决
--   留空后置（后续迁移只加列）。
--   selected_for_application：RESUME_SPEC §11 单选「用户确认实际投递的版本」，
--   由 POST /api/jobcraft/resume-version/{id}/current 维护（同岗单选，Q5
--   切换当前版本；M6-7 标记投递时归档选中快照的依据）。
--   job_id 可空：存量快照迁 v1（T-M6-2）与无岗场景不留死路。
--
-- 幂等性（DB-02）：CREATE TABLE IF NOT EXISTS，重复执行安全。
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）。

CREATE TABLE IF NOT EXISTS resume_version (
    id                       INT AUTO_INCREMENT PRIMARY KEY,
    user_id                  INT NOT NULL DEFAULT 1,
    job_id                   INT,
    direction_id             INT,
    version_no               INT NOT NULL DEFAULT 1,
    version_name             VARCHAR(200),
    sections                 JSON,
    resume_markdown          LONGTEXT,
    selected_for_application TINYINT(1) NOT NULL DEFAULT 0,
    source_expression_refs   JSON,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_resume_version_owner (user_id, job_id),
    KEY idx_resume_version_job (job_id),
    KEY idx_resume_version_direction (direction_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--
