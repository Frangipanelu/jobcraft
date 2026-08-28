"""
JobCraft 监控指标

定义和管理各种 Prometheus 指标。
"""

from prometheus_client import Counter, Histogram, Gauge, Info
from prometheus_fastapi_instrumentator import Instrumentator

# ============================================================
#  LLM 相关指标
# ============================================================

# LLM 调用次数
llm_calls_total = Counter(
    "jobcraft_llm_calls_total",
    "Total number of LLM calls",
    ["agent_name", "status"],
)

# LLM 调用耗时
llm_call_duration_seconds = Histogram(
    "jobcraft_llm_call_duration_seconds",
    "LLM call duration in seconds",
    ["agent_name"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120],
)

# LLM Token 使用量
llm_tokens_total = Counter(
    "jobcraft_llm_tokens_total",
    "Total tokens used by LLM",
    ["agent_name", "token_type"],
)

# ============================================================
#  数据库相关指标
# ============================================================

# 数据库查询耗时
db_query_duration_seconds = Histogram(
    "jobcraft_db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation", "table"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 5],
)

# 数据库连接数
db_connections_active = Gauge(
    "jobcraft_db_connections_active",
    "Number of active database connections",
)

# ============================================================
#  API 相关指标
# ============================================================

# API 请求总数
api_requests_total = Counter(
    "jobcraft_api_requests_total",
    "Total number of API requests",
    ["method", "endpoint", "status_code"],
)

# API 请求耗时
api_request_duration_seconds = Histogram(
    "jobcraft_api_request_duration_seconds",
    "API request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.1, 0.25, 0.5, 1, 2.5, 5, 10],
)

# ============================================================
#  业务相关指标
# ============================================================

# 经历卡数量
experience_cards_total = Gauge(
    "jobcraft_experience_cards_total",
    "Total number of experience cards",
    ["user_id"],
)

# 投递记录数量
submissions_total = Gauge(
    "jobcraft_submissions_total",
    "Total number of submissions",
    ["user_id", "status"],
)

# 面试准备生成次数
interview_prep_total = Counter(
    "jobcraft_interview_prep_total",
    "Total number of interview prep generated",
    ["round_type"],
)

# 面试复盘次数
interview_review_total = Counter(
    "jobcraft_interview_review_total",
    "Total number of interview reviews",
    ["round_type"],
)

# ============================================================
#  系统信息
# ============================================================

app_info = Info(
    "jobcraft_app",
    "JobCraft application information",
)


def setup_monitoring(app) -> None:
    """
    设置应用监控

    :param app: FastAPI 应用实例
    """
    # 设置应用信息
    app_info.info(
        {
            "version": "0.6.0",
            "environment": "production",
        }
    )

    # 集成 FastAPI Instrumentator
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health"],
    )

    # 添加自定义信息
    instrumentator.add(lambda info: info)

    # 暴露 /metrics 端点
    instrumentator.instrument(app).expose(app, endpoint="/metrics")
