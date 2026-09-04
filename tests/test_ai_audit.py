"""测试 AI 调用审计（TASK-AI-002）：
- db_ai 尽力而为、非阻塞（DB 不可用时不影响业务调用）
- invoke_structured 挂钩正确（success/error 路径均调用审计收尾）
- V0003 迁移声明 ai_tasks / ai_outputs 两张表
"""

import pytest
from pydantic import BaseModel

from app.tools import db_ai
from app.tools import llm_json


class _SampleOut(BaseModel):
    title: str = ""
    score: int = 0


class _FakeModel:
    """最小假模型：记录 bind_tools 是否被调用。"""

    model_name = "fake-model"

    def bind_tools(self, *a, **k):
        return self

    def bind(self, **k):
        return self

    def invoke(self, *a, **k):
        raise AssertionError("不应走到真实 invoke")


def test_sha256_hex_deterministic():
    assert db_ai.sha256_hex("abc") == db_ai.sha256_hex("abc")
    assert db_ai.sha256_hex("abc") != db_ai.sha256_hex("abd")
    assert len(db_ai.sha256_hex("abc")) == 64


def test_create_ai_task_non_blocking_when_db_down(monkeypatch):
    """DB 不可用时 create_ai_task 返回 None 且不抛出。"""

    def _boom(*a, **k):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(db_ai, "connect", _boom)
    assert (
        db_ai.create_ai_task(
            feature="f",
            model="m",
            schema_name="S",
            prompt_hash="ph",
            input_hash="ih",
        )
        is None
    )


def test_complete_ai_task_noop_when_task_id_none(monkeypatch):
    """task_id=None 时 complete_ai_task 直接返回，不触达数据库。"""
    calls = {"connect": 0}

    def _counter(*a, **k):
        calls["connect"] += 1
        raise RuntimeError("should not connect")

    monkeypatch.setattr(db_ai, "connect", _counter)
    db_ai.complete_ai_task(task_id=None, status="success", latency_ms=1)
    assert calls["connect"] == 0


def test_complete_ai_task_non_blocking_when_db_down(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(db_ai, "connect", _boom)
    db_ai.complete_ai_task(task_id=1, status="success", latency_ms=1)


def test_invoke_structured_audits_success(monkeypatch):
    """成功路径：create(开始) 后 complete(success) 并携带结构化输出。"""
    calls = {"create": {}, "complete": {}}

    def fake_create(**k):
        calls["create"] = k
        return 42

    def fake_complete(**k):
        calls["complete"] = k

    sample = _SampleOut(title="t", score=9)
    monkeypatch.setattr(llm_json, "_invoke_with_bind_tools", lambda *a, **k: sample)
    monkeypatch.setattr(db_ai, "create_ai_task", fake_create)
    monkeypatch.setattr(db_ai, "complete_ai_task", fake_complete)

    result = llm_json.invoke_structured(_FakeModel(), _SampleOut, "hello")

    assert result == sample
    assert calls["create"]["schema_name"] == "_SampleOut"
    assert calls["create"]["feature"] == "_SampleOut"
    assert calls["complete"]["status"] == "success"
    assert calls["complete"]["output_json"] == {"title": "t", "score": 9}


def test_invoke_structured_audits_error(monkeypatch):
    """失败且兜底也失败：complete(error)，并抛 RuntimeError。"""
    calls = {"complete": {}}

    def _boom(*a, **k):
        raise ValueError("llm down")

    def fake_complete(**k):
        calls["complete"] = k

    monkeypatch.setattr(llm_json, "_invoke_with_bind_tools", _boom)
    monkeypatch.setattr(llm_json, "_invoke_with_plain_json", _boom)
    monkeypatch.setattr(db_ai, "complete_ai_task", fake_complete)

    with pytest.raises(RuntimeError):
        llm_json.invoke_structured(_FakeModel(), _SampleOut, "hello")
    assert calls["complete"]["status"] == "error"
    assert "llm down" in calls["complete"]["error"]


def test_invoke_structured_audit_never_blocks(monkeypatch):
    """审计写入本身抛错时，业务调用仍应正常返回。"""

    def _inner(*a, **k):
        return _SampleOut(title="ok", score=1)

    def _boom(*a, **k):
        raise RuntimeError("audit db down")

    monkeypatch.setattr(llm_json, "_invoke_with_bind_tools", _inner)
    monkeypatch.setattr(db_ai, "create_ai_task", _boom)

    result = llm_json.invoke_structured(_FakeModel(), _SampleOut, "hello")
    assert result.title == "ok"

def test_v3_migration_declares_audit_tables():
    """V0003 迁移应声明 ai_tasks 与 ai_outputs 表。"""
    import os

    from migrations.runner import MIGRATIONS_DIR

    f = os.path.join(MIGRATIONS_DIR, "V0003__ai_audit.sql")
    assert os.path.exists(f)
    with open(f, encoding="utf-8") as fh:
        sql = fh.read()
    assert "CREATE TABLE IF NOT EXISTS ai_tasks" in sql
    assert "CREATE TABLE IF NOT EXISTS ai_outputs" in sql
    assert "REFERENCES ai_tasks (id)" in sql
