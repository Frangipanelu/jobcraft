import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.tools import db_tools, jobcraft_resume
from app.workflows.job_analysis_flow import run_job_analysis_workflow

router = APIRouter(prefix="/api/jobcraft/job", tags=["job_analysis"])

logger = logging.getLogger("jobcraft.api.job_analysis")


class JobAnalyzePayload(BaseModel):
    company: str = ""
    position: str
    jd_text: str
    card_ids: List[int]


class ATSRecommendPayload(BaseModel):
    company: str
    position: str
    jd_text: str


class GapPolishPayload(BaseModel):
    job_analysis_id: int
    card_ids: List[int]


class SaveCardVersionPayload(BaseModel):
    card_id: int
    source_type: str = "job_analysis"
    source_id: int
    raw_text: str
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    note: Optional[str] = None


class ATSOnlyPayload(BaseModel):
    position: str = ""
    jd_text: str


class SaveResumePayload(BaseModel):
    job_analysis_id: int
    selected_card_ids: List[int]
    card_versions: Optional[Dict[int, str]] = None
    personal_info: Optional[Dict[str, Any]] = None


@router.post("/step1-ats-recommend")
def jobcraft_step1_ats_recommend(
    payload: ATSRecommendPayload,
    current_user: int = Depends(get_current_user),
):
    if not payload.jd_text or not payload.jd_text.strip():
        raise HTTPException(status_code=400, detail="JD 文本不能为空")
    if len(payload.jd_text) > 10000:
        raise HTTPException(status_code=400, detail="JD 文本过长")
    try:
        from app.workflows.job_analysis_flow import run_step1_workflow

        all_cards = db_tools.list_cards(current_user, include_inactive=False)
        result = run_step1_workflow(
            user_id=current_user,
            company=payload.company,
            position=payload.position,
            jd_text=payload.jd_text,
            cards=all_cards,
        )

        job_id = db_tools.insert_job_analysis(
            {
                "user_id": current_user,
                "company": payload.company,
                "position": payload.position or result["ats"].get("job_title", ""),
                "jd_text": payload.jd_text,
                "jd_requirements": result["ats"],
            }
        )

        return {
            "job_analysis_id": job_id,
            "ats": result["ats"],
            "recommended_cards": result["recommended_cards"],
            "all_cards": all_cards,
        }
    except Exception as e:
        logger.exception("ATS+推荐失败")
        raise HTTPException(status_code=500, detail=f"分析失败: {e}")


@router.post("/step2-gap-polish")
def jobcraft_step2_gap_polish(
    payload: GapPolishPayload,
    current_user: int = Depends(get_current_user),
):
    if not payload.card_ids:
        raise HTTPException(status_code=400, detail="请至少选择 1 张经历卡")
    try:
        from app.workflows.job_analysis_flow import run_step2_workflow

        result = run_step2_workflow(payload.job_analysis_id, payload.card_ids)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("缺口+润色失败")
        raise HTTPException(status_code=500, detail=f"分析失败: {e}")


@router.post("/save-card-version")
def jobcraft_job_save_card_version(
    payload: SaveCardVersionPayload,
    current_user: int = Depends(get_current_user),
):
    if not payload.raw_text or not payload.raw_text.strip():
        raise HTTPException(status_code=400, detail="内容不能为空")
    try:
        version_id = db_tools.insert_card_version(
            {
                "card_id": payload.card_id,
                "version_type": "polished",
                "source_type": payload.source_type,
                "source_id": payload.source_id,
                "title": payload.title,
                "raw_text": payload.raw_text,
                "tags": payload.tags,
                "note": payload.note,
            }
        )
        return {"version_id": version_id, "status": "saved"}
    except Exception as e:
        logger.exception("保存版本失败")
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")


