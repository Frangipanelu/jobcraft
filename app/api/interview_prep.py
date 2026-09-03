import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.tools import db_tools

router = APIRouter(tags=["interview_prep"])

logger = logging.getLogger("jobcraft.api.interview_prep")


class InterviewPrepPayload(BaseModel):
    round_type: str = "技术面"
    card_ids: List[int]
    submission_id: Optional[int] = None


def _get_previous_review_summary(
    submission_id: Optional[int], user_id: Optional[int] = None
) -> Optional[str]:
    if not submission_id:
        return None
    try:
        rows = db_tools.list_interview_records_by_submission(
            submission_id, user_id=user_id
        )
        if not rows:
            return None
        latest = rows[0]
        analysis = latest.get("analysis_json") or {}
        parts = []
        if analysis.get("strengths"):
            parts.append(f"优势：{'、'.join(analysis['strengths'][:3])}")
        if analysis.get("weaknesses"):
            parts.append(f"劣势：{'、'.join(analysis['weaknesses'][:3])}")
        if analysis.get("action_items"):
            parts.append(f"改进项：{'、'.join(analysis['action_items'][:3])}")
        return "\n".join(parts) if parts else None
    except Exception:
        return None


@router.post("/api/jobcraft/job/{job_id}/interview-prep")
def jobcraft_job_interview_prep(
    job_id: int,
    payload: InterviewPrepPayload,
    current_user: int = Depends(get_current_user),
):
    from app.workflows.interview_prep_flow import run_interview_prep_workflow

    card_ids = payload.card_ids
    if not card_ids:
        card_ids = db_tools.get_selected_card_ids_by_job(job_id)
    if not card_ids:
        raise HTTPException(
            status_code=400, detail="该岗位分析未关联经历卡，请从岗位分析页重新分析"
        )

    company_research = None
    resume_markdown = None
    previous_review_summary = None
    try:
        analysis = db_tools.get_job_analysis(job_id, current_user)
        company = (analysis or {}).get("company", "")
        if company:
            from app.agents.company_research_agent import get_or_search_company

            company_research = get_or_search_company(company)

        submission = None
        if payload.submission_id:
            submission = db_tools.get_submission(payload.submission_id, current_user)
        elif analysis:
            subs = db_tools.list_submissions(current_user)
            for s in subs:
                if s.get("job_analysis_id") == job_id:
                    submission = db_tools.get_submission(s["id"], current_user)
                    break
        if submission:
            resume_markdown = submission.get("resume_markdown")

        previous_review_summary = _get_previous_review_summary(
            payload.submission_id or (submission.get("id") if submission else None),
            current_user,
        )
    except Exception:
        logger.warning("加载面试增强数据失败", exc_info=True)

    try:
        result = run_interview_prep_workflow(
            job_analysis_id=job_id,
            round_type=payload.round_type,
            card_ids=card_ids,
            user_id=current_user,
            submission_id=payload.submission_id,
            company_research=company_research,
            resume_markdown=resume_markdown,
            previous_review_summary=previous_review_summary,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("生成面试稿失败")
        raise HTTPException(status_code=500, detail=f"生成面试稿失败: {e}")


@router.get("/api/jobcraft/job/{job_id}/selected-cards")
def jobcraft_job_get_selected_cards(
    job_id: int, current_user: int = Depends(get_current_user)
):
    try:
        card_ids = db_tools.get_selected_card_ids_by_job(job_id)
        return {"card_ids": card_ids}
    except Exception as e:
        logger.exception("获取选中卡片失败")
        raise HTTPException(status_code=500, detail=f"获取选中卡片失败: {e}")


@router.get("/api/jobcraft/job/{job_id}/interview-prep")
def jobcraft_job_get_interview_prep(
    job_id: int, current_user: int = Depends(get_current_user)
):
    from app.tools import interview_pre

    try:
        result = interview_pre.get_interview_prep(job_id, current_user)
        if not result:
            raise HTTPException(status_code=404, detail="面试稿不存在")
        return result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取面试稿失败")
        raise HTTPException(status_code=500, detail=f"获取面试稿失败: {e}")


@router.get("/api/jobcraft/interview-prep")
def jobcraft_interview_prep_list(
    current_user: int = Depends(get_current_user),
):
    """列出当前用户所有面试准备稿（含公司/岗位/逐字稿/维度题/公司调研）。"""
    from app.schemas.jobcraft import InterviewPrepResult

    try:
        rows = db_tools.list_interview_preps(current_user)
        result = []
        for r in rows:
            extended = r.get("extended_version") or {}
            ability_matrix = r.get("ability_matrix") or []
            try:
                result.append(
                    InterviewPrepResult(
                        job_analysis_id=r["job_analysis_id"],
                        round_type=r.get("round_type", "技术面"),
                        duration=r.get("duration", "10-15 分钟"),
                        elevator_pitch=r.get("elevator_pitch", ""),
                        dimension_questions=ability_matrix,
                        full_version=extended.get("full_version", ""),
                        html_content=r.get("html_content", ""),
                        created_at=r.get("created_at"),
                        company_research=r.get("company_research") or {},
                    ).model_dump()
                    | {
                        "id": r["id"],
                        "company": r.get("company", ""),
                        "position": r.get("position", ""),
                        "submission_id": r.get("submission_id"),
                    }
                )
            except Exception:
                logger.exception("解析面试准备稿记录失败，跳过 id=%s", r.get("id"))
        return {"records": result}
    except Exception as e:
        logger.exception("列出面试准备稿失败")
        raise HTTPException(status_code=500, detail=f"列出面试准备稿失败: {e}")
