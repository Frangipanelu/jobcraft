import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.context import set_session_context, reset_session_context
from app.auth.dependencies import get_current_user
from app.tools import db_tools
from app.tools.upload_file_read_tool import read_file_content

router = APIRouter(prefix="/api/jobcraft/interview-review", tags=["interview_review"])

logger = logging.getLogger("jobcraft.api.interview_review")


class InterviewReviewCreatePayload(BaseModel):
    title: str = ""
    company: str = ""
    position: str = ""
    round_type: str = "业务面"
    job_analysis_id: Optional[int] = None
    submission_id: Optional[int] = None
    record_id: Optional[int] = None
    raw_text: str


class MockChatPayload(BaseModel):
    messages: List[dict]
    company: str = ""
    position: str = ""
    round_type: str = "技术面"
    experience_context: str = ""


class InterviewReviewAnalyzePayload(BaseModel):
    selected_sequences: List[int]


class FeedbackCandidateDecisionPayload(BaseModel):
    """T-M8-1 反馈闸门：候选决策请求体。

    target_ref 为候选定位键（experience 目标下即经历卡 id 字符串）。
    四槽位内容（background/problem/actions/results）仅 accept 需要，
    由前端在本地合成后提交，服务端只负责「幂等落卡 + 记台账」。
    """

    target_type: str = "experience"
    target_ref: str
    background: Optional[str] = None
    problem: Optional[str] = None
    actions: Optional[List[str]] = None
    results: Optional[List[str]] = None
    analysis_run_id: str = ""


class InterviewSessionCreatePayload(BaseModel):
    """T-M7-4 预建面试场次（status=planned）请求体：向导字段全透传。"""

    job_analysis_id: Optional[int] = None
    submission_id: Optional[int] = None
    company: str = ""
    position: str = ""
    round_type: str = ""
    round_seq: Optional[int] = None
    occurred_at: Optional[str] = None
    interviewer: Optional[str] = None
    format: Optional[str] = None
    resume_version_id: Optional[int] = None


def _parse_occurred_at(value: Optional[str]) -> Optional[datetime]:
    """解析向导场次时间：空→None；非空但无法解析→ValueError（暴露问题不静默置空）。"""
    text = (value or "").strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"occurred_at 格式错误: {text}")


def _get_updated_dir():
    from app.api.server import updated_dir

    return updated_dir


