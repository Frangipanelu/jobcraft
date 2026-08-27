"""
JobCraft 任务管理器

基于 Redis + RQ 的异步任务执行框架。
"""

import json
import os
import time
import uuid
from enum import Enum
from typing import Any, Callable, Dict, Optional

from redis import Redis


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskInfo:
    """任务信息"""

    def __init__(
        self,
        task_id: str,
        task_type: str,
        status: TaskStatus = TaskStatus.PENDING,
        params: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        created_at: Optional[float] = None,
        started_at: Optional[float] = None,
        completed_at: Optional[float] = None,
    ):
        self.task_id = task_id
        self.task_type = task_type
        self.status = status
        self.params = params or {}
        self.result = result
        self.error = error
        self.created_at = created_at or time.time()
        self.started_at = started_at
        self.completed_at = completed_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "params": self.params,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class TaskManager:
    """
    任务管理器

    使用 Redis 存储任务状态，支持任务提交、查询、取消。
    """

    def __init__(self, redis_url: Optional[str] = None):
        """
        初始化任务管理器

        :param redis_url: Redis 连接 URL，默认从环境变量读取
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis: Optional[Redis] = None
        self._tasks_key = "jobcraft:tasks"
        self._queue_key = "jobcraft:queue"

    @property
    def redis(self) -> Redis:
        """获取 Redis 连接（懒初始化）"""
        if self._redis is None:
            try:
                self._redis = Redis.from_url(self.redis_url, decode_responses=True)
                self._redis.ping()
            except Exception as e:
                raise RuntimeError(f"无法连接到 Redis: {e}")
        return self._redis

    def submit_task(
        self,
        task_type: str,
        params: Optional[Dict[str, Any]] = None,
        callback: Optional[Callable] = None,
    ) -> str:
        """
        提交异步任务

        :param task_type: 任务类型
        :param params: 任务参数
        :param callback: 回调函数（可选）
        :return: 任务 ID
        """
        task_id = str(uuid.uuid4())

        # 创建任务信息
        task_info = TaskInfo(
            task_id=task_id,
            task_type=task_type,
            params=params or {},
        )

        # 存储任务信息
        self.redis.hset(
            self._tasks_key,
            task_id,
            json.dumps(task_info.to_dict(), ensure_ascii=False),
        )

        # 加入任务队列
        self.redis.lpush(
            self._queue_key,
            json.dumps({
                "task_id": task_id,
                "task_type": task_type,
                "params": params or {},
            }, ensure_ascii=False),
        )

        return task_id

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """
        获取任务信息

        :param task_id: 任务 ID
        :return: 任务信息
        """
        data = self.redis.hget(self._tasks_key, task_id)
        if not data:
            return None

        task_dict = json.loads(data)
        return TaskInfo(
            task_id=task_dict["task_id"],
            task_type=task_dict["task_type"],
            status=TaskStatus(task_dict["status"]),
            params=task_dict.get("params", {}),
            result=task_dict.get("result"),
            error=task_dict.get("error"),
            created_at=task_dict.get("created_at"),
            started_at=task_dict.get("started_at"),
            completed_at=task_dict.get("completed_at"),
        )

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        更新任务状态

        :param task_id: 任务 ID
        :param status: 新状态
        :param result: 任务结果
        :param error: 错误信息
        """
        task = self.get_task(task_id)
        if not task:
            return

        now = time.time()
        task.status = status
        task.result = result
        task.error = error

        if status == TaskStatus.RUNNING:
            task.started_at = now
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            task.completed_at = now

        self.redis.hset(
            self._tasks_key,
            task_id,
            json.dumps(task.to_dict(), ensure_ascii=False),
        )

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        :param task_id: 任务 ID
        :return: 是否成功取消
        """
        task = self.get_task(task_id)
        if not task:
            return False

        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            return False

        self.update_task_status(task_id, TaskStatus.CANCELLED)
        return True

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 50,
    ) -> list:
        """
        列出任务

        :param status: 过滤状态
        :param limit: 返回数量限制
        :return: 任务列表
        """
        all_tasks = self.redis.hgetall(self._tasks_key)
        tasks = []

        for task_id, data in all_tasks.items():
            task_dict = json.loads(data)
            task = TaskInfo(
                task_id=task_dict["task_id"],
                task_type=task_dict["task_type"],
                status=TaskStatus(task_dict["status"]),
                params=task_dict.get("params", {}),
                result=task_dict.get("result"),
                error=task_dict.get("error"),
                created_at=task_dict.get("created_at"),
                started_at=task_dict.get("started_at"),
                completed_at=task_dict.get("completed_at"),
            )

            if status and task.status != status:
                continue

            tasks.append(task)

        # 按创建时间倒序
        tasks.sort(key=lambda t: t.created_at or 0, reverse=True)

        return tasks[:limit]


# 全局任务管理器实例
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """
    获取全局任务管理器

    :return: 任务管理器实例
    """
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
