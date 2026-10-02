"""direction 表查询模块（T-M3-1 起提供 P3 方向 CRUD）。

**迁移依赖**：direction 表由 V0009 创建、V0018 完善（六维标量列 + DIR-n 编码 +
唯一键），本模块零运行时 DDL——全新/旧环境均先 ``python -m migrations.runner
migrate``，否则新列缺失时 INSERT/UPDATE 会报未知列（errno 1054），本模块会把
该错误翻译为「请先执行迁移」的 ValueError 提示（``run_schema_bootstrap`` 启动
断言同样会校验 direction 表存在并提示迁移）。

模型（Q7=c 两级分离 · U-P2a′ 编码裁决 2026-10-01）：
- direction = 方向定义：name（展示 label 落此字段）+ 六维标量列 + code（DIR-n）
  + status(active|archived)；六维 = JD_ANALYSIS_SPEC §4
  Function/Role/Industry/Product/Scenario/Skills，列名避开 MySQL 保留字。
- 多值维（product/scenario/skills）以英文逗号分隔存标量（B 切片约定：
  中文词组不含 ASCII 逗号；六维多值提案侧见 jd_classification，V0019）。
- code 生成：用户内 max(既有 DIR-n)+1，UNIQUE(user_id, code) 兜底并发，
  冲突重试；UNIQUE(user_id, name) 保证同用户方向名唯一（find-or-create 依据）。
"""

import logging
from typing import Any, Dict, List, Optional

from mysql.connector import Error as MySQLError

from app.tools.db_conn import (
    execute,
    query_all,
    query_one,
    transaction,
)

logger = logging.getLogger("jobcraft.db.direction")

DIRECTION_STATUSES = ("active", "archived")
CODE_PREFIX = "DIR"
SIX_DIM_FIELDS = (
    "job_function",
    "primary_role",
    "industry",
    "product",
    "scenario",
    "skills",
)
_UPDATABLE_FIELDS = ("name", *SIX_DIM_FIELDS, "status")
_CODE_RETRY_TIMES = 3
_MISSING_COLUMN_ERRNO = 1054
_DUP_KEY_ERRNO = 1062


def _row_to_direction(row: Dict[str, Any]) -> Dict[str, Any]:
    """数据库行 → API 友好结构（snake_case wire 契约）。

    新列（V0018）用 .get 兜底：未迁移库读路径不炸（写路径会由
    create/update 报「请先迁移」），时间戳与 expression 同款 isoformat。
    """
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "code": row.get("code") or "",
        "name": row["name"],
        "job_function": row.get("job_function") or "",
        "primary_role": row.get("primary_role") or "",
        "industry": row.get("industry") or "",
        "product": row.get("product") or "",
        "scenario": row.get("scenario") or "",
        "skills": row.get("skills") or "",
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def _parse_code_number(code: Any) -> int:
    """从 DIR-n 编码解析顺序号；非 DIR-n 形态返回 0（不参与 max 计算）。"""
    if not isinstance(code, str) or not code.startswith(f"{CODE_PREFIX}-"):
        return 0
    try:
        return int(code.split("-", 1)[1])
    except ValueError:
        return 0


def _next_code(cur: Any, user_id: int) -> str:
    """在事务游标上计算该用户下一个方向编码 DIR-(max+1)。

    :param cur: dictionary 游标（事务内，保证与 INSERT 同连接可见）。
    :param user_id: 归属用户。
    :return: 形如 DIR-3 的编码。
    """
    cur.execute("SELECT code FROM direction WHERE user_id=%s", (user_id,))
    max_n = 0
    for row in cur.fetchall() or []:
        max_n = max(max_n, _parse_code_number(row.get("code")))
    return f"{CODE_PREFIX}-{max_n + 1}"


def _dup_key_of(exc: MySQLError) -> str:
    """识别重复键冲突命中的唯一键名（无匹配返回空串）。"""
    text = f"{exc} {getattr(exc, 'msg', '') or ''}"
    for key in ("uk_direction_code", "uk_direction_user_name"):
        if key in text:
            return key
    return ""


def _translate_write_error(exc: MySQLError) -> None:
    """把建表缺列 / 唯一键冲突翻译为带指引的 ValueError，其余原样上抛。"""
    errno = getattr(exc, "errno", None)
    if errno == _MISSING_COLUMN_ERRNO:
        raise ValueError(
            "direction 表缺少 P3 新列，请先执行 python -m migrations.runner migrate"
        ) from exc
    if errno == _DUP_KEY_ERRNO:
        if _dup_key_of(exc) == "uk_direction_user_name":
            raise ValueError("方向名称已存在（同名方向只允许一个）") from exc
        raise ValueError("方向编码冲突，请重试") from exc
    raise


