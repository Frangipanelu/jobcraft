"""Job 实体（岗位聚合根）CRUD 模块

P4-4a：岗位对象的聚合根。此前岗位由 `job_analysis`（分析）+ `resume_submission`
（投递记录）二分替代，没有「岗位」这一实体，导致：
- 同一岗位多次分析互不归属；
- RawJD 快照、投递记录、面试复盘都只能挂在分析/投递上；
- 前端创建岗位后没有稳定的 job 标识可缓存。

本模块提供岗位级 find-or-create 与关联维护：
- `find_or_create_job()`：按 (user_id, company, position) 复用同一岗位；
- `link_job()`：回填岗位的关联 id（分析/投递/快照）；
- `set_job_analysis_job_id()`：把分析记录反向挂到岗位；
- `sync_submission_job()`：投递状态变更后同步岗位状态；
- 不提供物理删除（岗位停用走 `is_active=0`）。

唯一键策略（`submission_id` 与 `company+position` 二选一）仍属批次 B 待定项，
故 job 表只加普通索引，find-or-create 以 SELECT 优先实现。
"""

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

logger = logging.getLogger("jobcraft.db.job_entity")


def _ensure_job_table() -> None:
    """确保 job 表存在（schema 已由启动引导保证时短路）"""
    if is_schema_ready():
        return
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS job (
                    id               INT AUTO_INCREMENT PRIMARY KEY,
                    user_id          INT DEFAULT 1,
                    company          VARCHAR(200) DEFAULT '',
                    position         VARCHAR(200) NOT NULL,
                    raw_jd_id        INT,
                    job_analysis_id  INT,
                    submission_id    INT,
                    status           VARCHAR(32) DEFAULT 'PREPARED',
                    is_active        TINYINT(1) DEFAULT 1,
                    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    KEY idx_job_owner (user_id),
                    KEY idx_job_lookup (user_id, company, position),
                    KEY idx_job_submission (submission_id),
                    KEY idx_job_raw_jd (raw_jd_id),
                    KEY idx_job_analysis (job_analysis_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )


def _normalize_identity(company: Optional[str], position: Optional[str]) -> tuple:
    """岗位身份归一：去空白；position 为空时无法定位岗位，回退 None。"""
    company_key = (company or "").strip()
    position_key = (position or "").strip()
    if not position_key:
        return company_key, ""
    return company_key, position_key


def find_or_create_job(
    user_id: int,
    position: str,
    company: Optional[str] = None,
    job_analysis_id: Optional[int] = None,
    submission_id: Optional[int] = None,
    raw_jd_id: Optional[int] = None,
) -> Optional[int]:
    """按 (user_id, company, position) 查找岗位，不存在则创建并回填关联。

    :param user_id: 归属用户
    :param position: 岗位名（必填，空则返回 None 且不落库）
    :param company: 公司名（可空）
    :param job_analysis_id: 关联的分析记录，创建时写入
    :param submission_id: 关联的投递记录，创建时写入
    :param raw_jd_id: 关联的 RawJD 快照（V0012），创建时写入
    :return: 岗位 id；position 为空时返回 None
    """
    _ensure_job_table()
    company_key, position_key = _normalize_identity(company, position)
    if not position_key:
        logger.debug("岗位名为空，跳过 Job 实体创建（company=%s）", company_key)
        return None
    row = query_one(
        "SELECT id FROM job WHERE user_id=%s AND company=%s AND position=%s "
        "AND is_active=1 LIMIT 1",
        (user_id, company_key, position_key),
    )
    if row:
        job_id = int(row["id"])
        if job_analysis_id or submission_id or raw_jd_id:
            link_job(
                job_id,
                job_analysis_id=job_analysis_id,
                submission_id=submission_id,
                raw_jd_id=raw_jd_id,
            )
        return job_id
    return execute_lastrowid(
        """
        INSERT INTO job (user_id, company, position, job_analysis_id, submission_id, raw_jd_id)
        VALUES (%s,%s,%s,%s,%s,%s)
        """,
        (
            user_id,
            company_key,
            position_key,
            job_analysis_id,
            submission_id,
            raw_jd_id,
        ),
    )


def link_job(
    job_id: int,
    job_analysis_id: Optional[int] = None,
    submission_id: Optional[int] = None,
    raw_jd_id: Optional[int] = None,
) -> bool:
    """回填岗位的关联 id（仅覆盖传入项，不清空已有值）。"""
    _ensure_job_table()
    sets: List[str] = []
    values: List[Any] = []
    for col, val in (
        ("job_analysis_id", job_analysis_id),
        ("submission_id", submission_id),
        ("raw_jd_id", raw_jd_id),
    ):
        if val is not None:
            sets.append(f"{col}=%s")
            values.append(val)
    if not sets:
        return False
    values.append(job_id)
    return execute(f"UPDATE job SET {', '.join(sets)} WHERE id=%s", tuple(values)) > 0


def link_raw_jd_by_analysis(job_analysis_id: int, raw_jd_id: int) -> bool:
    """把 RawJD 快照回链到岗位（按分析记录定位岗位，避免多一次查询）。

    :param job_analysis_id: 分析记录 id
    :param raw_jd_id: V0012 raw_jd 快照 id
    :return: 是否更新到在用岗位
    """
    _ensure_job_table()
    return (
        execute(
            "UPDATE job SET raw_jd_id=%s WHERE job_analysis_id=%s AND is_active=1",
            (raw_jd_id, job_analysis_id),
        )
        > 0
    )


def sync_submission_job(
    submission_id: int,
    status: Optional[str] = None,
    job_analysis_id: Optional[int] = None,
) -> Optional[int]:
    """投递记录变更后同步岗位状态与分析归属（仅覆盖传入项）。

    :param submission_id: 投递记录 id
    :param status: 新状态；None 表示不改动
    :param job_analysis_id: 关联的分析记录；None 表示不改动
    :return: 受影响的岗位 id（无岗位或未改动时返回 None）
    """
    _ensure_job_table()
    if status is None and job_analysis_id is None:
        return None
    row = query_one(
        "SELECT id FROM job WHERE submission_id=%s AND is_active=1 LIMIT 1",
        (submission_id,),
    )
    if not row:
        return None
    job_id = int(row["id"])
    link_job(job_id, job_analysis_id=job_analysis_id)
    if status is not None:
        execute("UPDATE job SET status=%s WHERE id=%s", (status, job_id))
    return job_id


def set_job_analysis_job_id(job_analysis_id: int, job_id: int) -> bool:
    """把分析记录反向关联到岗位（job_analysis.job_id，V0013 新增列）。

    旧库未迁移时该列不存在会抛错，由调用方降级处理（分析结果已落库，
    仅缺岗位归属，不阻断主流程）。
    """
    try:
        return (
            execute(
                "UPDATE job_analysis SET job_id=%s WHERE id=%s",
                (job_id, job_analysis_id),
            )
            > 0
        )
    except Exception as e:
        logger.warning(
            "job_analysis.job_id 关联失败（analysis_id=%s）: %s", job_analysis_id, e
        )
        return False


def _row_to_job(row: Any) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "company": row.get("company") or "",
        "position": row.get("position") or "",
        "raw_jd_id": row.get("raw_jd_id"),
        "job_analysis_id": row.get("job_analysis_id"),
        "submission_id": row.get("submission_id"),
        "status": row.get("status") or "PREPARED",
        "is_active": bool(row.get("is_active", 1)),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def get_job(job_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """单条岗位查询（可选按 user_id 过滤所有权）。"""
    _ensure_job_table()
    sql = "SELECT * FROM job WHERE id=%s"
    params: List[Any] = [job_id]
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    row = query_one(sql, tuple(params))
    if not row:
        return None
    return _row_to_job(row)


def list_jobs(user_id: int) -> List[Dict[str, Any]]:
    """列出某用户全部在用岗位（最新在前）。"""
    _ensure_job_table()
    rows = query_all(
        "SELECT * FROM job WHERE user_id=%s AND is_active=1 "
        "ORDER BY updated_at DESC, id DESC",
        (user_id,),
    )
    return [_row_to_job(r) for r in rows]


def update_job(
    job_id: int,
    user_id: Optional[int] = None,
    company: Optional[str] = None,
    position: Optional[str] = None,
    status: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    """按字段更新岗位（仅覆盖传入项，None 表示不改动）。

    T-M5-1 / M5-Q2：job 增删查改不碰 submission；删除走 is_active=0。

    :param job_id: 岗位 id
    :param user_id: 归属校验（可选）
    :param company: 新公司名（去空白；None 不改动）
    :param position: 新岗位名（去空白；空串抛 ValueError）
    :param status: 新状态（调用方应先 normalize_status）
    :param is_active: 是否在用（False = 停用岗位）
    :return: 更新后的岗位；不存在/无归属返回 None
    :raises ValueError: position 归一化后为空
    """
    _ensure_job_table()
    current = get_job(job_id, user_id)
    if not current:
        return None
    sets: List[str] = []
    values: List[Any] = []
    if company is not None:
        sets.append("company=%s")
        values.append(company.strip())
    if position is not None:
        position_key = position.strip()
        if not position_key:
            raise ValueError("岗位名称不能为空")
        sets.append("position=%s")
        values.append(position_key)
    if status is not None:
        sets.append("status=%s")
        values.append(status)
    if is_active is not None:
        sets.append("is_active=%s")
        values.append(1 if is_active else 0)
    if sets:
        values.append(job_id)
        execute(f"UPDATE job SET {', '.join(sets)} WHERE id=%s", tuple(values))
    return get_job(job_id, user_id)


def get_job_by_submission(
    submission_id: int, user_id: int = 1
) -> Optional[Dict[str, Any]]:
    """按投递记录反查岗位（submission → job 归属）。"""
    _ensure_job_table()
    row = query_one(
        "SELECT * FROM job WHERE submission_id=%s AND user_id=%s AND is_active=1 LIMIT 1",
        (submission_id, user_id),
    )
    if not row:
        return None
    return _row_to_job(row)
