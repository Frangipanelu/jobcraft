"""简历版本（resume_version）CRUD 模块 — T-M6-1 / M6-Q1-B

M6-Q1 裁决 B：简历版本独立落库。此前简历只在 `resume_submission.resume_markdown`
单点覆盖（无历史、无结构化），且 M5-Q2 Job 先行后投递前简历不再有 submission
可存（T-M6-2 将 save-resume 产物改写入本表）。

设计要点：
- `version_no` 每（user_id, job_id）自增，创建时取 MAX+1；
- `selected_for_application` 是 RESUME_SPEC §11 单选「用户确认实际投递的版本」，
  `set_current_resume_version()` 同岗清其他（Q5 切换当前版本，M6-7 归档依据）；
- `sections JSON` 为结构化模块（Q6 中栏直编落库、diff/溯源/缺口列的前提）；
- factualCheck / userStatus / type / baseResumeId 按 Q1 留空后置（只加列前向兼容）。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.tools.db_conn import (
    execute,
    execute_lastrowid,
    is_schema_ready,
    query_all,
    query_one,
    connection,
)

logger = logging.getLogger("jobcraft.db.resume_version")


def _ensure_resume_version_table() -> None:
    """确保 resume_version 表存在（schema 已由启动引导/迁移保证时短路）。

    T-M6-2：既有表补 job_analysis_id 列（V0022 建表/ALTER 的运行时兜底，
    仿 db_job 字段增强模式——SHOW COLUMNS 命中即短路，重复执行安全）。
    """
    if is_schema_ready():
        return
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS resume_version (
                    id                       INT AUTO_INCREMENT PRIMARY KEY,
                    user_id                  INT NOT NULL DEFAULT 1,
                    job_id                   INT,
                    job_analysis_id          INT,
                    direction_id             INT,
                    version_no               INT NOT NULL DEFAULT 1,
                    version_name             VARCHAR(200),
                    sections                 JSON,
                    resume_markdown          LONGTEXT,
                    selected_for_application TINYINT(1) NOT NULL DEFAULT 0,
                    source_expression_refs   JSON,
                    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    KEY idx_resume_version_owner (user_id, job_id),
                    KEY idx_resume_version_job (job_id),
                    KEY idx_resume_version_analysis (job_analysis_id),
                    KEY idx_resume_version_direction (direction_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cur.execute("SHOW COLUMNS FROM resume_version LIKE 'job_analysis_id'")
            if not cur.fetchone():
                cur.execute(
                    "ALTER TABLE resume_version "
                    "ADD COLUMN job_analysis_id INT NULL, "
                    "ADD KEY idx_resume_version_analysis (job_analysis_id)"
                )


def _dump_json(value: Optional[Any]) -> Optional[str]:
    """JSON 入参序列化（pymysql 不能直接绑定 dict/list）。"""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _parse_json(raw: Any) -> Optional[Any]:
    """JSON 列读出（str）→ Python 结构；空/坏数据回退 None。"""
    if raw is None or raw == "":
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("resume_version JSON 列解析失败，按 None 处理")
        return None


def _row_to_version(row: Any) -> Dict[str, Any]:
    """DB 行 → API dict（时间戳 isoformat，JSON 列解析为结构）。

    T-M6-2：JOIN job_analysis 带出 company/position（FE 简历地图显示归属，
    存量版本可能无 job 行，岗位信息以 analysis 为准）。
    """
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "job_id": row.get("job_id"),
        "job_analysis_id": row.get("job_analysis_id"),
        "direction_id": row.get("direction_id"),
        "version_no": row.get("version_no") or 1,
        "version_name": row.get("version_name"),
        "sections": _parse_json(row.get("sections")),
        "resume_markdown": row.get("resume_markdown"),
        "selected_for_application": bool(row.get("selected_for_application", 0)),
        "source_expression_refs": _parse_json(row.get("source_expression_refs")),
        "company": row.get("ana_company"),
        "position": row.get("ana_position"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


_LIST_JOIN = (
    "SELECT v.*, a.company AS ana_company, a.position AS ana_position "
    "FROM resume_version v "
    "LEFT JOIN job_analysis a ON a.id = v.job_analysis_id AND a.user_id = v.user_id "
)


def list_resume_versions(
    user_id: int, job_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """列出当前用户的简历版本（可按岗位过滤，新版本在前）。

    :param user_id: 归属用户
    :param job_id: 可选岗位过滤（Q5 版本列表按岗取数）
    :return: 版本列表（version_no DESC, id DESC），含 company/position
    """
    _ensure_resume_version_table()
    sql = _LIST_JOIN + "WHERE v.user_id=%s"
    params: List[Any] = [user_id]
    if job_id is not None:
        sql += " AND v.job_id=%s"
        params.append(job_id)
    sql += " ORDER BY v.version_no DESC, v.id DESC"
    return [_row_to_version(r) for r in query_all(sql, tuple(params))]


def get_resume_version(
    version_id: int, user_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """单条版本查询（可选按 user_id 过滤所有权）。

    :param version_id: 版本 id
    :param user_id: 归属校验（None 不校验）
    :return: 版本 dict（含 company/position）；不存在/无归属返回 None
    """
    _ensure_resume_version_table()
    sql = _LIST_JOIN + "WHERE v.id=%s"
    params: List[Any] = [version_id]
    if user_id is not None:
        sql += " AND v.user_id=%s"
        params.append(user_id)
    row = query_one(sql, tuple(params))
    if not row:
        return None
    return _row_to_version(row)


def get_latest_resume_version(
    user_id: int, job_analysis_id: int
) -> Optional[Dict[str, Any]]:
    """按分析记录取最新版本（T-M6-2：面试准备等读简历正文的入口）。

    :param user_id: 归属用户
    :param job_analysis_id: 岗位分析 id
    :return: 最新版本 dict；无则 None
    """
    _ensure_resume_version_table()
    row = query_one(
        _LIST_JOIN + "WHERE v.user_id=%s AND v.job_analysis_id=%s "
        "ORDER BY v.version_no DESC, v.id DESC LIMIT 1",
        (user_id, job_analysis_id),
    )
    if not row:
        return None
    return _row_to_version(row)


def get_selected_resume_version(
    user_id: int, job_analysis_id: int
) -> Optional[Dict[str, Any]]:
    """取该分析下用户确认投递的版本（T-M6-7 投递归档依据）。

    语义「单选优先、无单选取最新」：
    - 单选优先：取 ``selected_for_application=1`` 的行。单选作用域是
      (user, job)（见 ``set_current_resume_version``），同一 analysis 下
      可能存在多条选中行，按 ``version_no DESC, id DESC`` 取最新一条；
    - 无单选：回落 ``get_latest_resume_version``（该分析下最新版本）；
    - 均无版本：返回 None。

    归属收口在 WHERE（v.user_id=%s），他用户行不可见。

    :param user_id: 归属用户
    :param job_analysis_id: 岗位分析 id
    :return: 版本 dict；该分析下无任何版本返回 None
    """
    _ensure_resume_version_table()
    row = query_one(
        _LIST_JOIN + "WHERE v.user_id=%s AND v.job_analysis_id=%s "
        "AND v.selected_for_application=1 "
        "ORDER BY v.version_no DESC, v.id DESC LIMIT 1",
        (user_id, job_analysis_id),
    )
    if row:
        return _row_to_version(row)
    return get_latest_resume_version(user_id, job_analysis_id)


def create_resume_version(
    user_id: int,
    job_id: int,
    direction_id: Optional[int] = None,
    version_name: Optional[str] = None,
    sections: Optional[Any] = None,
    resume_markdown: Optional[str] = None,
    source_expression_refs: Optional[Any] = None,
    job_analysis_id: Optional[int] = None,
) -> Dict[str, Any]:
    """保存一个新简历版本（version_no 每岗 MAX+1）。

    :param user_id: 归属用户
    :param job_id: 归属岗位（Q1-B 核心字段，必填）
    :param direction_id: 关联方向（可空，依赖 M3 数据）
    :param version_name: 版本名（建议值 方向-公司-日期，可改）
    :param sections: 结构化模块（JSON 结构）
    :param resume_markdown: 简历 Markdown 快照
    :param source_expression_refs: 来源表达引用（溯源）
    :param job_analysis_id: 岗位分析归属（T-M6-2：FE 地图/面试准备按
        analysis 归组读取，存量岗位可能无 job 行）
    :return: 新建版本 dict
    :raises ValueError: job_id 缺失
    """
    _ensure_resume_version_table()
    if job_id is None:
        raise ValueError("job_id 不能为空")
    row = query_one(
        "SELECT COALESCE(MAX(version_no), 0) AS next_no FROM resume_version "
        "WHERE user_id=%s AND job_id=%s",
        (user_id, job_id),
    )
    next_no = int(row["next_no"]) + 1 if row else 1
    new_id = execute_lastrowid(
        """
        INSERT INTO resume_version
            (user_id, job_id, job_analysis_id, direction_id, version_no, version_name,
             sections, resume_markdown, source_expression_refs)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            user_id,
            job_id,
            job_analysis_id,
            direction_id,
            next_no,
            (version_name.strip() or None) if version_name else None,
            _dump_json(sections),
            resume_markdown,
            _dump_json(source_expression_refs),
        ),
    )
    created = get_resume_version(new_id, user_id)
    if not created:
        raise ValueError("简历版本创建失败")
    return created


