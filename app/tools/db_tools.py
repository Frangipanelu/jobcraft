"""
MySQL 数据库查询工具模块

封装数据库查询助手使用的三个 LangChain 工具：
list_sql_tables 用于发现真实表名，get_table_data 用于预览字段和样例数据，
execute_sql_query 用于在确认结构后执行自定义查询。
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_core.tools import tool
from mysql.connector import Error, connect

from app.api.monitor import monitor

logger = logging.getLogger("jobcraft.db_tools")

# override=True: 强制用 .env 覆盖系统环境里的同名变量, 避免旧 key 干扰
load_dotenv(override=True)


# 集中读取数据库配置，后续三个工具都复用这份连接参数
# JobCraft 调用时通过 overrides 参数临时切换 database,不影响主流程 default 库
def get_db_config(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    从环境变量读取 MySQL 连接配置

    所有数据库工具都通过此函数拿到同一份连接参数，避免每个工具重复读取环境变量
    :return: mysql.connector.connect 可直接使用的连接参数
    """
    config = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "database": os.getenv("MYSQL_DATABASE"),
        "charset": os.getenv("MYSQL_CHARSET", "utf8mb4"),
        "collation": os.getenv("MYSQL_COLLATION", "utf8mb4_unicode_ci"),
        "autocommit": True,
        "sql_mode": os.getenv("MYSQL_SQL_MODE", "TRADITIONAL"),
    }

    # 去掉未配置的可选项，避免把 None 传给 mysql.connector 造成连接参数异常
    config = {k: v for k, v in config.items() if v is not None}

    # JobCraft 临时覆盖 (例如切换到 jobcraft 库)
    if overrides:
        config.update({k: v for k, v in overrides.items() if v is not None})

    # user/password/database 是本教程工具能正常查询业务库的最小必要配置
    required_keys = ["user", "password", "database"]
    missing_keys = [k for k in required_keys if k not in config]
    if missing_keys:
        raise ValueError(f"缺失数据库核心配置：{', '.join(missing_keys)}")

    return config


# JobCraft 求职助手统一使用此配置 (database=jobcraft)
JOBCRAFT_DB = "jobcraft"


def _jc_config() -> Dict[str, Any]:
    return get_db_config({"database": JOBCRAFT_DB})


@tool
def list_sql_tables() -> str:
    """
    查询当前数据库中所有可用表

    作用：让模型先识别真实可用的表名，方便后续预览表结构和编写自定义 SQL。
    :return: 有表：可用的表有：表1,表2,表3...
             没有表：没有可用的表
             出现异常：查询出现异常：异常信息
    """

    # 埋点：工具一被调用，前端可以展示当前正在查询数据库表名
    monitor.report_tool(tool_name="数据库表名查询工具：list_sql_tables", args={})

    # 加载数据库连接信息
    config = get_db_config()

    # MySQL 查询的固定步骤：
    # 1. 创建连接
    # 2. 创建 cursor
    # 3. 执行 SQL
    # 4. 获取返回结果
    # 5. 释放连接和 cursor 资源
    # 这里捕获异常并返回中文提示，避免工具报错直接中断 Agent 执行链路
    try:
        # 使用 with 管理连接和游标，查询结束后自动释放数据库资源
        with connect(**config) as conn:
            with conn.cursor() as cursor:
                sql = "SHOW TABLES"
                cursor.execute(sql)

                # SHOW TABLES 返回形如：[("drugs",), ("inventory",), ("sales_records",)]
                tables = cursor.fetchall()
                if not tables:
                    return "没有可用的表"

                # 取每个元组的第一个元素，拼成模型容易阅读的表名列表
                table_names = [table[0] for table in tables]
                return f"可用的表有：{', '.join(table_names)}"
    except Error as e:
        return f"查询出现异常：{str(e)}"


