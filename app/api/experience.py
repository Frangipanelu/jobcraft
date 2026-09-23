import logging
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.context import set_session_context, reset_session_context
from app.auth.dependencies import get_current_user
from app.schemas.jobcraft import ExperienceCardCreate, ExperienceCardUpdate
from app.tools import db_tools
from app.tools.upload_file_read_tool import read_file_content

router = APIRouter(prefix="/api/jobcraft/experience", tags=["experience"])

logger = logging.getLogger("jobcraft.api.experience")


class BackfillPayload(BaseModel):
    min_chars: int = 100


def _get_updated_dir() -> Path:
    from app.api.server import updated_dir

    return updated_dir


@router.post("/upload/preview")
async def jobcraft_experience_upload_preview(
    file: UploadFile = File(...),
    current_user: int = Depends(get_current_user),
):
    """预览简历解析结果（不保存），返回解析出的经历条目供用户确认。"""
    MAX_BYTES = 10 * 1024 * 1024
    if file.size is not None and file.size > MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大 ({file.size / 1024 / 1024:.1f}MB > 10MB)",
        )

    updated_dir = _get_updated_dir()
    upload_id = uuid.uuid4().hex[:12]
    target_dir = updated_dir / f"preview_{upload_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_path = target_dir / file.filename
    with saved_path.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    SUPPORTED_EXTS = {".pdf", ".docx", ".md", ".txt"}
    ext = saved_path.suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"暂不支持「{ext or '无后缀'}」格式, 请使用 PDF / DOCX / MD / TXT",
        )

    token = set_session_context(str(target_dir))
    try:
        resume_text = read_file_content.invoke(str(saved_path))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件读取失败: {e}")
    finally:
        reset_session_context(token)

    if not resume_text or not resume_text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")
    if resume_text.startswith("错误"):
        raise HTTPException(status_code=400, detail=resume_text)

    # 反向改造（EXPERIENCE_SPEC §34.3）：规则优先 + LLM 兜底
    try:
        from app.tools.resume_splitter import split_resume_text

        entries = split_resume_text(resume_text.strip())
    except Exception:
        logger.warning("简历规则分块失败")
        entries = None

    # 规则分块失败 → LLM 兜底（单次调用）
    if not entries:
        try:
            from app.workflows.extract_flow import run_parse_resume_entries_workflow

            entries = run_parse_resume_entries_workflow(resume_text.strip())
        except Exception:
            logger.warning("简历预览解析失败")
            entries = []

    # 如果解析出条目，返回结构化预览；否则返回原始文本让用户手动分段
    if entries:
        preview_items = []
        for ent in entries:
            if ent.get("raw_text"):
                raw_text = ent["raw_text"]
            else:
                # LLM 兜底产物：从 achievements 构建可读的 raw_text
                achievements = ent.get("achievements", [])
                bullets = []
                for a in achievements:
                    if isinstance(a, dict):
                        # 提取可读文本，避免输出 JSON
                        parts = []
                        if a.get("title"):
                            parts.append(f"【{a['title']}】")
                        if a.get("situation"):
                            parts.append(f"背景：{a['situation']}")
                        if isinstance(a.get("action"), dict) and a["action"].get(
                            "main"
                        ):
                            parts.append(f"行动：{a['action']['main']}")
                        elif a.get("action"):
                            parts.append(f"行动：{a['action']}")
                        if a.get("result"):
                            parts.append(f"结果：{a['result']}")
                        if parts:
                            bullets.append(" ".join(parts))
                        elif a.get("text"):
                            bullets.append(a["text"])
                        elif a.get("description"):
                            bullets.append(a["description"])
                    elif isinstance(a, str) and a.strip():
                        bullets.append(a.strip())

                raw_text_parts = []
                if ent.get("summary"):
                    raw_text_parts.append(ent["summary"])
                if ent.get("company"):
                    raw_text_parts.append(f"公司：{ent['company']}")
                if ent.get("role"):
                    raw_text_parts.append(f"岗位：{ent['role']}")
                if ent.get("period"):
                    raw_text_parts.append(f"时间：{ent['period']}")
                if bullets:
                    raw_text_parts.append("工作内容：")
                    raw_text_parts.extend(f"- {b}" for b in bullets)

                raw_text = "\n".join(raw_text_parts)

            preview_items.append(
                {
                    "title": ent.get("title")
                    or ent.get("role")
                    or ent.get("company")
                    or "未命名经历",
                    "company": ent.get("company", ""),
                    "role": ent.get("role", ""),
                    "period": ent.get("period", ""),
                    "card_type": ent.get("card_type", "work"),
                    "raw_text": raw_text,
                    "summary": ent.get("summary", ""),
                    "selected": True,  # 默认选中
                }
            )
        return {"mode": "structured", "items": preview_items, "raw_text": ""}
    else:
        return {"mode": "raw", "items": [], "raw_text": resume_text.strip()}


