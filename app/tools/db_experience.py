"""经历卡 CRUD 模块"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.tools.db_conn import (
    connection,
    execute,
    execute_lastrowid,
    query_all,
    query_one,
    query_scalar,
)
from app.tools.db_tools import _parse_json

logger = logging.getLogger("jobcraft.db.experience")


def _ensure_experience_card_columns() -> None:
    """确保 experience_card 表有新架构字段（兼容旧库）"""
    # 先确保旧字段存在（兼容尚未迁移的库）
    old_columns = [
        ("company", "VARCHAR(200)"),
        ("role", "VARCHAR(100)"),
        ("period", "VARCHAR(100)"),
        ("background", "TEXT"),
        ("problem", "TEXT"),
        ("solution", "TEXT"),
        ("execution", "TEXT"),
        ("result", "TEXT"),
        ("dimensions", "JSON"),
    ]
    # 新字段
    new_columns = [
        ("raw_text", "LONGTEXT"),
        ("ai_structured", "JSON"),
        ("card_type", "VARCHAR(32) DEFAULT 'work'"),
    ]
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM experience_card")
            existing = {c[0] for c in cur.fetchall()}
            for col, dtype in old_columns + new_columns:
                if col not in existing:
                    cur.execute(
                        "ALTER TABLE experience_card ADD COLUMN %s %s" % (col, dtype)
                    )
            # 修复 source 列类型（旧库是 ENUM，新代码需要 VARCHAR）
            cur.execute("SHOW COLUMNS FROM experience_card LIKE 'source'")
            col_info = cur.fetchone()
            if col_info and col_info[1].startswith("enum("):
                cur.execute(
                    "ALTER TABLE experience_card MODIFY COLUMN source VARCHAR(50) DEFAULT 'manual'"
                )

            # 回填: 已有 content 但 raw_text 为空的卡, 用 content 填充
            cur.execute(
                "SELECT id, content, summary FROM experience_card "
                "WHERE raw_text IS NULL AND (content IS NOT NULL OR summary IS NOT NULL) "
                "LIMIT 500"
            )
            rows = cur.fetchall()
            for row in rows:
                fallback = row[1] or row[2] or ""
                if fallback:
                    cur.execute(
                        "UPDATE experience_card SET raw_text=%s WHERE id=%s",
                        (fallback, row[0]),
                    )


def _row_to_card(row: Dict[str, Any]) -> Dict[str, Any]:
    """把数据库原始行转换成 API 友好结构 (新架构优先)"""
    if not row:
        return row
    raw_text = row.get("raw_text") or row.get("content") or row.get("summary", "")
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "raw_text": raw_text,
        "tags": _parse_json(row["tags"]) or [],
        "ai_structured": _parse_json(row.get("ai_structured")),
        # 向下兼容字段
        "summary": row.get("summary", ""),
        "content": row.get("content", ""),
        "company": row.get("company"),
        "role": row.get("role"),
        "period": row.get("period"),
        "background": row.get("background", ""),
        "problem": row.get("problem", ""),
        "solution": row.get("solution", ""),
        "execution": row.get("execution", ""),
        "result": row.get("result", ""),
        "dimensions": _parse_json(row.get("dimensions")) or [],
        "source": row["source"],
        "card_type": row.get("card_type") or "work",
        "version": row["version"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def list_cards(user_id: int, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    获取用户经历卡列表

    :param user_id: 用户 ID (本期固定 1)
    :param include_inactive: True 同时返回归档卡片,默认 False 只看激活
    """
    _ensure_experience_card_columns()
    if include_inactive:
        rows = query_all(
            "SELECT * FROM experience_card WHERE user_id=%s "
            "ORDER BY company, period, updated_at DESC",
            (user_id,),
        )
    else:
        rows = query_all(
            "SELECT * FROM experience_card WHERE user_id=%s AND is_active=1 "
            "ORDER BY company, period, updated_at DESC",
            (user_id,),
        )
    return [_row_to_card(r) for r in rows]


def count_cards(user_id: int, include_inactive: bool = False) -> int:
    """
    统计用户经历卡数量

    :param user_id: 用户 ID
    :param include_inactive: 是否包含归档卡片
    :return: 经历卡数量
    """
    _ensure_experience_card_columns()
    if include_inactive:
        return query_scalar(
            "SELECT COUNT(*) FROM experience_card WHERE user_id=%s", (user_id,)
        )
    return query_scalar(
        "SELECT COUNT(*) FROM experience_card WHERE user_id=%s AND is_active=1",
        (user_id,),
    )


