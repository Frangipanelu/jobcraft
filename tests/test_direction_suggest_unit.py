"""方向词典建议端点测试（T-M4-3：POST /api/jobcraft/direction/suggest）。

覆盖：认证（401）、命中响应、未命中 matched=false、空文本、超长 422。
词典本身逻辑见 test_direction_dict_unit.py；此处走真实词典（零 I/O 确定性）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.api.server import app
from app.auth import create_access_token

_TOKEN = create_access_token({"user_id": 1, "username": "unittest"})
_HEADERS = {"Authorization": f"Bearer {_TOKEN}"}

client = TestClient(app, raise_server_exceptions=False)


class TestDirectionSuggestEndpoint:
    """POST /api/jobcraft/direction/suggest"""

    def test_requires_auth(self):
        resp = client.post("/api/jobcraft/direction/suggest", json={"text": "电商"})
        assert resp.status_code == 401

    def test_hit_returns_match_and_four_dims(self):
        resp = client.post(
            "/api/jobcraft/direction/suggest",
            json={"text": "跨境电商运营专员，负责 GMV 与商家履约"},
            headers=_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is True
        assert data["direction_name"] == "电商零售"
        assert data["industry"] == "电商与零售"
        assert data["product"]
        assert data["scenario"]
        assert data["skills"]
        # 词典不产职能/主角色（Q4 范围）→ 响应占位空串
        assert "job_function" not in data
        assert "primary_role" not in data

    def test_miss_returns_matched_false_with_placeholders(self):
        resp = client.post(
            "/api/jobcraft/direction/suggest",
            json={"text": "一段与词典完全无关的描述 xyz"},
            headers=_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is False
        assert data["direction_name"] == ""
        assert data["industry"] == ""

    def test_empty_text_returns_matched_false(self):
        resp = client.post("/api/jobcraft/direction/suggest", json={}, headers=_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["matched"] is False

    def test_oversize_text_returns_422(self):
        resp = client.post(
            "/api/jobcraft/direction/suggest",
            json={"text": "x" * 5001},
            headers=_HEADERS,
        )
        assert resp.status_code == 422
