-- T-M8-8 / BE-INDEX-01：interview_qa_pairs 补聚合查询索引
--
-- 背景：T-M8-3 上线跨场次聚合题库（单 JOIN 扫 qa_pairs JOIN records），
--   该路径全靠 record_id 过滤与 (record_id, sequence) 排序。索引虽已在
--   V0001 基线 / 运行时 _ensure_interview_qa_pairs_table / docker 基线三处声明，
--   但**存量库**（基线加索引之前建的表）不会回填——BE-INDEX-01 即此缺口。
--
-- 前向兼容约束（AGENTS §4.4）：只加索引，不改/删列/不改语义；
--   存量数据不迁移，索引由 MySQL 后台在线构建。
--
-- 幂等性（DB-02）：information_schema.STATISTICS 探测 + PREPARE/EXECUTE 动态执行，
--   重复执行安全；与运行时守卫先到先得（探测同一元数据表）。
--
-- 语句分隔：多条语句间用 --SPLIT-- 标记（分号加短横线）。
SET @cnt = (SELECT COUNT(*) FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'interview_qa_pairs'
              AND INDEX_NAME = 'idx_record')
;--SPLIT--
SET @ddl = IF(@cnt = 0,
              'ALTER TABLE interview_qa_pairs ADD KEY idx_record (record_id)',
              'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_241 FROM @ddl
;--SPLIT--
EXECUTE _mig_stmt_241
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_241
;--SPLIT--
SET @cnt2 = (SELECT COUNT(*) FROM information_schema.STATISTICS
             WHERE TABLE_SCHEMA = DATABASE()
               AND TABLE_NAME = 'interview_qa_pairs'
               AND INDEX_NAME = 'idx_sequence')
;--SPLIT--
SET @ddl2 = IF(@cnt2 = 0,
               'ALTER TABLE interview_qa_pairs ADD KEY idx_sequence (record_id, sequence)',
               'SET @noop = 1')
;--SPLIT--
PREPARE _mig_stmt_242 FROM @ddl2
;--SPLIT--
EXECUTE _mig_stmt_242
;--SPLIT--
DEALLOCATE PREPARE _mig_stmt_242