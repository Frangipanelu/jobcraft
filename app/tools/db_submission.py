"""投递记录 CRUD 模块"""

import json
import logging
from typing import Any, Dict, List, Optional

from mysql.connector import connect

from app.schemas.submission_status import normalize_status
from app.tools.db_config import _jc_config
from app.tools.db_tools import _parse_json

logger = logging.getLogger("jobcraft.db.submission")


def _normalize_or_raw(value: Any) -> Any:
    """把状态归一化为枚举码；无法识别时返回原值。"""
    normalized = normalize_status(value)
    if normalized is None or normalized == value:
        return value
    return normalized.value


def _ensure_resume_submission_table() -> None:
    """确保 resume_submission 表存在"""
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS resume_submission (
                    id               INT AUTO_INCREMENT PRIMARY KEY,
                    user_id          INT DEFAULT 1,
                    job_analysis_id  INT,
                    position         VARCHAR(200) NOT NULL,
                    company          VARCHAR(200) DEFAULT '',
                    jd_text          LONGTEXT,
                    resume_markdown  LONGTEXT,
                    resume_file_path VARCHAR(500),
                    card_version_ids JSON,
                    status           VARCHAR(32) DEFAULT 'APPLIED',
                    notes            TEXT,
                    is_manual        TINYINT(1) DEFAULT 0,
                    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    KEY idx_user_status (user_id, status),
                    KEY idx_job_analysis (job_analysis_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )


def _ensure_interview_submission_columns() -> None:
    """为 interview_preps 和 interview_records 表加 submission_id 字段"""
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM interview_preps")
            existing = {c[0] for c in cur.fetchall()}
            if "submission_id" not in existing:
                cur.execute(
                    "ALTER TABLE interview_preps ADD COLUMN submission_id INT, ADD KEY idx_submission (submission_id)"
                )
            if "company_research_json" not in existing:
                cur.execute(
                    "ALTER TABLE interview_preps ADD COLUMN company_research_json JSON"
                )
            if "company_research_at" not in existing:
                cur.execute(
                    "ALTER TABLE interview_preps ADD COLUMN company_research_at DATETIME"
                )

            cur.execute("SHOW COLUMNS FROM interview_records")
            existing = {c[0] for c in cur.fetchall()}
            if "submission_id" not in existing:
                cur.execute(
                    "ALTER TABLE interview_records ADD COLUMN submission_id INT, ADD KEY idx_submission (submission_id)"
                )
            if "round_label" not in existing:
                cur.execute(
                    "ALTER TABLE interview_records ADD COLUMN round_label VARCHAR(32) DEFAULT ''"
                )


def insert_submission(data: Dict[str, Any]) -> int:
    _ensure_resume_submission_table()
    _ensure_interview_submission_columns()
    config = _jc_config()
    status = normalize_status(data.get("status", "APPLIED"))
    if status is None:
        status = normalize_status("APPLIED")
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO resume_submission
                    (user_id, job_analysis_id, position, company, jd_text,
                     resume_markdown, resume_file_path, card_version_ids, status, notes, is_manual)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    data.get("user_id", 1),
                    data.get("job_analysis_id"),
                    data["position"],
                    data.get("company", ""),
                    data.get("jd_text", ""),
                    data.get("resume_markdown"),
                    data.get("resume_file_path"),
                    json.dumps(data.get("card_version_ids") or [], ensure_ascii=False),
                    status.value,
                    data.get("notes"),
                    data.get("is_manual", 0),
                ),
            )
            return cur.lastrowid


def get_submission(
    submission_id: int, user_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    _ensure_resume_submission_table()
    config = _jc_config()
    sql = "SELECT * FROM resume_submission WHERE id=%s"
    params: List[Any] = [submission_id]
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(sql, tuple(params))
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "job_analysis_id": row["job_analysis_id"],
        "position": row["position"],
        "company": row["company"] or "",
        "jd_text": row["jd_text"] or "",
        "resume_markdown": row["resume_markdown"] or "",
        "resume_file_path": row["resume_file_path"],
        "card_version_ids": _parse_json(row["card_version_ids"]) or [],
        "status": _normalize_or_raw(row["status"]),
        "notes": row["notes"] or "",
        "is_manual": bool(row.get("is_manual")),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def list_submissions(user_id: int = 1, limit: int = 50) -> List[Dict[str, Any]]:
    _ensure_resume_submission_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT id, position, company, status, job_analysis_id, created_at, updated_at "
                "FROM resume_submission WHERE user_id=%s ORDER BY updated_at DESC LIMIT %s",
                (user_id, limit),
            )
            rows = cur.fetchall()
    result = []
    for r in rows:
        result.append(
            {
                "id": r["id"],
                "position": r["position"],
                "company": r["company"] or "",
                "status": _normalize_or_raw(r["status"]),
                "job_analysis_id": r["job_analysis_id"],
                "created_at": r["created_at"].isoformat()
                if r.get("created_at")
                else None,
                "updated_at": r["updated_at"].isoformat()
                if r.get("updated_at")
                else None,
            }
        )
    return result


