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
    ("GET", "/api/jobcraft/experience/export", None),
    (
        "POST",
        "/api/jobcraft/experience/cards/batch",
        {"action": "archive", "card_ids": [1]},
    ),
    ("GET", "/api/jobcraft/experience/cards/1/versions", None),
    ("POST", "/api/jobcraft/experience/cards/1/versions", {"title": "v"}),
    ("POST", "/api/jobcraft/experience/cards", {"title": "t", "raw_text": "x"}),
    ("PATCH", "/api/jobcraft/experience/cards/1", {"title": "t"}),
    ("DELETE", "/api/jobcraft/experience/cards/1", None),
    ("POST", "/api/jobcraft/experience/cards/1/structure", None),
    ("POST", "/api/jobcraft/experience/cards/1/recommend-tags", None),
    ("POST", "/api/jobcraft/experience/cards/backfill", {"min_chars": 100}),
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
        "/api/jobcraft/job/step1-ats-recommend",
        {"company": "C", "position": "P", "jd_text": "J"},
    ),
    (
        "POST",
        "/api/jobcraft/job/step2-gap-polish",
        {"job_analysis_id": 1, "card_ids": [1]},
    ),
    (
        "POST",
        "/api/jobcraft/job/save-card-version",
        {"card_id": 1, "source_id": 1, "raw_text": "x"},
    ),
    ("POST", "/api/jobcraft/job/analyze-ats", {"jd_text": "J"}),
    (
        "POST",
        "/api/jobcraft/job/save-resume",
        {"job_analysis_id": 1, "selected_card_ids": [1]},
    ),
    ("POST", "/api/jobcraft/job/1/resume-preview", {"selected_card_ids": [1]}),
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
    ("GET", "/api/jobcraft/job/1/selected-cards", None),
    ("GET", "/api/jobcraft/job/1/interview-prep", None),
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
    # tasks
    ("POST", "/api/jobcraft/tasks/submit", {"task_type": "export_pdf", "params": {}}),
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
        "/api/jobcraft/experience/upload",
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
    assert "密码" in resp.json()["msg"]


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
    assert "邮箱" in resp.json()["msg"]


def test_register_duplicate_username_rejected(monkeypatch):
    monkeypatch.setattr("app.tools.db_tools.get_user_by_username", lambda *a: {"id": 1})
    resp = client.post(
        "/api/auth/register",
        json={"username": "bob", "password": "Secret123"},
    )
    assert resp.status_code == 400
    assert "用户名已存在" in resp.json()["msg"]


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
    assert "邮箱已被使用" in resp.json()["msg"]


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
    assert "用户名或密码错误" in resp.json()["msg"]


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
