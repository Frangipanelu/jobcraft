import logging
import shutil
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.api.context import set_session_context, reset_session_context
from app.auth.dependencies import get_current_user
from app.schemas.jobcraft import ResumeSuggestionRecord
from app.schemas.submission_status import (
    SubmissionStatus,
    is_valid_transition,
    normalize_status,
    requires_delivered,
    status_to_cn,
)
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
    # P11-a：创建 ≠ 投递，默认「待投递」；「已投递」需用户确认（delivered=1）
    status: str = "PREPARED"
    # T-M5-1 / Q2：「标记投递」创建 submission 时创建即 delivered=1
    # （缺省 False，additive，旧调用方行为不变）
    delivered: bool = False


class UpdateSubmissionPayload(BaseModel):
    position: Optional[str] = None
    company: Optional[str] = None
    # P4-2：jd_text 为 RawJD 不可变快照，传入即拒绝（见 PATCH 端点）
    jd_text: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    resume_markdown: Optional[str] = None
    # FE-RESUME-02：AI 优化建议列表（逐条 Schema 校验；[] 清空，字段缺省不更新）
    resume_suggestions: Optional[List[ResumeSuggestionRecord]] = Field(
        default=None, max_length=50
    )
    job_analysis_id: Optional[int] = None
    card_version_ids: Optional[List[int]] = None
    delivered: Optional[bool] = None


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
        if normalize_status(data.get("status")) is None:
            raise HTTPException(
                status_code=400,
                detail=f"无效的投递状态: {data.get('status')}",
            )
        sid = db_tools.insert_submission(data)
        return db_tools.get_submission(sid, current_user)
    except HTTPException:
        raise
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
        if payload.jd_text is not None:
            # P4-2：原始 JD 为不可变快照（raw_jd），不接受覆写。
            # 权威原文请走 RawJD 快照，jd_text 仅作展示副本。
            raise HTTPException(
                status_code=400,
                detail="jd_text 为不可变快照，不支持覆写；请新增岗位分析以记录新的 JD 原文",
            )
        current = None
        if "status" in updates:
            if normalize_status(updates["status"]) is None:
                raise HTTPException(
                    status_code=400, detail=f"无效的投递状态: {updates['status']}"
                )
            current = db_tools.get_submission(submission_id, current_user)
            if (
                current
                and current.get("status") != normalize_status(updates["status"]).value
            ):
                if not is_valid_transition(current.get("status"), updates["status"]):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"非法状态流转: {status_to_cn(current.get('status'))} "
                            f"→ {status_to_cn(updates['status'])}"
                        ),
                    )
                # P11-a：面试/offer 类状态隐含「已投递」，未确认投递时不自洽
                if requires_delivered(updates["status"]) and not current.get(
                    "delivered"
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"{status_to_cn(updates['status'])} 需先确认已投递（delivered=1）"
                        ),
                    )
        if updates.get("delivered") is True and "status" not in updates:
            # P11-a：用户确认投递 → 状态推进为「已投递」（仅从待投递推进）
            current = db_tools.get_submission(submission_id, current_user)
            if (
                current
                and normalize_status(current.get("status")) is SubmissionStatus.PREPARED
            ):
                updates["status"] = SubmissionStatus.APPLIED.value
        ok = db_tools.update_submission(submission_id, updates, current_user)
        if not ok:
            raise HTTPException(status_code=404, detail="投递记录不存在或无变化")
        return db_tools.get_submission(submission_id, current_user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")


class ResumeSuggestBullet(BaseModel):
    """简历要点定位 + 文本（前端结构化解析产物）"""

    item_index: int = Field(..., ge=0)
    bullet_index: int = Field(..., ge=0)
    text: str = Field(..., max_length=4000)


class ResumeSuggestPayload(BaseModel):
    """resume_suggest 同步入参（JD 上下文由服务端自取，前端不传岗位数据）"""

    bullets: List[ResumeSuggestBullet] = Field(default_factory=list, max_length=200)


@router.post("/api/jobcraft/submission/{submission_id}/resume-suggest")
def jobcraft_submission_resume_suggest(
    submission_id: int,
    payload: ResumeSuggestPayload,
    current_user: int = Depends(get_current_user),
):
    """生成简历 AI 优化建议（1 次 LLM 调用；只算不写，落库走 PATCH）。

    :return: {"suggestions": [ResumeSuggestionRecord, ...]}（含 id/status=pending）
    """
    from app.tools.resume_suggest import load_suggest_context, suggest_resume_edits

    submission = db_tools.get_submission(submission_id, current_user)
    if not submission:
        raise HTTPException(status_code=404, detail="投递记录不存在")
    if not payload.bullets:
        raise HTTPException(status_code=400, detail="简历要点为空，无法生成建议")
    context = load_suggest_context(submission, current_user)
    try:
        suggestions = suggest_resume_edits(
            [b.model_dump() for b in payload.bullets],
            jd_text=context["jd_text"],
            ats=context["ats"],
            gap_items=context["gap_items"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("简历建议生成失败 submission_id=%s", submission_id)
        raise HTTPException(status_code=502, detail=f"建议生成失败: {e}")
    return {"suggestions": suggestions}


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
                "delivered": 1,
                "status": "APPLIED",
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
