"""direction 表查询模块（V0009 建表；P3 六维分类 CRUD 落地前的最小只读子集）。

P2C-07 归属校验使用：POST /expressions 携带 direction_id 时确认方向存在且
归属当前用户，防止跨用户数据关联（与 P0-5 同类的所有权守卫）。
"""

import logging
from typing import Any, Dict, List, Optional

from app.tools.db_conn import query_one

logger = logging.getLogger("jobcraft.db.direction")


def get_direction(
    direction_id: int, user_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """按 id 查方向，可选按 user_id 过滤所有权。

    :param direction_id: 方向 id。
    :param user_id: 归属用户；提供时方向不归属该用户视同不存在（返回 None）。
    :return: 方向行 dict，或 None。
    """
    sql = "SELECT * FROM direction WHERE id=%s"
    params: List[Any] = [direction_id]
    if user_id is not None:
        sql += " AND user_id=%s"
        params.append(user_id)
    row = query_one(sql, tuple(params))
    return dict(row) if row else None
