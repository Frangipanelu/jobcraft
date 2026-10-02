-- T-M3-2：jd_classification 新表（Q7=c 两级分离 · 第二级 = JD 六维分类提案）
--
-- 背景：P3 方向体系两级分离（Q7=c，2026-10-01 裁决）——direction 只存方向定义
-- （V0018 已加六维标量列），JD 侧的分类提案/确认独立落本表：
--   1. 一行 = 一个 job_analysis 的六维分类，UNIQUE(job_analysis_id)，
--      API POST 为全量 upsert（INSERT ... ON DUPLICATE KEY UPDATE）；
--   2. 六维列与 direction（V0018）同构同宽（100/100/100/200/200/500），
--      多值维（product/scenario/skills）英文逗号分隔（B 切片约定）；
--   3. confidence = high|medium|low（JD_ANALYSIS_SPEC §4；manual 直填未评置信
--      允许空串），列宽 8；
--   4. source = manual|rule|ai（JOBCRAFT_AI_BOUNDARY 分类来源三类，AI 建议
--      链路留位，本期仅 manual 落地），列宽 16；
--   5. status = proposed|confirmed（AI 提议→用户确认门，SYSTEM_SPEC §8 /
--      functional-review P3「proposal→confirm 写门」），默认 proposed；
--   6. direction_id 可空逻辑外键（PRD 6.2「关键列」非穷举；承接 T-M3-3 提交期
--      find-or-create 的指向与 direction 删除守卫计数），无 FK 约束——与
--      V0009/V0014 既有风格一致，索引 idx_jd_classification_direction 单列兜底。
--
-- 归属：user_id 冗余保存（越权过滤与 expression/direction 同款），job_analysis
-- 归属校验在 API 层先行（db_tools.get_job_analysis(id, user_id)）。
--
-- 前向兼容（AGENTS §4.4）：仅新建表，不改/不删任何既有表与列；
-- CREATE TABLE IF NOT EXISTS 幂等，重放无操作（DB-02）。
--
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）分隔。

CREATE TABLE IF NOT EXISTS jd_classification (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL DEFAULT 1,
    job_analysis_id INT NOT NULL,
    direction_id INT NULL,
    job_function VARCHAR(100) NOT NULL DEFAULT '',
    primary_role VARCHAR(100) NOT NULL DEFAULT '',
    industry VARCHAR(100) NOT NULL DEFAULT '',
    product VARCHAR(200) NOT NULL DEFAULT '',
    scenario VARCHAR(200) NOT NULL DEFAULT '',
    skills VARCHAR(500) NOT NULL DEFAULT '',
    confidence VARCHAR(8) NOT NULL DEFAULT '',
    source VARCHAR(16) NOT NULL DEFAULT 'manual',
    status VARCHAR(16) NOT NULL DEFAULT 'proposed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_jd_classification_analysis (job_analysis_id),
    KEY idx_jd_classification_user (user_id, status),
    KEY idx_jd_classification_direction (direction_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--