def update_submission(
    submission_id: int, updates: Dict[str, Any], user_id: Optional[int] = None
) -> bool:
    _ensure_resume_submission_table()
    field_map = {
        "position": "position",
        "company": "company",
        "jd_text": "jd_text",
        "resume_markdown": "resume_markdown",
        "resume_file_path": "resume_file_path",
        "status": "status",
        "notes": "notes",
    }
    sets: List[str] = []
    values: List[Any] = []
    for k, col in field_map.items():
        if k in updates and updates[k] is not None:
            if k == "status":
                normalized = normalize_status(updates[k])
                sets.append(f"{col}=%s")
                values.append(normalized.value if normalized else updates[k])
            else:
                sets.append(f"{col}=%s")
                values.append(updates[k])
    if "card_version_ids" in updates:
        sets.append("card_version_ids=%s")
        values.append(json.dumps(updates["card_version_ids"], ensure_ascii=False))
    if "job_analysis_id" in updates:
        sets.append("job_analysis_id=%s")
        values.append(updates["job_analysis_id"])
    if not sets:
        return False
    values.append(submission_id)
    config = _jc_config()
    sql = "UPDATE resume_submission SET " + ", ".join(sets) + " WHERE id=%s"
    if user_id is not None:
        sql += " AND user_id=%s"
        values.append(user_id)
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(values))
            return cur.rowcount > 0


def delete_submission(submission_id: int, user_id: Optional[int] = None) -> bool:
    _ensure_resume_submission_table()
    config = _jc_config()
    sql = "DELETE FROM resume_submission WHERE id=%s"
    params: List[Any] = [submission_id]
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.rowcount > 0


def get_submission_prep_count(submission_id: int) -> int:
    from app.tools.db_interview import _ensure_interview_preps_table

    _ensure_interview_preps_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM interview_preps WHERE submission_id=%s",
                (submission_id,),
            )
            return cur.fetchone()[0]


def list_interview_records_by_submission(
    submission_id: int, user_id: Optional[int] = None, limit: int = 5
) -> List[Dict[str, Any]]:
    """按 submission_id 获取面试记录（可选按 user_id 过滤所有权）"""
    from app.tools.db_interview import _ensure_interview_records_table

    _ensure_interview_records_table()
    config = _jc_config()
    sql = (
        "SELECT * FROM interview_records WHERE submission_id=%s "
        "ORDER BY created_at DESC LIMIT %s"
    )
    params: List[Any] = [submission_id, limit]
    if user_id is not None:
        sql = (
            "SELECT * FROM interview_records WHERE submission_id=%s AND user_id=%s "
            "ORDER BY created_at DESC LIMIT %s"
        )
        params = [submission_id, user_id, limit]
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
    result = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "title": row["title"] or "",
                "company": row["company"] or "",
                "position": row["position"] or "",
                "round_type": row["round_type"] or "",
                "analysis_json": _parse_json(row.get("analysis_json")) or {},
                "created_at": row["created_at"].isoformat()
                if row.get("created_at")
                else None,
            }
        )
    return result


def get_submission_review_count(submission_id: int) -> int:
    from app.tools.db_interview import _ensure_interview_records_table

    _ensure_interview_records_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM interview_records WHERE submission_id=%s",
                (submission_id,),
            )
            return cur.fetchone()[0]


def get_dashboard(user_id: int = 1) -> List[Dict[str, Any]]:
    """返回主页所需数据：投递列表 + 各按钮状态"""
    from app.tools.db_experience import get_card_versions_by_source, list_cards

    subs = list_submissions(user_id)
    card_count = len(list_cards(user_id))
    result = []
    for s in subs:
        full = get_submission(s["id"])
        if not full:
            continue
        # 只展示已有简历的投递（投递记录 = 简历已生成）
        if not full.get("resume_markdown"):
            continue
        sid = s["id"]
        ja_id = s.get("job_analysis_id")
        cv_count = 0
        if ja_id:
            versions = get_card_versions_by_source("job_analysis", ja_id)
            cv_count = len(versions)
        result.append(
            {
                "id": sid,
                "position": full["position"],
                "company": full["company"],
                "status": full["status"],
                "job_analysis_id": ja_id,
                "has_analysis": ja_id is not None,
                "card_version_count": cv_count,
                "card_count": card_count,
                "has_resume": True,
                "is_manual": full.get("is_manual", False),
                "prep_count": get_submission_prep_count(sid),
                "review_count": get_submission_review_count(sid),
                "created_at": full["created_at"],
                "updated_at": full["updated_at"],
            }
        )
    return result
