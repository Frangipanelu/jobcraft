"""RawJD 不可变快照 CRUD 模块

岗位对象模型中的 RawJD：一条岗位分析所依据的原始 JD 文本快照。
按 P4-2 约定，快照**只增不改**——因此本模块不提供 update/delete 任何写路径，
原始 JD 一旦入库即不可覆写（避免 PATCH 投递记录改写 jd_text 后分析结果失去可复核依据）。

`job_analysis.jd_text` / `resume_submission.jd_text` 仍保留原列（不改既有表结构），
但它们的角色降级为「当前展示副本」，权威原文以本表快照为准。
"""

import logging
from typing import Any, Dict, List, Optional

from app.tools.db_conn import (
    connection,
    execute_lastrowid,
    is_schema_ready,
    query_all,
    query_one,
)

logger = logging.getLogger("jobcraft.db.raw_jd")

# 允许的快照来源（保持与 V0012 source 列默认一致）
RAW_JD_SOURCES = ("job_analysis", "split_jd", "manual")


def _ensure_raw_jd_table() -> None:
    """确保 raw_jd 表存在（schema 已由启动引导保证时短路）"""
    if is_schema_ready():
        return
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS raw_jd (
                    id               INT AUTO_INCREMENT PRIMARY KEY,
                    user_id          INT DEFAULT 1,
                    job_analysis_id  INT,
                    source           VARCHAR(32) DEFAULT 'job_analysis',
                    jd_text          LONGTEXT NOT NULL,
                    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    KEY idx_raw_jd_job (job_analysis_id),
                    KEY idx_raw_jd_user (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )


def insert_raw_jd(
    jd_text: str,
    user_id: int = 1,
    job_analysis_id: Optional[int] = None,
    source: str = "job_analysis",
) -> int:
    """写入一条 RawJD 不可变快照。

    :param jd_text: 原始 JD 原文（空文本不落快照，返回 0）。
    :param user_id: 归属用户。
    :param job_analysis_id: 归属岗位分析 id；split JD 阶段尚未落 job_analysis 时可为空。
    :param source: 快照来源，取值见 :data:`RAW_JD_SOURCES`，非法值回落 `job_analysis`。
    :return: 新快照 id；`jd_text` 为空时返回 0（不产生空快照）。
    """
    _ensure_raw_jd_table()
    text = (jd_text or "").strip()
    if not text:
        return 0
    return execute_lastrowid(
        """
        INSERT INTO raw_jd (user_id, job_analysis_id, source, jd_text)
        VALUES (%s,%s,%s,%s)
        """,
        (
            user_id,
            job_analysis_id,
            source if source in RAW_JD_SOURCES else "job_analysis",
            text,
        ),
    )


def _row_to_raw_jd(row: Any) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "job_analysis_id": row.get("job_analysis_id"),
        "source": row.get("source") or "job_analysis",
        "jd_text": row["jd_text"] or "",
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def get_raw_jd(
    raw_jd_id: int, user_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """单条快照查询（可选按 user_id 过滤所有权）。"""
    _ensure_raw_jd_table()
    sql = "SELECT * FROM raw_jd WHERE id=%s"
    params: List[Any] = [raw_jd_id]
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    row = query_one(sql, tuple(params))
    if not row:
        return None
    return _row_to_raw_jd(row)


def list_raw_jds(
    user_id: int, job_analysis_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """列出某用户的快照（可按岗位分析过滤；最新在前）。"""
    _ensure_raw_jd_table()
    sql = "SELECT * FROM raw_jd WHERE user_id=%s"
    params: List[Any] = [user_id]
    if job_analysis_id is not None:
        sql += " AND job_analysis_id=%s"
        params.append(job_analysis_id)
    sql += " ORDER BY created_at DESC, id DESC"
    return [_row_to_raw_jd(r) for r in query_all(sql, tuple(params))]
