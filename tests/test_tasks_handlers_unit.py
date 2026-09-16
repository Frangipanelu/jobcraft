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
    """任务注册表应暴露全部已接入任务类型。"""
    from app.tasks import handlers

    assert set(handlers.TASK_REGISTRY.keys()) == {
        "resume_generate",
        "interview_prep",
        "export_pdf",
        "jd_analyze_structured",
        "interview_review_analyze",
        "question_table",
        "parse_preview",
        "experience_polish",
    }


def test_interview_prep_missing_job_analysis_id_raises(monkeypatch):
    """执行面试准备前必须提供 job_analysis_id。"""
    from app.tasks.handlers import execute_interview_prep

    with pytest.raises(ValueError):
        execute_interview_prep({"round_type": "技术面", "card_ids": [1], "user_id": 1})


def test_interview_prep_calls_real_workflow_with_params(monkeypatch):
    """execute_interview_prep 应将参数对齐传给 interview_prep_flow.run_interview_prep_workflow。"""
    fake_mgr = FakeTaskManager()
    monkeypatch.setattr("app.tasks.handlers.get_task_manager", lambda: fake_mgr)

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


def test_jd_analyze_structured_calls_real_workflow_with_params(monkeypatch):
    """execute_jd_analyze_structured 应把 duties/requirements 对齐传给 workflow。"""
    from app.schemas.jobcraft import StructuredRequirementItem
    from app.tasks.handlers import execute_jd_analyze_structured

    fake_mgr = FakeTaskManager()
    monkeypatch.setattr("app.tasks.handlers.get_task_manager", lambda: fake_mgr)

    captured = {}

    def fake_workflow(**kwargs):
        captured.update(kwargs)
        return {
            "ats_profile": {"salary": "面议"},
            "raw": {},
            "company": "A",
            "position": "P",
        }

    monkeypatch.setattr(
        "app.workflows.job_analysis_flow.run_structured_ats_workflow", fake_workflow
    )

    result = execute_jd_analyze_structured(
        {
            "task_id": "t-s",
            "company": "A",
            "position": "P",
            "duties": ["职责1"],
            "requirements": [
                {"text": "熟悉 Python", "tag": "required"},
                {"text": "多模态加分", "tag": "preferred"},
            ],
        }
    )

    assert result["ats_profile"]["salary"] == "面议"
    assert captured["company"] == "A"
    assert captured["duties"] == ["职责1"]
    assert captured["requirements"][0] == StructuredRequirementItem(
        text="熟悉 Python", tag="required"
    )
    assert captured["requirements"][1].tag == "preferred"
    assert any(u["task_id"] == "t-s" for u in fake_mgr.status_updates)


def test_jd_analyze_structured_rejects_empty_input(monkeypatch):
    """职责与任职要求同时为空时应报错。"""
    from app.tasks.handlers import execute_jd_analyze_structured

    with pytest.raises(ValueError):
        execute_jd_analyze_structured(
            {
                "task_id": "t-s",
                "company": "A",
                "position": "P",
                "duties": [],
                "requirements": [],
            }
        )


def test_interview_review_analyze_calls_real_workflow_with_params(monkeypatch):
    """execute_interview_review_analyze 应把参数对齐传给 review workflow。"""
    from app.tasks.handlers import execute_interview_review_analyze

    fake_mgr = FakeTaskManager()
    monkeypatch.setattr("app.tasks.handlers.get_task_manager", lambda: fake_mgr)

    captured = {}

    def fake_workflow(**kwargs):
        captured.update(kwargs)
        return {"overall_score": 78, "questions": []}

    monkeypatch.setattr(
        "app.workflows.interview_review_flow.run_interview_review_workflow",
        fake_workflow,
    )

    result = execute_interview_review_analyze(
        {"task_id": "t-r", "record_id": 9, "selected_sequences": [2, 4], "user_id": 7}
    )

    assert result == {"overall_score": 78, "questions": []}
    assert captured["record_id"] == 9
    assert captured["selected_sequences"] == [2, 4]
    assert captured["user_id"] == 7
    assert any(u["task_id"] == "t-r" for u in fake_mgr.status_updates)


