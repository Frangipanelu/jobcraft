"""通用 AI 调用缓存（TASK-AI-003）。

在 `llm_json.invoke_structured` 结构化 LLM chokepoint 处提供热缓存：
- cache key = `ai:{feature}:{model}:{input_hash}`（input_hash 已涵盖 prompt + schema 内容，prompt/schema 版本变更会使哈希变化从而天然失效）
- 后端使用 Redis 热缓存（TTL 可配），复用 `REDIS_URL` 环境变量（tasks 模块同款）
- **尽力而为 / 非阻塞**：Redis 不可用或读写异常时静默降级（未命中 / 不写入），绝不影响业务 LLM 调用

设计约束：
- 不新增依赖（redis 库已在 tasks 模块使用）
- 不持有跨进程可变状态，懒初始化
- 缓存内容为结构化输出的 dict（序列化回 schema 由调用方负责）
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("jobcraft.tools.ai_cache")

_DEFAULT_TTL = int(os.getenv("JC_AI_CACHE_TTL", "86400"))

# 连接超时（秒）：Redis 不可用时快速失败，避免阻塞业务/测试
_CONNECT_TIMEOUT = float(os.getenv("JC_AI_CACHE_CONNECT_TIMEOUT", "0.5"))
_SOCKET_TIMEOUT = float(os.getenv("JC_AI_CACHE_SOCKET_TIMEOUT", "1.0"))

_DISABLED = object()
_redis: Any = None


def _get_redis() -> Optional[Any]:
    """懒初始化 Redis 客户端；不可用返回 None（不抛出，不重复重试）。"""
    global _redis
    if _redis is not None:
        return None if _redis is _DISABLED else _redis
    try:
        from redis import Redis

        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=_CONNECT_TIMEOUT,
            socket_timeout=_SOCKET_TIMEOUT,
        )
        client.ping()
        _redis = client
        return _redis
    except Exception:
        logger.debug("Redis 不可用，AI 缓存降级为未命中")
        _redis = _DISABLED
        return None


def build_cache_key(feature: str, model: str, input_hash: str) -> str:
    """构造缓存 key：ai:{feature}:{model}:{input_hash}。"""
    return f"ai:{feature}:{model}:{input_hash}"


def cache_get(key: str) -> Optional[Dict[str, Any]]:
    """读取缓存；未命中或 Redis 不可用返回 None（不抛出）。"""
    client = _get_redis()
    if client is None:
        return None
    try:
        raw = client.get(key)
        if raw is None:
            return None
        import json

        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except Exception:
        logger.debug("AI 缓存读取失败，忽略", exc_info=True)
        return None


def cache_set(
    key: str, value: Dict[str, Any], ttl_seconds: Optional[int] = None
) -> None:
    """写入缓存；失败静默忽略（不抛出）。"""
    client = _get_redis()
    if client is None:
        return
    try:
        import json

        raw = json.dumps(value, ensure_ascii=False, default=str)
        client.set(key, raw, ex=ttl_seconds if ttl_seconds is not None else _DEFAULT_TTL)
    except Exception:
        logger.debug("AI 缓存写入失败，忽略", exc_info=True)


def invalidate(feature: str, model: str, input_hash: str) -> None:
    """按 key 删除缓存（一般用于手动失效）。"""
    client = _get_redis()
    if client is None:
        return
    try:
        client.delete(build_cache_key(feature, model, input_hash))
    except Exception:
        logger.debug("AI 缓存删除失败，忽略", exc_info=True)
