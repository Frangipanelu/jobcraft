# -*- coding: utf-8 -*-
"""LLM 进程级限流与 429 退避（app/tools/llm_rate_limit.py）单测。

覆盖：限流错误识别、退避重试/耗尽/非限流不重试、最小启动间隔、
并发槽互斥、环境变量重建单例，以及 invoke_structured 限流跳过兜底。
"""

import threading
import time

import pytest
from pydantic import BaseModel

from app.tools import llm_json, llm_rate_limit
from app.tools.llm_rate_limit import RateLimiter, call_with_limits, is_rate_limit_error


class _Schema(BaseModel):
    title: str
    score: int


class _FakeModel:
    """invoke_structured 需要的最小 model 占位。"""


class _FakeResponse:
    content = '{"title": "t", "score": 1}'
    tool_calls = None


def _no_wait(monkeypatch):
    """关闭限流间隔/退避等待，让单测瞬时完成。"""
    monkeypatch.setenv("LLM_RATE_LIMIT_RPS", "0")
    monkeypatch.setenv("LLM_CONCURRENCY_LIMIT", "0")
    monkeypatch.setenv("LLM_RATE_LIMIT_RETRIES", "0")
    sleeps = []
    monkeypatch.setattr(llm_rate_limit, "_sleep", sleeps.append)
    return sleeps


class TestIsRateLimitError:
    def test_detects_zhipu_1302(self):
        exc = RuntimeError(
            "Error code: 429 - {'error': {'code': '1302', "
            "'message': '您的账户已达到速率限制，请您控制请求频率'}}"
        )
        assert is_rate_limit_error(exc) is True

    def test_detects_platform_overload_1305(self):
        exc = RuntimeError(
            "Error code: 429 - {'error': {'code': '1305', "
            "'message': '该模型当前访问量过大，请您稍后再试'}}"
        )
        assert is_rate_limit_error(exc) is True

    def test_detects_rate_limit_text(self):
        assert is_rate_limit_error(Exception("Rate limit exceeded")) is True
        assert is_rate_limit_error(Exception("Too Many Requests")) is True

    def test_ignores_generic_errors(self):
        assert is_rate_limit_error(ValueError("llm down")) is False
        assert is_rate_limit_error(RuntimeError("无法从模型输出中提取 JSON")) is False
        assert is_rate_limit_error(ValueError("模型未返回 tool_call 或 JSON")) is False


class TestCallWithLimits:
    def test_retries_on_rate_limit_then_succeeds(self, monkeypatch):
        """限流错误退避重试，成功后返回，不放大为二次不同请求。"""
        sleeps = _no_wait(monkeypatch)
        monkeypatch.setenv("LLM_RATE_LIMIT_RETRIES", "3")
        monkeypatch.setenv("LLM_RATE_LIMIT_BACKOFF_BASE", "0")
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("Error code: 429 速率限制 1302")
            return "ok"

        assert call_with_limits(flaky) == "ok"
        assert calls["n"] == 3
        assert len(sleeps) == 2

    def test_raises_after_retries_exhausted(self, monkeypatch):
        sleeps = _no_wait(monkeypatch)
        monkeypatch.setenv("LLM_RATE_LIMIT_RETRIES", "2")
        monkeypatch.setenv("LLM_RATE_LIMIT_BACKOFF_BASE", "0")
        calls = {"n": 0}

        def always_limited():
            calls["n"] += 1
            raise RuntimeError("Error code: 429 速率限制")

        with pytest.raises(RuntimeError, match="429"):
            call_with_limits(always_limited)
        assert calls["n"] == 3  # 1 次原始 + 2 次重试
        assert len(sleeps) == 2

    def test_non_rate_limit_error_raises_immediately(self, monkeypatch):
        sleeps = _no_wait(monkeypatch)
        calls = {"n": 0}

        def broken():
            calls["n"] += 1
            raise ValueError("llm down")

        with pytest.raises(ValueError, match="llm down"):
            call_with_limits(broken)
        assert calls["n"] == 1
        assert sleeps == []

    def test_zero_retries_disables_retry(self, monkeypatch):
        sleeps = _no_wait(monkeypatch)
        monkeypatch.setenv("LLM_RATE_LIMIT_RETRIES", "0")
        calls = {"n": 0}

        def always_limited():
            calls["n"] += 1
            raise RuntimeError("Error code: 429 速率限制")

        with pytest.raises(RuntimeError):
            call_with_limits(always_limited)
        assert calls["n"] == 1
        assert sleeps == []

    def test_backoff_is_exponential_with_jitter(self, monkeypatch):
        monkeypatch.setenv("LLM_RATE_LIMIT_RPS", "0")
        monkeypatch.setenv("LLM_CONCURRENCY_LIMIT", "0")
        monkeypatch.setenv("LLM_RATE_LIMIT_RETRIES", "3")
        monkeypatch.setenv("LLM_RATE_LIMIT_BACKOFF_BASE", "1")
        monkeypatch.setattr(llm_rate_limit.random, "uniform", lambda a, b: 0.0)
        sleeps = []
        monkeypatch.setattr(llm_rate_limit, "_sleep", sleeps.append)
        calls = {"n": 0}

        def always_limited():
            calls["n"] += 1
            raise RuntimeError("Error code: 429 速率限制")

        with pytest.raises(RuntimeError):
            call_with_limits(always_limited)
        assert sleeps == [1.0, 2.0, 4.0]


