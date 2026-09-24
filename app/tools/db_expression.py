"""标准化表达（expression）CRUD 与版本链模块

表结构见 migrations/versions/V0009__expression_direction.sql（EXP-P2-01）：
expression 表是 V0009 的唯一落点，不在本模块补充运行时 DDL。

版本链语义（§31 / U1）：同 (experience_id, type, direction_id, job_id) 的多行
构成一条表达版本链；每次生成 / 修改都会新插入一行（不覆盖旧行），可回溯。
- version 在该组内单调递增（新建 = 组内 max+1）
- 新版本行 status 默认 candidate，经用户确认（U4 diff 闸门）后 active
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.tools.db_conn import (
    execute,
    execute_lastrowid,
    query_all,
    query_one,
    transaction,
)
from app.tools.db_conn import _parse_json

logger = logging.getLogger("jobcraft.db.expression")

EXPRESSION_TYPES = ("standardized", "direction", "job_specific")
EXPRESSION_STATUSES = ("candidate", "active", "deprecated")


def _row_to_expression(row: Dict[str, Any]) -> Dict[str, Any]:
    """数据库行 → API 友好结构（snake_case wire 契约）。"""
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "experience_id": row["experience_id"],
        "direction_id": row.get("direction_id"),
        "job_id": row.get("job_id"),
        "type": row["type"],
        "content": row["content"],
        "version": int(row["version"]),
        "validation_level": int(row.get("validation_level") or 0),
        "usage_count": int(row.get("usage_count") or 0),
        "source_refs": _parse_json(row.get("source_refs")) or [],
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def create_expression(data: Dict[str, Any]) -> int:
    """创建一条标准化表达（新版本行的首个版本）。

    版本号取同 (experience_id, type, direction_id, job_id) 组内 max+1，
    保证同一来源新表达的版本链单调递增且不覆盖旧行（§31）。

    :param data: 含 experience_id/type/content/user_id，可选 direction_id/job_id/
        source_refs/status/validation_level/usage_count。
    :return: 新行主键 id。
    """
    user_id = int(data["user_id"])
    experience_id = int(data["experience_id"])
    expr_type = data["type"]
    direction_id = data.get("direction_id")
    job_id = data.get("job_id")
    content = data["content"]
    source_refs = data.get("source_refs") or []
    status = data.get("status", "candidate")
    validation_level = int(data.get("validation_level") or 0)
    usage_count = int(data.get("usage_count") or 0)

    if expr_type not in EXPRESSION_TYPES:
        raise ValueError(f"type 仅允许 {'/'.join(EXPRESSION_TYPES)}，收到: {expr_type}")
    if status not in EXPRESSION_STATUSES:
        raise ValueError(
            f"status 仅允许 {'/'.join(EXPRESSION_STATUSES)}，收到: {status}"
        )
    if not content or not content.strip():
        raise ValueError("expression content 不能为空")

    next_version = (
        query_scalar_group_max_version(
            experience_id, expr_type, direction_id, job_id, user_id
        )
        + 1
    )
    return execute_lastrowid(
        """
        INSERT INTO expression
            (user_id, experience_id, direction_id, job_id, type, content,
             version, validation_level, usage_count, source_refs, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            user_id,
            experience_id,
            direction_id,
            job_id,
            expr_type,
            content,
            next_version,
            validation_level,
            usage_count,
            json.dumps(source_refs, ensure_ascii=False),
            status,
        ),
    )


def create_expression_version(
    expression_id: int,
    content: str,
    user_id: int,
    source_refs: Optional[List[Any]] = None,
    status: str = "candidate",
) -> int:
    """在既有表达基础上创建新版本行（不覆盖原行，§8.3 / §31）。

    :param expression_id: 参照的既有表达 id（取其组归属与字段）。
    :param content: 新版本内容。
    :param user_id: 归属用户（所有权校验用）。
    :param source_refs: 新版本来源引用（缺省继承原行）。
    :param status: 新版本状态，默认 candidate。
    :return: 新行主键 id。
    """
    base = get_expression(expression_id, user_id)
    if not base:
        raise LookupError(f"expression 不存在或不属于用户: {expression_id}")
    return create_expression(
        {
            "user_id": user_id,
            "experience_id": base["experience_id"],
            "direction_id": base["direction_id"],
            "job_id": base["job_id"],
            "type": base["type"],
            "content": content,
            "source_refs": list(
                source_refs
                if source_refs is not None
                else (base.get("source_refs") or [])
            ),
            "status": status,
        }
    )