def list_cards_paginated(
    user_id: int,
    include_inactive: bool = False,
    offset: int = 0,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    分页获取用户经历卡列表

    :param user_id: 用户 ID
    :param include_inactive: 是否包含归档卡片
    :param offset: 偏移量
    :param limit: 限制数量
    :return: 经历卡列表
    """
    _ensure_experience_card_columns()
    if include_inactive:
        rows = query_all(
            "SELECT * FROM experience_card WHERE user_id=%s "
            "ORDER BY company, period, updated_at DESC LIMIT %s OFFSET %s",
            (user_id, limit, offset),
        )
    else:
        rows = query_all(
            "SELECT * FROM experience_card WHERE user_id=%s AND is_active=1 "
            "ORDER BY company, period, updated_at DESC LIMIT %s OFFSET %s",
            (user_id, limit, offset),
        )
    return [_row_to_card(r) for r in rows]


def search_cards(
    user_id: int,
    query: str,
    include_inactive: bool = False,
    offset: int = 0,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    搜索用户经历卡

    支持按标题、公司、角色、标签、内容进行全文搜索。

    :param user_id: 用户 ID
    :param query: 搜索关键词
    :param include_inactive: 是否包含归档卡片
    :param offset: 偏移量
    :param limit: 限制数量
    :return: 匹配的经历卡列表
    """
    _ensure_experience_card_columns()

    # 构建搜索条件
    search_pattern = f"%{query}%"
    conditions = ["user_id=%s"]
    params: List[Any] = [user_id]

    if not include_inactive:
        conditions.append("is_active=1")

    # 搜索标题、公司、角色、原始内容
    search_conditions = [
        "title LIKE %s",
        "company LIKE %s",
        "role LIKE %s",
        "raw_text LIKE %s",
        "JSON_CONTAINS(tags, %s)",  # 搜索JSON数组中的标签
    ]

    # 为每个搜索条件添加参数
    for _ in search_conditions:
        params.append(search_pattern)

    # 添加标签搜索的JSON格式
    params[-1] = json.dumps(query, ensure_ascii=False)

    where_clause = " AND ".join(conditions)
    search_where = " OR ".join(search_conditions)

    rows = query_all(
        f"""
        SELECT * FROM experience_card
        WHERE {where_clause} AND ({search_where})
        ORDER BY updated_at DESC
        LIMIT %s OFFSET %s
        """,
        (*params, limit, offset),
    )
    return [_row_to_card(r) for r in rows]


def count_search_cards(
    user_id: int,
    query: str,
    include_inactive: bool = False,
) -> int:
    """
    统计搜索结果数量

    :param user_id: 用户 ID
    :param query: 搜索关键词
    :param include_inactive: 是否包含归档卡片
    :return: 匹配数量
    """
    _ensure_experience_card_columns()

    search_pattern = f"%{query}%"
    conditions = ["user_id=%s"]
    params: List[Any] = [user_id]

    if not include_inactive:
        conditions.append("is_active=1")

    search_conditions = [
        "title LIKE %s",
        "company LIKE %s",
        "role LIKE %s",
        "raw_text LIKE %s",
        "JSON_CONTAINS(tags, %s)",
    ]

    for _ in search_conditions:
        params.append(search_pattern)
    params[-1] = json.dumps(query, ensure_ascii=False)

    where_clause = " AND ".join(conditions)
    search_where = " OR ".join(search_conditions)

    return query_scalar(
        f"""
        SELECT COUNT(*) FROM experience_card
        WHERE {where_clause} AND ({search_where})
        """,
        tuple(params),
    )


def get_card(card_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """按主键获取单张经历卡（可选按 user_id 过滤所有权）"""
    _ensure_experience_card_columns()
    sql = "SELECT * FROM experience_card WHERE id=%s"
    params: List[Any] = [card_id]
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    row = query_one(sql, tuple(params))
    return _row_to_card(row) if row else None


def find_card_by_company_role(
    user_id: int, company: str, role: str
) -> Optional[Dict[str, Any]]:
    """按公司+岗位查找一张 active 经历卡（用于上传去重）"""
    if not company:
        return None
    _ensure_experience_card_columns()
    row = query_one(
        "SELECT * FROM experience_card WHERE user_id=%s AND is_active=1 "
        "AND company=%s AND role=%s LIMIT 1",
        (user_id, company, role),
    )
    return _row_to_card(row) if row else None


def insert_card(data: Dict[str, Any]) -> int:
    """
    插入一张经历卡,返回新主键

    :param data: 必含 title/raw_text; 可选 tags/ai_structured
    """
    _ensure_experience_card_columns()
    sql = """
        INSERT INTO experience_card
            (user_id, title, raw_text, tags, ai_structured, summary, content,
             company, role, period, card_type, background, problem, solution, execution, result,
             dimensions, source)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    raw_text = data.get("raw_text", "")
    return execute_lastrowid(
        sql,
        (
            data.get("user_id", 1),
            data["title"],
            raw_text,
            json.dumps(data.get("tags", []), ensure_ascii=False),
            json.dumps(data.get("ai_structured"), ensure_ascii=False)
            if data.get("ai_structured")
            else None,
            data.get("summary") or raw_text[:200],
            data.get("content") or raw_text,
            data.get("company"),
            data.get("role"),
            data.get("period"),
            data.get("card_type") or "work",
            data.get("background"),
            data.get("problem"),
            data.get("solution"),
            data.get("execution"),
            data.get("result"),
            json.dumps(data.get("dimensions", []), ensure_ascii=False),
            data.get("source") or "manual",
        ),
    )


def update_card(
    card_id: int, updates: Dict[str, Any], user_id: Optional[int] = None
) -> bool:
    """
    按字段白名单增量更新

    只更新调用方实际传入的字段,避免覆盖空值;
    JSON 字段统一序列化; 可选按 user_id 过滤所有权
    """
    _ensure_experience_card_columns()
    field_map = {
        "title": "title",
        "raw_text": "raw_text",
        "summary": "summary",
        "content": "content",
        "company": "company",
        "role": "role",
        "period": "period",
        "card_type": "card_type",
        "background": "background",
        "problem": "problem",
        "solution": "solution",
        "execution": "execution",
        "result": "result",
        "is_active": "is_active",
    }
    sets: List[str] = []
    values: List[Any] = []
    for k, col in field_map.items():
        if k in updates and updates[k] is not None:
            sets.append(f"{col}=%s")
            values.append(updates[k])
    for json_field in ("tags", "ai_structured", "dimensions"):
        if json_field in updates and updates[json_field] is not None:
            sets.append(f"{json_field}=%s")
            values.append(json.dumps(updates[json_field], ensure_ascii=False))

    if not sets:
        return False
    values.append(card_id)
    sql = "UPDATE experience_card SET " + ", ".join(sets) + " WHERE id=%s"
    if user_id is not None:
        sql += " AND user_id=%s"
        values.append(user_id)
    return execute(sql, tuple(values)) > 0


def delete_card(card_id: int, user_id: Optional[int] = None) -> bool:
    """
    物理删除一张经历卡, 同时清理 experience_job_mapping 关联 (FK 已设 CASCADE 也行)

    可选按 user_id 过滤所有权: 越权删除时返回 False
    """
    with connection() as conn:
        with conn.cursor() as cur:
            # 先删关联 (FK CASCADE 应该会处理, 但显式删更稳)
            # 字段名是 experience_id, 不是 card_id (建表时用的是 experience)
            cur.execute(
                "DELETE FROM experience_job_mapping WHERE experience_id=%s",
                (card_id,),
            )
            sql = "DELETE FROM experience_card WHERE id=%s"
            params: List[Any] = [card_id]
            if user_id is not None:
                sql += " AND user_id=%s"
                params.append(user_id)
            cur.execute(sql, tuple(params))
            return cur.rowcount > 0


# 时间范围特征：如 2019.03 - 2021.06 / 2020/01~2020/12 / 2019 年 3 月 - 至今
_RANGE_RE = re.compile(
    r"(?:19|20)\d{2}\s*[年.\-/]?\s*\d{0,2}\s*[月]?\s*[-~–—至到]\s*"
    r"(?:(?:19|20)\d{2}\s*[年.\-/]?\s*\d{0,2}\s*[月]?|至今|现在)"
)
# 素材库式多段经历：markdown 标题形如 `#### 经历1：xxx`
_ENTRY_HEADER_RE = re.compile(r"^#{1,6}\s*经历\s*\d+", re.MULTILINE)
_RESUME_MARKERS = [
    "工作经历",
    "项目经历",
    "实习经历",
    "教育背景",
    "个人技能",
    "自我评价",
    "专业技能",
]


def _looks_like_full_resume(raw_text: str, min_chars: int = 100) -> bool:
    """
    启发式判断 raw_text 是否为「单卡装下整份简历」的旧数据

    判定依据（满足其一即可）：
    1. 文本长度足够且出现 >=2 个时间范围（如 2019.03-2021.06）
    2. 文本包含 >=2 个简历章节标题（工作经历 / 项目经历 / 教育背景等）
    3. 文本包含 >=2 个素材库式经历标题（`#### 经历1：xxx`）

    :param raw_text: 卡片原始文本
    :param min_chars: 视为整份简历的最短长度, 过短说明只是单段经历
    :return: True 表示疑似整份简历, 需要拆分
    """
    if not raw_text or len(raw_text) < min_chars:
        return False
    ranges = _RANGE_RE.findall(raw_text)
    if len(ranges) >= 2:
        return True
    markers_hit = sum(1 for m in _RESUME_MARKERS if m in raw_text)
    if markers_hit >= 2:
        return True
    return len(_ENTRY_HEADER_RE.findall(raw_text)) >= 2


def _rebuild_entry_text(entry: Dict[str, Any]) -> str:
    """
    把 parse_resume_entries 解析出的一段经历重建为单张卡的 raw_text

    :param entry: 解析结果, 含 company/role/period/summary/achievements
    :return: 可读的纯文本经历描述
    """
    lines = []
    head = " / ".join(
        x for x in [entry.get("company"), entry.get("role"), entry.get("period")] if x
    )
    if head:
        lines.append(head)
    if entry.get("summary"):
        lines.append(str(entry["summary"]))
    for a in entry.get("achievements") or []:
        title = a.get("title") or ""
        action = a.get("action") or {}
        main = action.get("main") if isinstance(action, dict) else ""
        result = a.get("result") or ""
        bullet = title or main
        if result:
            bullet = f"{bullet}（{result}）" if bullet else f"结果：{result}"
        if bullet:
            lines.append(f"- {bullet}")
    return "\n".join(lines)


def split_resume_card_by_entries(
    user_id: int, card: Dict[str, Any], entries: List[Dict[str, Any]]
) -> List[int]:
    """
    把一张「整份简历」卡按解析出的经历条目拆成多张经历卡（纯 DB，无 LLM）。

    每段经历新建一张卡；原卡标记为归档（is_active=0, 可恢复, 不做物理删除）。

    :param user_id: 用户 ID
    :param card: 原经历卡 dict（含 id/title/source）
    :param entries: ParseResumeEntriesAgent 解析出的经历条目
    :return: 新建卡片 ID 列表
    """
    created_ids = []
    seen: set = set()
    for e in entries:
        company = (e.get("company") or "").strip()
        role = (e.get("role") or "").strip()
        if company and f"{company}::{role}" in seen:
            continue
        seen.add(f"{company}::{role}")
        title = e.get("title") or e.get("role") or "未命名经历"
        new_id = insert_card(
            {
                "user_id": user_id,
                "title": title,
                "raw_text": _rebuild_entry_text(e),
                "tags": [],
                "company": company,
                "role": role,
                "period": e.get("period") or "",
                "summary": e.get("summary") or "",
                "card_type": (e.get("card_type") or "work"),
                "source": card.get("source", "manual"),
            }
        )
        created_ids.append(new_id)
    update_card(card["id"], {"is_active": False})
    return created_ids


def list_full_resume_cards(
    user_id: int = 1, min_chars: int = 100
) -> List[Dict[str, Any]]:
    """筛选疑似「单卡装下整份简历」的旧数据卡（纯 DB，无 LLM）。"""
    cards = list_cards(user_id, include_inactive=False)
    return [
        card
        for card in cards
        if _looks_like_full_resume(card.get("raw_text") or "", min_chars)
    ]


def get_company_research(company: str) -> Optional[Dict[str, Any]]:
    """
    读取公司背调,含 7 天新鲜度校验

    :return: {info, cached_at, fresh: bool} 或 None (库中无记录)
    """
    row = query_one(
        "SELECT info, cached_at FROM company_research WHERE company=%s",
        (company,),
    )
    if not row:
        return None
    cached_at = row["cached_at"]
    fresh = (datetime.now() - cached_at).days < 7
    return {
        "company": company,
        "info": _parse_json(row["info"]) or {},
        "cached_at": cached_at.isoformat(),
        "fresh": fresh,
    }


def upsert_company_research(company: str, info: Dict[str, Any]) -> None:
    """写入或刷新公司背调 (ON DUPLICATE KEY UPDATE)"""
    execute(
        """
        INSERT INTO company_research (company, info, cached_at)
        VALUES (%s, %s, NOW())
        ON DUPLICATE KEY UPDATE info=VALUES(info), cached_at=NOW()
        """,
        (company, json.dumps(info, ensure_ascii=False)),
    )


# ---------------- 经历卡版本表 (card_versions) ----------------


def _ensure_card_versions_table() -> None:
    """确保 card_versions 表存在"""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS card_versions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    card_id INT NOT NULL,
                    version_type VARCHAR(32) NOT NULL COMMENT 'polished | review_refined',
                    source_type VARCHAR(32) NOT NULL COMMENT 'job_analysis | interview_review',
                    source_id INT NOT NULL,
                    title VARCHAR(300),
                    raw_text LONGTEXT NOT NULL,
                    tags JSON,
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    KEY idx_card (card_id),
                    KEY idx_source (source_type, source_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )


def insert_card_version(data: Dict[str, Any]) -> int:
    """插入一条经历卡版本记录，返回主键"""
    _ensure_card_versions_table()
    return execute_lastrowid(
        """
        INSERT INTO card_versions
            (card_id, version_type, source_type, source_id, title, raw_text, tags, note)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            data["card_id"],
            data["version_type"],
            data["source_type"],
            data["source_id"],
            data.get("title"),
            data["raw_text"],
            json.dumps(data.get("tags") or [], ensure_ascii=False)
            if data.get("tags")
            else None,
            data.get("note"),
        ),
    )