class ConfirmUploadPayload(BaseModel):
    items: List[Dict[str, Any]]
    raw_text: Optional[str] = None


class BaseResumePayload(BaseModel):
    name: str = "上传简历"
    file_size: str = ""
    format: str = "docx"
    parsed_count: int = 0
    tags: List[str] = []


@router.post("/base-resumes", response_model=Dict[str, Any])
async def create_base_resume(
    payload: BaseResumePayload,
    current_user: int = Depends(get_current_user),
):
    """记录一条上传的底座简历（元信息），用于历史版本列表的持久化。"""
    from app.tools.db_base_resume import create_base_resume as db_create
    from app.tools.db_base_resume import list_base_resumes

    existing = list_base_resumes(current_user)
    resume_id = db_create(
        {
            "user_id": current_user,
            "name": payload.name,
            "file_size": payload.file_size,
            "format": payload.format,
            "parsed_count": payload.parsed_count,
            "tags": payload.tags,
            "is_default": len(existing) == 0,
        }
    )
    from app.tools.db_base_resume import get_base_resume

    return get_base_resume(resume_id, current_user)


@router.get("/base-resumes", response_model=List[Dict[str, Any]])
async def list_base_resumes(current_user: int = Depends(get_current_user)):
    """返回当前用户的全部底座简历历史版本。"""
    from app.tools.db_base_resume import list_base_resumes as db_list

    return db_list(current_user)


@router.patch("/base-resumes/{resume_id}/default", response_model=Dict[str, Any])
async def set_default_base_resume(
    resume_id: int,
    current_user: int = Depends(get_current_user),
):
    """把指定底座简历设为默认。"""
    from app.tools.db_base_resume import get_base_resume, set_default_base_resume

    if not get_base_resume(resume_id, current_user):
        raise HTTPException(status_code=404, detail="底座简历不存在")
    set_default_base_resume(resume_id, current_user)
    return get_base_resume(resume_id, current_user)


@router.delete("/base-resumes/{resume_id}")
async def delete_base_resume(
    resume_id: int,
    current_user: int = Depends(get_current_user),
):
    """删除一条底座简历历史记录。"""
    from app.tools.db_base_resume import delete_base_resume as db_delete

    if not db_delete(resume_id, current_user):
        raise HTTPException(status_code=404, detail="底座简历不存在")
    return {"ok": True}


