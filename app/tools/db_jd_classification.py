"""jd_classification 表查询模块（T-M3-2：JD 六维分类提案/确认）。

**迁移依赖**：本表由 V0019 创建，模块零运行时 DDL——缺表（errno 1146）读写均
翻译为「请先执行 ``python -m migrations.runner migrate``」的 ValueError 提示，
API 层捕获 ValueError 返回 400。

模型（Q7=c 两级分离 · 2026-10-01 裁决）：
- 一行 = 一个 job_analysis 的六维分类，``UNIQUE(job_analysis_id)``，POST 全量
  upsert（INSERT ... ON DUPLICATE KEY UPDATE；VALUES() 风格同 db_experience
  写公司背调先例）；
- 六维标量列与 direction（V0018）同构同宽，多值维英文逗号分隔（B 切片约定）；
- confidence = high|medium|low（空串 = manual 直填未评置信）；
- source = manual|rule|ai（AI 建议链路留位）；status = proposed|confirmed；
- direction_id 可空：T-M3-3 提交期 find-or-create 的指向，
  ``db_direction.count_direction_references`` 删除守卫同步计数。
"""

import logging
from typing import Any, Dict, List, Optional

from mysql.connector import Error as MySQLError

from app.tools.db_conn import execute, query_one

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
