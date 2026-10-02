-- T-M3-1（P3 方向体系 / M3 B 切片）：direction 表完善——六维标量列 + 方向编码 DIR-n
--
-- 背景与裁决：
--   1. Q7=c 两级分离：direction 的 6 标量列 + code/label 构成「方向定义」（索引检索），
--      JD 侧六维分类提案另落 jd_classification 独立表（V0019），本迁移不动 JD 侧。
--   2. U-P2a′ 编码规范（2026-10-01 对齐确认，采纳 DIR- 前缀方案）：类型前缀 + 用户内
--      自增顺序码 = DIR-1 / DIR-2 …，UNIQUE(user_id, code)，用途 = UI 徽标 + LLM prompt
--      引用代号 + 日志串联；采用 DIR- 而非裸 D1 是为与能力维度 D1-D8 区分
--      （feature-alignment-matrix ⚠️ 注意点）。展示 label 内容落既有 name 字段
--      （U-P2a′「落 name 字段」），不新增 label 列。
--   3. 六维字段依据 JD_ANALYSIS_SPEC §4：Function / Role / Industry / Product /
--      Scenario / Skills；多值维（Product/Scenario/Skills）以英文逗号分隔存标量
--      （B 切片约定，见 app/tools/db_direction.py 模块注释）。
--      列名避免 MySQL 保留字：FUNCTION → job_function，ROLE → primary_role。
--
-- 前向兼容约束（AGENTS §4.4）：只加列 / 只加索引，不改/删既有列；旧代码不读新列。
-- 幂等性（DB-02）：MySQL 8 无 ADD COLUMN IF NOT EXISTS / ADD KEY IF NOT EXISTS，
--   采用 information_schema.COLUMNS / STATISTICS 探测 + PREPARE/EXECUTE 动态执行。
-- 存量回填：direction 此前无任何 CRUD 入口（P3 前零写入，全环境应为空表），
--   防御性把 code='' 行按用户内 id 序回填 DIR-n（空表为 no-op），再加唯一键；
--   若同名行已存在（理论上的脏数据），UNIQUE(user_id,name) 会显式失败，不静默吞。
-- 迁移依赖：direction 表本身仅由 V0009 创建，本迁移依赖其已存在（先 migrate 后建列）。
--
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）。

-- 1. code（DIR-n 方向编码）
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'direction'
              AND COLUMN_NAME = 'code')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE direction ADD COLUMN code VARCHAR(16) NOT NULL DEFAULT ''''',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_181 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_181
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_181
;--SPLIT--

-- 2. job_function（六维 Function，主值 1 个；避开 FUNCTION 保留字）
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'direction'
              AND COLUMN_NAME = 'job_function')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE direction ADD COLUMN job_function VARCHAR(100) NOT NULL DEFAULT ''''',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_182 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_182
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_182
;--SPLIT--

-- 3. primary_role（六维 Role 主角色，主值 1 个；避开 ROLE 保留字）
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'direction'
              AND COLUMN_NAME = 'primary_role')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE direction ADD COLUMN primary_role VARCHAR(100) NOT NULL DEFAULT ''''',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_183 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_183
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_183
;--SPLIT--

-- 4. industry（六维 Industry，主值 1 个，允许 Unknown 留空）
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'direction'
              AND COLUMN_NAME = 'industry')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE direction ADD COLUMN industry VARCHAR(100) NOT NULL DEFAULT ''''',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_184 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_184
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_184
;--SPLIT--

-- 5. product（六维 Product，多选 → 英文逗号分隔）
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'direction'
              AND COLUMN_NAME = 'product')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE direction ADD COLUMN product VARCHAR(200) NOT NULL DEFAULT ''''',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_185 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_185
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_185
;--SPLIT--

-- 6. scenario（六维 Scenario，多选 → 英文逗号分隔）
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'direction'
              AND COLUMN_NAME = 'scenario')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE direction ADD COLUMN scenario VARCHAR(200) NOT NULL DEFAULT ''''',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_186 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_186
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_186
;--SPLIT--

-- 7. skills（六维 Skills，多选 → 英文逗号分隔）
SET @cnt = (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'direction'
              AND COLUMN_NAME = 'skills')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE direction ADD COLUMN skills VARCHAR(500) NOT NULL DEFAULT ''''',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_187 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_187
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_187
;--SPLIT--

-- 8. 存量回填 DIR-n（code 列就绪后执行；空表 no-op，重复执行只影响 code='' 行）
UPDATE direction d
JOIN (
    SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY id) AS rn
    FROM direction
    WHERE code = '' OR code IS NULL
) t ON t.id = d.id
SET d.code = CONCAT('DIR-', t.rn)
;--SPLIT--

-- 9. UNIQUE(user_id, code)：方向编码用户内唯一（U-P2a′）
SET @cnt = (SELECT COUNT(*) FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'direction'
              AND INDEX_NAME = 'uk_direction_code')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE direction ADD UNIQUE KEY uk_direction_code (user_id, code)',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_188 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_188
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_188
;--SPLIT--

-- 10. UNIQUE(user_id, name)：同用户方向名唯一（find-or-create 与建重校验的存储基础）
SET @cnt = (SELECT COUNT(*) FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'direction'
              AND INDEX_NAME = 'uk_direction_user_name')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE direction ADD UNIQUE KEY uk_direction_user_name (user_id, name)',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_189 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_189
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_189
;--SPLIT--
