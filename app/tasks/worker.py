"""
JobCraft 任务管理器

基于 Redis + RQ 的异步任务执行框架。

BE-QUEUE-01 队列加固：
- tasks hash 无 field TTL → 终态任务按保留期惰性清理（prune_tasks）；
- queue blpop at-most-once → handler 失败至少重试 1 次，耗尽进死信队列（DLQ）；
- 重复提交同一参数跑满 LLM → 并发幂等占位（同参数未完成任务复用）。
"""

import hashlib
import json
import logging
import os
import time
import uuid
from enum import Enum
from typing import Any, Callable, Dict, Optional

from redis import Redis

logger = logging.getLogger("jobcraft.tasks.worker")

#: 终态任务保留期（秒）：tasks hash 无 field TTL，超期条目惰性删除
TASK_RETENTION_SECONDS = 7 * 86400
#: 幂等占位 TTL（秒）：worker 异常死亡导致任务永不终态时的兜底过期
_DEDUPE_TTL_SECONDS = 7200
#: 单条消息最大执行次数（首次 + 1 次重试）
_MAX_ATTEMPTS = 2
#: 死信队列保留上限
_DLQ_LIMIT = 1000


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
        dedupe_key: Optional[str] = None,
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
        #: 幂等键（BE-QUEUE-01）：任务进入终态时据此删除占位
        self.dedupe_key = dedupe_key

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
            "dedupe_key": self.dedupe_key,
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
        #: 死信队列（BE-QUEUE-01）
        self._dlq_key = "jobcraft:queue:dlq"
        #: 幂等占位键前缀（BE-QUEUE-01）
        self._dedupe_prefix = "jobcraft:dedupe:"

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

    @staticmethod
    def _auto_dedupe_key(task_type: str, params: Dict[str, Any]) -> str:
        """默认幂等键：task_type + 规范化 params 哈希（并发重复提交防抖）。"""
        canonical = json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)
        return f"{task_type}:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"

    def submit_task(
        self,
        task_type: str,
        params: Optional[Dict[str, Any]] = None,
        callback: Optional[Callable] = None,
        dedupe_key: Optional[str] = None,
    ) -> str:
        """
        提交异步任务（默认并发幂等：同参数未完成任务复用，不重复入队）

        BE-QUEUE-01：重复提交同一 JD 会跑满多次 LLM。占位键 NX 原子抢占；
        命中既有 pending/running 任务则返回其 task_id；既有任务已终态则
        覆盖占位重新提交（终态后合法的“重新生成”不被去重）。占位带 TTL，
        worker 异常死亡导致任务永不终态时兜底过期。

        :param task_type: 任务类型
        :param params: 任务参数
        :param callback: 回调函数（可选）
        :param dedupe_key: 显式幂等键；缺省自动生成（task_type + params 哈希）
        :return: 任务 ID（复用时为既有任务的 ID）
        """
        params = params or {}
        key = dedupe_key or self._auto_dedupe_key(task_type, params)
        cache_key = self._dedupe_prefix + key
        task_id = str(uuid.uuid4())

        if not self.redis.set(cache_key, task_id, nx=True, ex=_DEDUPE_TTL_SECONDS):
            existing_id = self.redis.get(cache_key)
            existing = self.get_task(existing_id) if existing_id else None
            if existing and existing.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                logger.info(
                    "重复提交命中未完成任务 %s（%s），复用不重新入队",
                    existing_id,
                    task_type,
                )
                return existing_id
            # 占位存在但任务已终态/缺失 → 覆盖占位，继续新提交
            self.redis.set(cache_key, task_id, ex=_DEDUPE_TTL_SECONDS)

        # 创建任务信息
        task_info = TaskInfo(
            task_id=task_id,
            task_type=task_type,
            params=params,
            dedupe_key=key,
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
            json.dumps(
                {
                    "task_id": task_id,
                    "task_type": task_type,
                    "params": params,
                },
                ensure_ascii=False,
            ),
        )

        self._maybe_prune()
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
            dedupe_key=task_dict.get("dedupe_key"),
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
        elif status == TaskStatus.PENDING:
            # 重试回队（BE-QUEUE-01）：清除上一轮的终态时间，避免残留
            task.completed_at = None
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            task.completed_at = now
            # 终态释放幂等占位：完成后的合法重复提交不再被去重
            if task.dedupe_key:
                try:
                    self.redis.delete(self._dedupe_prefix + task.dedupe_key)
                except Exception as e:  # noqa: BLE001 - 占位有 TTL 兜底
                    logger.debug("释放幂等占位失败（task_id=%s）: %s", task_id, e)

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
                dedupe_key=task_dict.get("dedupe_key"),
            )

            if status and task.status != status:
                continue

            tasks.append(task)

        # 按创建时间倒序
        tasks.sort(key=lambda t: t.created_at or 0, reverse=True)

        return tasks[:limit]

    # ------------------------------------------------------------------
    # BE-QUEUE-01：过期清理 / 重试与死信
    # ------------------------------------------------------------------

    def prune_tasks(self, retention: int = TASK_RETENTION_SECONDS) -> int:
        """删除超过保留期的终态任务（hash 无 field TTL，惰性清理）。

        :param retention: 终态任务保留秒数
        :return: 删除条数
        """
        cutoff = time.time() - retention
        removed = 0
        for task_id, data in self.redis.hgetall(self._tasks_key).items():
            try:
                task_dict = json.loads(data)
            except json.JSONDecodeError:
                # 脏数据一并清理（不可恢复）
                self.redis.hdel(self._tasks_key, task_id)
                removed += 1
                continue
            if task_dict.get("status") not in {
                TaskStatus.COMPLETED.value,
                TaskStatus.FAILED.value,
                TaskStatus.CANCELLED.value,
            }:
                continue
            ended_at = task_dict.get("completed_at") or task_dict.get("created_at") or 0
            if ended_at < cutoff:
                self.redis.hdel(self._tasks_key, task_id)
                removed += 1
        return removed

    def _maybe_prune(self) -> None:
        """节流触发清理：Redis NX 锁保证每小时至多扫描一次（跨进程）。"""
        try:
            acquired = self.redis.set(
                "jobcraft:tasks:prune_lock", "1", nx=True, ex=3600
            )
        except Exception as e:  # noqa: BLE001 - 清理是尽力而为
            logger.debug("清理锁获取失败: %s", e)
            return
        if not acquired:
            return
        try:
            removed = self.prune_tasks()
            if removed:
                logger.info("清理过期任务 %s 条", removed)
        except Exception as e:  # noqa: BLE001 - 清理失败不影响提交
            logger.debug("清理过期任务失败: %s", e)

    def requeue(self, payload: Dict[str, Any], attempts: int) -> Dict[str, Any]:
        """失败消息重新入队（累计 attempts，至少 1 次重试）。

        :param payload: 原始队列消息
        :param attempts: 已累计执行次数
        :return: 写回队列的消息（含 attempts）
        """
        retried = {**payload, "attempts": attempts}
        self.redis.lpush(self._queue_key, json.dumps(retried, ensure_ascii=False))
        return retried

    def restore_dedupe(self, task_id: str) -> None:
        """重试回队时重建幂等占位。

        handler 失败会先把任务标 failed（终态路径已释放占位），随后
        ``_process_payload`` 把状态改回 pending 等待重试；此处按任务存储
        的 dedupe_key 重新占位，堵住重试窗口期的并发重复提交。
        """
        task = self.get_task(task_id)
        if not task or not task.dedupe_key:
            return
        try:
            self.redis.set(
                self._dedupe_prefix + task.dedupe_key,
                task_id,
                ex=_DEDUPE_TTL_SECONDS,
            )
        except Exception as e:  # noqa: BLE001 - 占位有 TTL 兜底
            logger.debug("重建幂等占位失败（task_id=%s）: %s", task_id, e)

    def dead_letter(self, payload: Dict[str, Any], error: str, attempts: int) -> None:
        """重试耗尽写入死信队列（DLQ 有界，仅保留最近 _DLQ_LIMIT 条）。

        :param payload: 原始队列消息
        :param error: 最后一次失败原因
        :param attempts: 总执行次数
        """
        entry = json.dumps(
            {
                "payload": payload,
                "error": error,
                "attempts": attempts,
                "failed_at": time.time(),
            },
            ensure_ascii=False,
        )
        self.redis.lpush(self._dlq_key, entry)
        self.redis.ltrim(self._dlq_key, 0, _DLQ_LIMIT - 1)

    def list_dead_letters(self, limit: int = 50) -> list:
        """读取死信队列（最新在前）。

        :param limit: 返回条数
        :return: 解析后的死信条目列表
        """
        raw_items = self.redis.lrange(self._dlq_key, 0, limit - 1)
        entries = []
        for raw in raw_items or []:
            try:
                entries.append(json.loads(raw))
            except json.JSONDecodeError:
                logger.warning("死信条目非合法 JSON，跳过: %s", str(raw)[:200])
        return entries


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


