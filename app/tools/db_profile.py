"""用户资料表（user_profiles）DDL 与访问封装。

TASK-P1-10 收敛：user_profiles 的建表 DDL 原散落在 app/api/profile.py（API 层直写 DDL），
本模块将其下沉到 tools 层单一出口；DDL 只由启动引导
（app.tools.db_bootstrap.run_schema_bootstrap）一次性执行，schema 就绪后短路为空操作。
"""

import logging

from app.tools.db_conn import execute, is_schema_ready

logger = logging.getLogger("jobcraft.db.profile")


def _ensure_user_profiles_table() -> None:
    """确保 user_profiles 表存在（幂等；schema 已就绪则直接返回）。"""
    if is_schema_ready():
        return
    execute(
        """CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INT NOT NULL PRIMARY KEY,
            display_name VARCHAR(100) DEFAULT '',
            role VARCHAR(100) DEFAULT '求职者',
            target_salary VARCHAR(50) DEFAULT '',
            years_of_exp INT DEFAULT 0,
            city VARCHAR(100) DEFAULT '',
            phone VARCHAR(30) DEFAULT '',
            summary TEXT,
            target_cities JSON,
            target_companies JSON,
            target_roles JSON,
            avatar_url VARCHAR(500) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
    )
