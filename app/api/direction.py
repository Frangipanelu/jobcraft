"""方向（Direction）路由（T-M3-1/T-M3-3：P3 方向体系 CRUD + 表单接线）。

约定（Q7=c 两级分离 + U-P2a′ 编码裁决）：
- 集合前缀 ``/api/jobcraft/direction``（单数集合，同 submission 先例）；
- code（DIR-n）服务端生成，创建响应回带；
- ``POST /find-or-create``（T-M3-3 表单方向字段数据侧接线）：按 name 复用
  已有方向，无则创建；命中不覆盖六维，响应 ``{direction, created}``；
- 删除守卫：被 expression 等下游引用 → 409 提示改用归档
  （PATCH status=archived，DIRECTION_SPEC §15 状态机）；
- 统一错误信封由 server.py exception handler 包装，此处只抛 HTTPException。
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.schemas.jobcraft import (
    DirectionCreate,
    DirectionFindOrCreateResponse,
    DirectionRead,
    DirectionSummaryResponse,
    DirectionUpdate,
)
from app.tools import db_capability_gap, db_direction

router = APIRouter(prefix="/api/jobcraft/direction", tags=["direction"])

logger = logging.getLogger("jobcraft.api.direction")


@router.get("", response_model=List[DirectionRead])
def list_directions(
    status: Optional[str] = Query(None, description="active / archived 过滤"),
    current_user: int = Depends(get_current_user),
):
    """列出当前用户的方向（创建序 DIR-1 在前）。"""
    try:
        return db_direction.list_directions(current_user, status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("方向列表查询失败")
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")


@router.post("", response_model=DirectionRead)
def create_direction(
    payload: DirectionCreate,
    current_user: int = Depends(get_current_user),
):
    """创建方向（自动生成 DIR-n 编码；同名方向 400）。"""
    try:
        data = payload.model_dump()
        data["user_id"] = current_user
        return db_direction.create_direction(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("方向创建失败")
        raise HTTPException(status_code=500, detail=f"创建失败: {e}")


@router.post("/find-or-create", response_model=DirectionFindOrCreateResponse)
def find_or_create_direction(
    payload: DirectionCreate,
    current_user: int = Depends(get_current_user),
):
    """按 name 查找或创建方向（T-M3-3：结构化表单方向字段数据侧接线）。

    命中已有（含归档）原样返回不覆盖六维；未命中创建（DIR-n）；
    并发同名竞态回读已存在行。响应 ``{direction, created}``。
    """
    try:
        data = payload.model_dump()
        direction, created = db_direction.find_or_create_direction(current_user, data)
        return {"direction": direction, "created": created}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("方向 find-or-create 失败")
        raise HTTPException(status_code=500, detail=f"find-or-create 失败: {e}")


@router.get("/summary", response_model=DirectionSummaryResponse)
def direction_summary(current_user: int = Depends(get_current_user)):
    """方向沉淀汇总（T-M3-6：/workbench 面板——方向列表+计数+高频缺口）。

    注册必须早于 ``GET /{direction_id}``：FastAPI 按注册顺序匹配，
    晚注册会被路径参数吞掉（"summary" → int 解析 422）。
    """
    try:
        return DirectionSummaryResponse(
            directions=db_direction.list_direction_summary(current_user),
            top_gaps=db_capability_gap.count_gaps_by_dimension(current_user),
        )
    except Exception as e:
        logger.exception("方向汇总查询失败")
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")


@router.get("/{direction_id}", response_model=DirectionRead)
def get_direction(
    direction_id: int,
    current_user: int = Depends(get_current_user),
):
    """查询单个方向（不存在或越权 → 404）。"""
    direction = db_direction.get_direction(direction_id, current_user)
    if not direction:
        raise HTTPException(status_code=404, detail="方向不存在")
    return direction


@router.patch("/{direction_id}", response_model=DirectionRead)
def update_direction(
    direction_id: int,
    payload: DirectionUpdate,
    current_user: int = Depends(get_current_user),
):
    """按白名单字段部分更新方向（code 不可改）。"""
    try:
        fields = payload.model_dump(exclude_unset=True)
        direction = db_direction.update_direction(direction_id, current_user, fields)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not direction:
        raise HTTPException(status_code=404, detail="方向不存在")
    return direction


@router.delete("/{direction_id}")
def delete_direction(
    direction_id: int,
    current_user: int = Depends(get_current_user),
):
    """删除方向；被下游引用 → 409（改用归档），不存在/越权 → 404。"""
    if not db_direction.get_direction(direction_id, current_user):
        raise HTTPException(status_code=404, detail="方向不存在")
    refs = db_direction.count_direction_references(direction_id, current_user)
    if any(refs.values()):
        raise HTTPException(
            status_code=409,
            detail="方向已被表达等下游数据引用，无法删除；请改为归档（status=archived）",
        )
    if not db_direction.delete_direction(direction_id, current_user):
        raise HTTPException(status_code=404, detail="方向不存在")
    return {"deleted": True, "direction_id": direction_id}
