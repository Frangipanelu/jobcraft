"""Job 实体（岗位聚合根）CRUD 路由 — T-M5-1 / M5-Q2

Q2 裁决（Job 先行模型）：
- 新建 JD / 添加岗位 → job 表 +1（本路由，find-or-create 幂等）；
- 用户点「标记已投递」→ 才建 submission（归档简历版本），
  submission_id 由 `insert_submission._attach_job_entity` find-or-create 自动回挂；
- job 增删查改不碰 submission。

路由注册顺序：必须注册在 job_analysis（prefix=/api/jobcraft/job）之后，
其字面量路径（/analyses、/analyze/{id} 等）先匹配，避免被 {job_id} 参数路由吞掉。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.schemas.submission_status import normalize_status
from app.tools import db_job_entity

router = APIRouter(tags=["job_entity"])

logger = logging.getLogger("jobcraft.api.job_entity")


class CreateJobPayload(BaseModel):
    company: str = ""
    position: str
    job_analysis_id: Optional[int] = None
    raw_jd_id: Optional[int] = None


class UpdateJobPayload(BaseModel):
    company: Optional[str] = None
    position: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("/api/jobcraft/job")
def jobcraft_job_create(
    payload: CreateJobPayload,
    current_user: int = Depends(get_current_user),
):
    """创建岗位（按 user+company+position find-or-create 幂等，不建 submission）。"""
    try:
        job_id = db_job_entity.find_or_create_job(
            user_id=current_user,
            position=payload.position,
            company=payload.company,
            job_analysis_id=payload.job_analysis_id,
            raw_jd_id=payload.raw_jd_id,
        )
    except Exception as e:
        logger.exception("创建岗位失败")
        raise HTTPException(status_code=500, detail=f"创建岗位失败: {e}")
    if job_id is None:
        raise HTTPException(status_code=400, detail="岗位名称不能为空")
    job = db_job_entity.get_job(job_id, current_user)
    if not job:
        raise HTTPException(status_code=500, detail="创建岗位失败")
    return job


@router.get("/api/jobcraft/job")
def jobcraft_job_list(current_user: int = Depends(get_current_user)):
    """列出当前用户全部在用岗位（T-M5-1 最小合并：job-only 行数据源）。"""
    return db_job_entity.list_jobs(current_user)


@router.get("/api/jobcraft/job/{job_id}")
def jobcraft_job_get(job_id: int, current_user: int = Depends(get_current_user)):
    """单岗位查询（归属校验，不存在或非本人 404）。"""
    job = db_job_entity.get_job(job_id, current_user)
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    return job


@router.patch("/api/jobcraft/job/{job_id}")
def jobcraft_job_update(
    job_id: int,
    payload: UpdateJobPayload,
    current_user: int = Depends(get_current_user),
):
    """更新岗位字段（company/position/status/is_active；删除= is_active=False）。"""
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "status" in updates:
        normalized = normalize_status(updates["status"])
        if normalized is None:
            raise HTTPException(
                status_code=400, detail=f"无效的岗位状态: {updates['status']}"
            )
        updates["status"] = normalized.value
    try:
        job = db_job_entity.update_job(job_id, user_id=current_user, **updates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("更新岗位失败（job_id=%s）", job_id)
        raise HTTPException(status_code=500, detail=f"更新岗位失败: {e}")
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    return job
