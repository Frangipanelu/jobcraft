import logging
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.context import set_session_context, reset_session_context
from app.tools import db_tools
from app.tools.upload_file_read_tool import read_file_content

router = APIRouter(prefix="/api/jobcraft/interview-review", tags=["interview_review"])

logger = logging.getLogger("jobcraft.api.interview_review")


class InterviewReviewCreatePayload(BaseModel):
    user_id: int = 1
    title: str = ""
    company: str = ""
    position: str = ""
    round_type: str = "业务面"
    job_analysis_id: Optional[int] = None
    submission_id: Optional[int] = None
    raw_text: str


class InterviewReviewQuestionTablePayload(BaseModel):
    user_id: int = 1


class InterviewReviewAnalyzePayload(BaseModel):
    user_id: int = 1
    selected_sequences: List[int]


def _get_updated_dir():
    from app.api.server import updated_dir

    return updated_dir


@router.post("")
def jobcraft_interview_review_create(payload: InterviewReviewCreatePayload):
    from app.tools import interview_review

    if not payload.raw_text or not payload.raw_text.strip():
        raise HTTPException(status_code=400, detail="面试记录文本不能为空")
    try:
        record_id = interview_review.create_interview_record(
            user_id=payload.user_id,
            title=payload.title,
            company=payload.company,
            position=payload.position,
            round_type=payload.round_type,
            raw_text=payload.raw_text,
            job_analysis_id=payload.job_analysis_id,
            submission_id=payload.submission_id,
        )
        dialogue = interview_review._parse_dialogue(payload.raw_text)
        from app.workflows.question_table_flow import run_question_table_workflow

        qa_pairs_with_intent = run_question_table_workflow(
            record_id, user_id=payload.user_id
        )
        return {
            "record_id": record_id,
            "status": "parsed",
            "qa_pairs": qa_pairs_with_intent,
            "qa_pair_count": len(qa_pairs_with_intent),
            "dialogue": dialogue,
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("面试复盘创建失败")
        raise HTTPException(status_code=500, detail=f"面试复盘创建失败: {e}")


@router.post("/upload")
async def jobcraft_interview_review_upload(
    file: UploadFile = File(...),
    user_id: int = Form(1),
    title: str = Form(""),
    company: str = Form(""),
    position: str = Form(""),
    round_type: str = Form("业务面"),
    job_analysis_id: Optional[int] = Form(None),
    submission_id: Optional[int] = Form(None),
):
    from app.tools import interview_review

    if not position or not position.strip():
        raise HTTPException(status_code=400, detail="岗位名称不能为空")

    MAX_BYTES = 10 * 1024 * 1024
    if file.size is not None and file.size > MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大 ({file.size / 1024 / 1024:.1f}MB > 10MB)",
        )

    SUPPORTED_EXTS = {".txt", ".md", ".pdf", ".docx"}
    ext = (file.filename or "").lower()
    suffix = Path(ext).suffix
    if suffix not in SUPPORTED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"暂不支持 {suffix or '无后缀'} 格式，请上传 TXT / PDF / DOCX / MD",
        )

    updated_dir = _get_updated_dir()
    upload_id = uuid.uuid4().hex[:12]
    target_dir = updated_dir / f"interview_review_{upload_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_path = target_dir / file.filename
    with saved_path.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    token = set_session_context(str(target_dir))
    try:
        try:
            raw_text = read_file_content.invoke(str(saved_path))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"文件解析失败: {e}")
    finally:
        reset_session_context(token)

    if not raw_text or not raw_text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")
    if raw_text.startswith("错误"):
        raise HTTPException(status_code=400, detail=raw_text)
    if len(raw_text.strip()) < 30:
        raise HTTPException(
            status_code=400,
            detail=f"文件内容过短 (仅 {len(raw_text.strip())} 字符)，请检查文件",
        )

    try:
        record_id = interview_review.create_interview_record(
            user_id=user_id,
            title=title,
            company=company,
            position=position,
            round_type=round_type,
            raw_text=raw_text,
            job_analysis_id=job_analysis_id,
            submission_id=submission_id,
        )
        dialogue = interview_review._parse_dialogue(raw_text)
        from app.workflows.question_table_flow import run_question_table_workflow

        qa_pairs_with_intent = run_question_table_workflow(record_id, user_id=user_id)
        return {
            "record_id": record_id,
            "status": "parsed",
            "qa_pairs": qa_pairs_with_intent,
            "qa_pair_count": len(qa_pairs_with_intent),
            "dialogue": dialogue,
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("面试复盘文件创建失败")
        raise HTTPException(status_code=500, detail=f"面试复盘文件创建失败: {e}")


@router.post("/parse-preview")
async def jobcraft_interview_review_parse_preview(
    raw_text: str = Form(""),
    file: Optional[UploadFile] = File(None),
    company: str = Form(""),
    position: str = Form(""),
    round_type: str = Form("业务面"),
    job_analysis_id: Optional[int] = Form(None),
    with_intent: bool = Form(False),
):
    from app.tools import interview_review

    text = raw_text or ""

    if file and file.filename:
        MAX_BYTES = 10 * 1024 * 1024
        if file.size is not None and file.size > MAX_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"文件过大 ({file.size / 1024 / 1024:.1f}MB > 10MB)",
            )

        SUPPORTED_EXTS = {".txt", ".md", ".pdf", ".docx"}
        ext = (file.filename or "").lower()
        suffix = Path(ext).suffix
        if suffix not in SUPPORTED_EXTS:
            raise HTTPException(
                status_code=400,
                detail=f"暂不支持 {suffix or '无后缀'} 格式，请上传 TXT / PDF / DOCX / MD",
            )

        updated_dir = _get_updated_dir()
        upload_id = uuid.uuid4().hex[:12]
        target_dir = updated_dir / f"interview_preview_{upload_id}"
        target_dir.mkdir(parents=True, exist_ok=True)
        saved_path = target_dir / file.filename
        with saved_path.open("wb") as buf:
            shutil.copyfileobj(file.file, buf)

        token = set_session_context(str(target_dir))
        try:
            file_text = read_file_content.invoke(str(saved_path))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"文件解析失败: {e}")
        finally:
            reset_session_context(token)

        if not file_text or not file_text.strip():
            raise HTTPException(status_code=400, detail="文件内容为空")
        if file_text.startswith("错误"):
            raise HTTPException(status_code=400, detail=file_text)
        if len(file_text.strip()) < 30:
            raise HTTPException(
                status_code=400,
                detail=f"文件内容过短 (仅 {len(file_text.strip())} 字符)，请检查文件",
            )
        text = file_text

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="面试记录文本不能为空")
    if len(text.strip()) < 30:
        raise HTTPException(
            status_code=400,
            detail=f"面试记录文本过短 (仅 {len(text.strip())} 字符)，请补充内容",
        )

    dialogue = interview_review._parse_dialogue(text)
    qa_pairs = interview_review._build_qa_pairs(dialogue)

    jd_text = ""
    if job_analysis_id:
        analysis = db_tools.get_job_analysis(job_analysis_id)
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

    return {
        "dialogue": dialogue,
        "qa_pairs": qa_pairs,
        "qa_pair_count": len(qa_pairs),
        "speaker_count": len({d["speaker"] for d in dialogue}),
        "role_counts": {
            "interviewer": sum(1 for d in dialogue if d.get("role") == "interviewer"),
            "candidate": sum(1 for d in dialogue if d.get("role") == "candidate"),
            "unknown": sum(
                1 for d in dialogue if d.get("role") not in ("interviewer", "candidate")
            ),
        },
    }