@tool
def get_table_data(table_name) -> str:
    """
    查询指定表的前 100 行数据

    当前工具调用之前，应先调用 list_sql_tables 完成表名校验。
    此工具的作用：
    1. 完成单表样例数据查询
    2. 为多表查询提供表结构信息和数据格式参考
    :param table_name: 表名
    :return: CSV 格式数据
             1. 第一行是列信息，列之间使用英文逗号分隔
             2. 第二行开始是表数据，值之间也使用英文逗号分隔
             3. 行和行之间使用 \n 分隔
             4. 至多查询 100 条表数据
             例如：
                id,name,age\n -> 列头
                1,张三,18\n
                1,张三,18\n
                1,张三,18\n -> 至多查询 100 条
    """
    # 埋点：工具二被调用，前端可以展示当前正在预览哪张表
    monitor.report_tool(
        tool_name="数据库表数据查询工具：get_table_data",
        args={"table_name": table_name},
    )

    # 获取数据库参数
    config = get_db_config()

    # 查询流程同样是：连接 -> cursor -> 执行 SQL -> 获取列信息和数据 -> 自动释放资源
    try:
        with connect(**config) as conn:
            with conn.cursor() as cursor:
                # 教程代码直接拼接表名，重点演示 Agent 查询链路；生产环境应改为白名单校验
                sql = f"SELECT * FROM {table_name} LIMIT 100"
                cursor.execute(sql)

                # cursor.description 保存查询结果的列元信息
                # 例如：[("id", ...), ("name", ...), ("age", ...)]
                # 如果 SQL 没有结果集，description 可能为 None
                description = cursor.description
                if not description:
                    return f"数据表 {table_name} 暂无数据。"

                # 只取每个列信息元组的第一个元素，也就是列名
                # 例如：["id", "name", "age"]
                columns = [desc[0] for desc in description]

                # fetchall 返回表数据，形如：[(1, "张三", 18), (2, "李四", 20)]
                rows = cursor.fetchall()

                # 把每一行数据从元组转成 CSV 行文本
                # 例如：(1, "张三", 18) -> "1,张三,18"
                results = [",".join(map(str, row)) for row in rows]

                # columns 组成 CSV 头部，rows 组成 CSV 数据体
                # 最终返回：
                # id,name,age
                # 1,张三,18
                header_str = ",".join(columns)
                data_str = "\n".join(results)
                return f"{header_str}\n{data_str}"
    except Error as e:
        return f"查询出现异常：{str(e)}"


@tool
def execute_sql_query(query) -> str:
    """
    执行自定义 SQL 查询

    切记：执行之前，需要通过 list_sql_tables 明确真实表名，
    再通过 get_table_data 明确表结构和数据格式。
    适合多表关联、筛选、聚合、排序等复杂查询。
    :param query: 要执行的自定义 SQL 语句
    :return: CSV 格式数据
             1. 第一行是列信息，列之间使用英文逗号分隔
             2. 第二行开始是表数据，值之间也使用英文逗号分隔
             3. 行和行之间使用 \n 分隔
             例如：
                id,name,age\n -> 列头
                1,张三,18\n
                1,张三,18\n
    """
    # 埋点：记录模型最终生成的 SQL，便于教学时观察是否真的落到了正确表字段上
    monitor.report_tool(
        tool_name="数据库表数据查询工具：execute_sql_query", args={"query": query}
    )

    # 获取数据库参数
    config = get_db_config()

    # 自定义查询和 get_table_data 的结果处理逻辑一致：
    # 执行 SQL -> 读取 description 得到列名 -> fetchall 得到数据 -> 拼成 CSV 返回
    try:
        with connect(**config) as conn:
            with conn.cursor() as cursor:
                # 当前章节依赖提示词约束模型生成只读查询；生产环境建议在工具层限制 SELECT/SHOW
                cursor.execute(query)

                # 非查询类 SQL 没有结果集描述，这里统一返回提示，避免工具调用直接抛错给模型
                description = cursor.description
                if not description:
                    return f"执行自定义 SQL 语句没有查询结果，SQL 为：{query}"
                # description => [("列1", ...), ("列2", ...)]
                columns = [desc[0] for desc in description]

                # rows => [(值1, 值2), (值1, 值2)]
                rows = cursor.fetchall()

                # 每行元组统一转为逗号分隔文本，便于模型读取和后续整理
                results = [",".join(map(str, row)) for row in rows]

                # 第一行是列名，后续是查询数据
                header_str = ",".join(columns)
                data_str = "\n".join(results)
                return f"{header_str}\n{data_str}"
    except Error as e:
        return f"查询出现异常：{str(e)}"


if __name__ == "__main__":
    # 本地调试入口：直接运行本文件可验证 .env 中的 MySQL 连接配置是否可用
    logging.basicConfig(level=logging.INFO)
    logger.info(
        "%s",
        execute_sql_query.invoke(
            {
                "query": "SELECT * FROM `drugs` dgs join sales_records srd on dgs.drug_id = srd.drug_id"
            }
        ),
    )


# ============================================================
# 投递记录 (resume_submission)
# ============================================================


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
                    status           VARCHAR(32) DEFAULT '已投递',
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
                    data.get("status", "已投递"),
                    data.get("notes"),
                    data.get("is_manual", 0),
                ),
            )
            return cur.lastrowid


