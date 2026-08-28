"""岗位分析 CRUD 模块"""

import json
import logging
from typing import Any, Dict, List, Optional

from mysql.connector import connect

from app.tools.db_tools import _jc_config, _parse_json

logger = logging.getLogger("jobcraft.db.job")


def _ensure_job_analysis_columns() -> None:
    """为 job_analysis 表增加 dimension_requirements 字段（兼容旧库）"""
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM job_analysis")
            existing = {c[0] for c in cur.fetchall()}
            if "dimension_requirements" not in existing:
                cur.execute(
                    "ALTER TABLE job_analysis ADD COLUMN dimension_requirements JSON"
                )


def insert_job_analysis(data: Dict[str, Any]) -> int:
    """插入一条岗位分析记录,返回主键"""
    _ensure_job_analysis_columns()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO job_analysis
                    (user_id, company, position, jd_text,
                     jd_requirements, match_score, gap_analysis,
                     dimension_requirements)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    data.get("user_id", 1),
                    data["company"],
                    data["position"],
                    data["jd_text"],
                    json.dumps(data.get("jd_requirements") or {}, ensure_ascii=False),
                    data.get("match_score"),
                    json.dumps(data.get("gap_analysis") or [], ensure_ascii=False),
                    json.dumps(
                        data.get("dimension_requirements") or [], ensure_ascii=False
                    ),
                ),
            )
            return cur.lastrowid


def get_job_analysis(job_id: int) -> Optional[Dict[str, Any]]:
    """按主键获取岗位分析记录"""
    _ensure_job_analysis_columns()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT * FROM job_analysis WHERE id=%s", (job_id,))
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "company": row["company"],
        "position": row["position"],
        "jd_text": row["jd_text"],
        "jd_requirements": _parse_json(row["jd_requirements"]) or {},
        "match_score": float(row["match_score"])
        if row.get("match_score") is not None
        else None,
        "gap_analysis": _parse_json(row["gap_analysis"]) or [],
        "dimension_requirements": _parse_json(row["dimension_requirements"]) or [],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def list_job_analyses(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """列出用户历史岗位分析,按时间倒序"""
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT id, company, position, match_score, created_at "
                "FROM job_analysis WHERE user_id=%s ORDER BY created_at DESC LIMIT %s",
                (user_id, limit),
            )
            rows = cur.fetchall()
    for r in rows:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
        if r.get("match_score") is not None:
            r["match_score"] = float(r["match_score"])
    return rows


def delete_job_analysis(job_id: int) -> bool:
    """删除岗位分析记录（同时清理关联的 mapping 与 prep 记录）"""
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM experience_job_mapping WHERE job_analysis_id=%s", (job_id,)
            )
            cur.execute(
                "DELETE FROM interview_preps WHERE job_analysis_id=%s", (job_id,)
            )
            cur.execute("DELETE FROM job_analysis WHERE id=%s", (job_id,))
            return cur.rowcount > 0


def upsert_job_mapping(job_id: int, experience_id: int) -> None:
    """
    写入经历-岗位关联 (用 INSERT IGNORE 避免重复)

    同一 (experience_id, job_analysis_id) 多次保存时不会报错
    """
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT IGNORE INTO experience_job_mapping
                    (experience_id, job_analysis_id, selected)
                VALUES (%s, %s, 1)
                """,
                (experience_id, job_id),
            )


def get_selected_card_ids_by_job(job_id: int) -> List[int]:
    """根据岗位分析 ID 获取当时选中的经历卡 ID 列表"""
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT experience_id FROM experience_job_mapping WHERE job_analysis_id=%s AND selected=1",
                (job_id,),
            )
            return [row[0] for row in cur.fetchall()]
