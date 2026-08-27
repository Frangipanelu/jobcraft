"""
JobCraft 监控模块

提供 Prometheus 指标收集和暴露。
"""

from .metrics import (
    llm_calls_total,
    llm_call_duration_seconds,
    db_query_duration_seconds,
    api_requests_total,
    setup_monitoring,
)

__all__ = [
    "llm_calls_total",
    "llm_call_duration_seconds",
    "db_query_duration_seconds",
    "api_requests_total",
    "setup_monitoring",
]