def get_submission(submission_id: int) -> Optional[Dict[str, Any]]:
    _ensure_resume_submission_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT * FROM resume_submission WHERE id=%s", (submission_id,))
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
        "status": row["status"],
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
                "status": r["status"],
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


def update_submission(submission_id: int, updates: Dict[str, Any]) -> bool:
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
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE resume_submission SET " + ", ".join(sets) + " WHERE id=%s",
                tuple(values),
            )
            return cur.rowcount > 0


def delete_submission(submission_id: int) -> bool:
    _ensure_resume_submission_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM resume_submission WHERE id=%s", (submission_id,))
            return cur.rowcount > 0


def get_submission_prep_count(submission_id: int) -> int:
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
    submission_id: int, limit: int = 5
) -> List[Dict[str, Any]]:
    """按 submission_id 获取面试记录"""
    _ensure_interview_records_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT * FROM interview_records WHERE submission_id=%s ORDER BY created_at DESC LIMIT %s",
                (submission_id, limit),
            )
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


# ============================================================
# JobCraft 求职助手底层 DAO (非 LangChain tool, 仅供 server.py 调用)
# ============================================================


def _parse_json(value: Any) -> Any:
    """
    数据库 JSON 字段读取时统一解析,容错处理 NULL/字符串/已解析对象

    MySQL JSON 列在 mysql-connector 中可能以 dict/list 形式返回,
    也可能因字符集以 str 返回,因此统一做一次 json.loads 兜底
    """
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _ensure_experience_card_columns() -> None:
    """确保 experience_card 表有新架构字段（兼容旧库）"""
    config = _jc_config()
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
    ]
    with connect(**config) as conn:
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
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            if include_inactive:
                cur.execute(
                    "SELECT * FROM experience_card WHERE user_id=%s ORDER BY company, period, updated_at DESC",
                    (user_id,),
                )
            else:
                cur.execute(
                    "SELECT * FROM experience_card WHERE user_id=%s AND is_active=1 ORDER BY company, period, updated_at DESC",
                    (user_id,),
                )
            rows = cur.fetchall()
    return [_row_to_card(r) for r in rows]


def get_card(card_id: int) -> Optional[Dict[str, Any]]:
    """按主键获取单张经历卡"""
    _ensure_experience_card_columns()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT * FROM experience_card WHERE id=%s", (card_id,))
            row = cur.fetchone()
    return _row_to_card(row) if row else None


def insert_card(data: Dict[str, Any]) -> int:
    """
    插入一张经历卡,返回新主键

    :param data: 必含 title/raw_text; 可选 tags/ai_structured
    """
    _ensure_experience_card_columns()
    config = _jc_config()
    sql = """
        INSERT INTO experience_card
            (user_id, title, raw_text, tags, ai_structured, summary, content,
             company, role, period, background, problem, solution, execution, result,
             dimensions, source)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    raw_text = data.get("raw_text", "")
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
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
                    data.get("background"),
                    data.get("problem"),
                    data.get("solution"),
                    data.get("execution"),
                    data.get("result"),
                    json.dumps(data.get("dimensions", []), ensure_ascii=False),
                    data.get("source") or "manual",
                ),
            )
            return cur.lastrowid


def update_card(card_id: int, updates: Dict[str, Any]) -> bool:
    """
    按字段白名单增量更新

    只更新调用方实际传入的字段,避免覆盖空值;
    JSON 字段统一序列化
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
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE experience_card SET " + ", ".join(sets) + " WHERE id=%s",
                tuple(values),
            )
            return cur.rowcount > 0


