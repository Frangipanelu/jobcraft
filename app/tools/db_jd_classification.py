"""jd_classification 表查询模块（T-M3-2：JD 六维分类提案/确认）。

**迁移依赖**：本表由 V0019 创建，模块零运行时 DDL——缺表（errno 1146）写侧
翻译为「请先执行 ``python -m migrations.runner migrate``」的 ValueError 提示，
API 层捕获 ValueError 返回 400；读侧 grouped（T-M4-4）缺表降级为空映射。

模型（Q7=c 两级分离 · 2026-10-01 裁决）：
- 一行 = 一个 job_analysis 的六维分类，``UNIQUE(job_analysis_id)``，POST 全量
  upsert（INSERT ... ON DUPLICATE KEY UPDATE；VALUES() 风格同 db_experience
  写公司背调先例）；
- 六维标量列与 direction（V0018）同构同宽，多值维英文逗号分隔（B 切片约定）；
- confidence = high|medium|low（空串 = manual 直填未评置信）；
- source = manual|rule|ai（AI 建议链路留位）；status = proposed|confirmed；
- direction_id 可空：T-M3-3 提交期 find-or-create 的指向，
  ``db_direction.count_direction_references`` 删除守卫同步计数。
- 读侧两条：``get_jd_classification``（单条）与 ``list_jd_classifications_grouped``
  （T-M4-4 批量，附 direction_name/direction_code，缺表降级空映射）。
"""

import logging
from typing import Any, Dict, List, Optional, Sequence

from mysql.connector import Error as MySQLError

from app.tools.db_conn import execute, query_all, query_one

logger = logging.getLogger("jobcraft.db.jd_classification")

JD_STATUSES = ("proposed", "confirmed")
JD_SOURCES = ("manual", "rule", "ai")
JD_CONFIDENCE_LEVELS = ("high", "medium", "low")
SIX_DIM_FIELDS = (
    "job_function",
    "primary_role",
    "industry",
    "product",
    "scenario",
    "skills",
)
_UPDATABLE_FIELDS = (*SIX_DIM_FIELDS, "direction_id", "confidence", "source", "status")
_TABLE_MISSING_ERRNO = 1146


def _row_to_classification(row: Dict[str, Any]) -> Dict[str, Any]:
    """数据库行 → API 友好结构（snake_case wire 契约）。"""
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "job_analysis_id": row["job_analysis_id"],
        "direction_id": row.get("direction_id"),
        "job_function": row.get("job_function") or "",
        "primary_role": row.get("primary_role") or "",
        "industry": row.get("industry") or "",
        "product": row.get("product") or "",
        "scenario": row.get("scenario") or "",
        "skills": row.get("skills") or "",
        "confidence": row.get("confidence") or "",
        "source": row.get("source") or "manual",
        "status": row.get("status") or "proposed",
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def _translate_error(exc: MySQLError) -> None:
    """缺表翻译为带迁移指引的 ValueError，其余错误交由调用方原样上抛。"""
    if getattr(exc, "errno", None) == _TABLE_MISSING_ERRNO:
        raise ValueError(
            "jd_classification 表不存在，请先执行 python -m migrations.runner migrate"
        ) from exc


def _clean_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    """白名单 + 枚举 + 六维至少一项非空的入库前校验。

    :param fields: API payload 或 T-M3-3 代码路径传入的原始字段。
    :return: 仅含 ``_UPDATABLE_FIELDS`` 的清洗后字段。
    :raises ValueError: 枚举非法 / 六维全空 / direction_id 非整数。
    """
    clean: Dict[str, Any] = {}
    for key in _UPDATABLE_FIELDS:
        value = fields.get(key)
        if value is None:
            continue
        clean[key] = value.strip() if isinstance(value, str) else value
    if "direction_id" in clean:
        try:
            clean["direction_id"] = int(clean["direction_id"])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"direction_id 必须为整数: {clean['direction_id']}"
            ) from exc
    if clean.get("confidence", "") not in ("", *JD_CONFIDENCE_LEVELS):
        raise ValueError(
            f"confidence 仅允许 {'/'.join(JD_CONFIDENCE_LEVELS)} 或空，收到: {clean['confidence']}"
        )
    if "source" in clean and clean["source"] not in JD_SOURCES:
        raise ValueError(
            f"source 仅允许 {'/'.join(JD_SOURCES)}，收到: {clean['source']}"
        )
    if "status" in clean and clean["status"] not in JD_STATUSES:
        raise ValueError(
            f"status 仅允许 {'/'.join(JD_STATUSES)}，收到: {clean['status']}"
        )
    if not any(clean.get(field, "") for field in SIX_DIM_FIELDS):
        raise ValueError("六维分类至少填写一维")
    return clean


