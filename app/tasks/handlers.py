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
TASK_TYPE_JD_ANALYZE_STRUCTURED = "jd_analyze_structured"
TASK_TYPE_INTERVIEW_REVIEW_ANALYZE = "interview_review_analyze"
TASK_TYPE_QUESTION_TABLE = "question_table"
TASK_TYPE_PARSE_PREVIEW = "parse_preview"
TASK_TYPE_EXPERIENCE_POLISH = "experience_polish"


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
    company = params.get("company", "")
    position = params.get("position", "")
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
            company=company,
            position=position,
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
    from app.workflows.interview_prep_flow import run_interview_prep_workflow

    task_id = params.get("task_id")
    user_id = params.get("user_id", 1)
    job_analysis_id = params.get("job_analysis_id")
    round_type = params.get("round_type", "技术面")
    card_ids = params.get("card_ids", [])
    submission_id = params.get("submission_id")
    company_research = params.get("company_research")
    resume_markdown = params.get("resume_markdown")
    previous_review_summary = params.get("previous_review_summary")

    if not job_analysis_id:
        raise ValueError("job_analysis_id 缺失，无法生成面试准备")

    logger.info(f"开始执行面试准备任务: {task_id}")

    try:
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.RUNNING)

        result = run_interview_prep_workflow(
            job_analysis_id=job_analysis_id,
            round_type=round_type,
            card_ids=card_ids,
            user_id=user_id,
            submission_id=submission_id,
            company_research=company_research,
            resume_markdown=resume_markdown,
            previous_review_summary=previous_review_summary,
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
    job_analysis_id = params.get("job_analysis_id")
    selected_card_ids = params.get("selected_card_ids") or params.get("card_ids", [])

    if not job_analysis_id:
        raise ValueError("job_analysis_id 缺失，无法导出简历")

    logger.info(f"开始执行PDF导出任务: {task_id}")

    try:
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.RUNNING)

        # 生成简历内容
        resume_content = jobcraft_resume.generate_resume(
            job_analysis_id=job_analysis_id,
            selected_card_ids=selected_card_ids,
            user_id=user_id,
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


def execute_jd_analyze_structured(params: Dict[str, Any]) -> Dict[str, Any]:
    """执行结构化 JD 分析任务（前端已分好 duties/requirements）。

    :param params: 任务参数（company/position/duties/requirements）
    :return: {ats_profile, raw, company, position}
    """
    from app.schemas.jobcraft import StructuredRequirementItem
    from app.workflows.job_analysis_flow import run_structured_ats_workflow

    task_id = params.get("task_id")
    company = params.get("company", "")
    position = params.get("position", "")
    duties = [d for d in params.get("duties", []) if d and str(d).strip()]
    raw_reqs = [
        r
        for r in params.get("requirements", [])
        if r and str(r.get("text", "")).strip()
    ]
    if not duties and not raw_reqs:
        raise ValueError("岗位职责与任职要求不能同时为空")

    requirements = [
        StructuredRequirementItem(**r)
        for r in raw_reqs
        if str(r.get("tag", "required")).lower() in ("hard", "required", "preferred")
    ]

    logger.info(f"开始执行结构化 JD 分析任务: {task_id}")

    try:
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.RUNNING)

        result = run_structured_ats_workflow(
            company=company,
            position=position,
            duties=duties,
            requirements=requirements,
        )

        manager.update_task_status(task_id, TaskStatus.COMPLETED, result=result)
        return result

    except Exception as e:
        logger.error(f"结构化 JD 分析任务失败: {e}")
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
        raise


def execute_interview_review_analyze(params: Dict[str, Any]) -> Dict[str, Any]:
    """执行面试复盘详细分析任务。

    :param params: 任务参数（record_id/selected_sequences/user_id）
    :return: InterviewReviewResult dict
    """
    from app.workflows.interview_review_flow import run_interview_review_workflow

    task_id = params.get("task_id")
    record_id = params.get("record_id")
    selected_sequences = params.get("selected_sequences", [])
    user_id = params.get("user_id", 1)

    if not record_id:
        raise ValueError("record_id 缺失，无法执行复盘分析")

    logger.info(f"开始执行面试复盘分析任务: {task_id}")

    try:
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.RUNNING)

        result = run_interview_review_workflow(
            record_id=record_id,
            selected_sequences=selected_sequences,
            user_id=user_id,
        )

        manager.update_task_status(task_id, TaskStatus.COMPLETED, result=result)
        return result

    except Exception as e:
        logger.error(f"面试复盘分析任务失败: {e}")
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
        raise


