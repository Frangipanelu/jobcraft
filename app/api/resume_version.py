"""简历版本 API — T-M6-1 / M6-Q1-B

M6-Q1 裁决 B 核心字段版端点集合：
- GET    /api/jobcraft/resume-version            版本列表（可按 job_id 过滤，Q5 版本列表数据源）
- POST   /api/jobcraft/resume-version            保存新版本（version_no 每岗 MAX+1）
- PATCH  /api/jobcraft/resume-version/{id}       改 version_name/sections/resume_markdown/来源引用
- DELETE /api/jobcraft/resume-version/{id}       删版本
- POST   /api/jobcraft/resume-version/{id}/current  设当前（RESUME_SPEC §11 单选
  「用户确认实际投递的版本」，同岗清其他；M6-7 标记投递归档选中快照的依据）
- POST   /api/jobcraft/resume-version/{id}/rewrite  按能力缺口改写选中要点
  （T-M6-3，1 次 LLM；只算不写，落库走 PATCH resume_markdown）

路径为独立字面量前缀，与 /job、/submission 等无 {param} 吞路径冲突。
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.tools import db_job_entity, db_resume_version
from app.tools.resume_rewrite import rewrite_resume_bullet

router = APIRouter(tags=["resume_version"])

logger = logging.getLogger("jobcraft.api.resume_version")


class CreateResumeVersionPayload(BaseModel):
    job_id: int
    direction_id: Optional[int] = None
    version_name: Optional[str] = Field(default=None, max_length=200)
    sections: Optional[Any] = None
    resume_markdown: Optional[str] = None
    source_expression_refs: Optional[Any] = None


class UpdateResumeVersionPayload(BaseModel):
    version_name: Optional[str] = Field(default=None, max_length=200)
    sections: Optional[Any] = None
    resume_markdown: Optional[str] = None
    source_expression_refs: Optional[Any] = None


class RewriteBulletPayload(BaseModel):
    """按能力缺口改写选中要点的入参（T-M6-3）"""

    original_text: str = Field(..., min_length=1, max_length=4000)
    dimension: str = Field(default="", max_length=200)
    gap_current: str = Field(default="", max_length=2000)
    jd_evidence: str = Field(default="", max_length=4000)
    rewrite_hint: str = Field(default="", max_length=1000)


@router.get("/api/jobcraft/resume-version")
def resume_version_list(
    job_id: Optional[int] = Query(default=None),
    current_user: int = Depends(get_current_user),
):
    """列出当前用户的简历版本（可按岗位过滤，新版本在前）。"""
    return db_resume_version.list_resume_versions(current_user, job_id=job_id)


@router.post("/api/jobcraft/resume-version")
def resume_version_create(
    payload: CreateResumeVersionPayload,
    current_user: int = Depends(get_current_user),
):
    """保存新版本（归属岗位校验 404；version_no 每岗自增）。"""
    if not db_job_entity.get_job(payload.job_id, current_user):
        raise HTTPException(status_code=404, detail="岗位不存在")
    try:
        return db_resume_version.create_resume_version(
            user_id=current_user,
            job_id=payload.job_id,
            direction_id=payload.direction_id,
            version_name=payload.version_name,
            sections=payload.sections,
            resume_markdown=payload.resume_markdown,
            source_expression_refs=payload.source_expression_refs,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("保存简历版本失败（job_id=%s）", payload.job_id)
        raise HTTPException(status_code=500, detail=f"保存简历版本失败: {e}")


@router.patch("/api/jobcraft/resume-version/{version_id}")
def resume_version_update(
    version_id: int,
    payload: UpdateResumeVersionPayload,
    current_user: int = Depends(get_current_user),
):
    """更新版本字段（仅传入项；无有效字段 400，非本人 404）。"""
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="无有效更新字段")
    try:
        version = db_resume_version.update_resume_version(
            version_id, user_id=current_user, **updates
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("更新简历版本失败（version_id=%s）", version_id)
        raise HTTPException(status_code=500, detail=f"更新简历版本失败: {e}")
    if not version:
        raise HTTPException(status_code=404, detail="简历版本不存在")
    return version


@router.delete("/api/jobcraft/resume-version/{version_id}")
def resume_version_delete(
    version_id: int,
    current_user: int = Depends(get_current_user),
):
    """删除版本（硬删；非本人 404）。"""
    deleted = db_resume_version.delete_resume_version(version_id, current_user)
    if not deleted:
        raise HTTPException(status_code=404, detail="简历版本不存在")
    return {"deleted": True}


@router.post("/api/jobcraft/resume-version/{version_id}/current")
def resume_version_set_current(
    version_id: int,
    current_user: int = Depends(get_current_user),
):
    """设为当前版本（同岗单选，清其他选中；非本人 404）。"""
    version = db_resume_version.set_current_resume_version(version_id, current_user)
    if not version:
        raise HTTPException(status_code=404, detail="简历版本不存在")
    return version


@router.post("/api/jobcraft/resume-version/{version_id}/rewrite")
def resume_version_rewrite(
    version_id: int,
    payload: RewriteBulletPayload,
    current_user: int = Depends(get_current_user),
):
    """按能力缺口 AI 改写选中要点（T-M6-3；1 次 LLM，只算不写）。

    :return: {"rewritten_text": str}（前端替换选中要点后经 PATCH 落库）
    """
    if not db_resume_version.get_resume_version(version_id, current_user):
        raise HTTPException(status_code=404, detail="简历版本不存在")
    try:
        rewritten = rewrite_resume_bullet(
            payload.original_text,
            dimension=payload.dimension,
            gap_current=payload.gap_current,
            jd_evidence=payload.jd_evidence,
            rewrite_hint=payload.rewrite_hint,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("简历要点改写失败（version_id=%s）", version_id)
        raise HTTPException(status_code=502, detail=f"改写失败: {e}")
    return {"rewritten_text": rewritten}
