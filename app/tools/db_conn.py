"""
统一 MySQL 访问封装（TASK-REF-DB-001 / TASK-REF-DB-002）

把散落在各 db_* 业务模块（db_user / db_experience / db_job / db_submission /
db_interview / db_ai）的 `connect(**config) + cursor().execute()` 样板收敛到
本模块的单一出口，并在该单一出口接入 DB 可观测指标（TASK-REF-DB-002）：
- `db_query_duration_seconds{operation,table}`：每次经封装函数的查询耗时。
- `db_connections_active`：活动连接数（经 `connection()` 或封装函数建立/释放）。

约定：
- 本模块的 `connect` 是全项目唯一创建 mysql 连接的地方；业务模块改成
  `from app.tools.db_conn import connect, ...` 使用，不再直接 import
  mysql.connector。
- `connect()` 默认读取 jobcraft 库配置（经 db_config.get_db_config）；也可显式传参覆盖。
- 提供常用查询/写操作的封装函数，让单语句读写折叠成一行（自动记录查询指标）；
  同连接多语句场景使用 `connection()` 上下文管理器（仅记录连接指标）。
- operation/table 通过 SQL 启发式推断，仅用于观测，不保证语义完备。
"""

import logging
import re
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from mysql.connector import connect as _raw_connect

from app.monitoring.metrics import (
    db_connections_active,
    db_query_duration_seconds,
)
from app.tools.db_config import JOBCRAFT_DB, get_db_config

logger = logging.getLogger("jobcraft.db.conn")


def _jc_config() -> Dict[str, Any]:
    """返回统一使用的 jobcraft 库连接配置。"""
    return get_db_config({"database": JOBCRAFT_DB})


# SQL 操作/表启发式推断（仅用于观测标签，低基数、有界）
_TABLE_START_RE = re.compile(
    r"^\s*(?:insert|replace)\s+into\s+`?(\w+)`?", re.IGNORECASE
)
_TABLE_UPDATE_RE = re.compile(r"^\s*update\s+`?(\w+)`?", re.IGNORECASE)
_TABLE_DELETE_RE = re.compile(r"^\s*delete\s+from\s+`?(\w+)`?", re.IGNORECASE)
_TABLE_SELECT_RE = re.compile(r"^\s*select\b[\s\S]*?\bfrom\s+`?(\w+)`?", re.IGNORECASE)
_TABLE_DDL_RE = re.compile(
    r"^\s*(?:alter|create|drop|truncate|rename)\s+table\s+"
    r"(?:if\s+not\s+exists\s+)?`?(\w+)`?",
    re.IGNORECASE,
)
_TABLE_SHOW_RE = re.compile(r"^\s*show\s+.*?\bfrom\s+`?(\w+)`?", re.IGNORECASE)


def _sql_meta(sql: str) -> tuple:
    """从 SQL 推断 (operation, table) 用于观测标签。

    operation 取值：select / insert / update / delete / ddl / other；
    table 为推断的主表名，无法推断时为 "unknown"。

    :param sql: SQL 语句
    :return: (operation, table) 二元组
    """
    if not sql:
        return ("other", "unknown")
    if sql.lstrip().lower().startswith("with"):
        return ("select", "unknown")
    for regex, op in (
        (_TABLE_START_RE, "insert"),
        (_TABLE_UPDATE_RE, "update"),
        (_TABLE_DELETE_RE, "delete"),
        (_TABLE_DDL_RE, "ddl"),
        (_TABLE_SHOW_RE, "select"),
        (_TABLE_SELECT_RE, "select"),
    ):
        match = regex.search(sql)
        if match:
            return (op, match.group(1) or "unknown")
    return ("other", "unknown")


@contextmanager
def _tracked_connection(sql: str) -> Iterator[Any]:
    """建立连接并记录查询与连接指标（供封装函数使用）。

    建立连接时递增活动连接数；退出时观测 `db_query_duration_seconds`
    并递减活动连接数。

    :param sql: 将被执行的 SQL（用于推断 operation/table）
    :yield: 兼容 `with conn:` + `conn.cursor()` 的连接对象
    """
    operation, table = _sql_meta(sql)
    db_connections_active.inc()
    started = time.perf_counter()
    try:
        with connect() as conn:
            yield conn
    finally:
        db_query_duration_seconds.labels(operation=operation, table=table).observe(
            time.perf_counter() - started
        )
        db_connections_active.dec()


def connect(*args: Any, **kwargs: Any) -> Any:
    """创建到 jobcraft 库的连接（统一入口）。

    不传任何连接参数时默认使用 jobcraft 库配置；否则透传给 mysql.connector。

    :return: 兼容 `with connect() as conn:` + `conn.cursor()` 的连接对象
    """
    if not args and not kwargs:
        kwargs = _jc_config()
    return _raw_connect(*args, **kwargs)


@contextmanager
def connection() -> Iterator[Any]:
    """打开一个可复用的连接上下文（供同连接多语句场景）。

    用于 `_ensure_*` DDL、级联删除等需要在同一连接/游标上连续执行的场景。
    建立/释放连接时维护 `db_connections_active` 指标（多语句内部各 `cur.execute`
    的逐句耗时不由本函数观测，见 `_tracked_connection`）。

    :yield: mysql.connector 连接对象（调用方负责 `with conn.cursor() as cur:`）
    """
    conn = connect()
    db_connections_active.inc()
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            logger.warning("关闭 DB 连接失败（忽略）", exc_info=True)
        finally:
            db_connections_active.dec()


def query_one(sql: str, params: Optional[Any] = None) -> Optional[Dict[str, Any]]:
    """执行 SELECT 并返回单行（字典）；无结果返回 None。

    :param sql: SQL 语句
    :param params: 参数（tuple / list 或 None）
    :return: 单行字典或 None
    """
    with _tracked_connection(sql) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def query_all(sql: str, params: Optional[Any] = None) -> List[Dict[str, Any]]:
    """执行 SELECT 并返回全部行（字典列表）。

    :param sql: SQL 语句
    :param params: 参数（tuple / list 或 None）
    :return: 字典列表（可能为空）
    """
    with _tracked_connection(sql) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def query_scalar(sql: str, params: Optional[Any] = None) -> Any:
    """执行返回单值标量的查询（如 COUNT / MAX）。

    :param sql: SQL 语句
    :param params: 参数（tuple / list 或 None）
    :return: 首行首列值；无结果返回 None
    """
    with _tracked_connection(sql) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return row[0] if row else None


def execute(sql: str, params: Optional[Any] = None) -> int:
    """执行写操作（INSERT / UPDATE / DELETE），返回受影响行数（rowcount）。

    :param sql: SQL 语句
    :param params: 参数（tuple / list 或 None）
    :return: rowcount
    """
    with _tracked_connection(sql) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount


def execute_lastrowid(sql: str, params: Optional[Any] = None) -> int:
    """执行 INSERT，返回自增主键（lastrowid）。

    :param sql: SQL 语句
    :param params: 参数（tuple / list 或 None）
    :return: 新行自增主键
    """
    with _tracked_connection(sql) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.lastrowid