def delete_card(card_id: int) -> bool:
    """
    物理删除一张经历卡, 同时清理 experience_job_mapping 关联 (FK 已设 CASCADE 也行)
    """
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            # 先删关联 (FK CASCADE 应该会处理, 但显式删更稳)
            # 字段名是 experience_id, 不是 card_id (建表时用的是 experience)
            cur.execute(
                "DELETE FROM experience_job_mapping WHERE experience_id=%s",
                (card_id,),
            )
            cur.execute(
                "DELETE FROM experience_card WHERE id=%s",
                (card_id,),
            )
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
    for e in entries:
        title = e.get("title") or e.get("role") or "未命名经历"
        new_id = insert_card(
            {
                "user_id": user_id,
                "title": title,
                "raw_text": _rebuild_entry_text(e),
                "tags": [],
                "company": e.get("company") or "",
                "role": e.get("role") or "",
                "period": e.get("period") or "",
                "summary": e.get("summary") or "",
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
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT info, cached_at FROM company_research WHERE company=%s",
                (company,),
            )
            row = cur.fetchone()
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
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO company_research (company, info, cached_at)
                VALUES (%s, %s, NOW())
                ON DUPLICATE KEY UPDATE info=VALUES(info), cached_at=NOW()
                """,
                (company, json.dumps(info, ensure_ascii=False)),
            )


def _ensure_job_analysis_columns() -> None:
    """为 job_analysis 表增加 dimension_requirements 字段（兼容旧库）"""
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM job_analysis")
            existing = {c[0] for c in cur.fetchall()}
            if "dimension_requirements" not in existing:
                cur.execute(
                    "ALTER TABLE job_analysis ADD COLUMN dimension_requirements JSON"
                )


def insert_job_analysis(data: Dict[str, Any]) -> int:
    """插入一条岗位分析记录,返回主键"""
    _ensure_job_analysis_columns()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO job_analysis
                    (user_id, company, position, jd_text,
                     jd_requirements, match_score, gap_analysis,
                     dimension_requirements)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    data.get("user_id", 1),
                    data["company"],
                    data["position"],
                    data["jd_text"],
                    json.dumps(data.get("jd_requirements") or {}, ensure_ascii=False),
                    data.get("match_score"),
                    json.dumps(data.get("gap_analysis") or [], ensure_ascii=False),
                    json.dumps(
                        data.get("dimension_requirements") or [], ensure_ascii=False
                    ),
                ),
            )
            return cur.lastrowid


def get_job_analysis(job_id: int) -> Optional[Dict[str, Any]]:
    """按主键获取岗位分析记录"""
    _ensure_job_analysis_columns()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT * FROM job_analysis WHERE id=%s", (job_id,))
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "company": row["company"],
        "position": row["position"],
        "jd_text": row["jd_text"],
        "jd_requirements": _parse_json(row["jd_requirements"]) or {},
        "match_score": float(row["match_score"])
        if row.get("match_score") is not None
        else None,
        "gap_analysis": _parse_json(row["gap_analysis"]) or [],
        "dimension_requirements": _parse_json(row["dimension_requirements"]) or [],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def list_job_analyses(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """列出用户历史岗位分析,按时间倒序"""
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT id, company, position, match_score, created_at "
                "FROM job_analysis WHERE user_id=%s ORDER BY created_at DESC LIMIT %s",
                (user_id, limit),
            )
            rows = cur.fetchall()
    for r in rows:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
        if r.get("match_score") is not None:
            r["match_score"] = float(r["match_score"])
    return rows


def delete_job_analysis(job_id: int) -> bool:
    """删除岗位分析记录（同时清理关联的 mapping 与 prep 记录）"""
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM experience_job_mapping WHERE job_analysis_id=%s", (job_id,)
            )
            cur.execute(
                "DELETE FROM interview_preps WHERE job_analysis_id=%s", (job_id,)
            )
            cur.execute("DELETE FROM job_analysis WHERE id=%s", (job_id,))
            return cur.rowcount > 0


def upsert_job_mapping(job_id: int, experience_id: int) -> None:
    """
    写入经历-岗位关联 (用 INSERT IGNORE 避免重复)

    同一 (experience_id, job_analysis_id) 多次保存时不会报错
    """
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT IGNORE INTO experience_job_mapping
                    (experience_id, job_analysis_id, selected)
                VALUES (%s, %s, 1)
                """,
                (experience_id, job_id),
            )


def get_selected_card_ids_by_job(job_id: int) -> List[int]:
    """根据岗位分析 ID 获取当时选中的经历卡 ID 列表"""
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT experience_id FROM experience_job_mapping WHERE job_analysis_id=%s AND selected=1",
                (job_id,),
            )
            return [row[0] for row in cur.fetchall()]


# ---------------- 面试逐字稿 ----------------


def _ensure_interview_preps_table() -> None:
    """确保 interview_preps 表存在"""
    config = _jc_config()
    with connect(**config) as conn:
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    KEY idx_job (job_analysis_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )


def insert_interview_prep(data: Dict[str, Any]) -> int:
    """插入面试准备稿,返回主键"""
    _ensure_interview_preps_table()
    _ensure_interview_submission_columns()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
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
            return cur.lastrowid


def get_interview_prep_by_job(job_id: int) -> Optional[Dict[str, Any]]:
    """按 job_analysis_id 获取最新面试准备稿"""
    _ensure_interview_preps_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT * FROM interview_preps WHERE job_analysis_id=%s ORDER BY created_at DESC LIMIT 1",
                (job_id,),
            )
            row = cur.fetchone()
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
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


# ---------------- 面试复盘 ----------------