def _dispatch_one(task_manager: TaskManager, payload: Dict[str, Any]) -> None:
    """
    消费单条队列消息：找到对应的 handler 并执行。

    :param task_manager: 任务管理器实例
    :param payload: 队列消息 `{task_id, task_type, params}`
    :raises ValueError: params 的 user_id 缺失或非正整数（T-M10-4：不回落固定用户）
    """
    from .handlers import get_task_handler

    task_id = payload.get("task_id")
    task_type = payload.get("task_type")
    params = payload.get("params", {})

    if not task_type:
        logger.error("队列消息缺少 task_type，跳过: %s", payload)
        return

    handler = get_task_handler(task_type)
    if not handler:
        logger.error("无法识别的任务类型 %s，标记失败", task_type)
        if task_id:
            task_manager.update_task_status(
                task_id, TaskStatus.FAILED, error=f"unsupported task_type: {task_type}"
            )
        return

    # 参数中补入 task_id / task_type，供 handler 更新状态
    run_params = dict(params)
    run_params.setdefault("task_id", task_id)
    # T-M10-4：user_id 必须由 submit 端点从 JWT 注入，分发层不再回落固定用户。
    # 缺失/非正整数为确定性输入错误，抛出交由 _process_payload 走既有失败/死信路径
    raw_user_id = run_params.get("user_id")
    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError):
        user_id = 0
    if user_id <= 0:
        raise ValueError(f"user_id 缺失：submit 未注入（收到 {raw_user_id!r}）")
    run_params["user_id"] = user_id
    logger.info("消费任务: %s (%s)", task_id, task_type)
    handler(run_params)


