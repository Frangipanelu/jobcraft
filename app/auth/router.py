"""
JobCraft 认证路由

提供用户注册、登录接口。
"""

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from . import create_access_token, get_password_hash, verify_password
from .dependencies import get_current_user
from app.tools import db_tools

router = APIRouter(prefix="/api/auth", tags=["认证"])

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    """注册请求"""

    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    email: Optional[str] = Field(None, max_length=200, description="邮箱")


class LoginRequest(BaseModel):
    """登录请求"""

    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """Token 响应"""

    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str


class UserInfo(BaseModel):
    """用户信息"""

    user_id: int
    username: str
    email: Optional[str] = None


def _validate_register_input(
    username: str, password: str, email: Optional[str]
) -> None:
    """校验注册输入：密码强度与邮箱格式"""
    if (
        len(password) < 8
        or not re.search(r"[A-Za-z]", password)
        or not re.search(r"\d", password)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码长度至少 8 位，且必须同时包含字母和数字",
        )
    if email and not _EMAIL_PATTERN.match(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱格式不正确"
        )


@router.post("/register", response_model=TokenResponse)
async def register(payload: RegisterRequest):
    """
    用户注册

    创建新用户并返回 JWT Token。
    """
    # 检查用户名是否已存在
    existing_user = db_tools.get_user_by_username(payload.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在"
        )

    _validate_register_input(payload.username, payload.password, payload.email)

    if payload.email:
        existing_email = db_tools.get_user_by_email(payload.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被使用"
            )

    # 创建用户
    password_hash = get_password_hash(payload.password)
    user_id = db_tools.create_user(
        username=payload.username, password_hash=password_hash, email=payload.email
    )

    # 生成 Token
    access_token = create_access_token(
        data={"user_id": user_id, "username": payload.username}
    )

    return TokenResponse(
        access_token=access_token, user_id=user_id, username=payload.username
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    """
    用户登录

    验证用户名密码，返回 JWT Token。
    """
    # 获取用户
    user = db_tools.get_user_by_username(payload.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )

    # 验证密码
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )

    # 生成 Token
    access_token = create_access_token(
        data={"user_id": user["id"], "username": user["username"]}
    )

    return TokenResponse(
        access_token=access_token, user_id=user["id"], username=user["username"]
    )


@router.get("/me", response_model=UserInfo)
async def get_me(user_id: int = Depends(get_current_user)):
    """
    获取当前用户信息

    需要认证。
    """
    user = db_tools.get_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    return UserInfo(
        user_id=user["id"], username=user["username"], email=user.get("email")
    )