def _ensure_interview_records_table() -> None:
    """确保 interview_records 表存在"""
    config = _jc_config()
    with connect(**config) as conn:
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
                    raw_text LONGTEXT,
                    parsed_dialogue_json JSON,
                    analysis_json JSON,
                    status VARCHAR(50) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    KEY idx_user_created (user_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )


def _ensure_interview_qa_pairs_table() -> None:
    """确保 interview_qa_pairs 表存在"""
    config = _jc_config()
    with connect(**config) as conn:
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
                    KEY idx_sequence (record_id, sequence)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )


def insert_interview_record(data: Dict[str, Any]) -> int:
    """插入面试记录，返回主键"""
    _ensure_interview_records_table()
    _ensure_interview_submission_columns()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO interview_records
                    (user_id, title, company, position, round_type, job_analysis_id,
                     raw_text, parsed_dialogue_json, analysis_json, status,
                     submission_id, round_label)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                ),
            )
            return cur.lastrowid


def update_interview_record_analysis(record_id: int, analysis: Dict[str, Any]) -> None:
    """更新面试记录的分析结果"""
    _ensure_interview_records_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
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
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE interview_records SET status=%s WHERE id=%s",
                (status, record_id),
            )


def get_interview_record(record_id: int) -> Optional[Dict[str, Any]]:
    """获取单条面试记录"""
    _ensure_interview_records_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT * FROM interview_records WHERE id=%s", (record_id,))
            row = cur.fetchone()
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
    }


def list_interview_records(user_id: int = 1, limit: int = 100) -> List[Dict[str, Any]]:
    """列出用户的面试记录，按时间倒序"""
    _ensure_interview_records_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT * FROM interview_records WHERE user_id=%s ORDER BY created_at DESC LIMIT %s",
                (user_id, limit),
            )
            rows = cur.fetchall()
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
            }
        )
    return result


def insert_interview_qa_pair(data: Dict[str, Any]) -> int:
    """插入面试 QA 对，返回主键"""
    _ensure_interview_qa_pairs_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
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
            return cur.lastrowid


def delete_interview_qa_pair(qa_pair_id: int) -> None:
    """按主键删除单个 QA 对"""
    _ensure_interview_qa_pairs_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM interview_qa_pairs WHERE id=%s", (qa_pair_id,))


def delete_interview_qa_pairs_by_record(record_id: int) -> None:
    """按面试记录 ID 删除其下所有 QA 对"""
    _ensure_interview_qa_pairs_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM interview_qa_pairs WHERE record_id=%s", (record_id,)
            )


def list_interview_qa_pairs(record_id: int) -> List[Dict[str, Any]]:
    """列出某条面试记录下的所有 QA 对"""
    _ensure_interview_qa_pairs_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT * FROM interview_qa_pairs WHERE record_id=%s ORDER BY sequence ASC",
                (record_id,),
            )
            rows = cur.fetchall()
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


def delete_interview_record(record_id: int) -> None:
    """删除面试记录及其 QA 对"""
    _ensure_interview_records_table()
    _ensure_interview_qa_pairs_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM interview_qa_pairs WHERE record_id=%s", (record_id,)
            )
            cur.execute("DELETE FROM interview_records WHERE id=%s", (record_id,))


# ---------------- 经历卡版本表 (card_versions) ----------------


def _ensure_card_versions_table() -> None:
    """确保 card_versions 表存在"""
    config = _jc_config()
    with connect(**config) as conn:
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
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
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
            return cur.lastrowid


def get_card_version(
    card_id: int, source_type: str, source_id: int
) -> Optional[Dict[str, Any]]:
    """按卡 + 来源获取最新版本（每个来源最多一条）"""
    _ensure_card_versions_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT * FROM card_versions WHERE card_id=%s AND source_type=%s AND source_id=%s ORDER BY created_at DESC LIMIT 1",
                (card_id, source_type, source_id),
            )
            row = cur.fetchone()
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


def get_card_versions_by_source(
    source_type: str, source_id: int
) -> List[Dict[str, Any]]:
    """按来源（job_analysis / interview_review）获取所有版本"""
    _ensure_card_versions_table()
    config = _jc_config()
    with connect(**config) as conn:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT * FROM card_versions WHERE source_type=%s AND source_id=%s ORDER BY card_id, created_at DESC",
                (source_type, source_id),
            )
            rows = cur.fetchall()
    result = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "card_id": row["card_id"],
                "version_type": row["version_type"],
                "source_type": row["source_type"],
                "source_id": row["source_id"],
                "title": row["title"],
                "raw_text": row["raw_text"],
                "tags": _parse_json(row["tags"]) or [],
                "note": row["note"],
                "created_at": row["created_at"].isoformat()
                if row.get("created_at")
                else None,
            }
        )
    return result
