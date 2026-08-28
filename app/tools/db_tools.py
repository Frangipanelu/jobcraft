"""
MySQL 数据库查询工具模块

封装数据库查询助手使用的三个 LangChain 工具：
list_sql_tables 用于发现真实表名，get_table_data 用于预览字段和样例数据，
execute_sql_query 用于在确认结构后执行自定义查询。
"""

import json
import logging
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from langchain_core.tools import tool
from mysql.connector import Error, connect

from app.api.monitor import monitor

logger = logging.getLogger("jobcraft.db_tools")

# override=True: 强制用 .env 覆盖系统环境里的同名变量, 避免旧 key 干扰
load_dotenv(override=True)


# ============================================================
# 连接配置（子模块共用）
# ============================================================


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


# ============================================================
# 通用辅助函数
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


# ============================================================
# LangChain 工具
# ============================================================


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

    try:
        with connect(**config) as conn:
            with conn.cursor() as cursor:
                sql = "SHOW TABLES"
                cursor.execute(sql)

                tables = cursor.fetchall()
                if not tables:
                    return "没有可用的表"

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
    """
    monitor.report_tool(
        tool_name="数据库表数据查询工具：get_table_data",
        args={"table_name": table_name},
    )

    config = get_db_config()

    try:
        with connect(**config) as conn:
            with conn.cursor() as cursor:
                sql = f"SELECT * FROM {table_name} LIMIT 100"
                cursor.execute(sql)

                description = cursor.description
                if not description:
                    return f"数据表 {table_name} 暂无数据。"

                columns = [desc[0] for desc in description]
                rows = cursor.fetchall()

                results = [",".join(map(str, row)) for row in rows]

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
    """
    monitor.report_tool(
        tool_name="数据库表数据查询工具：execute_sql_query", args={"query": query}
    )

    config = get_db_config()

    try:
        with connect(**config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)

                description = cursor.description
                if not description:
                    return f"执行自定义 SQL 语句没有查询结果，SQL 为：{query}"
                columns = [desc[0] for desc in description]

                rows = cursor.fetchall()

                results = [",".join(map(str, row)) for row in rows]

                header_str = ",".join(columns)
                data_str = "\n".join(results)
                return f"{header_str}\n{data_str}"
    except Error as e:
        return f"查询出现异常：{str(e)}"


if __name__ == "__main__":
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
# Re-export：保持向后兼容
# from app.tools.db_tools import insert_card  仍然可用
# ============================================================

from app.tools.db_user import (  # noqa: E402, F401
    create_user,
    get_user,
    get_user_by_username,
    update_user,
)

from app.tools.db_experience import (  # noqa: E402, F401
    _looks_like_full_resume,
    _rebuild_entry_text,
    _row_to_card,
    count_cards,
    count_search_cards,
    delete_card,
    find_card_by_company_role,
    get_card,
    get_card_version,
    get_card_versions_by_card_id,
    get_card_versions_by_source,
    get_company_research,
    insert_card,
    insert_card_version,
    list_cards,
    list_cards_paginated,
    list_full_resume_cards,
    search_cards,
    split_resume_card_by_entries,
    update_card,
    upsert_company_research,
)

from app.tools.db_job import (  # noqa: E402, F401
    delete_job_analysis,
    get_job_analysis,
    get_selected_card_ids_by_job,
    insert_job_analysis,
    list_job_analyses,
    upsert_job_mapping,
)

from app.tools.db_submission import (  # noqa: E402, F401
    delete_submission,
    get_dashboard,
    get_submission,
    get_submission_prep_count,
    get_submission_review_count,
    insert_submission,
    list_interview_records_by_submission,
    list_submissions,
    update_submission,
)

from app.tools.db_interview import (  # noqa: E402, F401
    delete_interview_qa_pair,
    delete_interview_qa_pairs_by_record,
    delete_interview_record,
    get_interview_prep_by_job,
    get_interview_record,
    insert_interview_prep,
    insert_interview_qa_pair,
    insert_interview_record,
    list_interview_qa_pairs,
    list_interview_records,
    update_interview_record_analysis,
    update_interview_record_status,
)