@router.post("")
def jobcraft_interview_review_create(
    payload: InterviewReviewCreatePayload,
    current_user: int = Depends(get_current_user),
):
    from app.tools import interview_review

    if not payload.raw_text or not payload.raw_text.strip():
        raise HTTPException(status_code=400, detail="面试记录文本不能为空")
    try:
        if payload.record_id is not None:
            # T-M8-7：record_id → update 分支（复用预建 planned 行，不重复插行）
            interview_review.fill_interview_record(
                payload.record_id,
                current_user,
                title=payload.title,
                company=payload.company,
                position=payload.position,
                round_type=payload.round_type,
                raw_text=payload.raw_text,
                job_analysis_id=payload.job_analysis_id,
                submission_id=payload.submission_id,
            )
            record_id = payload.record_id
        else:
            record_id = interview_review.create_interview_record(
                user_id=current_user,
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
            record_id, user_id=current_user
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


@router.post("/session")
def jobcraft_create_interview_session(
    payload: InterviewSessionCreatePayload,
    current_user: int = Depends(get_current_user),
):
    """预建面试场次行（status=planned，T-M7-4 / M7-Q3-A）。

    新建面试即 interview_records +1（record+1 前向骨架）；复盘时经
    T-M8-7 的 record_id → update 分支填充内容。向导字段（round_seq /
    occurred_at / interviewer / format / resume_version_id）全透传落列。
    """
    company = (payload.company or "").strip()
    position = (payload.position or "").strip()
    if not company or not position:
        raise HTTPException(status_code=400, detail="公司与岗位不能为空")
    if payload.round_seq is not None and payload.round_seq < 1:
        raise HTTPException(status_code=400, detail="轮次序号必须 ≥ 1")
    try:
        occurred_at = _parse_occurred_at(payload.occurred_at)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if (
        payload.job_analysis_id is not None
        and db_tools.get_job_analysis(payload.job_analysis_id, current_user) is None
    ):
        raise HTTPException(status_code=400, detail="岗位分析不存在或无权访问")

    title = f"{company}-{position}"
    if payload.round_type:
        title = f"{title}-{payload.round_type}"
    try:
        record_id = db_tools.insert_interview_record(
            {
                "user_id": current_user,
                "title": title,
                "company": company,
                "position": position,
                "round_type": payload.round_type or "",
                "job_analysis_id": payload.job_analysis_id,
                "submission_id": payload.submission_id,
                "raw_text": "",
                "parsed_dialogue": [],
                "analysis": {},
                "status": "planned",
                "round_seq": payload.round_seq,
                "occurred_at": occurred_at,
                "interviewer": (payload.interviewer or "").strip() or None,
                "format": (payload.format or "").strip() or None,
                "resume_version_id": payload.resume_version_id,
            }
        )
    except Exception:
        logger.exception("预建面试场次失败")
        raise HTTPException(status_code=500, detail="预建面试场次失败")
    return {"record_id": record_id, "status": "planned"}


@router.post("/upload")
async def jobcraft_interview_review_upload(
    file: UploadFile = File(...),
    current_user: int = Depends(get_current_user),
    title: str = Form(""),
    company: str = Form(""),
    position: str = Form(""),
    round_type: str = Form("业务面"),
    job_analysis_id: Optional[int] = Form(None),
    submission_id: Optional[int] = Form(None),
    record_id: Optional[int] = Form(None),
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
        if record_id is not None:
            # T-M8-7：record_id → update 分支（复用预建 planned 行，不重复插行）
            interview_review.fill_interview_record(
                record_id,
                current_user,
                title=title,
                company=company,
                position=position,
                round_type=round_type,
                raw_text=raw_text,
                job_analysis_id=job_analysis_id,
                submission_id=submission_id,
            )
            target_record_id = record_id
        else:
            target_record_id = interview_review.create_interview_record(
                user_id=current_user,
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

        qa_pairs_with_intent = run_question_table_workflow(
            target_record_id, user_id=current_user
        )
        return {
            "record_id": target_record_id,
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
    current_user: int = Depends(get_current_user),
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
        analysis = db_tools.get_job_analysis(job_analysis_id, current_user)
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
def jobcraft_interview_review_list(current_user: int = Depends(get_current_user)):
    try:
        return {"records": db_tools.list_interview_records(user_id=current_user)}
    except Exception as e:
        logger.exception("获取面试复盘列表失败")
        raise HTTPException(status_code=500, detail=f"获取面试复盘列表失败: {e}")


@router.get("/qa-pairs")
def jobcraft_interview_review_qa_pairs(
    job_analysis_id: Optional[int] = None,
    current_user: int = Depends(get_current_user),
):
    """T-M8-3 聚合题库：跨场次列出本人 QA 对；不传 job_analysis_id 即全量。

    声明须早于 `@router.get("/{record_id}")`，否则被路径参数吞掉。
    """
    try:
        qa_pairs = db_tools.list_interview_qa_pairs_by_user(
            user_id=current_user, job_analysis_id=job_analysis_id
        )
        return {
            "qa_pairs": qa_pairs,
            "qa_pair_count": len(qa_pairs),
            "job_analysis_id": job_analysis_id,
        }
    except Exception as e:
        logger.exception("获取聚合题库失败")
        raise HTTPException(status_code=500, detail=f"获取聚合题库失败: {e}")


@router.post("/{record_id}/question-table")
def jobcraft_interview_review_question_table(
    record_id: int, current_user: int = Depends(get_current_user)
):
    from app.workflows.question_table_flow import run_question_table_workflow

    try:
        questions = run_question_table_workflow(
            record_id=record_id, user_id=current_user
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
    record_id: int,
    payload: InterviewReviewAnalyzePayload,
    current_user: int = Depends(get_current_user),
):
    from app.workflows.interview_review_flow import run_interview_review_workflow

    # 非空/≤8 校验下沉 workflow（BE-TASKDIV-01），此处只做 HTTP 映射
    try:
        result = run_interview_review_workflow(
            record_id=record_id,
            selected_sequences=payload.selected_sequences,
            user_id=current_user,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("面试复盘详细分析失败")
        raise HTTPException(status_code=500, detail=f"面试复盘详细分析失败: {e}")


@router.post("/mock-chat")
def jobcraft_mock_chat(
    payload: MockChatPayload,
    current_user: int = Depends(get_current_user),
):
    """模拟面试实时对话端点 - 替代前端直连 Gemini"""
    from app.tools.mock_chat import mock_interview_chat

    try:
        reply = mock_interview_chat(
            round_type=payload.round_type,
            company=payload.company or "",
            position=payload.position or "",
            experience_context=payload.experience_context or "",
            messages=payload.messages,
        )
        return {"reply": reply, "role": "interviewer"}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"模拟面试对话失败: {e}")
    except Exception as e:
        logger.exception("模拟面试对话失败")
        raise HTTPException(status_code=500, detail=f"模拟面试对话失败: {e}")


def _feedback_gate_items(record: dict, ledger: List[dict]) -> List[dict]:
    """合并候选正文（analysis_json 唯一来源）与决策台账，输出闸门条目。

    台账只记决策，候选内容仍在 analysis_json——避免同一建议两处存储漂移。
    """
    feedbacks = (record.get("analysis") or {}).get("experienceFeedbacks") or []
    decided = {(row["target_type"], row["target_ref"]): row for row in ledger}
    items: List[dict] = []
    for fb in feedbacks:
        target_ref = str(fb.get("experienceId") or "")
        row = decided.get((fb.get("target_type") or "experience", target_ref))
        items.append(
            {
                "target_type": fb.get("target_type") or "experience",
                "target_ref": target_ref,
                "experience_id": target_ref,
                "experience_title": fb.get("experienceTitle") or "",
                "discovered_issues": fb.get("discoveredIssues") or [],
                "suggestions": fb.get("suggestions") or [],
                "current_version": fb.get("currentVersion") or "",
                "proposed_version": fb.get("proposedVersion") or "",
                "proposed_changes": fb.get("proposedChanges") or [],
                "decision": (row or {}).get("decision") or "pending",
                "card_version": (row or {}).get("card_version"),
                "decided_at": (row or {}).get("decided_at"),
            }
        )
    return items


def _gate_status(items: List[dict]) -> str:
    """闸门状态由台账推导：有待决策候选 → awaiting_confirmation，否则 done。

    不新增 interview_records.status 取值（SPEC §5 分期：`failed`/`done` 是否入库
    留待 M9 裁决），状态由 feedback_candidates 台账派生，刷新不丢。
    """
    if not items:
        return "none"
    return (
        "awaiting_confirmation"
        if any(item["decision"] == "pending" for item in items)
        else "done"
    )


@router.get("/{record_id}/feedback-candidates")
def jobcraft_interview_review_feedback_candidates(
    record_id: int, current_user: int = Depends(get_current_user)
):
    """T-M8-1 反馈闸门：列出复盘候选建议 + 各自动策状态（pending/accepted/rejected）"""
    try:
        record = db_tools.get_interview_record(record_id, current_user)
        if not record:
            raise HTTPException(status_code=404, detail="面试记录不存在")
        ledger = db_tools.list_feedback_candidates(record_id, current_user)
        items = _feedback_gate_items(record, ledger)
        return {
            "record_id": record_id,
            "candidates": items,
            "candidate_count": len(items),
            "pending_count": sum(1 for i in items if i["decision"] == "pending"),
            "gate_status": _gate_status(items),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取复盘反馈候选失败")
        raise HTTPException(status_code=500, detail=f"获取复盘反馈候选失败: {e}")


@router.post("/{record_id}/feedback-candidates/accept")
def jobcraft_interview_review_feedback_accept(
    record_id: int,
    payload: FeedbackCandidateDecisionPayload,
    current_user: int = Depends(get_current_user),
):
    """T-M8-1 反馈闸门：确认沉淀（幂等）——服务端写卡 + 记台账。

    幂等：唯一键 (record_id, target_type, target_ref) 已有 accepted 决策时
    直接返回原决策，不重复写卡（SPEC「重跑复盘 MUST NOT 重复落永久反馈」）。
    """
    try:
        record = db_tools.get_interview_record(record_id, current_user)
        if not record:
            raise HTTPException(status_code=404, detail="面试记录不存在")
        target_ref = payload.target_ref.strip()
        if not target_ref:
            raise HTTPException(status_code=400, detail="target_ref 不能为空")

        existing = db_tools.get_feedback_candidate(
            record_id, payload.target_type, target_ref
        )
        if existing and existing["decision"] == "accepted":
            ledger = db_tools.list_feedback_candidates(record_id, current_user)
            items = _feedback_gate_items(record, ledger)
            return {
                "record_id": record_id,
                "target_ref": target_ref,
                "decision": "accepted",
                "card_version": existing["card_version"],
                "decided_at": existing["decided_at"],
                "idempotent": True,
                "gate_status": _gate_status(items),
            }

        # 候选必须真实存在于 analysis_json，禁止凭空写卡
        ledger = db_tools.list_feedback_candidates(record_id, current_user)
        items = _feedback_gate_items(record, ledger)
        matched = [
            i
            for i in items
            if i["target_type"] == payload.target_type and i["target_ref"] == target_ref
        ]
        if not matched:
            raise HTTPException(status_code=404, detail="反馈候选不存在")

        card_id = int(target_ref)
        card = db_tools.get_card(card_id, current_user)
        if not card:
            raise HTTPException(status_code=404, detail="目标经历卡不存在或无权访问")

        updates = {
            k: v
            for k, v in (
                ("background", payload.background),
                ("problem", payload.problem),
                ("actions", payload.actions),
                ("results", payload.results),
            )
            if v is not None
        }
        if updates:
            db_tools.update_card(card_id, updates, user_id=current_user)
        card_version = (db_tools.get_card(card_id, current_user) or {}).get("version")

        row = db_tools.decide_feedback_candidate(
            record_id=record_id,
            user_id=current_user,
            target_type=payload.target_type,
            target_ref=target_ref,
            decision="accepted",
            card_version=card_version,
            analysis_run_id=payload.analysis_run_id,
        )
        ledger = db_tools.list_feedback_candidates(record_id, current_user)
        return {
            "record_id": record_id,
            "target_ref": target_ref,
            "decision": row["decision"],
            "card_version": row["card_version"],
            "decided_at": row["decided_at"],
            "idempotent": False,
            "gate_status": _gate_status(_feedback_gate_items(record, ledger)),
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("复盘反馈确认失败")
        raise HTTPException(status_code=500, detail=f"复盘反馈确认失败: {e}")


@router.post("/{record_id}/feedback-candidates/reject")
def jobcraft_interview_review_feedback_reject(
    record_id: int,
    payload: FeedbackCandidateDecisionPayload,
    current_user: int = Depends(get_current_user),
):
    """T-M8-1 反馈闸门：忽略候选（不写卡，仅记台账，可反悔重确认）"""
    try:
        record = db_tools.get_interview_record(record_id, current_user)
        if not record:
            raise HTTPException(status_code=404, detail="面试记录不存在")
        target_ref = payload.target_ref.strip()
        if not target_ref:
            raise HTTPException(status_code=400, detail="target_ref 不能为空")

        ledger = db_tools.list_feedback_candidates(record_id, current_user)
        items = _feedback_gate_items(record, ledger)
        matched = [
            i
            for i in items
            if i["target_type"] == payload.target_type and i["target_ref"] == target_ref
        ]
        if not matched:
            raise HTTPException(status_code=404, detail="反馈候选不存在")

        row = db_tools.decide_feedback_candidate(
            record_id=record_id,
            user_id=current_user,
            target_type=payload.target_type,
            target_ref=target_ref,
            decision="rejected",
            analysis_run_id=payload.analysis_run_id,
        )
        ledger = db_tools.list_feedback_candidates(record_id, current_user)
        return {
            "record_id": record_id,
            "target_ref": target_ref,
            "decision": row["decision"],
            "card_version": row["card_version"],
            "decided_at": row["decided_at"],
            "gate_status": _gate_status(_feedback_gate_items(record, ledger)),
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("复盘反馈忽略失败")
        raise HTTPException(status_code=500, detail=f"复盘反馈忽略失败: {e}")


@router.get("/{record_id}")
def jobcraft_interview_review_detail(
    record_id: int, current_user: int = Depends(get_current_user)
):
    try:
        record = db_tools.get_interview_record(record_id, current_user)
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
def jobcraft_interview_review_delete(
    record_id: int, current_user: int = Depends(get_current_user)
):
    try:
        db_tools.delete_interview_record(record_id, current_user)
        return {"status": "deleted", "record_id": record_id}
    except Exception as e:
        logger.exception("删除面试复盘失败")
        raise HTTPException(status_code=500, detail=f"删除面试复盘失败: {e}")
