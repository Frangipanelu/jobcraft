"""投递记录 CRUD 模块"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.schemas.submission_status import effective_status, normalize_status
from app.tools.db_conn import (
    connection,
    execute,
    execute_lastrowid,
    is_schema_ready,
    query_all,
    query_one,
    query_scalar,
)
from app.tools.db_conn import _parse_json

logger = logging.getLogger("jobcraft.db.submission")


def _normalize_or_raw(value: Any) -> Any:
    """把状态归一化为枚举码；无法识别时返回原值。"""
    normalized = normalize_status(value)
    if normalized is None or normalized == value:
        return value
    return normalized.value


def _ensure_resume_submission_table() -> None:
    """确保 resume_submission 表存在（schema 已由启动引导保证时短路）

    BE-DRIFT-01 决策：`status` DEFAULT 在三处不一致——V0001 基线为
    ``'APPLIED'``、本函数为 ``'PREPARED'``、``docker/mysql/jobcraft.sql``
    为 ``'已投递'``。按 AGENTS §4.4（只加列/表，不改/删列）不改既有 DDL；
    应用层已隔离：写路径 ``insert_submission`` 恒显式 normalize 并传 status
    （DEFAULT 永不参与），读路径统一 ``effective_status`` 投影（见
    ``app/schemas/submission_status.py``）。统一 DEFAULT 需独立迁移决策。

    T-M6-7：``resume_version_id`` 归档列（V0027）——建表语句直接声明，
    存量表由建表后的 SHOW COLUMNS 守卫补列（同款守卫见
    ``db_resume_version._ensure_resume_version_table`` 的 LIKE-probe +
    合并 ALTER），两路径幂等。
    """
    if is_schema_ready():
        return
    with connection() as conn:
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
                    resume_suggestions JSON,
                    resume_version_id INT NULL,
                    status           VARCHAR(32) DEFAULT 'PREPARED',
                    notes            TEXT,
                    is_manual        TINYINT(1) DEFAULT 0,
                    delivered        TINYINT(1) DEFAULT 0,
                    is_active        TINYINT(1) DEFAULT 1,
                    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    KEY idx_user_status (user_id, status),
                    KEY idx_job_analysis (job_analysis_id),
                    KEY idx_resume_version (resume_version_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            # T-M6-7：存量表缺归档列时守卫补列（V0027 未迁移环境的运行时兜底）
            cur.execute("SHOW COLUMNS FROM resume_submission LIKE 'resume_version_id'")
            if not cur.fetchall():
                cur.execute(
                    "ALTER TABLE resume_submission "
                    "ADD COLUMN resume_version_id INT NULL, "
                    "ADD KEY idx_resume_version (resume_version_id)"
                )


def _ensure_interview_submission_columns() -> None:
    """为 interview_preps 和 interview_records 表加 submission_id 字段（schema 已由启动引导保证时短路）"""
    if is_schema_ready():
        return
    with connection() as conn:
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
    """创建投递记录。

    P11-a：创建 ≠ 投递，默认状态为 `PREPARED`（待投递）；仅用户确认投递
    （delivered=1）后状态才是 `APPLIED`（已投递）。
    """
    _ensure_resume_submission_table()
    _ensure_interview_submission_columns()
    status = normalize_status(data.get("status", "PREPARED"))
    if status is None:
        status = normalize_status("PREPARED")
    submission_id = execute_lastrowid(
        """
        INSERT INTO resume_submission
            (user_id, job_analysis_id, position, company, jd_text,
             resume_markdown, resume_file_path, card_version_ids, status, notes, is_manual, delivered)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
            data.get("delivered", 0),
        ),
    )
    # P4-4a：投递记录挂到 Job 实体（find-or-create，前端据此缓存 jobId）
    _attach_job_entity(data, submission_id, status.value)
    return submission_id