@router.post("/upload/confirm")
async def jobcraft_experience_upload_confirm(
    payload: ConfirmUploadPayload,
    current_user: int = Depends(get_current_user),
):
    """确认保存预览中选中的经历条目。"""
    created_cards = []
    seen: set = set()
    try:
        for item in payload.items:
            if not item.get("selected", True):
                continue
            raw_text = item.get("raw_text") or payload.raw_text or ""
            company = (item.get("company") or "").strip()
            role = (item.get("role") or "").strip()
            dedup_key = f"{company}::{role}"

            # 按 company+role 去重（与 upload 端点对齐）
            if dedup_key in seen:
                continue
            if company and role:
                existing = db_tools.find_card_by_company_role(
                    current_user, company, role
                )
                if existing:
                    seen.add(dedup_key)
                    continue
            seen.add(dedup_key)

            card_data = {
                "user_id": current_user,
                "title": item.get("title") or "未命名经历",
                "raw_text": raw_text,
                "company": item.get("company", ""),
                "role": item.get("role", ""),
                "period": item.get("period", ""),
                "card_type": item.get("card_type", "work"),
                "source": "resume_upload",
                "tags": [],
                # EXP-P1-03：confirmUpload 只入库草稿，定稿在卡片页保存时完成
                "is_confirmed": False,
            }
            card_id = db_tools.insert_card(card_data)

            # AI 结构化抽取
            if raw_text and len(raw_text.strip()) >= 20:
                try:
                    from app.workflows.extract_flow import (
                        run_extract_structured_workflow,
                        run_recommend_tags_workflow,
                    )

                    cache = run_extract_structured_workflow(raw_text.strip())
                    if cache:
                        db_tools.update_card(
                            card_id, {"ai_structured": cache}, current_user
                        )
                    tags = run_recommend_tags_workflow(raw_text.strip())
                    if tags:
                        db_tools.update_card(card_id, {"tags": tags}, current_user)
                except Exception:
                    logger.warning("AI 结构化抽取失败，卡片 id=%s", card_id)

            card = db_tools.get_card(card_id, current_user)
            if card:
                created_cards.append(card)

        # 如果没有结构化条目但有 raw_text，创建单卡
        if not created_cards and payload.raw_text:
            card_data = {
                "user_id": current_user,
                "title": "上传简历",
                "raw_text": payload.raw_text,
                "source": "resume_upload",
                "is_confirmed": False,
            }
            card_id = db_tools.insert_card(card_data)
            card = db_tools.get_card(card_id, current_user)
            if card:
                created_cards.append(card)

        return {"cards": created_cards}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")


@router.post("/upload")
async def jobcraft_experience_upload(
    file: UploadFile = File(...),
    current_user: int = Depends(get_current_user),
):
    MAX_BYTES = 10 * 1024 * 1024
    if file.size is not None and file.size > MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大 ({file.size / 1024 / 1024:.1f}MB > 10MB)",
        )

    updated_dir = _get_updated_dir()
    upload_id = uuid.uuid4().hex[:12]
    target_dir = updated_dir / f"jobcraft_{upload_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_path = target_dir / file.filename
    with saved_path.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    SUPPORTED_EXTS = {".pdf", ".docx", ".md", ".txt"}
    ext = saved_path.suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"暂不支持「{ext or '无后缀'}」格式, 请使用 PDF / DOCX / MD / TXT",
        )

    token = set_session_context(str(target_dir))
    try:
        resume_text = read_file_content.invoke(str(saved_path))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件读取失败: {e}")
    finally:
        reset_session_context(token)

    if not resume_text or not resume_text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")
    if resume_text.startswith("错误"):
        raise HTTPException(status_code=400, detail=resume_text)
    if len(resume_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="内容过少 (可能为扫描件)，请使用纯文本简历",
        )

    try:
        from app.workflows.extract_flow import run_parse_resume_entries_workflow

        entries = run_parse_resume_entries_workflow(resume_text.strip())
    except Exception:
        logger.warning("简历解析失败，降级为单卡")
        entries = []

    created_cards = []
    seen: set = set()
    try:
        if entries:
            for ent in entries:
                company = (ent.get("company") or "").strip()
                role = (ent.get("role") or "").strip()
                dedup_key = f"{company}::{role}"
                if company and dedup_key in seen:
                    continue
                existing = db_tools.find_card_by_company_role(
                    current_user, company, role
                )
                if existing:
                    seen.add(dedup_key)
                    continue
                seen.add(dedup_key)
                card_data = {
                    "user_id": current_user,
                    "title": ent.get("title")
                    or role
                    or company
                    or file.filename
                    or "未命名经历",
                    "raw_text": db_tools._rebuild_entry_text(ent),
                    "company": company,
                    "role": role,
                    "period": ent.get("period", ""),
                    "card_type": (ent.get("card_type") or "work"),
                    "source": "resume_upload",
                    "tags": [],
                    "is_confirmed": False,
                    "ai_structured": {
                        "summary": ent.get("summary", ""),
                        "achievements": ent.get("achievements", []),
                    },
                }
                card_id = db_tools.insert_card(card_data)
                card = db_tools.get_card(card_id, current_user)
                if card:
                    created_cards.append(card)
        else:
            card_data = {
                "user_id": current_user,
                "title": file.filename or "未命名经历",
                "raw_text": resume_text.strip(),
                "source": "resume_upload",
                "is_confirmed": False,
            }
            card_id = db_tools.insert_card(card_data)
            card = db_tools.get_card(card_id, current_user)
            if card:
                try:
                    from app.workflows.extract_flow import (
                        run_extract_structured_workflow,
                        run_recommend_tags_workflow,
                    )

                    cache = run_extract_structured_workflow(resume_text.strip())
                    if cache:
                        db_tools.update_card(
                            card_id, {"ai_structured": cache}, current_user
                        )
                    tags = run_recommend_tags_workflow(resume_text.strip())
                    if tags:
                        db_tools.update_card(card_id, {"tags": tags}, current_user)
                except Exception:
                    logger.warning("自动结构化抽取失败")
                created_cards.append(card)

        return {"cards": created_cards}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建经历卡失败: {e}")


