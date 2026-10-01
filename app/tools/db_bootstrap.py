"""运行时 DDL 启动引导（TASK-P1-10）。

把散落在 db_* 模块的 `_ensure_*` 运行时 DDL 收敛为进程启动时一次性执行：
- FastAPI lifespan 启动时调用 `run_schema_bootstrap()`；
- 任务 worker（app.tasks.worker.run_worker）启动时同样调用；
- 全部成功后置位 db_conn 的 schema ready 标志，此后请求路径中的 `_ensure_*`
  调用在入口处短路为空操作，消除逐请求 SHOW COLUMNS / ALTER 的并发竞态
  （同一表多进程同时 ALTER 的风险）。

失败策略：尽力而为、非阻塞。DB 不可用时记录告警、不置位标志，请求路径
退化为引导前的逐调用执行，行为完全兼容。

启动断言（BE-INIT-01）：全部步骤成功后校验「仅由迁移创建、无运行时 DDL」
的核心表（expression / direction，见 V0009）；缺失即视为未就绪（返回 False
不置位），并在日志中提示先执行 ``python -m migrations.runner migrate``。

批量部署建议：先用 `python -m migrations.runner migrate` 固化 schema，
再启动多进程 worker（避免多进程启动并发 DDL）。
"""

import importlib
import logging
from typing import List, Tuple

from mysql.connector import Error as MySQLError

from app.tools import db_conn

logger = logging.getLogger("jobcraft.db.bootstrap")

# 各模块 _ensure_* 按依赖顺序执行：
# 建表类先跑，字段增强类（SHOW COLUMNS / ALTER）依赖对应表已存在。
_BOOTSTRAP_STEPS: Tuple[Tuple[str, str], ...] = (
    ("app.tools.db_user", "_ensure_users_table"),
    ("app.tools.db_experience", "_ensure_experience_card_columns"),
    ("app.tools.db_experience", "_ensure_card_versions_table"),
    ("app.tools.db_job", "_ensure_job_analysis_columns"),
    ("app.tools.db_raw_jd", "_ensure_raw_jd_table"),
    ("app.tools.db_job_entity", "_ensure_job_table"),
    ("app.tools.db_submission", "_ensure_resume_submission_table"),
    ("app.tools.db_interview", "_ensure_interview_preps_table"),
    ("app.tools.db_interview", "_ensure_interview_records_table"),
    ("app.tools.db_interview", "_ensure_interview_qa_pairs_table"),
    ("app.tools.db_submission", "_ensure_interview_submission_columns"),
    ("app.tools.db_base_resume", "_ensure_base_resume_table"),
    ("app.tools.db_profile", "_ensure_user_profiles_table"),
)

# 仅由迁移创建、运行时 DDL 与 docker 基线均不覆盖的核心表（BE-INIT-01）：
# 引导结束前校验存在，缺失说明 V0009 等迁移未执行。
_CORE_TABLES: Tuple[str, ...] = ("expression", "direction")


def _verify_core_tables() -> List[str]:
    """校验仅由迁移创建的核心表是否就绪，返回缺失表名列表。

    :return: 缺失的核心表名；全部存在时为空列表
    :raises MySQLError: 表缺失之外的数据库错误（连接失败等）上抛，
        由调用方按「无法校验」处理，不阻断引导
    """
    missing: List[str] = []
    for table in _CORE_TABLES:
        try:
            db_conn.query_one(f"SELECT 1 FROM `{table}` LIMIT 1")
        except MySQLError as exc:
            if getattr(exc, "errno", None) == 1146:
                missing.append(table)
            else:
                raise
    return missing


def run_schema_bootstrap() -> bool:
    """启动时执行全部运行时 DDL（幂等；已就绪直接返回）。

    任一 `_ensure_*` 抛错即记录告警并返回 False（不置位标志，请求路径降级）；
    步骤全部成功后执行核心表断言（``_verify_core_tables``），缺失同样不置位。
    探测本身失败（连接类错误）不阻断断言之外的置位流程。

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

    try:
        missing = _verify_core_tables()
    except Exception:
        # 核心表探测失败（连接类错误）不阻断：各 _ensure_* 步骤已暴露连接问题
        logger.debug("核心表校验跳过（探测异常，非表缺失）", exc_info=True)
        missing = []
    if missing:
        logger.warning(
            "核心表缺失：%s（V0009 等迁移未执行），请先运行 "
            "python -m migrations.runner migrate；本次不置位 schema-ready",
            ", ".join(missing),
        )
        return False

    db_conn.mark_schema_ready()
    logger.info("schema 引导完成：运行时 DDL 已全部执行，请求路径 _ensure_* 短路生效")
    return True