def _attach_job_entity(
    data: Dict[str, Any], submission_id: int, status_value: str
) -> Optional[int]:
    """P4-4a：find-or-create 岗位并回填投递/分析归属（失败降级，不阻断创建）。"""
    from app.tools import db_job_entity

    try:
        job_id = db_job_entity.find_or_create_job(
            user_id=data.get("user_id", 1),
            position=data.get("position") or "",
            company=data.get("company"),
            job_analysis_id=data.get("job_analysis_id"),
            submission_id=submission_id,
        )
        if job_id and status_value:
            from app.tools.db_conn import execute

            execute("UPDATE job SET status=%s WHERE id=%s", (status_value, job_id))
        return job_id
    except Exception as e:
        logger.warning("Job 实体归属失败（submission_id=%s）: %s", submission_id, e)
        return None


def get_submission(
    submission_id: int, user_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    _ensure_resume_submission_table()
    # P4-4a：LEFT JOIN job 取岗位 id（旧库无 job 表时降级为原查询）
    sql = (
        "SELECT s.*, j.id AS job_id FROM resume_submission s "
        "LEFT JOIN job j ON j.submission_id = s.id AND j.is_active = 1 "
        "WHERE s.id=%s AND s.is_active=1"
    )
    params: List[Any] = [submission_id]
    if user_id is not None:
        sql += " AND s.user_id=%s"
        params.append(user_id)
    try:
        row = query_one(sql, tuple(params))
    except Exception as e:
        logger.warning(
            "岗位关联读取失败（submission_id=%s，回落无 job_id）: %s", submission_id, e
        )
        fallback = "SELECT * FROM resume_submission WHERE id=%s AND is_active=1"
        fallback_params: List[Any] = [submission_id]
        if user_id is not None:
            fallback += " AND user_id=%s"
            fallback_params.append(user_id)
        row = query_one(fallback, tuple(fallback_params))
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
        # FE-RESUME-02：AI 优化建议列表（列缺失/为空时回退 []，旧库行兼容）
        "resume_suggestions": _parse_json(row.get("resume_suggestions")) or [],
        # T-M6-7：归档的简历版本 id（旧库未迁移缺列时为 None，不炸）
        "resume_version_id": row.get("resume_version_id"),
        "status": effective_status(row["status"], bool(row.get("delivered"))),
        # P4-4a：岗位实体 id（前端创建岗位后缓存用）
        "job_id": row.get("job_id"),
        "notes": row["notes"] or "",
        "is_manual": bool(row.get("is_manual")),
        "delivered": bool(row.get("delivered")),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def list_submissions(user_id: int = 1, limit: int = 50) -> List[Dict[str, Any]]:
    _ensure_resume_submission_table()
    rows = query_all(
        "SELECT id, position, company, status, delivered, job_analysis_id, "
        "created_at, updated_at "
        "FROM resume_submission WHERE user_id=%s AND is_active=1 "
        "ORDER BY updated_at DESC LIMIT %s",
        (user_id, limit),
    )
    result = []
    for r in rows:
        result.append(
            {
                "id": r["id"],
                "position": r["position"],
                "company": r["company"] or "",
                "status": effective_status(r["status"], bool(r.get("delivered"))),
                "delivered": bool(r.get("delivered")),
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


def get_submission_by_analysis(
    job_analysis_id: int, user_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """根据 job_analysis_id 查找已存在的投递记录"""
    _ensure_resume_submission_table()
    sql = "SELECT * FROM resume_submission WHERE job_analysis_id=%s AND is_active=1"
    params: List[Any] = [job_analysis_id]
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    sql += " ORDER BY id DESC LIMIT 1"
    row = query_one(sql, tuple(params))
    if not row:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "job_analysis_id": row["job_analysis_id"],
        "position": row["position"],
        "company": row["company"],
        "jd_text": row["jd_text"] or "",
        "resume_markdown": row["resume_markdown"] or "",
        "resume_file_path": row["resume_file_path"] or "",
        "card_version_ids": json.loads(row["card_version_ids"] or "[]"),
        "resume_suggestions": _parse_json(row.get("resume_suggestions")) or [],
        # T-M6-7：归档的简历版本 id（旧库未迁移缺列时为 None，不炸）
        "resume_version_id": row.get("resume_version_id"),
        # BE-DRIFT-01：与 get_submission/list_submissions 一致，按 delivered
        # 事实投影（存量 APPLIED+delivered=0 → PREPARED），不透传裸存量值
        "status": effective_status(row["status"], bool(row.get("delivered"))),
        "notes": row["notes"] or "",
        "is_manual": row.get("is_manual", 0),
        "delivered": bool(row.get("delivered")),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def archive_selected_version(submission_id: int, user_id: int) -> Optional[int]:
    """T-M6-7：把用户当前选中的简历版本快照归档进投递记录（标记投递时）。

    分支（跳过类分支均返回 None 不炸，DB 异常向上抛由 API 钩子容忍）：

    - 投递不存在 / 无归属（``get_submission`` 为 None）→ None（越权）；
    - 行已有 ``resume_version_id`` → 幂等返回现值，不覆写（首次投递已归档）；
    - ``job_analysis_id`` 为空 → 经 job 实体回查（手工投递等场景），仍无 →
      logger.info 后 None（无分析无从选版本）；
    - 该分析下无任何简历版本 → logger.info 后 None；
    - 成功 → 单条 UPDATE 拷贝 ``resume_markdown`` 并写入 ``resume_version_id``。

    :param submission_id: 投递记录 id
    :param user_id: 归属校验（越权返回 None）
    :return: 归档的简历版本 id；已归档时为既有版本 id；跳过时 None
    """
    # 函数内局部导入：避免 db_submission ↔ db_resume_version/db_job_entity 循环依赖
    from app.tools import db_job_entity, db_resume_version

    submission = get_submission(submission_id, user_id)
    if not submission:
        logger.info(
            "投递归档跳过：投递记录不存在或无归属（submission_id=%s, user_id=%s）",
            submission_id,
            user_id,
        )
        return None
    existing = submission.get("resume_version_id")
    if existing is not None:
        return int(existing)
    analysis_id = submission.get("job_analysis_id")
    if not analysis_id:
        job = db_job_entity.get_job_by_submission(submission_id, user_id)
        analysis_id = job.get("job_analysis_id") if job else None
    if not analysis_id:
        logger.info(
            "投递归档跳过：投递无岗位分析归属（submission_id=%s）", submission_id
        )
        return None
    version = db_resume_version.get_selected_resume_version(user_id, analysis_id)
    if not version:
        logger.info(
            "投递归档跳过：该分析下无可归档简历版本（submission_id=%s, analysis_id=%s）",
            submission_id,
            analysis_id,
        )
        return None
    execute(
        "UPDATE resume_submission SET resume_markdown=%s, resume_version_id=%s "
        "WHERE id=%s AND user_id=%s AND is_active=1",
        (version.get("resume_markdown"), version["id"], submission_id, user_id),
    )
    return version["id"]


def update_submission(
    submission_id: int, updates: Dict[str, Any], user_id: Optional[int] = None
) -> bool:
    """更新投递记录。

    P4-2：`jd_text` 已从可更新字段中移除——原始 JD 以 raw_jd 不可变快照为准，
    覆写会使分析结果失去可复核依据；即使调用方误传也不落库。
    """
    _ensure_resume_submission_table()
    field_map = {
        "position": "position",
        "company": "company",
        "resume_markdown": "resume_markdown",
        "resume_file_path": "resume_file_path",
        "status": "status",
        "notes": "notes",
        "delivered": "delivered",
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
    if "resume_suggestions" in updates and updates["resume_suggestions"] is not None:
        # FE-RESUME-02：JSON 序列化写入（同 card_version_ids）；[] 表示清空，仅拒 None
        sets.append("resume_suggestions=%s")
        values.append(json.dumps(updates["resume_suggestions"], ensure_ascii=False))
    if "job_analysis_id" in updates:
        sets.append("job_analysis_id=%s")
        values.append(updates["job_analysis_id"])
    if not sets:
        return False
    values.append(submission_id)
    sql = (
        "UPDATE resume_submission SET "
        + ", ".join(sets)
        + " WHERE id=%s AND is_active=1"
    )
    if user_id is not None:
        sql += " AND user_id=%s"
        values.append(user_id)
    updated = execute(sql, tuple(values)) > 0
    if updated:
        # P4-4a：状态/投递标记变更同步到 Job 实体（岗位聚合根状态不落后于投递记录）
        _sync_job_entity(submission_id, updates)
    return updated


def _sync_job_entity(submission_id: int, updates: Dict[str, Any]) -> Optional[int]:
    """把投递状态与分析归属同步到 Job 实体（失败降级，不阻断更新）。"""
    from app.tools import db_job_entity

    status = updates.get("status")
    delivered = updates.get("delivered")
    job_analysis_id = updates.get("job_analysis_id")
    if status is None and delivered is None and job_analysis_id is None:
        return None
    status_value: Optional[str] = None
    if status is not None:
        normalized = normalize_status(status)
        status_value = normalized.value if normalized else str(status)
    elif delivered is not None:
        # 仅确认投递标记时，按存量状态 + delivered 推导岗位状态（P11-a 语义）
        row = query_one(
            "SELECT status FROM resume_submission WHERE id=%s", (submission_id,)
        )
        if row and row.get("status"):
            current = normalize_status(row["status"])
            current_value = current.value if current else str(row["status"])
            status_value = effective_status(current_value, bool(delivered))
    try:
        return db_job_entity.sync_submission_job(
            submission_id,
            status=status_value,
            job_analysis_id=job_analysis_id,
        )
    except Exception as e:
        logger.warning("Job 实体状态同步失败（submission_id=%s）: %s", submission_id, e)
        return None


def delete_submission(submission_id: int, user_id: Optional[int] = None) -> bool:
    """删除投递记录（软删：is_active=0，保留历史，防投递/复盘断链）。

    按 DMV2 §55（删除优先归档而非物理删除）不再级联物理删除关联的面试记录，
    历史投递与复盘保留；查询侧统一过滤 is_active=1。
    """
    _ensure_resume_submission_table()
    sql = "UPDATE resume_submission SET is_active=0 WHERE id=%s"
    params: List[Any] = [submission_id]
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    return execute(sql, tuple(params)) > 0


def get_submission_prep_count(submission_id: int) -> int:
    from app.tools.db_interview import _ensure_interview_preps_table

    _ensure_interview_preps_table()
    return query_scalar(
        "SELECT COUNT(*) FROM interview_preps WHERE submission_id=%s",
        (submission_id,),
    )


def list_interview_records_by_submission(
    submission_id: int, user_id: Optional[int] = None, limit: int = 5
) -> List[Dict[str, Any]]:
    """按 submission_id 获取面试记录（可选按 user_id 过滤所有权）"""
    from app.tools.db_interview import _ensure_interview_records_table

    _ensure_interview_records_table()
    if user_id is not None:
        sql = (
            "SELECT * FROM interview_records WHERE submission_id=%s AND user_id=%s "
            "ORDER BY created_at DESC LIMIT %s"
        )
        params: List[Any] = [submission_id, user_id, limit]
    else:
        sql = (
            "SELECT * FROM interview_records WHERE submission_id=%s "
            "ORDER BY created_at DESC LIMIT %s"
        )
        params = [submission_id, limit]
    rows = query_all(sql, tuple(params))
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
    return query_scalar(
        "SELECT COUNT(*) FROM interview_records WHERE submission_id=%s",
        (submission_id,),
    )


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
                # P4-4a：岗位实体 id（前端缓存 jobId）
                "job_id": full.get("job_id"),
                "has_analysis": ja_id is not None,
                "card_version_count": cv_count,
                "card_count": card_count,
                "has_resume": bool(full.get("resume_markdown")),
                "is_manual": full.get("is_manual", False),
                "delivered": full.get("delivered", False),
                "prep_count": get_submission_prep_count(sid),
                "review_count": get_submission_review_count(sid),
                "created_at": full["created_at"],
                "updated_at": full["updated_at"],
            }
        )
    return result
