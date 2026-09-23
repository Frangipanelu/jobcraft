-- EXP-P2-01：标准化表达（expression）与方向（direction）新表
--
-- 背景：JD 定制 / 面试过程产生的「表达版本链」需要可回溯存储；§31 明确新增
-- direction + expression 两张表（只加不改）。载体细节：
--   1. direction 表：字段依据 DATA_MODEL §7 + DIRECTION_SPEC §3（functionId/
--      primaryRoleId/status 取代 §31 早期的 description/level/group 建议）
--   2. expression 表：字段依据 DATA_MODEL §6 + EXPERIENCE_SPEC §8（id/experienceId/
--      userId/directionId?/jobId?/type=standardized|direction|job_specific/content/
--      version/validationLevel 0-4/usageCount/sourceRefs/status=candidate|active|
--      deprecated/createdAt/updatedAt），snake_case 落库
--   3. U2 手动触发生成（非自动）；U6 P2 仅 Standardized Expression 回写，
--      direction 表本期只是建表，P2 不建 CRUD（归 P3）
--
-- 版本链语义：每次生成/修改 → 新插入一行 expression（不覆盖旧行），可回溯；
-- 同 (experience_id, type, direction_id, job_id) 的多行构成一个表达版本链。
--
-- 前向兼容约束（AGENTS §4.4 / U8）：只加表，不改/删列；CREATE TABLE IF NOT EXISTS
-- 幂等，已存在则无操作。函数 / 角色主键表尚不存在（P3 六维分类），故
-- function_id/primary_role_id 仅保留 INT 可空位，不在本期建外键（与 V0001
-- 基线风格一致：无 FK，FK 由专用迁移统一补齐，见 V0002）。
--
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）分隔。

CREATE TABLE IF NOT EXISTS direction (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL DEFAULT 1,
    name VARCHAR(200) NOT NULL,
    function_id INT NULL,
    primary_role_id INT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_direction_user (user_id),
    KEY idx_direction_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--

CREATE TABLE IF NOT EXISTS expression (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL DEFAULT 1,
    experience_id INT NOT NULL,
    direction_id INT NULL,
    job_id INT NULL,
    type VARCHAR(16) NOT NULL DEFAULT 'standardized',
    content TEXT NOT NULL,
    version INT NOT NULL DEFAULT 1,
    validation_level TINYINT NOT NULL DEFAULT 0,
    usage_count INT NOT NULL DEFAULT 0,
    source_refs JSON,
    status VARCHAR(16) NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_expression_user (user_id),
    KEY idx_expression_experience (experience_id),
    KEY idx_expression_direction (direction_id),
    KEY idx_expression_job (job_id),
    KEY idx_expression_status (type, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--