@router.get("")
def jobcraft_interview_review_list(user_id: int = 1):
    try:
        return {"records": db_tools.list_interview_records(user_id=user_id)}
    except Exception as e:
        logger.exception("获取面试复盘列表失败")
        raise HTTPException(status_code=500, detail=f"获取面试复盘列表失败: {e}")


@router.post("/{record_id}/question-table")
def jobcraft_interview_review_question_table(
    record_id: int, payload: InterviewReviewQuestionTablePayload
):
    from app.workflows.question_table_flow import run_question_table_workflow

    try:
        questions = run_question_table_workflow(
            record_id=record_id, user_id=payload.user_id
        )
        return {
            "record_id": record_id,
            "status": "question_table",
            "questions": questions,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("生成面试问题表失败")
        raise HTTPException(status_code=500, detail=f"生成面试问题表失败: {e}")


@router.post("/{record_id}/analyze")
def jobcraft_interview_review_analyze(
    record_id: int, payload: InterviewReviewAnalyzePayload
):
    from app.workflows.interview_review_flow import run_interview_review_workflow

    if not payload.selected_sequences:
        raise HTTPException(status_code=400, detail="请至少选择 1 个问题进行详细解析")
    if len(payload.selected_sequences) > 8:
        raise HTTPException(
            status_code=400, detail="因模型输出长度限制，每次最多选择 8 个问题"
        )
    try:
        result = run_interview_review_workflow(
            record_id=record_id,
            selected_sequences=payload.selected_sequences,
            user_id=payload.user_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("面试复盘详细分析失败")
        raise HTTPException(status_code=500, detail=f"面试复盘详细分析失败: {e}")


@router.get("/{record_id}")
def jobcraft_interview_review_detail(record_id: int, user_id: int = 1):
    try:
        record = db_tools.get_interview_record(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="面试记录不存在")
        qa_pairs = db_tools.list_interview_qa_pairs(record_id)
        return {
            "record": record,
            "qa_pairs": qa_pairs,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取面试复盘详情失败")
        raise HTTPException(status_code=500, detail=f"获取面试复盘详情失败: {e}")


@router.delete("/{record_id}")
def jobcraft_interview_review_delete(record_id: int, user_id: int = 1):
    try:
        db_tools.delete_interview_record(record_id)
        return {"status": "deleted", "record_id": record_id}
    except Exception as e:
        logger.exception("删除面试复盘失败")
        raise HTTPException(status_code=500, detail=f"删除面试复盘失败: {e}")