def get_expression(
    expression_id: int, user_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """单条查询（可选按 user_id 过滤所有权）。"""
    sql = "SELECT * FROM expression WHERE id=%s"
    params: List[Any] = [expression_id]
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    row = query_one(sql, tuple(params))
    if not row:
        return None
    return _row_to_expression(row)


def get_expressions_by_experience(
    experience_id: int,
    user_id: int,
    expr_type: Optional[str] = None,
    direction_id: Optional[int] = None,
    job_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """列出某经历卡的表达（§8.1），可按 type/directionId/jobId 过滤。

    返回该卡全部表达行，同一条版本链按 version DESC（最新版本在前）。
    """
    sql = "SELECT * FROM expression WHERE experience_id=%s AND user_id=%s"
    params: List[Any] = [experience_id, user_id]
    if expr_type is not None:
        params.append(expr_type)
        sql += " AND type=%s"
    if direction_id is not None:
        params.append(direction_id)
        sql += " AND direction_id=%s"
    if job_id is not None:
        params.append(job_id)
        sql += " AND job_id=%s"
    sql += " ORDER BY type, direction_id, job_id, version DESC"
    rows = query_all(sql, tuple(params))
    return [_row_to_expression(r) for r in rows]


def get_all(user_id: int) -> List[Dict[str, Any]]:
    """列出某用户的全部表达（最新版本在前）。"""
    rows = query_all(
        "SELECT * FROM expression WHERE user_id=%s "
        "ORDER BY type, direction_id, job_id, version DESC",
        (user_id,),
    )
    return [_row_to_expression(r) for r in rows]


def update_status(expression_id: int, status: str, user_id: int) -> bool:
    """更新表达状态（candidate → active / deprecated 等，转合法则由 P2-06 校验）。

    :param expression_id: 表达 id。
    :param status: 目标状态。
    :param user_id: 归属用户。
    :return: 更新是否成功（不存在 / 非同用户返回 False）。
    """
    if status not in EXPRESSION_STATUSES:
        raise ValueError(
            f"status 仅允许 {'/'.join(EXPRESSION_STATUSES)}，收到: {status}"
        )
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE expression SET status=%s WHERE id=%s AND user_id=%s",
                (status, expression_id, user_id),
            )
            return cur.rowcount > 0


def delete_expression(expression_id: int, user_id: int) -> bool:
    """删除单条表达行（含其版本链中该行；不影响源经历卡）。"""
    return (
        execute(
            "DELETE FROM expression WHERE id=%s AND user_id=%s",
            (expression_id, user_id),
        )
        > 0
    )


def _query_scalar_version(
    experience_id: int,
    expr_type: str,
    direction_id: Optional[int],
    job_id: Optional[int],
    user_id: int,
    column: str,
) -> Any:
    """按版本链分组取聚合值（供组内版本号计算）。"""
    sql = (
        f"SELECT {column} FROM expression "
        "WHERE experience_id=%s AND user_id=%s AND type=%s "
        "AND (direction_id<=>%s) AND (job_id<=>%s)"
    )
    value = query_one(sql, (experience_id, user_id, expr_type, direction_id, job_id))
    if not value:
        return None
    return value[column]


def query_scalar_group_max_version(
    experience_id: int,
    expr_type: str,
    direction_id: Optional[int],
    job_id: Optional[int],
    user_id: int,
) -> int:
    """返回版本链组内当前最大版本号；无行时返回 0（用于 next = max+1）。"""
    return int(
        _query_scalar_version(
            experience_id, expr_type, direction_id, job_id, user_id, "max(version)"
        )
        or 0
    )


def query_group_max_version_id(
    experience_id: int,
    expr_type: str,
    direction_id: Optional[int],
    job_id: Optional[int],
    user_id: int,
) -> int:
    """返回版本链组内最大版本对应的行 id（用于"最新版本"定位）。"""
    row = query_one(
        "SELECT id FROM expression "
        "WHERE experience_id=%s AND user_id=%s AND type=%s "
        "AND (direction_id<=>%s) AND (job_id<=>%s) "
        "ORDER BY version DESC LIMIT 1",
        (experience_id, user_id, expr_type, direction_id, job_id),
    )
    if not row:
        raise LookupError("expression 版本链为空")
    return int(row["id"])
