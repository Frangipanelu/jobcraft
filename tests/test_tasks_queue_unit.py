"""
BE-QUEUE-01 Redis 任务队列加固单测

覆盖三缺陷：
1. tasks hash 过期清理（prune_tasks / _maybe_prune 节流）；
2. 队列至少 1 次重试 + 死信队列（_process_payload）；
3. 提交幂等占位（并发重复提交复用未完成任务）。

不依赖真实 Redis：用内存 FakeRedis 实现 TaskManager 用到的命令子集。
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tasks.worker import (  # noqa: E402
    TASK_RETENTION_SECONDS,
    TaskManager,
    TaskStatus,
    _process_payload,
)


class FakeRedis:
    """TaskManager 所需 Redis 命令子集的内存实现（decode_responses=True 语义）。"""

    def __init__(self):
        self.hashes: dict = {}
        self.lists: dict = {}
        self.strings: dict = {}

    def ping(self):
        return True

    # --- hash ---
    def hset(self, key, field, value):
        self.hashes.setdefault(key, {})[field] = value
        return 1

    def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    def hdel(self, key, *fields):
        bucket = self.hashes.get(key, {})
        removed = 0
        for f in fields:
            if f in bucket:
                del bucket[f]
                removed += 1
        return removed

    # --- list ---
    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    def lrange(self, key, start, end):
        items = self.lists.get(key, [])
        end_exclusive = None if end == -1 else end + 1
        return items[start:end_exclusive]

    def ltrim(self, key, start, end):
        items = self.lists.get(key, [])
        end_exclusive = None if end == -1 else end + 1
        self.lists[key] = items[start:end_exclusive]
        return True

    def llen(self, key):
        return len(self.lists.get(key, []))

    def lpop(self, key):
        items = self.lists.get(key, [])
        return items.pop(0) if items else None

    # --- string ---
    def get(self, key):
        return self.strings.get(key)

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.strings:
            return None
        self.strings[key] = value
        return True

    def delete(self, key):
        existed = key in self.strings
        self.strings.pop(key, None)
        return 1 if existed else 0


def _make_manager() -> TaskManager:
    manager = TaskManager(redis_url="redis://unused")
    manager._redis = FakeRedis()
    return manager


class TestTaskManagerDedupe:
    """提交幂等（BE-QUEUE-01 第 3 项）。"""

    def test_duplicate_submit_reuses_pending_task(self):
        manager = _make_manager()
        first = manager.submit_task("jd_analyze", {"jd_text": "JD-A"})
        second = manager.submit_task("jd_analyze", {"jd_text": "JD-A"})
        assert first == second
        # 只入队 1 条消息（第二个请求复用，不重复跑 LLM）
        assert manager.redis.llen(manager._queue_key) == 1

    def test_different_params_create_distinct_tasks(self):
        manager = _make_manager()
        first = manager.submit_task("jd_analyze", {"jd_text": "JD-A"})
        second = manager.submit_task("jd_analyze", {"jd_text": "JD-B"})
        assert first != second
        assert manager.redis.llen(manager._queue_key) == 2

    def test_resubmit_after_completion_is_not_deduplicated(self):
        """终态释放占位：完成后的合法「重新生成」不被去重。"""
        manager = _make_manager()
        first = manager.submit_task("interview_prep", {"job_analysis_id": 7})
        manager.update_task_status(first, TaskStatus.COMPLETED, result={"ok": True})
        second = manager.submit_task("interview_prep", {"job_analysis_id": 7})
        assert first != second
        assert manager.redis.llen(manager._queue_key) == 2

    def test_stale_terminal_placeholder_is_overridden(self):
        """占位残留但任务已终态/缺失 → 覆盖占位重新提交，不返回死任务 id。"""
        manager = _make_manager()
        manager.redis.set(manager._dedupe_prefix + "k", "ghost-task", ex=60)
        task_id = manager.submit_task("jd_analyze", {"jd_text": "JD-A"}, dedupe_key="k")
        assert task_id != "ghost-task"
        assert manager.get_task(task_id) is not None

    def test_task_info_roundtrips_dedupe_key(self):
        manager = _make_manager()
        task_id = manager.submit_task("jd_analyze", {"jd_text": "JD-A"})
        task = manager.get_task(task_id)
        assert task is not None
        assert task.dedupe_key and task.dedupe_key.startswith("jd_analyze:")


class TestPruneTasks:
    """tasks hash 过期清理（BE-QUEUE-01 第 1 项）。"""

    def test_prune_removes_expired_terminal_only(self):
        manager = _make_manager()
        now = time.time()
        old = now - TASK_RETENTION_SECONDS - 1
        entries = {
            "old-done": {
                "task_id": "old-done",
                "task_type": "t",
                "status": "completed",
                "created_at": old,
                "completed_at": old,
            },
            "fresh-done": {
                "task_id": "fresh-done",
                "task_type": "t",
                "status": "completed",
                "created_at": now,
                "completed_at": now,
            },
            "old-pending": {
                "task_id": "old-pending",
                "task_type": "t",
                "status": "pending",
                "created_at": old,
                "completed_at": None,
            },
        }
        for tid, data in entries.items():
            manager.redis.hset(manager._tasks_key, tid, json.dumps(data))

        removed = manager.prune_tasks()
        assert removed == 1
        remaining = set(manager.redis.hgetall(manager._tasks_key))
        assert remaining == {"fresh-done", "old-pending"}

    def test_prune_drops_corrupt_entries(self):
        manager = _make_manager()
        manager.redis.hset(manager._tasks_key, "bad", "{not-json")
        manager.redis.hset(
            manager._tasks_key,
            "good",
            json.dumps(
                {
                    "task_id": "good",
                    "task_type": "t",
                    "status": "pending",
                    "created_at": time.time(),
                    "completed_at": None,
                }
            ),
        )
        removed = manager.prune_tasks()
        assert removed == 1
        assert "bad" not in manager.redis.hgetall(manager._tasks_key)
        assert "good" in manager.redis.hashes[manager._tasks_key]

    def test_maybe_prune_throttled_by_hourly_lock(self):
        manager = _make_manager()
        manager.submit_task("jd_analyze", {"jd_text": "A"})  # 触发首次节流清理
        # 锁已占：塞过期任务后再次触发不应删除
        manager.redis.hset(
            manager._tasks_key,
            "stale",
            json.dumps(
                {
                    "task_id": "stale",
                    "task_type": "t",
                    "status": "failed",
                    "created_at": 1.0,
                    "completed_at": 1.0,
                }
            ),
        )
        manager._maybe_prune()
        assert "stale" in manager.redis.hgetall(manager._tasks_key)
        # 释放锁后可清理
        manager.redis.delete("jobcraft:tasks:prune_lock")
        manager._maybe_prune()
        assert "stale" not in manager.redis.hgetall(manager._tasks_key)


class TestRetryAndDeadLetter:
    """至少 1 次重试 + 死信队列（BE-QUEUE-01 第 2 项）。"""

    def _submit_and_peek(self, manager: TaskManager) -> tuple:
        task_id = manager.submit_task("jd_analyze", {"jd_text": "JD-A"})
        raw = manager.redis.lpop(manager._queue_key)
        return task_id, json.loads(raw)

    def test_first_failure_requeues_with_attempts_and_restores_dedupe(
        self, monkeypatch
    ):
        manager = _make_manager()
        task_id, payload = self._submit_and_peek(manager)

        def _boom(_manager, _payload):
            raise RuntimeError("handler 炸了")

        monkeypatch.setattr("app.tasks.worker._dispatch_one", _boom)
        _process_payload(manager, payload)

        # 重新入队且 attempts=1
        assert manager.redis.llen(manager._queue_key) == 1
        retried = json.loads(manager.redis.lrange(manager._queue_key, 0, 0)[0])
        assert retried["attempts"] == 1
        # 任务回 pending（handler 的 FAILED 被回退），错误保留
        task = manager.get_task(task_id)
        assert task.status is TaskStatus.PENDING
        assert "attempt 1/2" in (task.error or "")
        # 幂等占位重建（handler 终态标记曾释放它）
        assert manager.redis.get(manager._dedupe_prefix + task.dedupe_key) == task_id

    def test_second_failure_marks_failed_and_dead_letters(self, monkeypatch):
        manager = _make_manager()
        task_id, payload = self._submit_and_peek(manager)

        def _boom(_manager, _payload):
            raise RuntimeError("handler 又炸了")

        monkeypatch.setattr("app.tasks.worker._dispatch_one", _boom)
        _process_payload(manager, payload)  # 第 1 次失败 → requeue
        retried = json.loads(manager.redis.lpop(manager._queue_key))
        _process_payload(manager, retried)  # 第 2 次失败 → 耗尽

        # 队列清空、任务终态、进入死信
        assert manager.redis.llen(manager._queue_key) == 0
        task = manager.get_task(task_id)
        assert task.status is TaskStatus.FAILED
        assert "handler 又炸了" in (task.error or "")
        dead = manager.list_dead_letters()
        assert len(dead) == 1
        assert dead[0]["attempts"] == 2
        assert "handler 又炸了" in dead[0]["error"]
        assert dead[0]["payload"]["task_id"] == task_id

    def test_success_path_has_no_retry_side_effects(self, monkeypatch):
        manager = _make_manager()
        task_id, payload = self._submit_and_peek(manager)

        monkeypatch.setattr("app.tasks.worker._dispatch_one", lambda m, p: None)
        _process_payload(manager, payload)

        assert manager.redis.llen(manager._queue_key) == 0
        assert manager.list_dead_letters() == []
        # 成功路径不改状态（handler 负责标 completed）
        assert manager.get_task(task_id).status is TaskStatus.PENDING

    def test_unsupported_task_type_is_not_retried(self, monkeypatch):
        """确定性失败（_dispatch_one 内部消化）不进重试/死信。"""
        manager = _make_manager()
        payload = {"task_id": None, "task_type": "nope", "params": {}}
        _process_payload(manager, payload)
        assert manager.redis.llen(manager._queue_key) == 0
        assert manager.list_dead_letters() == []

    def test_dead_letter_list_bounded(self):
        manager = _make_manager()
        for i in range(5):
            manager.dead_letter({"task_id": f"t{i}"}, error=f"e{i}", attempts=2)
            # 模拟有界：直接改小上限不便，这里验证写入与解析
        dead = manager.list_dead_letters(limit=50)
        assert len(dead) == 5
        # 最新在前
        assert dead[0]["payload"]["task_id"] == "t4"


class TestDispatchUserIdGuard:
    """T-M10-4：分发层缺 user_id 不再 fallback 1，走既有失败/死信路径。"""

    def test_missing_user_id_marks_failed_and_dead_letters(self, monkeypatch):
        manager = _make_manager()
        invoked = []

        def _forbidden_handler(params):
            invoked.append(params)
            raise AssertionError("缺 user_id 不得进入 handler")

        monkeypatch.setattr(
            "app.tasks.handlers.get_task_handler", lambda _t: _forbidden_handler
        )

        task_id = manager.submit_task(
            "resume_generate", {"company": "A", "position": "P"}
        )
        payload = json.loads(manager.redis.lpop(manager._queue_key))

        _process_payload(manager, payload)  # 第 1 次失败 → 重试
        retried = json.loads(manager.redis.lpop(manager._queue_key))
        _process_payload(manager, retried)  # 第 2 次失败 → failed + 死信

        task = manager.get_task(task_id)
        assert task is not None
        assert task.status is TaskStatus.FAILED
        assert "user_id" in (task.error or "")
        assert "submit" in (task.error or "")
        # handler 从未被执行（绝不静默用 1 继续跑）
        assert invoked == []
        dead = manager.list_dead_letters()
        assert len(dead) == 1
        assert dead[0]["payload"]["task_id"] == task_id

    def test_invalid_user_id_marks_failed(self, monkeypatch):
        """user_id 非正整数（0/负数）同样视为缺失，不回落。"""
        manager = _make_manager()
        monkeypatch.setattr(
            "app.tasks.handlers.get_task_handler", lambda _t: lambda _p: None
        )

        task_id = manager.submit_task("resume_generate", {"user_id": 0})
        payload = json.loads(manager.redis.lpop(manager._queue_key))
        _process_payload(manager, payload)
        retried = json.loads(manager.redis.lpop(manager._queue_key))
        _process_payload(manager, retried)

        task = manager.get_task(task_id)
        assert task is not None
        assert task.status is TaskStatus.FAILED
        assert "user_id" in (task.error or "")

    def test_valid_user_id_passes_through_to_handler(self, monkeypatch):
        """正常路径：submit 注入的 user_id 原样送达 handler。"""
        manager = _make_manager()
        received = {}

        def _handler(params):
            received.update(params)

        monkeypatch.setattr("app.tasks.handlers.get_task_handler", lambda _t: _handler)

        task_id = manager.submit_task("resume_generate", {"user_id": 42})
        payload = json.loads(manager.redis.lpop(manager._queue_key))
        _process_payload(manager, payload)

        assert received["user_id"] == 42
        assert received["task_id"] == task_id
        assert manager.list_dead_letters() == []