@router.post("/analyze")
def jobcraft_job_analyze(
    payload: JobAnalyzePayload,
    current_user: int = Depends(get_current_user),
):
    if not payload.company or not payload.company.strip():
        raise HTTPException(status_code=400, detail="公司名不能为空")
    if not payload.position or not payload.position.strip():
        raise HTTPException(status_code=400, detail="岗位名不能为空")
    if not payload.jd_text or not payload.jd_text.strip():
        raise HTTPException(status_code=400, detail="JD 文本不能为空")
    if len(payload.jd_text) > 10000:
        raise HTTPException(
            status_code=400, detail=f"JD 文本过长 ({len(payload.jd_text)} 字)"
        )
    if not payload.card_ids:
        raise HTTPException(status_code=400, detail="请至少选择 1 张经历卡")
    try:
        return run_job_analysis_workflow(
            user_id=current_user,
            company=payload.company,
            position=payload.position,
            jd_text=payload.jd_text,
            card_ids=payload.card_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("岗位分析失败")
        raise HTTPException(status_code=500, detail=f"岗位分析失败: {e}")


@router.get("/analyses")
def jobcraft_job_list(current_user: int = Depends(get_current_user), limit: int = 20):
    try:
        return {"analyses": db_tools.list_job_analyses(current_user, limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")


@router.get("/analyze/{job_id}")
def jobcraft_job_get(job_id: int, current_user: int = Depends(get_current_user)):
    try:
        analysis = db_tools.get_job_analysis(job_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="记录不存在")
        return analysis
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")


@router.delete("/analyze/{job_id}")
def jobcraft_job_delete(job_id: int, current_user: int = Depends(get_current_user)):
    try:
        ok = db_tools.delete_job_analysis(job_id)
        if not ok:
            raise HTTPException(status_code=404, detail="记录不存在")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")


@router.post("/save-resume")
def jobcraft_job_save_resume(
    payload: SaveResumePayload,
    current_user: int = Depends(get_current_user),
):
    if not payload.selected_card_ids:
        raise HTTPException(status_code=400, detail="请至少选择 1 张经历卡")
    try:
        return jobcraft_resume.generate_resume(
            job_analysis_id=payload.job_analysis_id,
            selected_card_ids=payload.selected_card_ids,
            card_versions=payload.card_versions,
            personal_info=payload.personal_info,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成简历失败: {e}")


@router.post("/analyze-ats")
def jobcraft_job_analyze_ats(
    payload: ATSOnlyPayload,
    current_user: int = Depends(get_current_user),
):
    if not payload.jd_text or not payload.jd_text.strip():
        raise HTTPException(status_code=400, detail="JD 文本不能为空")
    if len(payload.jd_text) > 10000:
        raise HTTPException(
            status_code=400, detail=f"JD 文本过长 ({len(payload.jd_text)} 字)"
        )
    try:
        from app.workflows.job_analysis_flow import run_analyze_ats_workflow

        ats = run_analyze_ats_workflow(payload.jd_text)
        return {"ats_profile": ats}
    except Exception as e:
        logger.exception("ATS 解析失败")
        raise HTTPException(status_code=500, detail=f"ATS 解析失败: {e}")


@router.post("/{job_id}/resume-preview")
def jobcraft_job_resume_preview(
    job_id: int,
    payload: Optional[dict] = None,
    current_user: int = Depends(get_current_user),
):
    payload = payload or {}
    try:
        analysis = db_tools.get_job_analysis(job_id)
        if not analysis:
            raise HTTPException(
                status_code=404, detail=f"job_analysis #{job_id} 不存在"
            )
        selected_ids = (
            payload.get("selected_card_ids") or analysis.get("selected_card_ids") or []
        )
        cards = []
        for cid in selected_ids:
            c = db_tools.get_card(cid)
            if c and c.get("is_active"):
                cards.append(c)
        if not cards:
            raise HTTPException(status_code=400, detail="无可用经历卡")

        from app.workflows.job_analysis_flow import run_resume_preview_workflow

        result = run_resume_preview_workflow(job_id, selected_ids)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("简历预览失败")
        raise HTTPException(status_code=500, detail=f"简历预览失败: {e}")


@router.get("/resume/download")
def jobcraft_resume_download(path: str, current_user: int = Depends(get_current_user)):
    from app.api.server import output_dir

    try:
        abs_path = Path(path).resolve()
        output_abs = output_dir.resolve()
        if not abs_path.is_relative_to(output_abs):
            return {"error": "拒绝访问: 只能下载 output 目录下的文件"}
    except Exception:
        return {"error": "无效的路径参数"}
    if not abs_path.exists():
        return {"error": "文件不存在"}
    from fastapi.responses import FileResponse

    return FileResponse(abs_path, filename=abs_path.name, media_type="text/markdown")
