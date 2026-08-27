"""
JobCraft 认证依赖

提供 FastAPI 依赖注入，用于接口认证。
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import get_user_id_from_token

# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> int:
    """
    获取当前认证用户

    从请求头中提取 JWT Token，验证并返回用户 ID。

    :raises HTTPException: 401 未授权
    :return: 用户 ID
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    user_id = get_user_id_from_token(token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证或令牌已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> int:
    """
    获取可选的当前用户

    如果提供了有效的 Token，返回用户 ID；否则返回默认用户 ID 1。

    :return: 用户 ID
    """
    if credentials is None:
        return 1  # 默认用户

    token = credentials.credentials
    user_id = get_user_id_from_token(token)

    if user_id is None:
        return 1  # Token 无效时返回默认用户

    return user_id
