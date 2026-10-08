"""Validation 验证信号模块（T-M9-1）

表结构见 migrations/versions/V0026__validations.sql（DATA_MODEL §24）：
validations 是 V0026 的唯一落点。运行时 DDL 走本模块 ``ensure_validations_table``
（仿 V0025 feedback_candidates 先例：写入方在事务路径内触发，不注册进
db_bootstrap._BOOTSTRAP_STEPS，不碰共享引导文件）。

职责边界：
- ``insert_user_confirmation_in_conn``：Feedback Accept 同一事务内追加一条
  user_confirmed 信号（API_SPEC §17.3「由 Accept 内部事务创建」），
  not applicable 的候选类型返回 False 且不执行 SQL；
- ``get_validation_summary``：读时派生 Validation Level 投影（§17.4 / §24.2）。
  本期只落 L0/L1 信号（Q1-A 裁决），不写 ``expression.validation_level``
  （架构评审：投影读时计算，落库即技术债）。

导入约束：只依赖 app.tools.db_conn，**不 import db_interview / db_tools（防环）**。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.tools.db_conn import connection, is_schema_ready, query_all, query_one

logger = logging.getLogger("jobcraft.db.validation")

VALIDATION_TARGET_TYPES: tuple[str, ...] = (
    "expression",
    "self_introduction",
    "answer_drill",
    "direction_knowledge",
    # §24.1 枚举之外的唯一扩展：W12 复盘反哺候选唯一落地类型即 experience
    # （feedback_candidates.target_type，V0025），accept 必须落点于此。
    "experience",
)
VALIDATION_SOURCE_TYPES: tuple[str, ...] = (
    "interview",
    "review",
    "job_outcome",
    "user_confirmation",
)
VALIDATION_SIGNAL_TYPES: tuple[str, ...] = (
    "successful_use",
    "follow_up",
    "repeated_acceptance",
    "contradiction",
    "user_confirmed",
)
VALIDATION_STRENGTHS: tuple[str, ...] = ("weak", "moderate", "strong")

# 用户一手确认是中等证据；strong 预留给 L2+ 跨场正向信号（Q1-A 设计决定 3）。
USER_CONFIRMATION_STRENGTH = "moderate"

# feedback_candidates.target_type → Validation.targetType（Q1-A 设计决定 2）。
_FEEDBACK_TARGET_TYPE_MAP: Dict[str, str] = {
    "standardized_expression": "expression",
    "direction_expression": "expression",
    "job_expression": "expression",
    "experience": "experience",
    "self_introduction": "self_introduction",
    "answer_drill": "answer_drill",
    "direction_knowledge": "direction_knowledge",
}

_VALIDATIONS_DDL = """
CREATE TABLE IF NOT EXISTS validations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL DEFAULT 1,
    target_type VARCHAR(32) NOT NULL,
    target_id VARCHAR(64) NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    source_id VARCHAR(64) NOT NULL,
    signal_type VARCHAR(32) NOT NULL,
    strength VARCHAR(16) NOT NULL DEFAULT 'moderate',
    evidence_refs JSON NULL,
    notes VARCHAR(500) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_validation (source_type, source_id, target_type, target_id, signal_type),
    KEY idx_validation_target (target_type, target_id),
    KEY idx_validation_user (user_id),
    KEY idx_validation_source (source_type, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# 幂等双保险之二：NOT EXISTS 段按 uk_validation 唯一键列同序判定，
# 同事务游标内可见本事务已插入行——重复证据静默跳过而非触发唯一键报错
# （报错会把整笔 accept 事务回滚）。
_INSERT_USER_CONFIRMATION_SQL = """
INSERT INTO validations
    (user_id, target_type, target_id, source_type, source_id,
     signal_type, strength, evidence_refs, notes)
SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM validations
    WHERE source_type=%s AND source_id=%s
      AND target_type=%s AND target_id=%s AND signal_type=%s
)
"""


def map_validation_target_type(feedback_target_type: str) -> Optional[str]:
    """把反馈候选 target_type 映射为 Validation.targetType。

    映射规则（Q1-A 设计决定 2）：

    - ``standardized_expression`` / ``direction_expression`` / ``job_expression``
      归并为 ``expression``；
    - ``experience`` / ``self_introduction`` / ``answer_drill`` /
      ``direction_knowledge`` 同名直通；
    - ``experience_story`` / ``expression_strategy`` 及未知值返回 None，
      即 §31 的「when applicable」——not applicable，不写 Validation。

    Args:
        feedback_target_type: 候选台账的 target_type。

    Returns:
        Optional[str]: Validation.targetType；不适用时为 None。
    """
    return _FEEDBACK_TARGET_TYPE_MAP.get(feedback_target_type)


def ensure_validations_table() -> None:
    """确保 validations 表存在（V0026；schema 已就绪时短路）。

    与 ``db_interview._ensure_feedback_candidates_table`` 同先例：只在
    ``is_schema_ready()`` 为 False 的环境（本地/测试未跑迁移）兜底建表，
    不注册进 db_bootstrap 启动步骤。
    """
    if is_schema_ready():
        return
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_VALIDATIONS_DDL)


