import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.context import set_session_context, reset_session_context
from app.schemas.jobcraft import ExperienceCardCreate, ExperienceCardUpdate
from app.tools import db_tools
from app.tools.upload_file_read_tool import read_file_content

router = APIRouter(prefix="/api/jobcraft/experience", tags=["experience"])

logger = logging.getLogger("jobcraft.api.experience")


class StructCachePayload(BaseModel):
    user_id: int = 1


class BackfillPayload(BaseModel):
    user_id: int = 1
    min_chars: int = 100


def _get_updated_dir() -> Path:
    from app.api.server import updated_dir

    return updated_dir


@router.post("/upload")
async def jobcraft_experience_upload(
    file: UploadFile = File(...),
    user_id: int = Form(1),
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
                existing = db_tools.find_card_by_company_role(user_id, company, role)
                if existing:
                    seen.add(dedup_key)
                    continue
                seen.add(dedup_key)
                card_data = {
                    "user_id": user_id,
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
                    "ai_structured": {
                        "summary": ent.get("summary", ""),
                        "achievements": ent.get("achievements", []),
                    },
                }
                card_id = db_tools.insert_card(card_data)
                card = db_tools.get_card(card_id)
                if card:
                    created_cards.append(card)
        else:
            card_data = {
                "user_id": user_id,
                "title": file.filename or "未命名经历",
                "raw_text": resume_text.strip(),
                "source": "resume_upload",
            }
            card_id = db_tools.insert_card(card_data)
            card = db_tools.get_card(card_id)
            if card:
                try:
                    from app.workflows.extract_flow import (
                        run_extract_structured_workflow,
                        run_recommend_tags_workflow,
                    )

                    cache = run_extract_structured_workflow(resume_text.strip())
                    if cache:
                        db_tools.update_card(card_id, {"ai_structured": cache})
                    tags = run_recommend_tags_workflow(resume_text.strip())
                    if tags:
                        db_tools.update_card(card_id, {"tags": tags})
                except Exception:
                    logger.warning("自动结构化抽取失败")
                created_cards.append(card)

        return {"cards": created_cards}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建经历卡失败: {e}")


@router.get("/cards")
def jobcraft_experience_list(
    user_id: int = 1,
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

        total = db_tools.count_cards(user_id, include_inactive)
        cards = db_tools.list_cards_paginated(
            user_id, include_inactive, offset, page_size
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
    user_id: int = 1,
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

        total = db_tools.count_search_cards(user_id, q, include_inactive)
        cards = db_tools.search_cards(user_id, q, include_inactive, offset, page_size)

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


@router.get("/export")
def jobcraft_experience_export(
    user_id: int = 1,
    card_ids: Optional[List[int]] = None,
    format: str = "json",
):
    try:
        if card_ids:
            cards = [
                db_tools.get_card(cid) for cid in card_ids if db_tools.get_card(cid)
            ]
        else:
            cards = db_tools.list_cards(user_id, include_inactive=True)

        if not cards:
            raise HTTPException(status_code=404, detail="没有可导出的经历卡")

        if format == "json":
            return {
                "format": "json",
                "count": len(cards),
                "data": cards,
            }

        elif format == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            headers = [
                "id",
                "company",
                "role",
                "period",
                "title",
                "tags",
                "is_active",
                "created_at",
            ]
            writer.writerow(headers)

            for card in cards:
                row = [
                    card.get("id", ""),
                    card.get("company", ""),
                    card.get("role", ""),
                    card.get("period", ""),
                    card.get("title", ""),
                    ",".join(card.get("tags", [])),
                    card.get("is_active", True),
                    card.get("created_at", ""),
                ]
                writer.writerow(row)

            return {
                "format": "csv",
                "count": len(cards),
                "content": output.getvalue(),
                "filename": f"experience_cards_{user_id}.csv",
            }

        elif format == "markdown":
            md_lines = ["# 经历卡导出\n"]
            md_lines.append(f"导出时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            md_lines.append(f"用户ID: {user_id}\n")
            md_lines.append(f"卡片数量: {len(cards)}\n\n")

            for card in cards:
                md_lines.append(
                    f"## {card.get('company', '未知公司')} - {card.get('role', '未知岗位')}\n"
                )
                md_lines.append(f"- **时间段**: {card.get('period', '未知')}\n")
                md_lines.append(f"- **标题**: {card.get('title', '无标题')}\n")
                md_lines.append(f"- **标签**: {', '.join(card.get('tags', []))}\n")
                md_lines.append(
                    f"- **状态**: {'活跃' if card.get('is_active') else '归档'}\n"
                )
                if card.get("raw_text"):
                    md_lines.append(f"\n### 详细内容\n\n{card['raw_text']}\n")
                md_lines.append("\n---\n\n")

            return {
                "format": "markdown",
                "count": len(cards),
                "content": "\n".join(md_lines),
                "filename": f"experience_cards_{user_id}.md",
            }

        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的导出格式: {format}，支持: json, csv, markdown",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {e}")


@router.post("/cards/batch")
def jobcraft_experience_batch(payload: Dict[str, Any]):
    try:
        action = payload.get("action")
        card_ids = payload.get("card_ids", [])
        params = payload.get("params", {})

        if not action:
            raise HTTPException(status_code=400, detail="action 不能为空")
        if not card_ids:
            raise HTTPException(status_code=400, detail="card_ids 不能为空")

        results = {"success": [], "failed": []}

        if action == "archive":
            for card_id in card_ids:
                try:
                    ok = db_tools.update_card(card_id, {"is_active": False})
                    if ok:
                        results["success"].append(card_id)
                    else:
                        results["failed"].append(
                            {"card_id": card_id, "reason": "卡片不存在"}
                        )
                except Exception as e:
                    results["failed"].append({"card_id": card_id, "reason": str(e)})

        elif action == "restore":
            for card_id in card_ids:
                try:
                    ok = db_tools.update_card(card_id, {"is_active": True})
                    if ok:
                        results["success"].append(card_id)
                    else:
                        results["failed"].append(
                            {"card_id": card_id, "reason": "卡片不存在"}
                        )
                except Exception as e:
                    results["failed"].append({"card_id": card_id, "reason": str(e)})

        elif action == "delete":
            for card_id in card_ids:
                try:
                    ok = db_tools.delete_card(card_id)
                    if ok:
                        results["success"].append(card_id)
                    else:
                        results["failed"].append(
                            {"card_id": card_id, "reason": "卡片不存在"}
                        )
                except Exception as e:
                    results["failed"].append({"card_id": card_id, "reason": str(e)})

        elif action == "tag":
            tags_to_add = params.get("tags", [])
            if not tags_to_add:
                raise HTTPException(status_code=400, detail="tags 不能为空")

            for card_id in card_ids:
                try:
                    card = db_tools.get_card(card_id)
                    if not card:
                        results["failed"].append(
                            {"card_id": card_id, "reason": "卡片不存在"}
                        )
                        continue

                    existing_tags = card.get("tags", [])
                    new_tags = list(set(existing_tags + tags_to_add))
                    ok = db_tools.update_card(card_id, {"tags": new_tags})

                    if ok:
                        results["success"].append(card_id)
                    else:
                        results["failed"].append(
                            {"card_id": card_id, "reason": "更新失败"}
                        )
                except Exception as e:
                    results["failed"].append({"card_id": card_id, "reason": str(e)})

        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的操作类型: {action}，支持: archive, restore, delete, tag",
            )

        return {
            "action": action,
            "total": len(card_ids),
            "success_count": len(results["success"]),
            "failed_count": len(results["failed"]),
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量操作失败: {e}")


@router.get("/cards/{card_id}/versions")
def jobcraft_experience_versions(card_id: int):
    try:
        card = db_tools.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")

        versions = db_tools.get_card_versions_by_card_id(card_id)

        return {
            "card_id": card_id,
            "versions": versions,
            "total": len(versions),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取版本历史失败: {e}")


@router.post("/cards/{card_id}/versions")
def jobcraft_experience_create_version(card_id: int, payload: Dict[str, Any]):
    try:
        card = db_tools.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")

        version_data = {
            "card_id": card_id,
            "version_type": payload.get("version_type", "manual"),
            "source_type": payload.get("source_type", "manual"),
            "source_id": payload.get("source_id", 0),
            "title": payload.get("title", card.get("title", "")),
            "raw_text": payload.get("raw_text", card.get("raw_text", "")),
            "tags": payload.get("tags", card.get("tags", [])),
            "note": payload.get("note", ""),
        }

        version_id = db_tools.insert_card_version(version_data)

        return {
            "version_id": version_id,
            "message": "版本创建成功",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建版本失败: {e}")


@router.post("/cards")
def jobcraft_experience_create(payload: ExperienceCardCreate):
    try:
        data = payload.model_dump()
        data["source"] = "manual"
        card_id = db_tools.insert_card(data)
        return db_tools.get_card(card_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"新建失败: {e}")


@router.patch("/cards/{card_id}")
def jobcraft_experience_update(card_id: int, payload: ExperienceCardUpdate):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "user_id" in updates:
        updates.pop("user_id")
    try:
        ok = db_tools.update_card(card_id, updates)
        if not ok:
            raise HTTPException(status_code=404, detail="卡片不存在或无变化")
        return db_tools.get_card(card_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")


@router.delete("/cards/{card_id}")
def jobcraft_experience_delete(card_id: int):
    try:
        ok = db_tools.delete_card(card_id)
        if not ok:
            raise HTTPException(status_code=404, detail="卡片不存在")
        return {"deleted": True, "card_id": card_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")


@router.post("/cards/{card_id}/structure")
def jobcraft_experience_structure(card_id: int, payload: StructCachePayload):
    try:
        card = db_tools.get_card(card_id)
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
        db_tools.update_card(card_id, {"ai_structured": cache})
        return db_tools.get_card(card_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("结构化抽取失败")
        raise HTTPException(status_code=500, detail=f"结构化抽取失败: {e}")


@router.post("/cards/{card_id}/recommend-tags")
def jobcraft_experience_recommend_tags(card_id: int):
    try:
        card = db_tools.get_card(card_id)
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
def jobcraft_experience_backfill(payload: BackfillPayload):
    try:
        from app.workflows.extract_flow import run_backfill_workflow

        result = run_backfill_workflow(payload.user_id, payload.min_chars)
        return result
    except Exception as e:
        logger.exception("卡片回填失败")
        raise HTTPException(status_code=500, detail=f"回填失败: {e}")