def get_card_version(
    card_id: int, source_type: str, source_id: int
) -> Optional[Dict[str, Any]]:
    """按卡 + 来源获取最新版本（每个来源最多一条）"""
    _ensure_card_versions_table()
    row = query_one(
        "SELECT * FROM card_versions WHERE card_id=%s AND source_type=%s AND source_id=%s "
        "ORDER BY created_at DESC LIMIT 1",
        (card_id, source_type, source_id),
    )
    if not row:
        return None
    return {
        "id": row["id"],
        "card_id": row["card_id"],
        "version_type": row["version_type"],
        "source_type": row["source_type"],
        "source_id": row["source_id"],
        "title": row["title"],
        "raw_text": row["raw_text"],
        "tags": _parse_json(row["tags"]) or [],
        "note": row["note"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def _version_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """把 card_versions 原始行转换成 API 结构"""
    return {
        "id": row["id"],
        "card_id": row["card_id"],
        "version_type": row["version_type"],
        "source_type": row["source_type"],
        "source_id": row["source_id"],
        "title": row["title"],
        "raw_text": row["raw_text"],
        "tags": _parse_json(row["tags"]) or [],
        "note": row["note"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def get_card_versions_by_source(
    source_type: str, source_id: int
) -> List[Dict[str, Any]]:
    """按来源（job_analysis / interview_review）获取所有版本"""
    _ensure_card_versions_table()
    rows = query_all(
        "SELECT * FROM card_versions WHERE source_type=%s AND source_id=%s "
        "ORDER BY card_id, created_at DESC",
        (source_type, source_id),
    )
    return [_version_row(r) for r in rows]


def get_card_versions_by_card_id(card_id: int) -> List[Dict[str, Any]]:
    """按卡片ID获取所有版本"""
    _ensure_card_versions_table()
    rows = query_all(
        "SELECT * FROM card_versions WHERE card_id=%s ORDER BY created_at DESC",
        (card_id,),
    )
    return [_version_row(r) for r in rows]