def _process_payload(manager: TaskManager, payload: Dict[str, Any]) -> None:
    """处理单条队列消息（BE-QUEUE-01 重试与死信决策）。

    - 成功/确定性失败（unsupported task_type 在 _dispatch_one 内部消化）：无动作；
    - handler 抛错且未达 ``_MAX_ATTEMPTS``：任务回 pending 并重新入队（至少 1 次重试）；
    - 重试耗尽：任务标 failed 并写入死信队列 ``jobcraft:queue:dlq``。

    :param manager: 任务管理器实例
    :param payload: 队列消息 ``{task_id, task_type, params, attempts?}``
    """
    task_id = payload.get("task_id")
    attempts = int(payload.get("attempts", 0) or 0)
    try:
        _dispatch_one(manager, payload)
    except Exception as e:  # noqa: BLE001 - 由本函数决策重试/死信
        attempts += 1
        if attempts < _MAX_ATTEMPTS:
            logger.warning(
                "任务 %s 执行失败（第 %s/%s 次），重新入队: %s",
                task_id,
                attempts,
                _MAX_ATTEMPTS,
                e,
            )
            if task_id:
                manager.update_task_status(
                    task_id,
                    TaskStatus.PENDING,
                    error=f"attempt {attempts}/{_MAX_ATTEMPTS} failed: {e}",
                )
                # handler 的 FAILED 标记曾释放幂等占位，回队后重建
                manager.restore_dedupe(task_id)
            manager.requeue(payload, attempts)
        else:
            logger.error(
                "任务 %s 重试耗尽（共 %s 次），写入死信队列: %s",
                task_id,
                attempts,
                e,
            )
            if task_id:
                manager.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
            manager.dead_letter(payload, error=str(e), attempts=attempts)


def run_worker(sleep_interval: float = 2.0, max_idle: int = -1) -> None:
    """
    Redis 异步任务消费循环（阻塞式 worker daemon）。

    从 `jobcraft:queue` 弹出消息并分发到对应 handler 执行。

    :param sleep_interval: 队列为空时的等待间隔（秒）
    :param max_idle: 连续空转多少次后退出（-1 表示永不退出）
    """
    # 启动时一次性执行运行时 DDL 引导（TASK-P1-10），handler 前置的 _ensure_* 随之短路
    from app.tools.db_bootstrap import run_schema_bootstrap

    run_schema_bootstrap()
    manager = get_task_manager()
    idle_rounds = 0
    logger.info("任务 worker 启动，监听队列 %s", manager._queue_key)
    while max_idle < 0 or idle_rounds < max_idle:
        try:
            item = manager.redis.blpop(manager._queue_key, timeout=sleep_interval)
        except RuntimeError as e:
            logger.error("Redis 不可用，停止消费: %s", e)
            return
        except Exception as e:  # noqa: BLE001 - worker daemon 需持续运行
            logger.exception("消费队列异常: %s", e)
            idle_rounds += 1
            continue

        if item is None:
            idle_rounds += 1
            continue

        idle_rounds = 0
        _, raw = item
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("队列消息不是合法 JSON，丢弃: %s", raw[:200])
            continue

        try:
            _process_payload(manager, payload)
        except Exception as e:  # noqa: BLE001 - 单任务失败不应终止 worker
            logger.exception("任务执行失败: %s", e)
    logger.info("任务 worker 退出")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_worker()