def insert_user_confirmation_in_conn(
    cur: Any,
    *,
    user_id: int,
    feedback_target_type: str,
    target_id: str,
    source_id: str,
    evidence_refs: Optional[List[Dict]] = None,
    notes: Optional[str] = None,
) -> bool:
    """在调用方事务游标上追加一条 user_confirmed Validation（幂等）。

    Feedback Accept 单条与批量确认共用本函数：写卡、台账 upsert 与本插入
    在同一事务内，任一失败整体回滚（DATA_MODEL §31 Accept Feedback）。

    Args:
        cur: 调用方事务游标（不自开事务、不提交）。
        user_id: 归属用户。
        feedback_target_type: 候选 target_type，经
            :func:`map_validation_target_type` 映射；不适用时直接返回。
        target_id: 被验证对象 ID（本期即候选 target_ref）。
        source_id: 证据来源 ID（本期即 interview_record_id）。
        evidence_refs: SourceRef[]（§3.2），JSON 序列化 ``ensure_ascii=False``。
        notes: 备注，可空。

    Returns:
        bool: 是否真正插入；not applicable（映射为 None）或证据已存在时为 False。
    """
    target_type = map_validation_target_type(feedback_target_type)
    if target_type is None:
        logger.debug(
            "候选类型无对应 Validation 目标，跳过 user_confirmed 写入: %s",
            feedback_target_type,
        )
        return False
    cur.execute(
        _INSERT_USER_CONFIRMATION_SQL,
        (
            user_id,
            target_type,
            str(target_id),
            "user_confirmation",
            str(source_id),
            "user_confirmed",
            USER_CONFIRMATION_STRENGTH,
            json.dumps(evidence_refs, ensure_ascii=False) if evidence_refs else None,
            notes,
            # WHERE NOT EXISTS 段：与 uk_validation 列同序
            "user_confirmation",
            str(source_id),
            target_type,
            str(target_id),
            "user_confirmed",
        ),
    )
    inserted = int(getattr(cur, "rowcount", 0) or 0) > 0
    logger.debug(
        "user_confirmed validation 写入: target=%s/%s source=%s inserted=%s",
        target_type,
        target_id,
        source_id,
        inserted,
    )
    return inserted


def get_validation_summary(
    user_id: int, target_type: str, target_id: str
) -> Dict[str, Any]:
    """读时派生某对象的 Validation Level 投影（API_SPEC §17.4 / §24.2）。

    本期信号（Q1-A 裁决，L2-L4 后置）：

    - ``usage_count``：仅 ``target_type='expression'`` 时读
      ``expression.usage_count``（user_id 归属过滤），其余类型恒 0；
    - ``level``：usage_count ≥ 1 或存在 user_confirmed 行 → 1，否则 0
      （§24.2 L0 未验证 / L1 已使用）；
    - ``strong/moderate/weak_signals``：该 target 全部 validation 行按
      strength 分组计数（本期只会命中 moderate）；
    - ``explanation``：确定性中文拼接，不引入随机文案。

    投影是派生视图：**不做目标存在性检查**（API_SPEC 未定义 404 语义），
    未知 target 返回 L0 全零结构。

    Args:
        user_id: 归属用户。
        target_type: 被验证对象类型，须在 :data:`VALIDATION_TARGET_TYPES` 内。
        target_id: 被验证对象 ID。

    Returns:
        Dict[str, Any]: ``{target_type, target_id, level, usage_count,
        strong_signals, moderate_signals, weak_signals, explanation}``。

    Raises:
        ValueError: target_type 不在白名单。
    """
    if target_type not in VALIDATION_TARGET_TYPES:
        raise ValueError(f"target_type 仅允许: {', '.join(VALIDATION_TARGET_TYPES)}")
    ensure_validations_table()
    rows = query_all(
        "SELECT strength, signal_type FROM validations "
        "WHERE user_id=%s AND target_type=%s AND target_id=%s",
        (user_id, target_type, str(target_id)),
    )
    usage_count = 0
    if target_type == "expression":
        expr_row = query_one(
            "SELECT usage_count FROM expression WHERE id=%s AND user_id=%s",
            (target_id, user_id),
        )
        if expr_row:
            usage_count = int(expr_row.get("usage_count") or 0)

    def _count(strength: str) -> int:
        return sum(1 for r in rows if (r.get("strength") or "") == strength)

    confirmed = sum(1 for r in rows if (r.get("signal_type") or "") == "user_confirmed")
    level = 1 if usage_count >= 1 or confirmed else 0
    if level == 0:
        explanation = "尚无验证信号（L0 未验证）"
    else:
        parts: List[str] = []
        if usage_count >= 1:
            parts.append(f"已使用 {usage_count} 次")
        if confirmed:
            parts.append(f"用户确认 {confirmed} 次")
        explanation = "；".join(parts) + "（L1 已验证）"

    return {
        "target_type": target_type,
        "target_id": str(target_id),
        "level": level,
        "usage_count": usage_count,
        "strong_signals": _count("strong"),
        "moderate_signals": _count("moderate"),
        "weak_signals": _count("weak"),
        "explanation": explanation,
    }