def upsert_jd_classification(
    user_id: int, job_analysis_id: int, fields: Dict[str, Any]
) -> Dict[str, Any]:
    """全量 upsert 该分析的六维分类（同 analysis 一行，重复提交覆盖更新）。

    :param user_id: 归属用户（分析归属由 API 层先行校验）。
    :param job_analysis_id: 目标分析 id。
    :param fields: 六维 + direction_id/confidence/source/status（缺省走列默认）。
    :return: 保存后的分类结构（_row_to_classification）。
    :raises ValueError: 枚举非法 / 六维全空 / 缺表未迁移 / 回读失败。
    """
    clean = _clean_fields(fields)
    values = (
        user_id,
        job_analysis_id,
        clean.get("direction_id"),
        clean.get("job_function", ""),
        clean.get("primary_role", ""),
        clean.get("industry", ""),
        clean.get("product", ""),
        clean.get("scenario", ""),
        clean.get("skills", ""),
        clean.get("confidence", ""),
        clean.get("source", "manual"),
        clean.get("status", "proposed"),
    )
    try:
        execute(
            "INSERT INTO jd_classification "
            "(user_id, job_analysis_id, direction_id, job_function, primary_role, "
            "industry, product, scenario, skills, confidence, source, status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE "
            "direction_id=VALUES(direction_id), job_function=VALUES(job_function), "
            "primary_role=VALUES(primary_role), industry=VALUES(industry), "
            "product=VALUES(product), scenario=VALUES(scenario), "
            "skills=VALUES(skills), confidence=VALUES(confidence), "
            "source=VALUES(source), status=VALUES(status)",
            values,
        )
    except MySQLError as exc:
        _translate_error(exc)
        raise
    saved = get_jd_classification(job_analysis_id, user_id)
    if not saved:
        raise ValueError("分类保存后回读失败，请重试")
    return saved


def get_jd_classification(
    job_analysis_id: int, user_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """按分析 id 查分类，可选按 user_id 过滤所有权。

    :param job_analysis_id: 目标分析 id（UNIQUE，一行）。
    :param user_id: 归属用户；提供时不归属视同不存在（返回 None）。
    :return: 分类结构（_row_to_classification），或 None。
    :raises ValueError: 缺表未迁移。
    """
    sql = "SELECT * FROM jd_classification WHERE job_analysis_id=%s"
    params: List[Any] = [job_analysis_id]
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    try:
        row = query_one(sql, tuple(params))
    except MySQLError as exc:
        _translate_error(exc)
        raise
    return _row_to_classification(row) if row else None


def _attach_direction_labels(classifications: Dict[int, Dict[str, Any]]) -> None:
    """为批量分类行解析关联方向的 name/code（原地填充，缺省先置 None）。

    direction_id 为 null/0 或 direction 行已缺失 → 保 None 不抛；direction 表
    缺表（errno 1146，未迁移环境）→ 同样降级为 None（读侧降级，不阻断列表）。

    :param classifications: {job_analysis_id: 分类结构}（由调用方构造）。
    """
    for cls in classifications.values():
        cls["direction_name"] = None
        cls["direction_code"] = None
    direction_ids = sorted(
        {c["direction_id"] for c in classifications.values() if c.get("direction_id")}
    )
    if not direction_ids:
        return
    try:
        rows = query_all(
            "SELECT id, name, code FROM direction "
            f"WHERE id IN ({','.join(['%s'] * len(direction_ids))})",
            tuple(direction_ids),
        )
    except MySQLError as exc:
        if getattr(exc, "errno", None) == _TABLE_MISSING_ERRNO:
            logger.debug("direction 表不存在，方向名降级为 None: %s", exc)
            return
        raise
    labels = {r["id"]: r for r in rows}
    for cls in classifications.values():
        label = labels.get(cls.get("direction_id"))
        if label:
            cls["direction_name"] = label.get("name")
            cls["direction_code"] = label.get("code")


def list_jd_classifications_grouped(
    job_analysis_ids: Sequence[int],
    user_id: Optional[int] = None,
) -> Dict[int, Dict[str, Any]]:
    """按多个岗位分析 id 批量读取六维分类（列表页单查询，消除 N+1，T-M4-4）。

    命中行附 ``direction_name`` / ``direction_code``（direction 表二次查询，
    direction_id 为 null/0 或方向缺行 → None）；jd_classification 缺表（errno
    1146）降级为空映射（DB-02 读降级惯例，参照
    ``db_capability_gap.list_capability_gaps_grouped``）。

    :param job_analysis_ids: 岗位分析 id 列表（空列表直接返回空映射）。
    :param user_id: 归属用户；提供时只取该用户的分类行（越权视同不存在）。
    :return: {job_analysis_id: 分类结构（含 direction_name/direction_code）}。
    """
    ids = [i for i in job_analysis_ids if i is not None]
    if not ids:
        return {}
    sql = (
        "SELECT * FROM jd_classification "
        f"WHERE job_analysis_id IN ({','.join(['%s'] * len(ids))})"
    )
    params: List[Any] = list(ids)
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    try:
        rows = query_all(sql, tuple(params))
    except MySQLError as exc:
        if getattr(exc, "errno", None) == _TABLE_MISSING_ERRNO:
            logger.debug("jd_classification 表不存在，方向分类降级为空: %s", exc)
            return {}
        raise
    grouped: Dict[int, Dict[str, Any]] = {
        r["job_analysis_id"]: _row_to_classification(r) for r in rows
    }
    _attach_direction_labels(grouped)
    return grouped
