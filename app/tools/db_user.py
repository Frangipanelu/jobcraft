"""用户 CRUD 模块"""

import logging
from typing import Any, Dict, Optional

from app.tools.db_conn import execute, execute_lastrowid, query_one

logger = logging.getLogger("jobcraft.db.user")


def _ensure_users_table() -> None:
    """确保 users 表存在"""
    execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            email VARCHAR(200),
            is_active TINYINT(1) DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            KEY idx_username (username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )


def create_user(username: str, password_hash: str, email: Optional[str] = None) -> int:
    """
    创建用户，返回用户 ID

    :param username: 用户名（唯一）
    :param password_hash: 密码哈希
    :param email: 邮箱（可选）
    :return: 新用户 ID
    """
    _ensure_users_table()
    return execute_lastrowid(
        """
        INSERT INTO users (username, password_hash, email)
        VALUES (%s, %s, %s)
        """,
        (username, password_hash, email),
    )


def _row_to_user(row: Dict[str, Any]) -> Dict[str, Any]:
    """把数据库原始行转换成 API 友好用户结构"""
    return {
        "id": row["id"],
        "username": row["username"],
        "password_hash": row["password_hash"],
        "email": row.get("email"),
        "is_active": bool(row.get("is_active", 1)),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """
    按 ID 获取用户

    :param user_id: 用户 ID
    :return: 用户信息字典或 None
    """
    _ensure_users_table()
    row = query_one("SELECT * FROM users WHERE id=%s", (user_id,))
    return _row_to_user(row) if row else None


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """
    按用户名获取用户

    :param username: 用户名
    :return: 用户信息字典或 None
    """
    _ensure_users_table()
    row = query_one("SELECT * FROM users WHERE username=%s", (username,))
    return _row_to_user(row) if row else None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    按邮箱获取用户

    :param email: 邮箱
    :return: 用户信息字典或 None
    """
    _ensure_users_table()
    row = query_one("SELECT * FROM users WHERE email=%s", (email,))
    return _row_to_user(row) if row else None


def update_user(user_id: int, updates: Dict[str, Any]) -> bool:
    """
    更新用户信息

    :param user_id: 用户 ID
    :param updates: 更新字段
    :return: 是否更新成功
    """
    _ensure_users_table()
    field_map = {
        "email": "email",
        "is_active": "is_active",
    }
    sets: list[str] = []
    values: list[Any] = []
    for k, col in field_map.items():
        if k in updates and updates[k] is not None:
            sets.append(f"{col}=%s")
            values.append(updates[k])
    if "password_hash" in updates:
        sets.append("password_hash=%s")
        values.append(updates["password_hash"])
    if not sets:
        return False
    values.append(user_id)
    return (
        execute(
            "UPDATE users SET " + ", ".join(sets) + " WHERE id=%s",
            tuple(values),
        )
        > 0
    )
