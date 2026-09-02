"""
JobCraft 认证模块

提供 JWT Token 签发、验证和用户认证功能。
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from dotenv import load_dotenv
from jose import JWTError, jwt

# 强制使用环境变量中的密钥，缺失则启动失败，避免在源码中兜底硬编码密钥
load_dotenv(override=True)

_JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not _JWT_SECRET_KEY:
    raise RuntimeError("缺失 JWT_SECRET_KEY 环境变量，请通过 .env 或环境变量注入")

SECRET_KEY = _JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))  # 默认7天


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建 JWT 访问令牌

    :param data: 令牌载荷
    :param expires_delta: 过期时间增量
    :return: JWT 字符串
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    验证 JWT 令牌

    :param token: JWT 字符串
    :return: 令牌载荷或 None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> Optional[int]:
    """
    从令牌中提取用户 ID

    :param token: JWT 字符串
    :return: 用户 ID 或 None
    """
    payload = verify_token(token)
    if payload is None:
        return None
    user_id = payload.get("user_id")
    if user_id is None:
        return None
    return int(user_id)
