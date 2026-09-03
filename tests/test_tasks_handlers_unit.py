"""tasks 模块单元测试：handlers 分发与 interview_prep 修复。"""

import pytest

from app.tasks.worker import _dispatch_one


class FakeTaskManager:
    """不含真实 Redis 的 task manager 替身，仅记录 update 调用。"""

    def __init__(self):
        self.status_updates = []

    def update_task_status(self, task_id, status, result=None, error=None):
        self.status_updates.append(
            {"task_id": task_id, "status": status, "result": result, "error": error}
        )


def test_registry_exposes_expected_types():
    """任务注册表应暴露三个类型，且不引用不存在的 interview_flow。"""
    from app.tasks import handlers

    assert set(handlers.TASK_REGISTRY.keys()) == {
        "resume_generate",
        "interview_prep",
        "export_pdf",
    }


def test_interview_prep_missing_job_analysis_id_raises(monkeypatch):
    """执行面试准备前必须提供 job_analysis_id。"""
    from app.tasks.handlers import execute_interview_prep

    with pytest.raises(ValueError):
        execute_interview_prep({"round_type": "技术面", "card_ids": [1], "user_id": 1})


def test_interview_prep_calls_real_workflow_with_params(monkeypatch):
    """execute_interview_prep 应将参数对齐传给 interview_prep_flow.run_interview_prep_workflow。"""
    fake_mgr = FakeTaskManager()
    monkeypatch.setattr(
        "app.tasks.handlers.get_task_manager", lambda: fake_mgr
    )

    captured = {}

    def fake_workflow(**kwargs):
        captured.update(kwargs)
        return {"elevator_pitch": "hello"}

    monkeypatch.setattr(
        "app.workflows.interview_prep_flow.run_interview_prep_workflow", fake_workflow
    )

    from app.tasks.handlers import execute_interview_prep

    result = execute_interview_prep(
        {
            "task_id": "t-1",
            "user_id": 7,
            "job_analysis_id": 10,
            "round_type": "技术面",
            "card_ids": [1, 2],
            "submission_id": 3,
            "company_research": {"basic": {}},
            "resume_markdown": "md",
            "previous_review_summary": "rev",
        }
    )

    assert result == {"elevator_pitch": "hello"}
    assert captured["job_analysis_id"] == 10
    assert captured["user_id"] == 7
    assert captured["round_type"] == "技术面"
    assert captured["card_ids"] == [1, 2]
    assert captured["submission_id"] == 3
    assert captured["company_research"] == {"basic": {}}
    assert captured["resume_markdown"] == "md"
    assert captured["previous_review_summary"] == "rev"

    assert any(u["task_id"] == "t-1" for u in fake_mgr.status_updates)


def test_dispatch_marks_unsupported_type_failed(monkeypatch):
    """队列中出现未知 task_type 时，应将任务标记为 failed。"""
    fake_mgr = FakeTaskManager()
    _dispatch_one(fake_mgr, {"task_id": "t-x", "task_type": "nope", "params": {}})

    assert len(fake_mgr.status_updates) == 1
    assert fake_mgr.status_updates[0]["task_id"] == "t-x"
    assert fake_mgr.status_updates[0]["status"].value == "failed"
    assert "unsupported" in fake_mgr.status_updates[0]["error"]


def test_dispatch_routes_to_known_handler(monkeypatch):
    """已知 task_type 应路由到对应 handler 并补入 task_id。"""
    fake_mgr = FakeTaskManager()
    called = {}

    def fake_handler(params):
        called.update(params)

    monkeypatch.setattr(
        "app.tasks.handlers.get_task_handler",
        lambda t: fake_handler if t == "interview_prep" else None,
    )

    _dispatch_one(
        fake_mgr,
        {"task_id": "t-2", "task_type": "interview_prep", "params": {"job_analysis_id": 5}},
    )

    assert called["task_id"] == "t-2"
    assert called["job_analysis_id"] == 5