def create_direction(data: Dict[str, Any]) -> Dict[str, Any]:
    """创建方向（自动生成 DIR-n 编码）。

    :param data: 含 user_id/name，可选六维字段（缺省空串）与 status。
    :return: 创建后的方向结构（_row_to_direction）。
    :raises ValueError: 名称为空 / 状态非法 / 同名方向已存在 / 编码冲突重试耗尽。
    """
    user_id = int(data["user_id"])
    name = (data.get("name") or "").strip()
    status = data.get("status") or "active"
    if not name:
        raise ValueError("方向名称不能为空")
    if status not in DIRECTION_STATUSES:
        raise ValueError(
            f"status 仅允许 {'/'.join(DIRECTION_STATUSES)}，收到: {status}"
        )

    insert_id: Optional[int] = None
    for attempt in range(_CODE_RETRY_TIMES):
        try:
            with transaction() as conn:
                with conn.cursor(dictionary=True) as cur:
                    code = _next_code(cur, user_id)
                    cur.execute(
                        "INSERT INTO direction "
                        "(user_id, code, name, job_function, primary_role, industry, "
                        "product, scenario, skills, status) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            user_id,
                            code,
                            name,
                            (data.get("job_function") or "").strip(),
                            (data.get("primary_role") or "").strip(),
                            (data.get("industry") or "").strip(),
                            (data.get("product") or "").strip(),
                            (data.get("scenario") or "").strip(),
                            (data.get("skills") or "").strip(),
                            status,
                        ),
                    )
                    insert_id = cur.lastrowid
            break
        except MySQLError as exc:
            errno = getattr(exc, "errno", None)
            if (
                errno == _DUP_KEY_ERRNO
                and _dup_key_of(exc) == "uk_direction_code"
                and attempt < _CODE_RETRY_TIMES - 1
            ):
                logger.warning(
                    "方向编码冲突重试 user_id=%s attempt=%s", user_id, attempt + 1
                )
                continue
            if errno in (_MISSING_COLUMN_ERRNO, _DUP_KEY_ERRNO):
                _translate_write_error(exc)
            raise

    created = get_direction(int(insert_id), user_id) if insert_id else None
    if not created:
        raise ValueError("方向创建后回读失败，请重试")
    return created


def list_directions(user_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """列出用户方向（创建序 DIR-1 在前），可按 status 过滤。

    :param user_id: 归属用户。
    :param status: 可选 active|archived 过滤；None 返回全部。
    :raises ValueError: status 非法。
    """
    if status is not None and status not in DIRECTION_STATUSES:
        raise ValueError(
            f"status 仅允许 {'/'.join(DIRECTION_STATUSES)}，收到: {status}"
        )
    sql = "SELECT * FROM direction WHERE user_id=%s"
    params: List[Any] = [user_id]
    if status is not None:
        sql += " AND status=%s"
        params.append(status)
    sql += " ORDER BY id ASC"
    return [_row_to_direction(r) for r in query_all(sql, tuple(params))]


def get_direction(
    direction_id: int, user_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """按 id 查方向，可选按 user_id 过滤所有权。

    :param direction_id: 方向 id。
    :param user_id: 归属用户；提供时方向不归属该用户视同不存在（返回 None）。
    :return: 方向结构（_row_to_direction），或 None。
    """
    sql = "SELECT * FROM direction WHERE id=%s"
    params: List[Any] = [direction_id]
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    row = query_one(sql, tuple(params))
    return _row_to_direction(row) if row else None


def update_direction(
    direction_id: int, user_id: int, fields: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """按白名单字段更新方向（部分更新；code 不可改）。

    :param direction_id: 方向 id。
    :param user_id: 归属用户。
    :param fields: name/六维/status 中的若干字段（None 值忽略）。
    :return: 更新后的方向结构；方向不存在或不归属返回 None。
    :raises ValueError: 名称为空 / 状态非法 / 同名方向已存在。
    """
    clean: Dict[str, Any] = {}
    for key, value in fields.items():
        if key in _UPDATABLE_FIELDS and value is not None:
            clean[key] = value.strip() if isinstance(value, str) else value
    if "name" in clean and not clean["name"]:
        raise ValueError("方向名称不能为空")
    if "status" in clean and clean["status"] not in DIRECTION_STATUSES:
        raise ValueError(
            f"status 仅允许 {'/'.join(DIRECTION_STATUSES)}，收到: {clean['status']}"
        )
    if not clean:
        return get_direction(direction_id, user_id)
    # 先存在性校验：等值 UPDATE 的 rowcount=0 不能误判为不存在
    if not get_direction(direction_id, user_id):
        return None
    sets = ", ".join(f"{col}=%s" for col in clean)  # 列名来自白名单，无注入面
    try:
        execute(
            f"UPDATE direction SET {sets} WHERE id=%s AND user_id=%s",
            (*clean.values(), direction_id, user_id),
        )
    except MySQLError as exc:
        if getattr(exc, "errno", None) == _DUP_KEY_ERRNO:
            _translate_write_error(exc)
        raise
    return get_direction(direction_id, user_id)


def delete_direction(direction_id: int, user_id: int) -> bool:
    """硬删除单方向（引用守卫由 API 层先行拦截；归档走 update status）。

    :return: 是否删除了行（不存在/越权为 False）。
    """
    return (
        execute(
            "DELETE FROM direction WHERE id=%s AND user_id=%s",
            (direction_id, user_id),
        )
        > 0
    )


def count_direction_references(direction_id: int, user_id: int) -> Dict[str, int]:
    """统计引用该方向的下游行数（删除守卫用，越权方向计 0）。

    :return: {"expressions": n, "jd_classifications": n}——后者为
    jd_classification.direction_id 引用计数（T-M3-2 / V0019 接入；表缺失
    时语义上必为 0，记 warning 后按 0 计，不阻断方向删除）。
    """
    owned = query_one(
        "SELECT id FROM direction WHERE id=%s AND user_id=%s",
        (direction_id, user_id),
    )
    if not owned:
        return {"expressions": 0, "jd_classifications": 0}
    expr_row = query_one(
        "SELECT COUNT(*) AS c FROM expression WHERE direction_id=%s AND user_id=%s",
        (direction_id, user_id),
    )
    try:
        cls_row = query_one(
            "SELECT COUNT(*) AS c FROM jd_classification "
            "WHERE direction_id=%s AND user_id=%s",
            (direction_id, user_id),
        )
    except MySQLError as exc:
        if getattr(exc, "errno", None) == 1146:
            logger.warning(
                "jd_classification 缺表（未迁移 V0019），方向引用计数按 0 计: %s", exc
            )
            cls_row = None
        else:
            raise
    return {
        "expressions": int((expr_row or {}).get("c") or 0),
        "jd_classifications": int((cls_row or {}).get("c") or 0),
    }
