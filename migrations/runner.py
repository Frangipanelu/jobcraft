"""SQL 迁移 runner。

用法：
    python -m migrations.runner status       # 查看已应用/待应用版本
    python -m migrations.runner migrate      # 应用所有待应用版本（幂等）
    python -m migrations.runner migrate 2    # 只应用到版本 2 之前（含 2）

每个 migrations/versions/*.sql 是一个迁移；以 `V0001` 形式命名、按序应用。
已应用版本记录在 schema_migrations 表。DDL 需幂等（CREATE TABLE IF NOT EXISTS 等），
本 runner 幂等：重复执行 migrate 不会重复应用已记录的版本。
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from typing import List, Optional, Tuple

from mysql.connector import connect
from mysql.connector.cursor import MySQLCursor

from app.tools.db_config import get_db_config

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "versions")
VERSION_PATTERN = re.compile(r"^V(\d{4})__(.+?)\.sql$")


def _config() -> dict:
    """返回 jobcraft 库的连接配置（与业务层一致）。"""
    return get_db_config({"database": "jobcraft"})


def _ensure_schema_migrations(cur: MySQLCursor) -> None:
    """确保版本表存在。"""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    VARCHAR(16) NOT NULL,
            name       VARCHAR(255) NOT NULL,
            checksum   CHAR(64) NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (version)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )


def _discover_migrations() -> List[Tuple[str, str, str]]:
    """返回 (version, filename, sql) 列表，按 version 升序。"""
    items: List[Tuple[str, str, str]] = []
    if not os.path.isdir(MIGRATIONS_DIR):
        return items
    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        m = VERSION_PATTERN.match(fname)
        if not m:
            continue
        version = m.group(1)
        with open(os.path.join(MIGRATIONS_DIR, fname), "r", encoding="utf-8") as fh:
            sql = fh.read()
        items.append((version, fname, sql))
    return items


def _checksum(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def _applied_versions(cur: MySQLCursor) -> dict:
    _ensure_schema_migrations(cur)
    cur.execute("SELECT version, checksum FROM schema_migrations")
    return {row[0]: row[1] for row in cur.fetchall()}


def status() -> None:
    """打印迁移状态。"""
    migrations = _discover_migrations()
    config = _config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            _ensure_schema_migrations(cur)
            applied = _applied_versions(cur)
    print(f"{'VERSION':<8} {'STATUS':<12} FILE")
    print("-" * 70)
    for version, fname, sql in migrations:
        if version in applied:
            status_str = "applied"
            if applied[version] != _checksum(sql):
                status_str = "changed"
        else:
            status_str = "pending"
        print(f"{version:<8} {status_str:<12} {fname}")
    if not migrations:
        print("(no migrations found)")


def migrate(limit: Optional[int] = None) -> None:
    """应用待应用的迁移（幂等）。

    :param limit: 可选，只应用到该版本号（int 或 str）。
    """
    migrations = _discover_migrations()
    config = _config()
    applied_count = 0
    with connect(**config) as conn:
        with conn.cursor() as cur:
            _ensure_schema_migrations(cur)
            applied = _applied_versions(cur)
            target = None
            if limit is not None:
                target = f"{int(limit):04d}"
            for version, fname, sql in migrations:
                if target is not None and version > target:
                    break
                if version in applied:
                    continue
                print(f"== applying {fname}")
                # 每条迁移一个事务，避免半应用
                for stmt in sql.split(";--SPLIT--"):
                    stmt = stmt.strip()
                    if stmt:
                        cur.execute(stmt)
                cur.execute(
                    "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                    (version, fname[:-4], _checksum(sql)),
                )
                conn.commit()
                applied_count += 1
    print(f"migrated {applied_count} migration(s); {len(migrations) - _applied_now()} pending")


def _applied_now() -> int:
    config = _config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            return len(_applied_versions(cur))


def main(argv: Optional[List[str]] = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    cmd = args[0]
    try:
        if cmd == "status":
            status()
        elif cmd == "migrate":
            limit = int(args[1]) if len(args) > 1 else None
            migrate(limit)
        else:
            print(f"unknown command: {cmd}")
            return 1
    except Exception as e:  # noqa: BLE001 - CLI 顶层兜底
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
