"""
JobCraft 任务处理器

定义各种异步任务的处理逻辑。
"""

import logging
from typing import Any, Dict

from .worker import TaskStatus, get_task_manager

logger = logging.getLogger(__name__)


# ============================================================
#  任务类型定义
# ============================================================

TASK_TYPE_RESUME_GENERATE = "resume_generate"
TASK_TYPE_INTERVIEW_PREP = "interview_prep"
TASK_TYPE_EXPORT_PDF = "export_pdf"
TASK_TYPE_EXPORT_DOCX = "export_docx"
TASK_TYPE_BATCH_ANALYZE = "batch_analyze"


# ============================================================
#  任务执行函数
# ============================================================


def execute_resume_generate(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行简历生成任务

    :param params: 任务参数
    :return: 生成结果
    """
    from app.workflows.job_analysis_flow import run_job_analysis_workflow

    task_id = params.get("task_id")
    user_id = params.get("user_id", 1)
    jd_text = params.get("jd_text", "")
    card_ids = params.get("card_ids", [])

    logger.info(f"开始执行简历生成任务: {task_id}")

    try:
        # 更新状态为运行中
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.RUNNING)

        # 执行工作流
        result = run_job_analysis_workflow(
            user_id=user_id,
            jd_text=jd_text,
            card_ids=card_ids,
        )

        # 更新状态为完成
        manager.update_task_status(task_id, TaskStatus.COMPLETED, result=result)

        return result

    except Exception as e:
        logger.error(f"简历生成任务失败: {e}")
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
        raise


def execute_interview_prep(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行面试准备生成任务

    :param params: 任务参数
    :return: 生成结果
    """
    from app.workflows.interview_flow import run_interview_workflow

    task_id = params.get("task_id")
    user_id = params.get("user_id", 1)
    round_type = params.get("round_type", "技术面")
    card_ids = params.get("card_ids", [])

    logger.info(f"开始执行面试准备任务: {task_id}")

    try:
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.RUNNING)

        result = run_interview_workflow(
            user_id=user_id,
            round_type=round_type,
            card_ids=card_ids,
        )

        manager.update_task_status(task_id, TaskStatus.COMPLETED, result=result)
        return result

    except Exception as e:
        logger.error(f"面试准备任务失败: {e}")
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
        raise


def execute_export_pdf(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行 PDF 导出任务

    :param params: 任务参数
    :return: 导出结果（包含文件路径）
    """
    from app.tools import jobcraft_resume

    task_id = params.get("task_id")
    user_id = params.get("user_id", 1)
    card_ids = params.get("card_ids", [])

    logger.info(f"开始执行PDF导出任务: {task_id}")

    try:
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.RUNNING)

        # 生成简历内容
        resume_content = jobcraft_resume.generate_resume(
            user_id=user_id,
            card_ids=card_ids,
        )

        # TODO: 将内容转换为PDF并保存到文件
        # 暂时返回生成的内容
        result = {
            "content": resume_content,
            "message": "PDF导出功能待完善",
        }

        manager.update_task_status(task_id, TaskStatus.COMPLETED, result=result)
        return result

    except Exception as e:
        logger.error(f"PDF导出任务失败: {e}")
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
        raise


# ============================================================
#  任务注册表
# ============================================================

TASK_REGISTRY = {
    TASK_TYPE_RESUME_GENERATE: execute_resume_generate,
    TASK_TYPE_INTERVIEW_PREP: execute_interview_prep,
    TASK_TYPE_EXPORT_PDF: execute_export_pdf,
}


def get_task_handler(task_type: str):
    """
    获取任务处理函数

    :param task_type: 任务类型
    :return: 处理函数
    """
    return TASK_REGISTRY.get(task_type)
