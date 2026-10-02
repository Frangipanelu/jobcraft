-- T-M4-2：capability_gap 新表（Q3 缺口重构 · 改写任务清单落库）
--
-- 背景：Q3 定稿（2026-10-02 用户确认）——缺口的输出是改写任务清单（非评价
-- 总结），全局 match_score 降级为参考分：
--   1. 一行 = 一个 job_analysis 的一条能力缺口任务，即
--      dimension_requirements × per_card_scores × suggestions 的结构化 join
--      结果，由 suggestions 节点单次 LLM 产出（规则兜底缺失判定），collate
--      节点整批插入；
--   2. dimension = D1-D8 对齐 JD 要求侧尺子，EXT = 门槛/格式类非能力缺口
--      扩展码，note 开放字段只展示不统计（Q3-a）；
--   3. kind = evidence|rewrite（A/B 类）；status = missing|weak；
--      severity = high|medium|low——枚举与 Pydantic CapabilityGap 的
--      Literal 完全一致；
--   4. card_id 可空逻辑外键（Q3-c 链式锚点：维级 gap=头 → suggestion=尾
--      → card=锚点），无 FK 约束，同 V0009/V0014 既有风格；
--   5. current_text 承载 Q3 定稿字段「现有表述 current」——MySQL 关键字
--      安全取列名 current_text，读侧（db_capability_gap）映射回 wire 字段
--      current，与 CapabilityGap schema 对齐。
--
-- 归属：user_id 冗余保存（越权过滤与 jd_classification 同款），读侧经
-- get_job_analysis(job_id, user_id) 归属校验后按 job_analysis_id 查询。
--
-- 前向兼容（AGENTS §4.4）：仅新建表，不动既有表与列；CREATE TABLE IF NOT
-- EXISTS 幂等，重放无操作（DB-02）；缺表时 db_capability_gap 读降级 []、
-- 写报 ValueError 提示迁移，分析本体不阻断（同 V0019 零运行时 DDL 模式）。
--
-- 编号：V0014 已被 BE-INDEX-01 占用（M5-8 原计划缺口表并入 V0014），顺延
-- V0020；TODO/矩阵 中的「落库 V0014」按此勘误为 V0020。
--
-- 语句分隔：多条语句间用 SPLIT 标记（分号加短横线 SPLIT 短横线）分隔。

CREATE TABLE IF NOT EXISTS capability_gap (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_analysis_id INT NOT NULL,
    user_id INT NOT NULL DEFAULT 1,
    dimension VARCHAR(8) NOT NULL DEFAULT 'EXT',
    kind VARCHAR(16) NOT NULL DEFAULT 'evidence',
    status VARCHAR(16) NOT NULL DEFAULT 'missing',
    severity VARCHAR(16) NOT NULL DEFAULT 'medium',
    jd_evidence TEXT,
    current_text TEXT,
    rewrite_hint TEXT,
    card_id INT NULL,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_capability_gap_analysis (job_analysis_id),
    KEY idx_capability_gap_user_dimension (user_id, dimension)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
;--SPLIT--
