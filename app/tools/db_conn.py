"""
统一 MySQL 访问封装（TASK-REF-DB-001）

把散落在各 db_* 业务模块（db_user / db_experience / db_job / db_submission /
db_interview / db_ai）的 `connect(**config) + cursor().execute()` 样板收敛到
本模块的单一出口，为后续接入 DB 可观测指标（db_query_duration_seconds /
db_connections_active）提供唯一 chokepoint。

约定：
- 本模块的 `connect` 是全项目唯一创建 mysql 连接的地方；业务模块改成
  `from app.tools.db_conn import connect, ...` 使用，不再直接 import
  mysql.connector。
- `connect()` 默认读取 jobcraft 库配置（经 db_config.get_db_config）；也可显式传参覆盖。
- 提供常用查询/写操作的封装函数，让单语句读写折叠成一行；同连接多语句
  场景使用 `connection()` 上下文管理器。
"""

import logging
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from mysql.connector import connect as _raw_connect

from app.tools.db_config import JOBCRAFT_DB, get_db_config

logger = logging.getLogger("jobcraft.db.conn")


def _jc_config() -> Dict[str, Any]:
    """返回统一使用的 jobcraft 库连接配置。"""
    return get_db_config({"database": JOBCRAFT_DB})


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

    :yield: mysql.connector 连接对象（调用方负责 `with conn.cursor() as cur:`）
    """
    conn = connect()
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            logger.warning("关闭 DB 连接失败（忽略）", exc_info=True)


def query_one(sql: str, params: Optional[Any] = None) -> Optional[Dict[str, Any]]:
    """执行 SELECT 并返回单行（字典）；无结果返回 None。

    :param sql: SQL 语句
    :param params: 参数（tuple / list 或 None）
    :return: 单行字典或 None
    """
    with connect() as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def query_all(sql: str, params: Optional[Any] = None) -> List[Dict[str, Any]]:
    """执行 SELECT 并返回全部行（字典列表）。

    :param sql: SQL 语句
    :param params: 参数（tuple / list 或 None）
    :return: 字典列表（可能为空）
    """
    with connect() as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def query_scalar(sql: str, params: Optional[Any] = None) -> Any:
    """执行返回单值标量的查询（如 COUNT / MAX）。

    :param sql: SQL 语句
    :param params: 参数（tuple / list 或 None）
    :return: 首行首列值；无结果返回 None
    """
    with connect() as conn:
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
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount


def execute_lastrowid(sql: str, params: Optional[Any] = None) -> int:
    """执行 INSERT，返回自增主键（lastrowid）。

    :param sql: SQL 语句
    :param params: 参数（tuple / list 或 None）
    :return: 新行自增主键
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.lastrowid
