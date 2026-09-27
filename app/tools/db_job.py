"""岗位分析 CRUD 模块"""

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

logger = logging.getLogger("jobcraft.db.job")


def _ensure_job_analysis_columns() -> None:
    """为 job_analysis 表补齐运行期所需字段（schema 已由启动引导保证时短路）。

    迁移基线：dimension_requirements / is_active 见 V0001/V0007；
    P4-1 分析物五列（ats_profile / suggestions / per_card_scores / match_level /
    analysis_version）见 V0011。此处保留 SHOW COLUMNS + ADD COLUMN 作为
    未迁移环境的降级兜底（行为与迁移一致，只加不改，AGENTS §4.4）。
    """
    if is_schema_ready():
        return
    additive_columns = (
        ("dimension_requirements", "JSON"),
        ("is_active", "TINYINT(1) DEFAULT 1"),
        ("ats_profile", "JSON"),
        ("suggestions", "JSON"),
        ("per_card_scores", "JSON"),
        ("match_level", "VARCHAR(32)"),
        ("analysis_version", "VARCHAR(32)"),
        # P4-4a：分析记录归属岗位（V0013 加列，runtime 兜底同步）
        ("job_id", "INT"),
    )
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM job_analysis")
            existing = {c[0] for c in cur.fetchall()}
            for column, ddl_type in additive_columns:
                if column not in existing:
                    cur.execute(
                        f"ALTER TABLE job_analysis ADD COLUMN {column} {ddl_type}"
                    )


def insert_job_analysis(data: Dict[str, Any]) -> int:
    """插入一条岗位分析记录,返回主键。

    P4-1：ats_profile / suggestions / per_card_scores / match_level /
    analysis_version 五列随插入落库，使历史列表（list_job_analyses）与
    单条读取（get_job_analysis）都能还原完整分析物。

    P4-4a：插入后按 (user_id, company, position) find-or-create Job 实体并回填
    ``job_analysis.job_id``；岗位归属失败不阻断分析落库（降级告警）。
    """
    _ensure_job_analysis_columns()
    analysis_id = execute_lastrowid(
        """
        INSERT INTO job_analysis
            (user_id, company, position, jd_text,
             jd_requirements, match_score, gap_analysis,
             dimension_requirements,
             ats_profile, suggestions, per_card_scores, match_level,
             analysis_version)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            data.get("user_id", 1),
            data["company"],
            data["position"],
            data["jd_text"],
            json.dumps(data.get("jd_requirements") or {}, ensure_ascii=False),
            data.get("match_score"),
            json.dumps(data.get("gap_analysis") or [], ensure_ascii=False),
            json.dumps(data.get("dimension_requirements") or [], ensure_ascii=False),
            json.dumps(data.get("ats_profile") or {}, ensure_ascii=False),
            json.dumps(data.get("suggestions") or [], ensure_ascii=False),
            json.dumps(data.get("per_card_scores") or [], ensure_ascii=False),
            data.get("match_level"),
            data.get("analysis_version"),
        ),
    )
    _attach_job_entity(data, analysis_id)
    return analysis_id


def _attach_job_entity(data: Dict[str, Any], analysis_id: int) -> Optional[int]:
    """P4-4a：把分析记录挂到 Job 实体（find-or-create + 回填 job_id）。"""
    from app.tools import db_job_entity

    try:
        job_id = db_job_entity.find_or_create_job(
            user_id=data.get("user_id", 1),
            position=data.get("position") or "",
            company=data.get("company"),
            job_analysis_id=analysis_id,
            submission_id=data.get("submission_id"),
            raw_jd_id=data.get("raw_jd_id"),
        )
        if job_id:
            db_job_entity.set_job_analysis_job_id(analysis_id, job_id)
        return job_id
    except Exception as e:
        logger.warning("Job 实体归属失败（analysis_id=%s）: %s", analysis_id, e)
        return None


def get_job_analysis(
    job_id: int, user_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """按主键获取岗位分析记录（可选按 user_id 过滤所有权；排除软删记录）"""
    _ensure_job_analysis_columns()
    sql = "SELECT * FROM job_analysis WHERE id=%s AND is_active=1"
    params: List[Any] = [job_id]
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    row = query_one(sql, tuple(params))
    if not row:
        return None
    return _job_analysis_to_dict(row)


def _job_analysis_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """把 job_analysis 行归一化为契约 dict。

    同时保留 ``id``（历史契约）与 ``job_analysis_id``（前端 JobAnalysisResult 契约），
    避免 GET/列表两条链路字段形状不一致。
    """
    return {
        "id": row["id"],
        "job_analysis_id": row["id"],
        "user_id": row["user_id"],
        "company": row["company"],
        "position": row["position"],
        "jd_text": row["jd_text"],
        "jd_requirements": _parse_json(row["jd_requirements"]) or {},
        "match_score": float(row["match_score"])
        if row.get("match_score") is not None
        else None,
        "match_level": row.get("match_level"),
        "analysis_version": row.get("analysis_version"),
        # P4-4a：分析记录归属岗位（V0013 新增列）
        "job_id": row.get("job_id"),
        "ats_profile": _parse_json(row.get("ats_profile")) or {},
        "suggestions": _parse_json(row.get("suggestions")) or [],
        "per_card_scores": _parse_json(row.get("per_card_scores")) or [],
        "gap_analysis": _parse_json(row["gap_analysis"]) or [],
        "dimension_requirements": _parse_json(row["dimension_requirements"]) or [],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def list_job_analyses(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """列出用户历史岗位分析，按时间倒序。

    返回完整详情字段（单条 SQL 查询），前端无需对每条再发 GET（消除 N+1）。
    """
    _ensure_job_analysis_columns()
    rows = query_all(
        "SELECT id, user_id, company, position, jd_text, jd_requirements, "
        "match_score, match_level, analysis_version, job_id, "
        "ats_profile, suggestions, per_card_scores, "
        "gap_analysis, dimension_requirements, created_at "
        "FROM job_analysis WHERE user_id=%s AND is_active=1 "
        "ORDER BY created_at DESC LIMIT %s",
        (user_id, limit),
    )
    return [_job_analysis_to_dict(r) for r in rows]


def delete_job_analysis(job_id: int, user_id: Optional[int] = None) -> bool:
    """删除岗位分析记录（软删：is_active=0，保留历史，防投递/复盘断链）。

    按 DMV2 §54/§55 不再级联物理删除关联的 mapping / prep / 面试复盘记录，
    历史投递与复盘保留；查询侧统一过滤 is_active=1。
    """
    _ensure_job_analysis_columns()
    sql = "UPDATE job_analysis SET is_active=0 WHERE id=%s"
    params: List[Any] = [job_id]
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    return execute(sql, tuple(params)) > 0


def upsert_job_mapping(job_id: int, experience_id: int) -> None:
    """
    写入经历-岗位关联 (用 INSERT IGNORE 避免重复)

    同一 (experience_id, job_analysis_id) 多次保存时不会报错
    """
    execute(
        """
        INSERT IGNORE INTO experience_job_mapping
            (experience_id, job_analysis_id, selected)
        VALUES (%s, %s, 1)
        """,
        (experience_id, job_id),
    )


def get_selected_card_ids_by_job(job_id: int) -> List[int]:
    """根据岗位分析 ID 获取当时选中的经历卡 ID 列表"""
    rows = query_all(
        "SELECT experience_id FROM experience_job_mapping "
        "WHERE job_analysis_id=%s AND selected=1",
        (job_id,),
    )
    return [row["experience_id"] for row in rows]