def execute_question_table(params: Dict[str, Any]) -> Dict[str, Any]:
    """执行面试问题表生成任务。

    :param params: 任务参数（record_id/user_id）
    :return: {record_id, status, questions}
    """
    from app.workflows.question_table_flow import run_question_table_workflow

    task_id = params.get("task_id")
    record_id = params.get("record_id")
    user_id = params.get("user_id", 1)

    if not record_id:
        raise ValueError("record_id 缺失，无法生成问题表")

    logger.info(f"开始执行问题表生成任务: {task_id}")

    try:
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.RUNNING)

        questions = run_question_table_workflow(record_id=record_id, user_id=user_id)
        result = {
            "record_id": record_id,
            "status": "question_table",
            "questions": questions,
        }

        manager.update_task_status(task_id, TaskStatus.COMPLETED, result=result)
        return result

    except Exception as e:
        logger.error(f"问题表生成任务失败: {e}")
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
        raise


def execute_parse_preview(params: Dict[str, Any]) -> Dict[str, Any]:
    """执行面试记录解析预览任务（含可选的题目意图 LLM 分析）。

    :param params: 任务参数（text/with_intent/company/position/round_type/job_analysis_id）
    :return: {dialogue, qa_pairs, qa_pair_count, speaker_count, role_counts}
    """
    from app.tools import db_tools, interview_review

    task_id = params.get("task_id")
    user_id = params.get("user_id", 1)
    text = params.get("text", "")
    with_intent = bool(params.get("with_intent", False))
    company = params.get("company", "")
    position = params.get("position", "")
    round_type = params.get("round_type", "业务面")
    job_analysis_id = params.get("job_analysis_id")

    if not text or not str(text).strip():
        raise ValueError("面试记录文本不能为空")

    logger.info(f"开始执行面试记录解析预览任务: {task_id}")

    try:
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.RUNNING)

        dialogue = interview_review._parse_dialogue(str(text))
        qa_pairs = interview_review._build_qa_pairs(dialogue)

        jd_text = ""
        if job_analysis_id:
            analysis = db_tools.get_job_analysis(job_analysis_id, user_id)
            if analysis:
                jd_text = analysis.get("jd_text", "")

        if with_intent:
            qa_pairs = interview_review.preview_question_intents(
                qa_pairs=qa_pairs,
                company=company,
                position=position,
                round_type=round_type,
                jd_text=jd_text,
            )

        result = {
            "dialogue": dialogue,
            "qa_pairs": qa_pairs,
            "qa_pair_count": len(qa_pairs),
            "speaker_count": len({d["speaker"] for d in dialogue}),
            "role_counts": {
                "interviewer": sum(
                    1 for d in dialogue if d.get("role") == "interviewer"
                ),
                "candidate": sum(1 for d in dialogue if d.get("role") == "candidate"),
                "unknown": sum(
                    1
                    for d in dialogue
                    if d.get("role") not in ("interviewer", "candidate")
                ),
            },
        }

        manager.update_task_status(task_id, TaskStatus.COMPLETED, result=result)
        return result

    except Exception as e:
        logger.error(f"面试记录解析预览任务失败: {e}")
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
        raise


def execute_experience_polish(params: Dict[str, Any]) -> Dict[str, Any]:
    """执行经历卡 AI 润色任务。

    :param params: 任务参数（raw_text/company/role）
    :return: {polished_text, original_text}
    """
    from app.tools.experience_polish import polish_experience

    task_id = params.get("task_id")
    raw_text = params.get("raw_text", "")
    company = params.get("company", "")
    role = params.get("role", "")

    if not raw_text or not str(raw_text).strip():
        raise ValueError("raw_text 缺失，无法润色经历")

    logger.info(f"开始执行经历润色任务: {task_id}")

    try:
        manager = get_task_manager()
        manager.update_task_status(task_id, TaskStatus.RUNNING)

        polished = polish_experience(raw_text=str(raw_text), company=company, role=role)
        result = {"polished_text": polished, "original_text": raw_text}

        manager.update_task_status(task_id, TaskStatus.COMPLETED, result=result)
        return result

    except Exception as e:
        logger.error(f"经历润色任务失败: {e}")
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
    TASK_TYPE_JD_ANALYZE_STRUCTURED: execute_jd_analyze_structured,
    TASK_TYPE_INTERVIEW_REVIEW_ANALYZE: execute_interview_review_analyze,
    TASK_TYPE_QUESTION_TABLE: execute_question_table,
    TASK_TYPE_PARSE_PREVIEW: execute_parse_preview,
    TASK_TYPE_EXPERIENCE_POLISH: execute_experience_polish,
}


def get_task_handler(task_type: str):
    """
    获取任务处理函数

    :param task_type: 任务类型
    :return: 处理函数
    """
    return TASK_REGISTRY.get(task_type)
