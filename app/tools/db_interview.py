"""面试准备/复盘 CRUD 模块"""

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
    transaction,
)
from app.tools.db_conn import _parse_json

logger = logging.getLogger("jobcraft.db.interview")


def _ensure_interview_preps_table() -> None:
    """确保 interview_preps 表存在且含全部列（schema 已由启动引导保证时短路）。

    列集合对齐 V0001 基线（submission_id / company_research_json /
    company_research_at）+ V0016 drafts：单函数调用即得完整表，
    不依赖 db_submission._ensure_interview_submission_columns 的补列守卫。
    """
    if is_schema_ready():
        return
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS interview_preps (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    job_analysis_id INT NOT NULL,
                    user_id INT DEFAULT 1,
                    round_type VARCHAR(32) NOT NULL,
                    duration VARCHAR(32) NOT NULL,
                    elevator_pitch TEXT,
                    standard_version_json JSON,
                    extended_version_json JSON,
                    ability_matrix_json JSON,
                    html_content LONGTEXT,
                    submission_id INT,
                    company_research_json JSON,
                    company_research_at DATETIME,
                    drafts JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    KEY idx_job (job_analysis_id),
                    KEY idx_submission (submission_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            # FE-PREP-01：V0001/V0016 之外的历史库缺 drafts 列，运行时守卫补列兜底
            cur.execute("SHOW COLUMNS FROM interview_preps")
            existing = {c[0] for c in cur.fetchall()}
            if "drafts" not in existing:
                cur.execute("ALTER TABLE interview_preps ADD COLUMN drafts JSON")


def insert_interview_prep(data: Dict[str, Any]) -> int:
    """插入面试准备稿,返回主键"""
    from app.tools.db_submission import _ensure_interview_submission_columns

    _ensure_interview_preps_table()
    _ensure_interview_submission_columns()
    return execute_lastrowid(
        """
INSERT INTO interview_preps
    (job_analysis_id, user_id, round_type, duration,
     elevator_pitch, standard_version_json, extended_version_json,
     ability_matrix_json, html_content, submission_id,
     company_research_json)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
""",
        (
            data["job_analysis_id"],
            data.get("user_id", 1),
            data["round_type"],
            data["duration"],
            data.get("elevator_pitch", ""),
            json.dumps(data.get("standard_version") or {}, ensure_ascii=False),
            json.dumps(data.get("extended_version") or {}, ensure_ascii=False),
            json.dumps(data.get("ability_matrix") or [], ensure_ascii=False),
            data.get("html_content", ""),
            data.get("submission_id"),
            json.dumps(data.get("company_research") or {}, ensure_ascii=False)
            if data.get("company_research")
            else None,
        ),
    )


def get_interview_prep_by_job(
    job_id: int, user_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """按 job_analysis_id 获取最新面试准备稿（可选按 user_id 过滤所有权）"""
    _ensure_interview_preps_table()
    if user_id is not None:
        sql = (
            "SELECT * FROM interview_preps WHERE job_analysis_id=%s AND user_id=%s "
            "ORDER BY created_at DESC LIMIT 1"
        )
        params: List[Any] = [job_id, user_id]
    else:
        sql = (
            "SELECT * FROM interview_preps WHERE job_analysis_id=%s "
            "ORDER BY created_at DESC LIMIT 1"
        )
        params = [job_id]
    row = query_one(sql, tuple(params))
    if not row:
        return None
    return {
        "id": row["id"],
        "job_analysis_id": row["job_analysis_id"],
        "user_id": row["user_id"],
        "round_type": row["round_type"],
        "duration": row["duration"],
        "elevator_pitch": row["elevator_pitch"] or "",
        "standard_version": _parse_json(row["standard_version_json"]) or {},
        "extended_version": _parse_json(row["extended_version_json"]) or {},
        "ability_matrix": _parse_json(row["ability_matrix_json"]) or [],
        "html_content": row["html_content"] or "",
        "submission_id": row["submission_id"] if "submission_id" in row else None,
        "company_research": _parse_json(row["company_research_json"])
        if "company_research_json" in row and row["company_research_json"]
        else None,
        "drafts": _parse_json(row.get("drafts")) or {},
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def list_interview_preps(user_id: int) -> List[Dict[str, Any]]:
    """列出用户所有面试准备稿（按时间倒序），并 JOIN job_analysis 带出公司/岗位。"""
    _ensure_interview_preps_table()
    rows = query_all(
        """
        SELECT p.id, p.job_analysis_id, p.user_id, p.round_type,
               p.duration, p.elevator_pitch,
               p.standard_version_json, p.extended_version_json,
               p.ability_matrix_json, p.html_content, p.submission_id,
               p.company_research_json, p.drafts, p.created_at,
               j.company, j.position
        FROM interview_preps p
        LEFT JOIN job_analysis j ON j.id = p.job_analysis_id
        WHERE p.user_id=%s
        ORDER BY p.created_at DESC
        """,
        (user_id,),
    )
    result = []
    for r in rows:
        result.append(
            {
                "id": r["id"],
                "job_analysis_id": r["job_analysis_id"],
                "user_id": r["user_id"],
                "round_type": r["round_type"],
                "duration": r["duration"],
                "elevator_pitch": r["elevator_pitch"] or "",
                "company": r.get("company") or "",
                "position": r.get("position") or "",
                "standard_version": _parse_json(r["standard_version_json"]) or {},
                "extended_version": _parse_json(r["extended_version_json"]) or {},
                "ability_matrix": _parse_json(r["ability_matrix_json"]) or [],
                "html_content": r["html_content"] or "",
                "submission_id": r["submission_id"] if "submission_id" in r else None,
                "company_research": _parse_json(r["company_research_json"])
                if r.get("company_research_json")
                else None,
                "drafts": _parse_json(r.get("drafts")) or {},
                "created_at": r["created_at"].isoformat()
                if r.get("created_at")
                else None,
            }
        )
    return result


def update_interview_prep_drafts(
    prep_id: int, user_id: int, drafts: Dict[str, Any]
) -> bool:
    """整体覆盖保存某份面试准备稿的应答草稿（按 id+user_id 校验所有权）。

    :param prep_id: interview_preps 主键
    :param user_id: 当前用户 id（越权写入直接不命中）
    :param drafts: 题号 -> 草稿文本的映射
    :return: True 表示已更新；False 表示记录不存在或不属于该用户
    """
    _ensure_interview_preps_table()
    row = query_one(
        "SELECT id FROM interview_preps WHERE id=%s AND user_id=%s",
        (prep_id, user_id),
    )
    if not row:
        return False
    execute(
        "UPDATE interview_preps SET drafts=%s WHERE id=%s AND user_id=%s",
        (json.dumps(drafts, ensure_ascii=False), prep_id, user_id),
    )
    return True


def get_interview_prep_ref(prep_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """按 id+user_id 取准备稿归属引用（T-M7-6 重新调研前置校验）。

    :param prep_id: interview_preps 主键
    :param user_id: 当前用户 id（越权查询不命中）
    :return: {"id", "job_analysis_id"} 或 None
    """
    _ensure_interview_preps_table()
    row = query_one(
        "SELECT id, job_analysis_id FROM interview_preps WHERE id=%s AND user_id=%s",
        (prep_id, user_id),
    )
    if not row:
        return None
    return {"id": row["id"], "job_analysis_id": row["job_analysis_id"]}


def update_interview_prep_company_research(
    prep_id: int, user_id: int, info: Dict[str, Any]
) -> bool:
    """回写准备稿的公司调研快照与调研时间（T-M7-6 force 重新调研）。

    :param prep_id: interview_preps 主键
    :param user_id: 当前用户 id（越权写入直接不命中）
    :param info: 重新调研后的 CompanyResearchInfo dict
    :return: True 表示已更新；False 表示记录不存在或不属于该用户
    """
    _ensure_interview_preps_table()
    row = query_one(
        "SELECT id FROM interview_preps WHERE id=%s AND user_id=%s",
        (prep_id, user_id),
    )
    if not row:
        return False
    execute(
        "UPDATE interview_preps SET company_research_json=%s, company_research_at=NOW() "
        "WHERE id=%s AND user_id=%s",
        (json.dumps(info, ensure_ascii=False, default=str), prep_id, user_id),
    )
    return True


# ---------------- 面试复盘 ----------------


def _ensure_interview_records_table() -> None:
    """确保 interview_records 表存在且含全部列（schema 已由启动引导保证时短路）。

    列集合对齐 V0001 基线（submission_id / round_label）+ V0023 场次骨架列
    （round_seq / occurred_at / interviewer / format / resume_version_id）：
    单函数调用即得完整表，不依赖 db_submission._ensure_interview_submission_columns
    的补列守卫。
    """
    if is_schema_ready():
        return
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS interview_records (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT DEFAULT 1,
                    title VARCHAR(300),
                    company VARCHAR(200),
                    position VARCHAR(200),
                    round_type VARCHAR(50),
                    job_analysis_id INT,
                    submission_id INT,
                    round_label VARCHAR(32) DEFAULT '',
                    round_seq INT NULL,
                    occurred_at DATETIME NULL,
                    interviewer VARCHAR(100) NULL,
                    format VARCHAR(20) NULL,
                    resume_version_id INT NULL,
                    raw_text LONGTEXT,
                    parsed_dialogue_json JSON,
                    analysis_json JSON,
                    status VARCHAR(50) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    KEY idx_user_created (user_id, created_at),
                    KEY idx_submission (submission_id),
                    KEY idx_job_analysis (job_analysis_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            # T-M7-4：V0001/V0023 之外的历史库缺场次列，运行时守卫补列兜底
            cur.execute("SHOW COLUMNS FROM interview_records")
            existing = {c[0] for c in cur.fetchall()}
            for col_ddl in (
                "round_seq INT NULL",
                "occurred_at DATETIME NULL",
                "interviewer VARCHAR(100) NULL",
                "format VARCHAR(20) NULL",
                "resume_version_id INT NULL",
            ):
                if col_ddl.split(" ")[0] not in existing:
                    cur.execute(f"ALTER TABLE interview_records ADD COLUMN {col_ddl}")


def _ensure_interview_qa_pairs_table() -> None:
    """确保 interview_qa_pairs 表存在（schema 已由启动引导保证时短路）"""
    if is_schema_ready():
        return
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS interview_qa_pairs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    record_id INT NOT NULL,
                    user_id INT DEFAULT 1,
                    sequence INT DEFAULT 0,
                    speaker VARCHAR(50),
                    start_time VARCHAR(20),
                    content TEXT,
                    is_question TINYINT DEFAULT 0,
                    question_text TEXT,
                    dimension VARCHAR(50),
                    level VARCHAR(10),
                    intent TEXT,
                    expected_answer TEXT,
                    my_answer TEXT,
                    feedback_json JSON,
                    suggestions_json JSON,
                    score INT DEFAULT 0,
                    related_card_id INT,
                    related_card_title VARCHAR(300),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    KEY idx_record (record_id),
                    KEY idx_sequence (record_id, sequence),
                    KEY idx_related_card (related_card_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )


def insert_interview_record(data: Dict[str, Any]) -> int:
    """插入面试记录，返回主键（含 T-M7-4 场次骨架列，可预建 planned 行）"""
    from app.tools.db_submission import _ensure_interview_submission_columns

    _ensure_interview_records_table()
    _ensure_interview_submission_columns()
    return execute_lastrowid(
        """
        INSERT INTO interview_records
            (user_id, title, company, position, round_type, job_analysis_id,
             raw_text, parsed_dialogue_json, analysis_json, status,
             submission_id, round_label,
             round_seq, occurred_at, interviewer, format, resume_version_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s)
        """,
        (
            data.get("user_id", 1),
            data.get("title", ""),
            data.get("company", ""),
            data.get("position", ""),
            data.get("round_type", ""),
            data.get("job_analysis_id"),
            data.get("raw_text", ""),
            json.dumps(data.get("parsed_dialogue") or [], ensure_ascii=False),
            json.dumps(data.get("analysis") or {}, ensure_ascii=False),
            data.get("status", "pending"),
            data.get("submission_id"),
            data.get("round_label", ""),
            data.get("round_seq"),
            data.get("occurred_at"),
            data.get("interviewer"),
            data.get("format"),
            data.get("resume_version_id"),
        ),
    )


def update_interview_record_session(
    record_id: int, user_id: int, fields: Dict[str, Any]
) -> bool:
    """更新场次骨架列（T-M7-4），先查归属再 UPDATE，越权返回 False 不发 UPDATE。

    仅允许白名单内的场次列（round_seq / occurred_at / interviewer / format /
    resume_version_id 及关联字段）；白名单外字段抛 ValueError（对齐
    update_interview_qa_pair_fields 的暴露原则）；空 fields 返回 True（幂等无操作）。
    """
    allowed = {
        "round_seq",
        "occurred_at",
        "interviewer",
        "format",
        "resume_version_id",
        "company",
        "position",
        "round_type",
        "round_label",
        "title",
        "job_analysis_id",
        "submission_id",
    }
    disallowed = set(fields) - allowed
    if disallowed:
        raise ValueError(f"不允许更新场次字段: {sorted(disallowed)}")
    if not fields:
        return True
    _ensure_interview_records_table()
    if not query_one(
        "SELECT id FROM interview_records WHERE id=%s AND user_id=%s",
        (record_id, user_id),
    ):
        return False
    set_clause = ", ".join(f"{k}=%s" for k in fields)
    execute(
        f"UPDATE interview_records SET {set_clause} WHERE id=%s AND user_id=%s",
        (*fields.values(), record_id, user_id),
    )
    return True


def update_interview_record_analysis(record_id: int, analysis: Dict[str, Any]) -> None:
    """更新面试记录的分析结果"""
    _ensure_interview_records_table()
    execute(
        """
        UPDATE interview_records
        SET analysis_json=%s, status=%s
        WHERE id=%s
        """,
        (
            json.dumps(analysis, ensure_ascii=False),
            "done",
            record_id,
        ),
    )


def update_interview_record_status(record_id: int, status: str) -> None:
    """更新面试记录状态（如 parsed / question_table / done）"""
    _ensure_interview_records_table()
    execute(
        "UPDATE interview_records SET status=%s WHERE id=%s",
        (status, record_id),
    )


def get_interview_record(
    record_id: int, user_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """获取单条面试记录（可选按 user_id 过滤所有权）"""
    _ensure_interview_records_table()
    sql = "SELECT * FROM interview_records WHERE id=%s"
    params: List[Any] = [record_id]
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    row = query_one(sql, tuple(params))
    if not row:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row["title"] or "",
        "company": row["company"] or "",
        "position": row["position"] or "",
        "round_type": row["round_type"] or "",
        "job_analysis_id": row["job_analysis_id"],
        "raw_text": row["raw_text"] or "",
        "parsed_dialogue": _parse_json(row["parsed_dialogue_json"]) or [],
        "analysis": _parse_json(row["analysis_json"]) or {},
        "status": row["status"] or "pending",
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        # T-M7-4 场次骨架列（历史行/未迁移库可能缺列，get 不抛错）
        "round_seq": row.get("round_seq"),
        "occurred_at": (
            row["occurred_at"].isoformat() if row.get("occurred_at") else None
        ),
        "interviewer": row.get("interviewer") or None,
        "format": row.get("format") or None,
        "resume_version_id": row.get("resume_version_id"),
    }


def list_interview_records(user_id: int = 1, limit: int = 100) -> List[Dict[str, Any]]:
    """列出用户的面试记录，按时间倒序"""
    _ensure_interview_records_table()
    rows = query_all(
        "SELECT * FROM interview_records WHERE user_id=%s ORDER BY created_at DESC LIMIT %s",
        (user_id, limit),
    )
    result = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "title": row["title"] or "",
                "company": row["company"] or "",
                "position": row["position"] or "",
                "round_type": row["round_type"] or "",
                "job_analysis_id": row["job_analysis_id"],
                "status": row["status"] or "pending",
                "created_at": row["created_at"].isoformat()
                if row.get("created_at")
                else None,
                "round_seq": row.get("round_seq"),
                "occurred_at": (
                    row["occurred_at"].isoformat() if row.get("occurred_at") else None
                ),
                "interviewer": row.get("interviewer") or None,
                "format": row.get("format") or None,
                "resume_version_id": row.get("resume_version_id"),
            }
        )
    return result


def insert_interview_qa_pair(data: Dict[str, Any]) -> int:
    """插入面试 QA 对，返回主键"""
    _ensure_interview_qa_pairs_table()
    return execute_lastrowid(
        """
        INSERT INTO interview_qa_pairs
            (record_id, user_id, sequence, speaker, start_time, content,
             is_question, question_text, dimension, level, intent,
             expected_answer, my_answer, feedback_json, suggestions_json,
             score, related_card_id, related_card_title)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            data["record_id"],
            data.get("user_id", 1),
            data.get("sequence", 0),
            data.get("speaker", ""),
            data.get("start_time", ""),
            data.get("content", ""),
            1 if data.get("is_question") else 0,
            data.get("question_text", ""),
            data.get("dimension", ""),
            data.get("level", ""),
            data.get("intent", ""),
            data.get("expected_answer", ""),
            data.get("my_answer", ""),
            json.dumps(data.get("feedback") or [], ensure_ascii=False),
            json.dumps(data.get("suggestions") or [], ensure_ascii=False),
            data.get("score", 0),
            data.get("related_card_id"),
            data.get("related_card_title", ""),
        ),
    )


def delete_interview_qa_pair(qa_pair_id: int) -> None:
    """按主键删除单个 QA 对"""
    _ensure_interview_qa_pairs_table()
    execute("DELETE FROM interview_qa_pairs WHERE id=%s", (qa_pair_id,))


def delete_interview_qa_pairs_by_record(record_id: int) -> None:
    """按面试记录 ID 删除其下所有 QA 对"""
    _ensure_interview_qa_pairs_table()
    execute("DELETE FROM interview_qa_pairs WHERE record_id=%s", (record_id,))


# 问题表重新生成时允许覆盖的列（BE-QT-01：深度研判字段必须保留）
_QA_PAIR_REGENERABLE_FIELDS = {"intent", "dimension", "level"}


def update_interview_qa_pair_fields(qa_pair_id: int, fields: Dict[str, Any]) -> bool:
    """按白名单更新单个 QA 对的可再生字段（问题表 upsert 用，不动已评估字段）。

    :param qa_pair_id: interview_qa_pairs 主键
    :param fields: 仅允许 intent / dimension / level
    :return: True 表示命中行并更新；False 表示行不存在
    :raises ValueError: 出现白名单之外的字段名（防误改 score/feedback 等）
    """
    _ensure_interview_qa_pairs_table()
    unknown = set(fields) - _QA_PAIR_REGENERABLE_FIELDS
    if unknown:
        raise ValueError(f"不允许更新的 QA 对字段: {sorted(unknown)}")
    if not fields:
        return False
    assignments = ", ".join(f"{name}=%s" for name in fields)
    sql = f"UPDATE interview_qa_pairs SET {assignments} WHERE id=%s"
    params = [*fields.values(), qa_pair_id]
    return execute(sql, tuple(params)) > 0


def list_interview_qa_pairs(record_id: int) -> List[Dict[str, Any]]:
    """列出某条面试记录下的所有 QA 对"""
    _ensure_interview_qa_pairs_table()
    rows = query_all(
        "SELECT * FROM interview_qa_pairs WHERE record_id=%s ORDER BY sequence ASC",
        (record_id,),
    )
    return [
        {
            "id": row["id"],
            "record_id": row["record_id"],
            "sequence": row["sequence"],
            "speaker": row["speaker"] or "",
            "start_time": row["start_time"] or "",
            "content": row["content"] or "",
            "is_question": bool(row["is_question"]),
            "question_text": row["question_text"] or "",
            "dimension": row["dimension"] or "",
            "level": row["level"] or "",
            "intent": row["intent"] or "",
            "expected_answer": row["expected_answer"] or "",
            "my_answer": row["my_answer"] or "",
            "feedback": _parse_json(row["feedback_json"]) or [],
            "suggestions": _parse_json(row["suggestions_json"]) or [],
            "score": row["score"] or 0,
            "related_card_id": row["related_card_id"],
            "related_card_title": row["related_card_title"] or "",
        }
        for row in rows
    ]


def delete_interview_record(record_id: int, user_id: Optional[int] = None) -> None:
    """删除面试记录及其 QA 对（可选按 user_id 过滤所有权，越权时无操作）"""
    _ensure_interview_records_table()
    _ensure_interview_qa_pairs_table()
    with transaction() as conn:
        with conn.cursor() as cur:
            sql = "DELETE FROM interview_records WHERE id=%s"
            params: List[Any] = [record_id]
            if user_id is not None:
                sql += " AND user_id=%s"
                params.append(user_id)
            cur.execute(sql, tuple(params))
            if cur.rowcount == 0:
                return
            cur.execute(
                "DELETE FROM interview_qa_pairs WHERE record_id=%s", (record_id,)
            )
