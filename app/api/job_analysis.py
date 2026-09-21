import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.tools import db_tools, jobcraft_resume
from app.workflows.job_analysis_flow import run_job_analysis_workflow

router = APIRouter(prefix="/api/jobcraft/job", tags=["job_analysis"])

logger = logging.getLogger("jobcraft.api.job_analysis")


class JobAnalyzePayload(BaseModel):
    company: str = ""
    position: str
    jd_text: str
    card_ids: List[int] = Field(default_factory=list)


class JDSplitPayload(BaseModel):
    jd_text: str


class StructuredJDRequest(BaseModel):
    company: str = ""
    position: str = ""
    duties: List[str]
    requirements: List[Dict[str, Any]]


class SaveResumePayload(BaseModel):
    job_analysis_id: int
    selected_card_ids: List[int] = Field(default_factory=list)
    card_versions: Optional[Dict[int, str]] = None
    personal_info: Optional[Dict[str, Any]] = None


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
        analysis = db_tools.get_job_analysis(job_id, current_user)
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
        ok = db_tools.delete_job_analysis(job_id, current_user)
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
            user_id=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成简历失败: {e}")


@router.post("/split-jd")
def jobcraft_jd_split(
    payload: JDSplitPayload,
    current_user: int = Depends(get_current_user),
):
    """把粘贴的原始 JD 拆成 岗位职责/任职要求（含标签），供前端结构化表单预填。"""
    if not payload.jd_text or not payload.jd_text.strip():
        raise HTTPException(status_code=400, detail="JD 文本不能为空")
    if len(payload.jd_text) > 10000:
        raise HTTPException(
            status_code=400, detail=f"JD 文本过长 ({len(payload.jd_text)} 字)"
        )
    try:
        from app.workflows.job_analysis_flow import run_structured_ats_split

        return run_structured_ats_split(payload.jd_text)
    except Exception as e:
        logger.exception("JD 拆分失败")
        raise HTTPException(status_code=500, detail=f"JD 拆分失败: {e}")


@router.post("/analyze-ats-structured")
def jobcraft_job_analyze_ats_structured(
    payload: StructuredJDRequest,
    current_user: int = Depends(get_current_user),
):
    """结构化 JD 分析：前端已把文本分好类，只对两块内容做细节分析。

    duties / requirements 均按条传入；requirements 的每条带 tag
    （hard 硬性门槛 / required 必选 / preferred 加分）。
    """
    duties = [d.strip() for d in payload.duties if d and d.strip()]
    reqs = []
    for r in payload.requirements:
        text = str(r.get("text", "")).strip()
        if not text:
            continue
        tag = str(r.get("tag", "required")).strip().lower()
        if tag not in ("hard", "required", "preferred"):
            raise HTTPException(
                status_code=400,
                detail=f"标签 {tag} 非法，仅支持 hard/required/preferred",
            )
        reqs.append({"text": text, "tag": tag})
    if not duties and not reqs:
        raise HTTPException(status_code=400, detail="岗位职责与任职要求不能同时为空")
    try:
        from app.schemas.jobcraft import StructuredRequirementItem
        from app.workflows.job_analysis_flow import run_structured_ats_workflow

        return run_structured_ats_workflow(
            company=payload.company,
            position=payload.position,
            duties=duties,
            requirements=[StructuredRequirementItem(**r) for r in reqs],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("结构化 ATS 解析失败")
        raise HTTPException(status_code=500, detail=f"结构化 ATS 解析失败: {e}")


@router.get("/resume/download")
def jobcraft_resume_download(path: str, current_user: int = Depends(get_current_user)):
    from app.api.server import output_dir

    try:
        abs_path = Path(path).resolve()
        output_abs = output_dir.resolve()
        if not abs_path.is_relative_to(output_abs):
            raise HTTPException(
                status_code=403, detail="拒绝访问: 只能下载 output 目录下的文件"
            )
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("简历下载路径参数校验失败: %s", exc)
        raise HTTPException(status_code=400, detail="无效的路径参数")
    from fastapi.responses import FileResponse

    return FileResponse(abs_path, filename=abs_path.name, media_type="text/markdown")