def update_resume_version(
    version_id: int,
    user_id: int,
    version_name: Optional[str] = None,
    sections: Optional[Any] = None,
    resume_markdown: Optional[str] = None,
    source_expression_refs: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    """按字段更新版本（仅覆盖传入项，None 表示不改动）。

    :param version_id: 版本 id
    :param user_id: 归属校验
    :param version_name: 新版本名（去空白，空串存 None）
    :param sections: 新结构化模块
    :param resume_markdown: 新 Markdown 快照
    :param source_expression_refs: 新来源表达引用
    :return: 更新后的版本；不存在/无归属返回 None
    """
    _ensure_resume_version_table()
    current = get_resume_version(version_id, user_id)
    if not current:
        return None
    sets: List[str] = []
    values: List[Any] = []
    if version_name is not None:
        sets.append("version_name=%s")
        values.append(version_name.strip() or None)
    if sections is not None:
        sets.append("sections=%s")
        values.append(_dump_json(sections))
    if resume_markdown is not None:
        sets.append("resume_markdown=%s")
        values.append(resume_markdown)
    if source_expression_refs is not None:
        sets.append("source_expression_refs=%s")
        values.append(_dump_json(source_expression_refs))
    if sets:
        values.append(version_id)
        execute(
            f"UPDATE resume_version SET {', '.join(sets)} WHERE id=%s AND user_id=%s",
            tuple(values),
        )
    return get_resume_version(version_id, user_id)


def delete_resume_version(version_id: int, user_id: int) -> bool:
    """删除版本（硬删；归属校验先行）。

    :param version_id: 版本 id
    :param user_id: 归属校验
    :return: 是否删除到本人版本
    """
    _ensure_resume_version_table()
    return (
        execute(
            "DELETE FROM resume_version WHERE id=%s AND user_id=%s",
            (version_id, user_id),
        )
        > 0
    )


def set_current_resume_version(
    version_id: int, user_id: int
) -> Optional[Dict[str, Any]]:
    """设为当前版本（RESUME_SPEC §11 单选，同 user+job 内清其他选中）。

    单条 UPDATE 原子完成：目标 id 置 1、同组其余置 0（job_id 走 <=> NULL 安全比较）。

    :param version_id: 目标版本 id
    :param user_id: 归属校验
    :return: 更新后的版本；不存在/无归属返回 None
    """
    _ensure_resume_version_table()
    current = get_resume_version(version_id, user_id)
    if not current:
        return None
    execute(
        "UPDATE resume_version SET selected_for_application = IF(id=%s, 1, 0) "
        "WHERE user_id=%s AND job_id <=> %s",
        (version_id, user_id, current["job_id"]),
    )
    return get_resume_version(version_id, user_id)
