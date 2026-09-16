"""运行时 DDL 启动引导（TASK-P1-10）。

把散落在 db_* 模块的 `_ensure_*` 运行时 DDL 收敛为进程启动时一次性执行：
- FastAPI lifespan 启动时调用 `run_schema_bootstrap()`；
- 任务 worker（app.tasks.worker.run_worker）启动时同样调用；
- 全部成功后置位 db_conn 的 schema ready 标志，此后请求路径中的 `_ensure_*`
  调用在入口处短路为空操作，消除逐请求 SHOW COLUMNS / ALTER 的并发竞态
  （同一表多进程同时 ALTER 的风险）。

失败策略：尽力而为、非阻塞。DB 不可用时记录告警、不置位标志，请求路径
退化为引导前的逐调用执行，行为完全兼容。

批量部署建议：先用 `python -m migrations.runner migrate` 固化 schema，
再启动多进程 worker（避免多进程启动并发 DDL）。
"""

import importlib
import logging
from typing import Tuple

from app.tools import db_conn

logger = logging.getLogger("jobcraft.db.bootstrap")

# 各模块 _ensure_* 按依赖顺序执行：
# 建表类先跑，字段增强类（SHOW COLUMNS / ALTER）依赖对应表已存在。
_BOOTSTRAP_STEPS: Tuple[Tuple[str, str], ...] = (
    ("app.tools.db_user", "_ensure_users_table"),
    ("app.tools.db_experience", "_ensure_experience_card_columns"),
    ("app.tools.db_experience", "_ensure_card_versions_table"),
    ("app.tools.db_job", "_ensure_job_analysis_columns"),
    ("app.tools.db_submission", "_ensure_resume_submission_table"),
    ("app.tools.db_interview", "_ensure_interview_preps_table"),
    ("app.tools.db_interview", "_ensure_interview_records_table"),
    ("app.tools.db_interview", "_ensure_interview_qa_pairs_table"),
    ("app.tools.db_submission", "_ensure_interview_submission_columns"),
    ("app.tools.db_base_resume", "_ensure_base_resume_table"),
    ("app.tools.db_profile", "_ensure_user_profiles_table"),
)


def run_schema_bootstrap() -> bool:
    """启动时执行全部运行时 DDL（幂等；已就绪直接返回）。

    任一 `_ensure_*` 抛错即记录告警并返回 False（不置位标志，请求路径降级）。

    :return: True 表示本次全部执行成功，此后请求路径 `_ensure_*` 短路；False 表示失败
    """
    if db_conn.is_schema_ready():
        return True
    # 先经 db_tools 的 re-export 链加载经典 db_* 模块：
    # db_experience ↔ db_tools 存在循环引用，唯有先加载 db_tools 才能安全解析。
    importlib.import_module("app.tools.db_tools")
    for module_path, func_name in _BOOTSTRAP_STEPS:
        try:
            mod = importlib.import_module(module_path)
            getattr(mod, func_name)()
        except Exception:
            logger.warning(
                "schema 引导步骤失败（%s.%s），退化为请求路径逐调用执行（可用迁移固化 schema）",
                module_path,
                func_name,
                exc_info=True,
            )
            return False
    db_conn.mark_schema_ready()
    logger.info("schema 引导完成：运行时 DDL 已全部执行，请求路径 _ensure_* 短路生效")
    return True
