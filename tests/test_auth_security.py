"""
认证安全测试

覆盖：
1. 所有业务端点未认证访问返回 401
2. 带合法 token 时 user_id 由 token 注入（客户端不能伪造身份）
3. 公开端点（register/login/health）无需认证
4. 注册输入加固（密码强度 / 邮箱格式 / 唯一性）
5. 登录（错误密码 401、正确登录返回 token）
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.server import app
from app.auth import create_access_token, get_password_hash

client = TestClient(app, raise_server_exceptions=False)


def make_token(user_id: int) -> str:
    return create_access_token({"user_id": user_id, "username": f"user_{user_id}"})


# ============================================================
# 1. 业务端点未认证 → 401
# ============================================================

_BUSINESS_ENDPOINTS = [
    # experience
    ("GET", "/api/jobcraft/experience/cards", None),
    ("GET", "/api/jobcraft/experience/cards/search?q=python", None),
    # 表达方向结构化检索（T-M3-4）
    ("GET", "/api/jobcraft/experience/expressions?direction_id=3", None),
    ("POST", "/api/jobcraft/experience/cards", {"title": "t", "raw_text": "x"}),
    ("PATCH", "/api/jobcraft/experience/cards/1", {"title": "t"}),
    ("DELETE", "/api/jobcraft/experience/cards/1", None),
    ("POST", "/api/jobcraft/experience/cards/1/structure", None),
    ("POST", "/api/jobcraft/experience/cards/1/recommend-tags", None),
    # direction（T-M3-1）
    ("GET", "/api/jobcraft/direction", None),
    ("POST", "/api/jobcraft/direction", {"name": "方向A"}),
    ("GET", "/api/jobcraft/direction/1", None),
    ("PATCH", "/api/jobcraft/direction/1", {"name": "方向B"}),
    ("DELETE", "/api/jobcraft/direction/1", None),
    # direction find-or-create（T-M3-3）
    ("POST", "/api/jobcraft/direction/find-or-create", {"name": "方向A"}),
    # direction summary（T-M3-6 方向沉淀汇总）
    ("GET", "/api/jobcraft/direction/summary", None),
    # direction 词典建议（T-M4-3 零 LLM）
    ("POST", "/api/jobcraft/direction/suggest", {"text": "跨境电商"}),
    # jd_classification（T-M3-2）
    ("GET", "/api/jobcraft/job/1/jd-classification", None),
    (
        "POST",
        "/api/jobcraft/job/1/jd-classification",
        {"job_function": "用户增长", "industry": "电商"},
    ),
    # job_analysis
    ("GET", "/api/jobcraft/job/analyses", None),
    ("GET", "/api/jobcraft/job/analyze/1", None),
    ("DELETE", "/api/jobcraft/job/analyze/1", None),
    (
        "POST",
        "/api/jobcraft/job/analyze",
        {"company": "C", "position": "P", "jd_text": "J", "card_ids": [1]},
    ),
    (
        "POST",
        "/api/jobcraft/job/analyze-ats-structured",
        {
            "company": "C",
            "position": "P",
            "duties": ["d"],
            "requirements": [{"text": "r", "tag": "required"}],
        },
    ),
    (
        "POST",
        "/api/jobcraft/experience/cards/1/polish",
        {"raw_text": "经历文本", "company": "C", "role": "P"},
    ),
    (
        "POST",
        "/api/jobcraft/job/save-resume",
        {"job_analysis_id": 1, "selected_card_ids": [1]},
    ),
    ("GET", "/api/jobcraft/job/resume/download?path=out.md", None),
    # submission
    ("POST", "/api/jobcraft/submission", {"position": "P"}),
    ("GET", "/api/jobcraft/submission/1", None),
    ("PATCH", "/api/jobcraft/submission/1", {"status": "面试中"}),
    ("DELETE", "/api/jobcraft/submission/1", None),
    ("GET", "/api/jobcraft/dashboard", None),
    # interview_prep
    (
        "POST",
        "/api/jobcraft/job/1/interview-prep",
        {"card_ids": [1], "round_type": "技术面"},
    ),
    ("GET", "/api/jobcraft/job/1/interview-prep", None),
    ("POST", "/api/jobcraft/interview-prep/1/company-research", None),
    # interview_review
    (
        "POST",
        "/api/jobcraft/interview-review",
        {"raw_text": "这是一段足够长的面试记录文本用于测试。"},
    ),
    ("GET", "/api/jobcraft/interview-review", None),
    ("POST", "/api/jobcraft/interview-review/1/question-table", None),
    ("POST", "/api/jobcraft/interview-review/1/analyze", {"selected_sequences": [1]}),
    ("GET", "/api/jobcraft/interview-review/1", None),
    ("DELETE", "/api/jobcraft/interview-review/1", None),
    (
        "POST",
        "/api/jobcraft/interview-review/session",
        {"company": "字节跳动", "position": "AI 产品经理"},
    ),
    (
        "GET",
        "/api/jobcraft/validation-summary?target_type=experience&target_id=1",
        None,
    ),
    # tasks
    (
        "POST",
        "/api/jobcraft/tasks/submit",
        {"task_type": "resume_generate", "params": {}},
    ),
    ("GET", "/api/jobcraft/tasks/t_1", None),
    ("POST", "/api/jobcraft/tasks/t_1/cancel", None),
    ("GET", "/api/jobcraft/tasks", None),
]


@pytest.mark.parametrize("method,path,json_body", _BUSINESS_ENDPOINTS)
def test_business_endpoint_requires_auth(method, path, json_body):
    """未认证访问业务端点一律 401"""
    resp = client.request(method, path, json=json_body)
    assert resp.status_code == 401, f"{method} {path} 期望 401，实际 {resp.status_code}"


def test_invalid_token_rejected():
    """伪造/损坏 token 拒绝访问"""
    resp = client.get(
        "/api/jobcraft/dashboard",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert resp.status_code == 401


def test_upload_and_form_endpoints_require_auth():
    """文件上传 / 表单类业务端点同样强制认证"""
    import io

    resp = client.post(
        "/api/jobcraft/experience/upload/preview",
        files={"file": ("resume.md", io.BytesIO(b"resume"), "text/plain")},
    )
    assert resp.status_code == 401

    resp = client.post(
        "/api/jobcraft/submission/manual",
        files={"file": ("resume.md", io.BytesIO(b"resume"), "text/plain")},
        data={"position": "SWE"},
    )
    assert resp.status_code == 401

    resp = client.post(
        "/api/jobcraft/interview-review/parse-preview",
        data={"raw_text": "这是一段足够长的面试记录文本用于测试。"},
    )
    assert resp.status_code == 401


# ============================================================
# 2. 认证请求使用 token 中的 user_id
# ============================================================


def test_authenticated_dashboard_uses_token_user(monkeypatch):
    """GET dashboard 的 user_id 来自 token，而非客户端传参"""
    captured = {}

    def fake_get_dashboard(user_id):
        captured["user_id"] = user_id
        return []

    monkeypatch.setattr("app.api.submission.db_tools.get_dashboard", fake_get_dashboard)
    token = make_token(42)
    resp = client.get(
        "/api/jobcraft/dashboard?user_id=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert captured["user_id"] == 42


def test_authenticated_create_card_uses_token_user(monkeypatch):
    """创建经历卡时 user_id 来自 token，忽略客户端传入的 user_id"""
    captured = {}

    def fake_insert_card(data):
        captured["data"] = data
        return 10

    monkeypatch.setattr("app.api.experience.db_tools.insert_card", fake_insert_card)
    monkeypatch.setattr(
        "app.api.experience.db_tools.get_card", lambda *a: {"id": 10, "user_id": 42}
    )
    token = make_token(42)
    resp = client.post(
        "/api/jobcraft/experience/cards",
        json={"user_id": 999, "title": "卡", "raw_text": "内容"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert captured["data"]["user_id"] == 42


def test_submit_task_injects_token_user_id(monkeypatch):
    """POST /tasks/submit：params.user_id 由服务端从 token 覆盖，客户端传值不生效"""
    captured = {}

    class _FakeManager:
        def submit_task(self, task_type, params, **kwargs):
            captured["task_type"] = task_type
            captured["params"] = params
            return "t-1"

    monkeypatch.setattr("app.tasks.get_task_manager", lambda: _FakeManager())

    token = make_token(42)
    resp = client.post(
        "/api/jobcraft/tasks/submit",
        json={
            "task_type": "resume_generate",
            "params": {"user_id": 999, "company": "A", "position": "P"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["task_id"] == "t-1"
    assert captured["task_type"] == "resume_generate"
    assert captured["params"]["user_id"] == 42
    assert captured["params"]["company"] == "A"


def test_submit_task_injects_user_id_when_client_omits(monkeypatch):
    """POST /tasks/submit：客户端未传 user_id 时同样由 token 注入（缺省不影响提交）"""
    captured = {}

    class _FakeManager:
        def submit_task(self, task_type, params, **kwargs):
            captured["params"] = params
            return "t-2"

    monkeypatch.setattr("app.tasks.get_task_manager", lambda: _FakeManager())

    token = make_token(7)
    resp = client.post(
        "/api/jobcraft/tasks/submit",
        json={"task_type": "resume_generate", "params": {"company": "A"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert captured["params"]["user_id"] == 7


def test_submit_task_strips_client_task_id(monkeypatch):
    """T-M10-4 评审修复：客户端塞入的 task_id 在源头剥离，不得进入队列 params。"""
    captured = {}

    class _FakeManager:
        def submit_task(self, task_type, params, **kwargs):
            captured["params"] = params
            return "t-new"

    monkeypatch.setattr("app.tasks.get_task_manager", lambda: _FakeManager())

    token = make_token(42)
    resp = client.post(
        "/api/jobcraft/tasks/submit",
        json={
            "task_type": "resume_generate",
            "params": {"task_id": "victim-task", "company": "A"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "task_id" not in captured["params"]
    assert captured["params"]["company"] == "A"
    assert captured["params"]["user_id"] == 42


@pytest.mark.parametrize("bad_params", [[], "", 0])
def test_submit_task_rejects_non_object_params(monkeypatch, bad_params):
    """params 为非对象（含 falsy 非对象）一律 400，不被 `or {}` 静默当空对象绕过。"""

    def _must_not_call():
        raise AssertionError("params 非对象时不得触达 task manager")

    monkeypatch.setattr("app.tasks.get_task_manager", _must_not_call)

    token = make_token(42)
    resp = client.post(
        "/api/jobcraft/tasks/submit",
        json={"task_type": "resume_generate", "params": bad_params},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "params" in resp.json()["error"]["message"]


@pytest.mark.parametrize(
    "body",
    [
        {"task_type": "resume_generate", "params": None},
        {"task_type": "resume_generate"},
    ],
)
def test_submit_task_accepts_null_or_absent_params(monkeypatch, body):
    """params 为 null / 缺省视为无参提交：200 且照常注入 user_id。"""
    captured = {}

    class _FakeManager:
        def submit_task(self, task_type, params, **kwargs):
            captured["params"] = params
            return "t-3"

    monkeypatch.setattr("app.tasks.get_task_manager", lambda: _FakeManager())

    token = make_token(42)
    resp = client.post(
        "/api/jobcraft/tasks/submit",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert captured["params"] == {"user_id": 42}


# ============================================================
# 3. 公开端点无需认证
# ============================================================

_PUBLIC_ENDPOINTS = [
    ("GET", "/health", None),
    ("GET", "/api/jobcraft/health", None),
]


@pytest.mark.parametrize("method,path,json_body", _PUBLIC_ENDPOINTS)
def test_public_endpoints_open(method, path, json_body):
    resp = client.request(method, path, json=json_body)
    assert resp.status_code != 401


# ============================================================
# 4. 注册输入加固
# ============================================================


def _monkeypatch_register_ok(monkeypatch, new_user_id=99):
    monkeypatch.setattr("app.tools.db_tools.get_user_by_username", lambda *a: None)
    monkeypatch.setattr("app.tools.db_tools.get_user_by_email", lambda *a: None)
    monkeypatch.setattr("app.tools.db_tools.create_user", lambda *a, **kw: new_user_id)


def test_register_weak_password_rejected(monkeypatch):
    _monkeypatch_register_ok(monkeypatch)
    resp = client.post(
        "/api/auth/register", json={"username": "alice", "password": "short1"}
    )
    assert resp.status_code == 400
    assert "密码" in resp.json()["error"]["message"]


def test_register_password_without_digit_rejected(monkeypatch):
    _monkeypatch_register_ok(monkeypatch)
    resp = client.post(
        "/api/auth/register", json={"username": "alice", "password": "abcdefgh"}
    )
    assert resp.status_code == 400


def test_register_invalid_email_rejected(monkeypatch):
    _monkeypatch_register_ok(monkeypatch)
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "Secret123", "email": "not-an-email"},
    )
    assert resp.status_code == 400
    assert "邮箱" in resp.json()["error"]["message"]


def test_register_duplicate_username_rejected(monkeypatch):
    monkeypatch.setattr("app.tools.db_tools.get_user_by_username", lambda *a: {"id": 1})
    resp = client.post(
        "/api/auth/register",
        json={"username": "bob", "password": "Secret123"},
    )
    assert resp.status_code == 400
    assert "用户名已存在" in resp.json()["error"]["message"]


def test_register_duplicate_email_rejected(monkeypatch):
    _monkeypatch_register_ok(monkeypatch)
    monkeypatch.setattr(
        "app.tools.db_tools.get_user_by_email",
        lambda *a: {"id": 2, "email": "a@b.com"},
    )
    resp = client.post(
        "/api/auth/register",
        json={"username": "new", "password": "Secret123", "email": "a@b.com"},
    )
    assert resp.status_code == 400
    assert "邮箱已被使用" in resp.json()["error"]["message"]


def test_register_success_returns_token(monkeypatch):
    _monkeypatch_register_ok(monkeypatch, new_user_id=99)
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "Secret123", "email": "a@b.com"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == 99
    assert data["access_token"]


# ============================================================
# 5. 登录
# ============================================================


def test_login_wrong_password_returns_401(monkeypatch):
    password_hash = get_password_hash("Secret123")
    monkeypatch.setattr(
        "app.tools.db_tools.get_user_by_username",
        lambda *a: {"id": 5, "username": "alice", "password_hash": password_hash},
    )
    resp = client.post(
        "/api/auth/login", json={"username": "alice", "password": "wrongpass9"}
    )
    assert resp.status_code == 401
    assert "用户名或密码错误" in resp.json()["error"]["message"]


def test_login_success_returns_token(monkeypatch):
    password_hash = get_password_hash("Secret123")
    monkeypatch.setattr(
        "app.tools.db_tools.get_user_by_username",
        lambda *a: {"id": 5, "username": "alice", "password_hash": password_hash},
    )
    resp = client.post(
        "/api/auth/login", json={"username": "alice", "password": "Secret123"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == 5
    assert data["access_token"]