class TestRateLimiter:
    def test_min_interval_enforced(self):
        limiter = RateLimiter(rps=50, max_concurrency=0)  # 20ms 间隔
        stamps = []
        for _ in range(3):
            with limiter.slot():
                stamps.append(time.monotonic())
        gaps = [b - a for a, b in zip(stamps, stamps[1:])]
        assert all(g >= 0.015 for g in gaps), gaps

    def test_concurrency_serialized(self):
        limiter = RateLimiter(rps=0, max_concurrency=1)
        state = {"active": 0, "peak": 0}
        lock = threading.Lock()

        def work():
            with limiter.slot():
                with lock:
                    state["active"] += 1
                    state["peak"] = max(state["peak"], state["active"])
                time.sleep(0.05)
                with lock:
                    state["active"] -= 1

        threads = [threading.Thread(target=work) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert state["peak"] == 1

    def test_disabled_limits_have_no_wait(self):
        limiter = RateLimiter(rps=0, max_concurrency=0)
        start = time.monotonic()
        for _ in range(50):
            with limiter.slot():
                pass
        assert time.monotonic() - start < 0.05

    def test_get_rate_limiter_rebuilds_on_env_change(self, monkeypatch):
        from app.tools.llm_rate_limit import get_rate_limiter

        monkeypatch.setenv("LLM_RATE_LIMIT_RPS", "2")
        monkeypatch.setenv("LLM_CONCURRENCY_LIMIT", "3")
        first = get_rate_limiter()
        assert first.rps == 2.0
        assert first.max_concurrency == 3
        assert get_rate_limiter() is first  # 配置未变复用单例

        monkeypatch.setenv("LLM_RATE_LIMIT_RPS", "5")
        second = get_rate_limiter()
        assert second is not first
        assert second.rps == 5.0


class TestInvokeStructuredIntegration:
    """invoke_structured 与限流分支的接线。"""

    @staticmethod
    def _patch_env(monkeypatch):
        monkeypatch.setenv("LLM_RATE_LIMIT_RPS", "0")
        monkeypatch.setenv("LLM_CONCURRENCY_LIMIT", "0")
        monkeypatch.setenv("LLM_RATE_LIMIT_RETRIES", "0")

    @staticmethod
    def _patch_audit(monkeypatch):
        from app.tools import ai_cache, db_ai

        monkeypatch.setattr(db_ai, "create_ai_task", lambda **k: 7)
        monkeypatch.setattr(db_ai, "complete_ai_task", lambda **k: None)
        monkeypatch.setattr(ai_cache, "cache_get", lambda key: None)
        monkeypatch.setattr(ai_cache, "cache_set", lambda key, value: None)

    def test_rate_limit_skips_fallback(self, monkeypatch):
        """限流且退避耗尽：直接上抛，不再打兜底第二枪。"""
        from app.tools import db_ai

        self._patch_env(monkeypatch)
        self._patch_audit(monkeypatch)
        errors = {}

        def _limited(*a, **k):
            raise RuntimeError(
                "Error code: 429 - {'code': '1302', 'message': '速率限制'}"
            )

        monkeypatch.setattr(llm_json, "_invoke_with_bind_tools", _limited)

        def _fallback_must_not_run(*a, **k):
            raise AssertionError("限流时不应发起兜底请求")

        monkeypatch.setattr(llm_json, "_invoke_with_plain_json", _fallback_must_not_run)
        monkeypatch.setattr(db_ai, "complete_ai_task", lambda **k: errors.update(k))

        with pytest.raises(RuntimeError, match="限流"):
            llm_json.invoke_structured(_FakeModel(), _Schema, "hello")

        assert "限流跳过兜底" in errors.get("error", "")

    def test_non_rate_limit_error_still_falls_back(self, monkeypatch):
        """非限流错误保持原语义：进入手动 JSON 兜底。"""
        self._patch_env(monkeypatch)
        self._patch_audit(monkeypatch)
        expected = _Schema(title="t", score=9)
        monkeypatch.setattr(
            llm_json,
            "_invoke_with_bind_tools",
            lambda *a, **k: (_ for _ in ()).throw(ValueError("bad tool call")),
        )
        monkeypatch.setattr(
            llm_json,
            "_invoke_with_plain_json",
            lambda *a, **k: (expected, _FakeResponse()),
        )

        result = llm_json.invoke_structured(_FakeModel(), _Schema, "hello")
        assert result == expected
