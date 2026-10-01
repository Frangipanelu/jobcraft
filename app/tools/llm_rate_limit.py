"""LLM 调用进程级限流与 429 退避。

对应智谱开放平台错误码 1302（账户速率限制，HTTP 429）：免费档约 1 req/s、
低并发上限，且限流按账户维度生效。本模块在进程内提供两层保护：

1. **调用前限流**：并发槽（`LLM_CONCURRENCY_LIMIT`）+ 最小启动间隔
   （`LLM_RATE_LIMIT_RPS`，间隔 = 1 / rps），避免瞬时洪峰触发账户级限流。
2. **限流后退避**：捕获限流错误后按指数退避 + 抖动重试同一请求
   （`LLM_RATE_LIMIT_RETRIES` / `LLM_RATE_LIMIT_BACKOFF_BASE`），
   而不是立刻再发第二个请求（旧逻辑会打「兜底」二次加重限流）。

环境变量（均可缺省）：

- `LLM_RATE_LIMIT_RPS`：每秒最大启动请求数，默认 1.0；<= 0 关闭间隔限制
- `LLM_CONCURRENCY_LIMIT`：进程内并发上限，默认 1；<= 0 关闭并发限制
- `LLM_RATE_LIMIT_RETRIES`：限流退避重试次数，默认 3；0 关闭重试
- `LLM_RATE_LIMIT_BACKOFF_BASE`：退避基数（秒），默认 1.0；
  第 n 次重试等待 `base * 2^n + random(0, base)`

注意：限流是**进程级**的，backend 与 worker 各自独立计算，合计仍受账户
全局速率约束；e2e 等突发场景建议错峰或临时调低 rps。
"""

import logging
import os
import random
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional, Tuple, TypeVar

logger = logging.getLogger("jobcraft.tools.llm_rate_limit")

T = TypeVar("T")

# 限流错误特征：智谱 HTTP 429 / 业务码 1302（速率限制）、1305（模型过载）
_RATE_LIMIT_MARKERS: Tuple[str, ...] = (
    "429",
    "1302",
    "1305",
    "速率限制",
    "请求过于密集",
    "rate limit",
    "rate_limit",
    "too many requests",
)


def _sleep(seconds: float) -> None:
    """休眠（独立包装便于测试替换）。"""
    time.sleep(seconds)


def _env_float(name: str, default: float) -> float:
    """读取 float 环境变量，非法值回落默认。

    :param name: 环境变量名
    :param default: 缺省/非法时的默认值
    :return: 解析后的浮点值
    """
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        logger.warning("环境变量 %s 非法，使用默认值 %s", name, default)
        return default


def _env_int(name: str, default: int) -> int:
    """读取 int 环境变量，非法值回落默认。

    :param name: 环境变量名
    :param default: 缺省/非法时的默认值
    :return: 解析后的整数值
    """
    try:
        return int(float(os.getenv(name, str(default))))
    except ValueError:
        logger.warning("环境变量 %s 非法，使用默认值 %s", name, default)
        return default


def is_rate_limit_error(exc: BaseException) -> bool:
    """判断异常是否为上游限流错误。

    依据错误文本特征匹配（OpenAI/智谱 SDK 异常消息包含 HTTP 状态码与
    业务错误码），不做异常类型强绑定以兼容不同 SDK 版本。

    :param exc: 待判断异常
    :return: 命中限流特征返回 True
    """
    text = str(exc).lower()
    return any(marker in text for marker in _RATE_LIMIT_MARKERS)


class RateLimiter:
    """进程内并发槽 + 最小启动间隔的同步限流器。"""

    def __init__(self, rps: float, max_concurrency: int) -> None:
        """初始化限流器。

        :param rps: 每秒最大启动请求数；<= 0 表示不限制启动间隔
        :param max_concurrency: 并发上限；<= 0 表示不限制并发
        """
        self.rps = float(rps)
        self.max_concurrency = int(max_concurrency)
        self._min_interval = (1.0 / self.rps) if self.rps > 0 else 0.0
        self._semaphore = (
            threading.Semaphore(self.max_concurrency)
            if self.max_concurrency > 0
            else None
        )
        self._clock_lock = threading.Lock()
        self._next_start = 0.0

    @contextmanager
    def slot(self) -> Iterator["RateLimiter"]:
        """获取一个调用槽：先占并发槽，再按最小间隔对齐启动时刻。

        释放时机为退出 with 块时；退避等待发生在持有槽期间，
        避免其他线程在限流窗口内并发穿插。

        :return: 上下文管理器，进入时已完成限流等待，yield 自身
        """
        if self._semaphore is not None:
            self._semaphore.acquire()
        try:
            self._reserve_start()
            yield self
        finally:
            if self._semaphore is not None:
                self._semaphore.release()

    def wait_interval(self) -> None:
        """按最小启动间隔对齐下一次启动时刻（退避重试路径复用）。"""
        self._reserve_start()

    def _reserve_start(self) -> None:
        """预约本次调用启动时刻，超出间隔则同步休眠对齐。"""
        if self._min_interval <= 0:
            return
        with self._clock_lock:
            now = time.monotonic()
            start_at = max(now, self._next_start)
            self._next_start = start_at + self._min_interval
        delay = start_at - time.monotonic()
        if delay > 0:
            _sleep(delay)


_limiter: Optional[RateLimiter] = None
_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """返回按当前环境变量配置的进程级限流器单例。

    环境变量变更后下一次调用会重建实例（便于测试与运行期调整）。

    :return: 进程级限流器
    """
    global _limiter
    rps = _env_float("LLM_RATE_LIMIT_RPS", 1.0)
    concurrency = _env_int("LLM_CONCURRENCY_LIMIT", 1)
    with _limiter_lock:
        if (
            _limiter is None
            or _limiter.rps != rps
            or _limiter.max_concurrency != concurrency
        ):
            _limiter = RateLimiter(rps=rps, max_concurrency=concurrency)
        return _limiter


def call_with_limits(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """在限流保护下调用 `fn`，限流错误按指数退避重试。

    持有并发槽执行整个重试循环；仅当异常命中限流特征时重试，
    其余异常原样抛出。重试耗尽后抛出最后一次限流错误。

    :param fn: 被调用函数
    :param args: 位置参数
    :param kwargs: 关键字参数
    :return: `fn` 的返回值
    """
    retries = max(_env_int("LLM_RATE_LIMIT_RETRIES", 3), 0)
    base = max(_env_float("LLM_RATE_LIMIT_BACKOFF_BASE", 1.0), 0.0)

    with get_rate_limiter().slot() as slot:
        attempt = 0
        while True:
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                if not is_rate_limit_error(exc) or attempt >= retries:
                    raise
                delay = base * (2**attempt) + random.uniform(0.0, base)
                logger.warning(
                    "LLM 限流（429/1302），%.2fs 后重试 %d/%d: %s",
                    delay,
                    attempt + 1,
                    retries,
                    exc,
                )
                _sleep(delay)
                slot.wait_interval()
                attempt += 1