@router.get("/cards")
def jobcraft_experience_list(
    current_user: int = Depends(get_current_user),
    include_inactive: bool = False,
    page: int = 1,
    page_size: int = 20,
):
    try:
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        offset = (page - 1) * page_size

        total = db_tools.count_cards(current_user, include_inactive)
        cards = db_tools.list_cards_paginated(
            current_user, include_inactive, offset, page_size
        )

        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

        return {
            "items": cards,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")


@router.get("/cards/search")
def jobcraft_experience_search(
    q: str,
    current_user: int = Depends(get_current_user),
    include_inactive: bool = False,
    page: int = 1,
    page_size: int = 20,
):
    try:
        if not q or not q.strip():
            raise HTTPException(status_code=400, detail="搜索关键词不能为空")
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        offset = (page - 1) * page_size

        total = db_tools.count_search_cards(current_user, q, include_inactive)
        cards = db_tools.search_cards(
            current_user, q, include_inactive, offset, page_size
        )

        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

        return {
            "items": cards,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "query": q,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {e}")


ALLOWED_CARD_TYPES = {"work", "intern", "project"}


def _validate_card_type(card_type: Optional[str]) -> Optional[str]:
    """校验 card_type 是否在允许枚举内（EXPERIENCE_SPEC §30.4.1），否则抛 400"""
    if card_type is None:
        return card_type
    if card_type not in ALLOWED_CARD_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"card_type 仅允许 work / intern / project，收到: {card_type}",
        )
    return card_type


@router.post("/cards")
def jobcraft_experience_create(
    payload: ExperienceCardCreate,
    current_user: int = Depends(get_current_user),
):
    try:
        _validate_card_type(payload.card_type)
        data = payload.model_dump()
        data["source"] = "manual"
        data["user_id"] = current_user
        # EXP-P1-03：手动建卡即定稿（用户在录入时完成审阅），写 V1 哨兵基线
        data["is_confirmed"] = True
        data["write_baseline"] = True
        card_id = db_tools.insert_card(data)
        return db_tools.get_card(card_id, current_user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"新建失败: {e}")


@router.patch("/cards/{card_id}")
def jobcraft_experience_update(
    card_id: int,
    payload: ExperienceCardUpdate,
    current_user: int = Depends(get_current_user),
):
    try:
        _validate_card_type(payload.card_type)
    except HTTPException:
        raise
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    # EXP-P1-03：is_confirmed 仅作定稿触发信号，不作为普通字段写入
    confirm = bool(updates.pop("is_confirmed", False))
    try:
        ok = db_tools.update_card(card_id, updates, current_user, confirm=confirm)
        if not ok:
            raise HTTPException(status_code=404, detail="卡片不存在或无变化")
        return db_tools.get_card(card_id, current_user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")


@router.delete("/cards/{card_id}")
def jobcraft_experience_delete(
    card_id: int, current_user: int = Depends(get_current_user)
):
    try:
        ok = db_tools.delete_card(card_id, current_user)
        if not ok:
            raise HTTPException(status_code=404, detail="卡片不存在")
        return {"deleted": True, "card_id": card_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")


@router.post("/cards/{card_id}/structure")
def jobcraft_experience_structure(
    card_id: int, current_user: int = Depends(get_current_user)
):
    try:
        card = db_tools.get_card(card_id, current_user)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
        raw_text = card.get("raw_text", "")
        if not raw_text or len(raw_text.strip()) < 20:
            raise HTTPException(
                status_code=400,
                detail="经历内容过短（至少 20 字符），请补充后再试",
            )
        from app.workflows.extract_flow import run_extract_structured_workflow

        cache = run_extract_structured_workflow(raw_text)
        if not cache:
            raise HTTPException(
                status_code=500,
                detail="AI 结构化抽取失败，请检查经历内容是否清晰完整",
            )
        db_tools.update_card(card_id, {"ai_structured": cache}, current_user)
        return db_tools.get_card(card_id, current_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("结构化抽取失败")
        raise HTTPException(status_code=500, detail=f"结构化抽取失败: {e}")


@router.post("/cards/{card_id}/recommend-tags")
def jobcraft_experience_recommend_tags(
    card_id: int, current_user: int = Depends(get_current_user)
):
    try:
        card = db_tools.get_card(card_id, current_user)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
        from app.workflows.extract_flow import run_recommend_tags_workflow

        tags = run_recommend_tags_workflow(card.get("raw_text", ""))
        return {"tags": tags}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("标签推荐失败")
        raise HTTPException(status_code=500, detail=f"标签推荐失败: {e}")


@router.post("/cards/backfill")
def jobcraft_experience_backfill(
    payload: BackfillPayload,
    current_user: int = Depends(get_current_user),
):
    try:
        from app.workflows.extract_flow import run_backfill_workflow

        result = run_backfill_workflow(current_user, payload.min_chars)
        return result
    except Exception as e:
        logger.exception("卡片回填失败")
        raise HTTPException(status_code=500, detail=f"回填失败: {e}")


class PolishPayload(BaseModel):
    raw_text: str
    role: Optional[str] = None
    company: Optional[str] = None


@router.post("/cards/{card_id}/polish")
def jobcraft_experience_polish(
    card_id: int,
    payload: PolishPayload,
    current_user: int = Depends(get_current_user),
):
    """AI 润色经历：优化措辞、强化量化指标、提升专业表述。"""
    card = db_tools.get_card(card_id, current_user)
    if not card:
        raise HTTPException(status_code=404, detail="卡片不存在")

    raw_text = payload.raw_text or card.get("raw_text", "")
    if not raw_text or len(raw_text.strip()) < 10:
        raise HTTPException(status_code=400, detail="经历内容过短，请补充后再试")

    from app.tools.experience_polish import polish_experience

    try:
        polished = polish_experience(
            raw_text=raw_text,
            company=payload.company or "",
            role=payload.role or "",
        )
        return {"polished_text": polished, "original_text": raw_text}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"AI 润色失败: {e}")
    except Exception as e:
        logger.exception("AI 润色失败")
        raise HTTPException(status_code=500, detail=f"AI 润色失败: {e}")
