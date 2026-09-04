"""测试 TASK-OBS-001：Prometheus 观测指标已真正接线。

- LLM 指标：`_record_llm_observability` 在成功/失败路径调用 calls_total / duration / tokens_total。
- API 指标：FastAPI 中间件对 /health 请求记录 api_requests_total（集成测试，TestClient）。
- DB 指标：按用户决策（LLM+API 先行），DB query 指标预留给后续 DB 访问集中重构，本任务不接线。
"""

from app.tools import llm_json


class _FakeBound:
    def __init__(self, store, labels):
        self._store = store
        self._labels = labels

    def inc(self, *a):
        self._store.append(("inc", self._labels, a))

    def observe(self, *a):
        self._store.append(("observe", self._labels, a))


class _FakeMetric:
    def __init__(self, store):
        self._store = store

    def labels(self, **labels):
        return _FakeBound(self._store, labels)


def test_record_llm_observability_success(monkeypatch):
    calls, durations, tokens = [], [], []
    monkeypatch.setattr("app.monitoring.metrics.llm_calls_total", _FakeMetric(calls))
    monkeypatch.setattr(
        "app.monitoring.metrics.llm_call_duration_seconds",
        _FakeMetric(durations),
    )
    monkeypatch.setattr("app.monitoring.metrics.llm_tokens_total", _FakeMetric(tokens))

    llm_json._record_llm_observability(
        "jd_ats_analysis",
        "success",
        1.5,
        {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    )

    assert ("inc", {"agent_name": "jd_ats_analysis", "status": "success"}, ()) in calls
    assert (
        "observe",
        {"agent_name": "jd_ats_analysis"},
        (1.5,),
    ) in durations
    for label, value in (
        ("prompt", 10),
        ("completion", 5),
        ("total", 15),
    ):
        assert (
            "inc",
            {"agent_name": "jd_ats_analysis", "token_type": label},
            (value,),
        ) in tokens


def test_record_llm_observability_error_no_tokens(monkeypatch):
    calls, durations, tokens = [], [], []
    monkeypatch.setattr("app.monitoring.metrics.llm_calls_total", _FakeMetric(calls))
    monkeypatch.setattr(
        "app.monitoring.metrics.llm_call_duration_seconds",
        _FakeMetric(durations),
    )
    monkeypatch.setattr("app.monitoring.metrics.llm_tokens_total", _FakeMetric(tokens))

    llm_json._record_llm_observability("tech_analyzer", "error", 0.3, None)

    assert ("inc", {"agent_name": "tech_analyzer", "status": "error"}, ()) in calls
    assert tokens == []


def test_record_llm_observability_never_raises(monkeypatch):
    """观测记录本身抛错时，不应影响业务。"""

    class _BoomMetric:
        def labels(self, **k):
            raise RuntimeError("prometheus down")

    monkeypatch.setattr(
        "app.monitoring.metrics.llm_calls_total", _BoomMetric(), raising=False
    )
    llm_json._record_llm_observability("x", "success", 1.0, None)


def test_api_metrics_middleware_records_request():
    """集成：对 /health 的请求应增加 api_requests_total。"""
    import prometheus_client
    from fastapi.testclient import TestClient

    from app.api.server import app

    label = {
        "method": "GET",
        "endpoint": "/health",
        "status_code": "200",
    }
    before = (
        prometheus_client.REGISTRY.get_sample_value(
            "jobcraft_api_requests_total", label
        )
        or 0
    )

    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200

    after = (
        prometheus_client.REGISTRY.get_sample_value(
            "jobcraft_api_requests_total", label
        )
        or 0
    )
    assert after >= before + 1
