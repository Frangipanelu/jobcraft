"""capability_gap 表查询模块（T-M4-2：能力缺口改写任务清单落库）。

**迁移依赖**：本表由 V0020 创建，模块零运行时 DDL（同 db_jd_classification
V0019 模式）——写入缺表（errno 1146）翻译为 ValueError 提示先执行迁移，
job_analysis_flow.collate 捕获后降级告警（分析本体不阻断）；读取缺表降级
为空列表，报告页回退既有能力匹配渲染。

模型（Q3 定稿，2026-10-02 用户确认）：
- 一行 = 一个 job_analysis 的一条改写任务（dimension_requirements ×
  per_card_scores × suggestions 的结构化 join 结果）；
- dimension = D1-D8 对齐 JD 要求侧尺子，EXT = 门槛/格式类扩展码（Q3-a）；
- kind = evidence|rewrite（A/B 类）；status = missing|weak；
  severity = high|medium|low——枚举与 CapabilityGap 的 Literal 一致；
- card_id 可空逻辑外键（Q3-c 链式锚点）；
- DB 列 ``current_text`` ↔ wire 字段 ``current``（Q3 字段名，关键字安全）；
- user_id 冗余保存，归属校验由读侧父级（get_job_analysis）先行。
"""

import logging
from typing import Any, Dict, List, Sequence

from mysql.connector import Error as MySQLError

from app.tools.db_conn import execute, query_all

logger = logging.getLogger("jobcraft.db.capability_gap")

_TABLE_MISSING_ERRNO = 1146


def _row_to_gap(row: Dict[str, Any]) -> Dict[str, Any]:
    """数据库行 → wire 结构（字段名与 Pydantic CapabilityGap 对齐）。"""
    return {
        "id": row["id"],
        "job_analysis_id": row["job_analysis_id"],
        "dimension": row.get("dimension") or "EXT",
        "kind": row.get("kind") or "evidence",
        "status": row.get("status") or "missing",
        "severity": row.get("severity") or "medium",
        "jd_evidence": row.get("jd_evidence") or "",
        "current": row.get("current_text") or "",
        "rewrite_hint": row.get("rewrite_hint") or "",
        "card_id": row.get("card_id"),
        "note": row.get("note") or "",
    }


def insert_capability_gaps(
    job_analysis_id: int,
    user_id: int,
    gaps: Sequence[Dict[str, Any]],
) -> int:
    """整批插入能力缺口任务清单，返回插入行数。

    :param job_analysis_id: 所属岗位分析 id（新一次分析 = 新任务清单）。
    :param user_id: 所属用户 id（冗余，越权过滤同款）。
    :param gaps: 缺口条目（键与 Pydantic CapabilityGap 字段一致）。
    :return: 实际插入行数。
    :raises ValueError: capability_gap 表不存在（提示先执行迁移）。
    """
    inserted = 0
    for g in gaps:
        try:
            inserted += execute(
                """
                INSERT INTO capability_gap
                    (job_analysis_id, user_id, dimension, kind, status, severity,
                     jd_evidence, current_text, rewrite_hint, card_id, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    job_analysis_id,
                    user_id,
                    g.get("dimension") or "EXT",
                    g.get("kind") or "evidence",
                    g.get("status") or "missing",
                    g.get("severity") or "medium",
                    g.get("jd_evidence") or "",
                    g.get("current") or "",
                    g.get("rewrite_hint") or "",
                    g.get("card_id"),
                    g.get("note") or "",
                ),
            )
        except MySQLError as exc:
            if getattr(exc, "errno", None) == _TABLE_MISSING_ERRNO:
                raise ValueError(
                    "capability_gap 表不存在，请先执行 "
                    "python -m migrations.runner migrate（V0020）"
                ) from exc
            raise
    return inserted


def list_capability_gaps(job_analysis_id: int) -> List[Dict[str, Any]]:
    """按岗位分析读取改写任务清单（id 升序），缺表降级为空列表。

    :param job_analysis_id: 岗位分析 id（归属校验由调用方父级先行）。
    :return: wire 结构缺口列表。
    """
    grouped = list_capability_gaps_grouped([job_analysis_id])
    return grouped.get(job_analysis_id, [])


def list_capability_gaps_grouped(
    job_analysis_ids: Sequence[int],
) -> Dict[int, List[Dict[str, Any]]]:
    """按多个岗位分析 id 批量读取改写任务清单（列表页单查询，消除 N+1）。

    :param job_analysis_ids: 岗位分析 id 列表（空列表直接返回空映射）。
    :return: {job_analysis_id: wire 结构缺口列表}；缺表降级为空映射。
    """
    ids = [i for i in job_analysis_ids if i is not None]
    if not ids:
        return {}
    try:
        rows = query_all(
            "SELECT * FROM capability_gap "
            f"WHERE job_analysis_id IN ({','.join(['%s'] * len(ids))}) "
            "ORDER BY job_analysis_id ASC, id ASC",
            tuple(ids),
        )
    except MySQLError as exc:
        if getattr(exc, "errno", None) == _TABLE_MISSING_ERRNO:
            logger.debug("capability_gap 表不存在，任务清单降级为空: %s", exc)
            return {}
        raise
    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for r in rows:
        grouped.setdefault(r["job_analysis_id"], []).append(_row_to_gap(r))
    return grouped


def count_gaps_by_dimension(user_id: int) -> List[Dict[str, Any]]:
    """按维度聚合用户全部能力缺口条数（T-M3-6：workbench 高频缺口）。

    :param user_id: 归属用户（user_id 冗余列直查，无需父级归属校验）。
    :return: ``[{"dimension": "D3", "count": 4}, ...]``——count 降序、同数按
        dimension 升序；缺表（errno 1146）降级为空列表（DB-02 读降级惯例）。
    """
    try:
        rows = query_all(
            "SELECT dimension, COUNT(*) AS c FROM capability_gap "
            "WHERE user_id=%s GROUP BY dimension "
            "ORDER BY c DESC, dimension ASC",
            (user_id,),
        )
    except MySQLError as exc:
        if getattr(exc, "errno", None) == _TABLE_MISSING_ERRNO:
            logger.debug("capability_gap 表不存在，高频缺口降级为空: %s", exc)
            return []
        raise
    return [
        {"dimension": r.get("dimension") or "EXT", "count": int(r["c"])} for r in rows
    ]
