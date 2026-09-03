"""
MySQL 数据库工具模块（兼容层）

业务 CRUD 已拆分至 db_user / db_experience / db_job / db_submission /
db_interview 模块，本文件保留通用辅助函数与向后兼容的 re-export。
"""

import json
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from mysql.connector import connect  # noqa: F401  # 供复用方与测试 import

# override=True: 强制用 .env 覆盖系统环境里的同名变量, 避免旧 key 干扰
load_dotenv(override=True)

# JobCraft 求职助手统一使用此配置 (database=jobcraft)
JOBCRAFT_DB = "jobcraft"


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

    # user/password/database 是本工具能正常查询业务库的最小必要配置
    required_keys = ["user", "password", "database"]
    missing_keys = [k for k in required_keys if k not in config]
    if missing_keys:
        raise ValueError(f"缺失数据库核心配置：{', '.join(missing_keys)}")

    return config


def _jc_config() -> Dict[str, Any]:
    """返回统一使用的 jobcraft 库连接配置"""
    return get_db_config({"database": JOBCRAFT_DB})


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
# Re-export：保持向后兼容
# from app.tools.db_tools import insert_card  仍然可用
# ============================================================

from app.tools.db_user import (  # noqa: E402, F401
    create_user,
    get_user,
    get_user_by_email,
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
    list_interview_preps,
    list_interview_records,
    update_interview_record_analysis,
    update_interview_record_status,
)
