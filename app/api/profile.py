"""用户资料 API：读取与更新个人资料（user_profiles 表）。"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.tools import db_conn

router = APIRouter(prefix="/api/auth", tags=["profile"])


class UserProfileUpdate(BaseModel):
    """前端保存个人资料请求体（全部可选）"""

    display_name: Optional[str] = None
    role: Optional[str] = None
    target_salary: Optional[str] = None
    years_of_exp: Optional[int] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    summary: Optional[str] = None
    target_cities: Optional[List[str]] = None
    target_companies: Optional[List[str]] = None
    target_roles: Optional[List[str]] = None
    avatar_url: Optional[str] = None


def _ensure_table() -> None:
    """确保 user_profiles 表存在（幂等）"""
    db_conn.execute(
        """CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INT NOT NULL PRIMARY KEY,
            display_name VARCHAR(100) DEFAULT '',
            role VARCHAR(100) DEFAULT '求职者',
            target_salary VARCHAR(50) DEFAULT '',
            years_of_exp INT DEFAULT 0,
            city VARCHAR(100) DEFAULT '',
            phone VARCHAR(30) DEFAULT '',
            summary TEXT,
            target_cities JSON,
            target_companies JSON,
            target_roles JSON,
            avatar_url VARCHAR(500) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )"""
    )


def _row_to_dict(row: Any) -> Dict[str, Any]:
    """将 DB 行转为前端 UserProfile 格式"""
    if row is None:
        return {}
    return {
        "display_name": row.get("display_name") or "",
        "role": row.get("role") or "求职者",
        "target_salary": row.get("target_salary") or "",
        "years_of_exp": row.get("years_of_exp") or 0,
        "city": row.get("city") or "",
        "phone": row.get("phone") or "",
        "email": row.get("email") or "",
        "summary": row.get("summary") or "",
        "target_cities": row.get("target_cities") or [],
        "target_companies": row.get("target_companies") or [],
        "target_roles": row.get("target_roles") or [],
        "avatar_url": row.get("avatar_url") or "",
    }


@router.get("/profile")
def get_profile(current_user: int = Depends(get_current_user)) -> Dict[str, Any]:
    """获取当前用户资料"""
    _ensure_table()
    row = db_conn.query_one(
        "SELECT * FROM user_profiles WHERE user_id = %s", (current_user,)
    )
    if row is None:
        # 返回空默认值（用户尚未填写）
        return _row_to_dict({})
    return _row_to_dict(row)


@router.patch("/profile")
def update_profile(
    payload: UserProfileUpdate,
    current_user: int = Depends(get_current_user),
) -> Dict[str, Any]:
    """更新当前用户资料（部分更新）"""
    _ensure_table()
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    # 把 JSON 字段序列化
    json_fields = {"target_cities", "target_companies", "target_roles"}
    for k in json_fields:
        if k in updates:
            import json
            updates[k] = json.dumps(updates[k], ensure_ascii=False)

    # 更新 email 到 users 表（如果提供了）
    if "email" in updates:
        db_conn.execute(
            "UPDATE users SET email=%s WHERE id=%s",
            (updates.pop("email"), current_user),
        )

    # Upsert user_profiles
    existing = db_conn.query_one(
        "SELECT user_id FROM user_profiles WHERE user_id = %s", (current_user,)
    )
    if existing is None:
        cols = ["user_id"] + list(updates.keys())
        vals = [current_user] + list(updates.values())
        placeholders = ", ".join(["%s"] * len(cols))
        col_names = ", ".join(cols)
        db_conn.execute(
            f"INSERT INTO user_profiles ({col_names}) VALUES ({placeholders})",
            vals,
        )
    else:
        set_clause = ", ".join(f"{k}=%s" for k in updates)
        vals = list(updates.values()) + [current_user]
        db_conn.execute(
            f"UPDATE user_profiles SET {set_clause} WHERE user_id=%s", vals
        )

    # 返回更新后的完整资料
    row = db_conn.query_one(
        "SELECT * FROM user_profiles WHERE user_id = %s", (current_user,)
    )
    return _row_to_dict(row)
