import logging
import shutil
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.context import set_session_context, reset_session_context
from app.auth.dependencies import get_current_user
from app.tools import db_tools
from app.tools.upload_file_read_tool import read_file_content

router = APIRouter(tags=["submission"])

logger = logging.getLogger("jobcraft.api.submission")


class CreateSubmissionPayload(BaseModel):
    job_analysis_id: Optional[int] = None
    position: str
    company: str = ""
    jd_text: str = ""
    resume_markdown: Optional[str] = None
    is_manual: bool = False
    status: str = "已投递"


class UpdateSubmissionPayload(BaseModel):
    position: Optional[str] = None
    company: Optional[str] = None
    jd_text: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    resume_markdown: Optional[str] = None
    job_analysis_id: Optional[int] = None
    card_version_ids: Optional[List[int]] = None


def _get_updated_dir():
    from app.api.server import updated_dir

    return updated_dir


@router.post("/api/jobcraft/submission")
def jobcraft_submission_create(
    payload: CreateSubmissionPayload,
    current_user: int = Depends(get_current_user),
):
    try:
        data = payload.model_dump()
        data["user_id"] = current_user
        sid = db_tools.insert_submission(data)
        return db_tools.get_submission(sid, current_user)
    except Exception as e:
        logger.exception("创建投递失败")
        raise HTTPException(status_code=500, detail=f"创建投递失败: {e}")


@router.get("/api/jobcraft/submission/{submission_id}")
def jobcraft_submission_get(
    submission_id: int, current_user: int = Depends(get_current_user)
):
    s = db_tools.get_submission(submission_id, current_user)
    if not s:
        raise HTTPException(status_code=404, detail="投递记录不存在")
    return s


@router.patch("/api/jobcraft/submission/{submission_id}")
def jobcraft_submission_update(
    submission_id: int,
    payload: UpdateSubmissionPayload,
    current_user: int = Depends(get_current_user),
):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        ok = db_tools.update_submission(submission_id, updates, current_user)
        if not ok:
            raise HTTPException(status_code=404, detail="投递记录不存在或无变化")
        return db_tools.get_submission(submission_id, current_user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")


@router.delete("/api/jobcraft/submission/{submission_id}")
def jobcraft_submission_delete(
    submission_id: int, current_user: int = Depends(get_current_user)
):
    try:
        ok = db_tools.delete_submission(submission_id, current_user)
        if not ok:
            raise HTTPException(status_code=404, detail="投递记录不存在")
        return {"deleted": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")


@router.post("/api/jobcraft/submission/manual")
async def jobcraft_submission_manual(
    file: UploadFile = File(...),
    position: str = Form(...),
    company: str = Form(""),
    jd_text: str = Form(""),
    current_user: int = Depends(get_current_user),
):
    MAX_BYTES = 10 * 1024 * 1024
    if file.size is not None and file.size > MAX_BYTES:
        raise HTTPException(status_code=400, detail="文件过大")

    updated_dir = _get_updated_dir()
    upload_id = uuid.uuid4().hex[:12]
    target_dir = updated_dir / f"jobcraft_manual_{upload_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_path = target_dir / file.filename
    with saved_path.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    SUPPORTED_EXTS = {".pdf", ".docx", ".md", ".txt"}
    ext = saved_path.suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise HTTPException(status_code=400, detail=f"暂不支持 {ext} 格式")

    token = set_session_context(str(target_dir))
    try:
        resume_text = read_file_content.invoke(str(saved_path))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件读取失败: {e}")
    finally:
        reset_session_context(token)

    if not resume_text or not resume_text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")
    if len(resume_text.strip()) < 50:
        raise HTTPException(status_code=400, detail="内容过少，请使用纯文本简历")

    resume_text = resume_text.strip()

    try:
        from app.workflows.extract_flow import run_parse_resume_entries_workflow

        entries = run_parse_resume_entries_workflow(resume_text)
    except Exception:
        logger.warning("简历解析失败，降级为单卡")
        entries = []

    created_ids: List[int] = []
    seen: set = set()
    try:
        if entries:
            for ent in entries:
                company = (ent.get("company") or "").strip()
                role = (ent.get("role") or "").strip()
                dedup_key = f"{company}::{role}"
                if company and dedup_key in seen:
                    continue
                if db_tools.find_card_by_company_role(current_user, company, role):
                    seen.add(dedup_key)
                    continue
                seen.add(dedup_key)
                card_id = db_tools.insert_card(
                    {
                        "user_id": current_user,
                        "title": ent.get("title") or role or company or file.filename,
                        "raw_text": db_tools._rebuild_entry_text(ent),
                        "company": company,
                        "role": role,
                        "period": ent.get("period", ""),
                        "card_type": (ent.get("card_type") or "work"),
                        "source": "manual_upload",
                        "tags": [],
                        "ai_structured": {
                            "summary": ent.get("summary", ""),
                            "achievements": ent.get("achievements", []),
                        },
                    }
                )
                created_ids.append(card_id)
        else:
            card_data = {
                "user_id": current_user,
                "title": file.filename or "已投简历",
                "raw_text": resume_text,
                "source": "manual_upload",
            }
            card_id = db_tools.insert_card(card_data)
            created_ids.append(card_id)
    except Exception as e:
        logger.exception("创建经历卡失败")
        raise HTTPException(status_code=500, detail=f"创建经历卡失败: {e}")

    try:
        sid = db_tools.insert_submission(
            {
                "user_id": current_user,
                "position": position,
                "company": company,
                "jd_text": jd_text,
                "resume_markdown": resume_text,
                "is_manual": 1,
                "status": "已投递",
            }
        )
        return db_tools.get_submission(sid, current_user)
    except Exception as e:
        logger.exception("创建投递记录失败")
        raise HTTPException(status_code=500, detail=f"创建投递记录失败: {e}")


@router.get("/api/jobcraft/dashboard")
def jobcraft_dashboard(current_user: int = Depends(get_current_user)):
    try:
        return {"submissions": db_tools.get_dashboard(current_user)}
    except Exception as e:
        logger.exception("获取主页数据失败")
        raise HTTPException(status_code=500, detail=f"获取主页数据失败: {e}")