def test_interview_review_analyze_missing_record_id_raises(monkeypatch):
    from app.tasks.handlers import execute_interview_review_analyze

    with pytest.raises(ValueError):
        execute_interview_review_analyze({"task_id": "t-r", "user_id": 1})


def test_question_table_calls_real_workflow_and_wraps_result(monkeypatch):
    """execute_question_table 应包装 workflow 返回值为端点契约形状。"""
    from app.tasks.handlers import execute_question_table

    fake_mgr = FakeTaskManager()
    monkeypatch.setattr("app.tasks.handlers.get_task_manager", lambda: fake_mgr)

    captured = {}

    def fake_workflow(record_id, user_id=1):
        captured["record_id"] = record_id
        captured["user_id"] = user_id
        return [{"question": "Q1"}]

    monkeypatch.setattr(
        "app.workflows.question_table_flow.run_question_table_workflow", fake_workflow
    )

    result = execute_question_table({"task_id": "t-q", "record_id": 3, "user_id": 2})

    assert result == {
        "record_id": 3,
        "status": "question_table",
        "questions": [{"question": "Q1"}],
    }
    assert captured["record_id"] == 3
    assert captured["user_id"] == 2
    assert any(u["task_id"] == "t-q" for u in fake_mgr.status_updates)


def test_parse_preview_parses_and_returns_response_shape(monkeypatch):
    """execute_parse_preview 应复用 interview_review 工具并返回端点契约形状。"""
    import app.tools.interview_review as ir

    from app.tasks.handlers import execute_parse_preview

    fake_mgr = FakeTaskManager()
    monkeypatch.setattr("app.tasks.handlers.get_task_manager", lambda: fake_mgr)

    monkeypatch.setattr(
        ir,
        "_parse_dialogue",
        lambda text: [
            {"speaker": "面试官", "role": "interviewer", "text": "请介绍自己"},
            {"speaker": "候选人", "role": "candidate", "text": "好的"},
        ],
    )
    monkeypatch.setattr(
        ir,
        "_build_qa_pairs",
        lambda dialogue: [
            {"sequence": 1, "question": "请介绍自己", "speaker": "面试官"}
        ],
    )
    monkeypatch.setattr(
        "app.tools.db_tools.get_job_analysis",
        lambda job_analysis_id, user_id: {"jd_text": "JD 内容"},
    )

    result = execute_parse_preview(
        {
            "task_id": "t-p",
            "user_id": 1,
            "text": "【面试官】：请介绍自己\n【候选人】：好的",
            "with_intent": False,
            "job_analysis_id": 3,
        }
    )

    assert result["qa_pair_count"] == 1
    assert result["speaker_count"] == 2
    assert result["dialogue"][0]["role"] == "interviewer"
    assert any(u["task_id"] == "t-p" for u in fake_mgr.status_updates)


def test_experience_polish_calls_tool_with_params(monkeypatch):
    """execute_experience_polish 应把参数对齐传给 polish_experience 工具。"""
    from app.tasks.handlers import execute_experience_polish

    fake_mgr = FakeTaskManager()
    monkeypatch.setattr("app.tasks.handlers.get_task_manager", lambda: fake_mgr)

    captured = {}

    def fake_polish(raw_text, company="", role=""):
        captured.update(raw_text=raw_text, company=company, role=role)
        return "润色后的文本"

    monkeypatch.setattr("app.tools.experience_polish.polish_experience", fake_polish)

    result = execute_experience_polish(
        {"task_id": "t-e", "raw_text": "原始文本", "company": "A", "role": "P"}
    )

    assert result == {"polished_text": "润色后的文本", "original_text": "原始文本"}
    assert captured["raw_text"] == "原始文本"
    assert captured["company"] == "A"
    assert captured["role"] == "P"
    assert any(u["task_id"] == "t-e" for u in fake_mgr.status_updates)


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
        {
            "task_id": "t-2",
            "task_type": "interview_prep",
            "params": {"job_analysis_id": 5},
        },
    )

    assert called["task_id"] == "t-2"
    assert called["job_analysis_id"] == 5
