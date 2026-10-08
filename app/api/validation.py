"""Validation 验证投影 API — T-M9-1

- GET /api/jobcraft/validation-summary?target_type=&target_id=
  Validation Level 投影（JOBCRAFT_API_SPEC §17.4，PRD:292 路由表 M9）。

投影是派生视图：底层 validations 记录 append-only 永久保留，本端点只做
读时计算（不写 expression.validation_level）；不做目标存在性检查，
未知 target 返回 L0（API_SPEC 未定义 404 语义）。

路由为独立字面量前缀 /api/jobcraft/validation-summary（query 参数传值），
与 /job、/submission 等 {param} 路由无吞路径冲突。
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.tools import db_tools

router = APIRouter(prefix="/api/jobcraft", tags=["validation"])

logger = logging.getLogger("jobcraft.api.validation")


@router.get("/validation-summary")
def jobcraft_validation_summary(
    target_type: str = Query(...),
    target_id: str = Query(...),
    current_user: int = Depends(get_current_user),
) -> Dict[str, Any]:
    """T-M9-1：某对象的 Validation Level 投影（本期只落 L0/L1 信号，Q1-A）。

    Args:
        target_type: 被验证对象类型（白名单 §24.1 + experience），strip 后非法值 400。
        target_id: 被验证对象 ID，strip 后为空 400。
        current_user: JWT 解析出的用户 ID。

    Returns:
        Dict[str, Any]: ``{target_type, target_id, level, usage_count,
        strong_signals, moderate_signals, weak_signals, explanation}``
        （API_SPEC §17.4，snake_case wire 符合 ADR-A4）。

    Raises:
        HTTPException: 400 参数非法 / 422 缺参 / 500 内部错误。
    """
    try:
        trimmed_target_type = target_type.strip()
        trimmed_target_id = target_id.strip()
        if not trimmed_target_id:
            raise HTTPException(status_code=400, detail="target_id 不能为空")
        return db_tools.get_validation_summary(
            current_user, trimmed_target_type, trimmed_target_id
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("获取 Validation 投影失败")
        raise HTTPException(status_code=500, detail=f"获取 Validation 投影失败: {e}")
