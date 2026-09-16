"""底座简历（历史版本）CRUD 模块

记录用户上传的"底座简历"元信息（文件名/大小/解析卡数/格式/标签/默认标记），
供「底座简历与历史版本管理」页在刷新后恢复列表。
仅存元数据，简历本体以解析出的 ExperienceCard 形式存在经历资产库。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.tools.db_conn import (
    connection,
    execute,
    execute_lastrowid,
    is_schema_ready,
    query_all,
    query_one,
)
from app.tools.db_conn import _parse_json

logger = logging.getLogger("jobcraft.db.base_resume")


def _ensure_base_resume_table() -> None:
    """确保 base_resume 表存在（schema 已由启动引导保证时短路）"""
    if is_schema_ready():
        return
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS base_resume (
                    id               INT AUTO_INCREMENT PRIMARY KEY,
                    user_id          INT NOT NULL,
                    name             VARCHAR(255) NOT NULL,
                    file_size        VARCHAR(50) DEFAULT '',
                    format           VARCHAR(16) DEFAULT 'docx',
                    parsed_count     INT DEFAULT 0,
                    tags             JSON,
                    is_default       TINYINT(1) DEFAULT 0,
                    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    KEY idx_user (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )


def create_base_resume(data: Dict[str, Any]) -> int:
    """创建一条底座简历记录。

    :param data: 含 user_id/name/file_size/format/parsed_count/tags/is_default。
    :return: 新记录 id。
    """
    _ensure_base_resume_table()
    return execute_lastrowid(
        """
        INSERT INTO base_resume
            (user_id, name, file_size, format, parsed_count, tags, is_default)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            data["user_id"],
            data.get("name", "上传简历"),
            data.get("file_size", ""),
            data.get("format", "docx"),
            data.get("parsed_count", 0),
            json.dumps(data.get("tags") or [], ensure_ascii=False),
            int(bool(data.get("is_default", False))),
        ),
    )


def _row_to_base_resume(row: Any) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "name": row["name"] or "",
        "file_size": row["file_size"] or "",
        "format": row["format"] or "docx",
        "parsed_count": int(row["parsed_count"] or 0),
        "tags": _parse_json(row["tags"]) or [],
        "is_default": bool(row.get("is_default")),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def list_base_resumes(user_id: int) -> List[Dict[str, Any]]:
    """列出某用户的全部底座简历（最新在前）。"""
    _ensure_base_resume_table()
    rows = query_all(
        "SELECT * FROM base_resume WHERE user_id=%s ORDER BY created_at DESC",
        (user_id,),
    )
    return [_row_to_base_resume(r) for r in rows]


def get_base_resume(
    resume_id: int, user_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """单条查询（可选按 user_id 过滤所有权）。"""
    _ensure_base_resume_table()
    sql = "SELECT * FROM base_resume WHERE id=%s"
    params: List[Any] = [resume_id]
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    row = query_one(sql, tuple(params))
    if not row:
        return None
    return _row_to_base_resume(row)


def delete_base_resume(resume_id: int, user_id: Optional[int] = None) -> bool:
    """删除一条底座简历记录。"""
    _ensure_base_resume_table()
    sql = "DELETE FROM base_resume WHERE id=%s"
    params: List[Any] = [resume_id]
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    return execute(sql, tuple(params)) > 0


def set_default_base_resume(resume_id: int, user_id: int) -> bool:
    """把指定记录设为默认（同一用户的其余记录取消默认）。"""
    _ensure_base_resume_table()
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE base_resume SET is_default=0 WHERE user_id=%s", (user_id,)
            )
            cur.execute(
                "UPDATE base_resume SET is_default=1 WHERE id=%s AND user_id=%s",
                (resume_id, user_id),
            )
            return cur.rowcount > 0
