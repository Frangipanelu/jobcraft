"""
数据库连接配置模块

所有 db_* 子模块共用，避免循环导入。
"""

import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# override=True: 强制用 .env 覆盖系统环境里的同名变量, 避免旧 key 干扰
load_dotenv(override=True)

# JobCraft 求职助手统一使用此配置 (database=jobcraft)
JOBCRAFT_DB = "jobcraft"


def get_db_config(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    从环境变量读取 MySQL 连接配置
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

    config = {k: v for k, v in config.items() if v is not None}

    if overrides:
        config.update({k: v for k, v in overrides.items() if v is not None})

    required_keys = ["user", "password", "database"]
    missing_keys = [k for k in required_keys if k not in config]
    if missing_keys:
        raise ValueError(f"缺失数据库核心配置：{', '.join(missing_keys)}")

    return config


def _jc_config() -> Dict[str, Any]:
    return get_db_config({"database": JOBCRAFT_DB})
