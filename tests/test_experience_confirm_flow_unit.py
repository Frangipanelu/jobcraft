"""EXP-P1-03 Confirm-As-V1 单元测试。

覆盖：
- db 层：insert_card 透传 is_confirmed/fields、write_baseline 哨兵基线；
  update_card(confirm=True) 定稿事务（写入基线+置位、幂等、越权/不存在）；
  _row_to_card 暴露 is_confirmed/fields。
- API 层：confirmUpload 入库草稿 is_confirmed=False；PATCH 携带 is_confirmed
  把 confirm 透传给 update_card。

不依赖真实 MySQL（假游标/上下文）。
"""

from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.api.server import app
from app.tools import db_experience as mod

_TOKEN = create_access_token({"user_id": 1, "username": "unittest"})
_HEADERS = {"Authorization": f"Bearer {_TOKEN}"}


def _noop(*a, **k):
    return None


# ============================================================
# db 层：insert_card
# ============================================================


def test_insert_card_passes_is_confirmed_and_fields(monkeypatch):
    """草稿卡 is_confirmed=False + fields 应出现在 INSERT SQL/参数中。"""
    captured = {}
    monkeypatch.setattr(mod, "_ensure_experience_card_columns", _noop)

    def fake_execute_lastrowid(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return 7

    monkeypatch.setattr(mod, "execute_lastrowid", fake_execute_lastrowid)
    card_id = mod.insert_card(
        {
            "user_id": 1,
            "title": "标题",
            "raw_text": "内容",
            "source": "resume_upload",
            "is_confirmed": False,
            "fields": {"focus": "推荐系统"},
        }
    )
    assert card_id == 7
    assert "is_confirmed" in captured["sql"]
    assert "fields" in captured["sql"]
    # 列序：... source, is_confirmed, fields
    assert captured["params"][-2] == 0
    assert captured["params"][-1] == '{"focus": "推荐系统"}'


def test_insert_card_defaults_is_confirmed_true(monkeypatch):
    """未传 is_confirmed 时默认定稿（存量/手动路径兼容）。"""
    captured = {}
    monkeypatch.setattr(mod, "_ensure_experience_card_columns", _noop)

    def fake_execute_lastrowid(sql, params):
        captured["params"] = params
        return 1

    monkeypatch.setattr(mod, "execute_lastrowid", fake_execute_lastrowid)
    mod.insert_card({"user_id": 1, "title": "t", "raw_text": "r"})
    assert captured["params"][-2] == 1


def test_insert_card_write_baseline_writes_sentinel(monkeypatch):
    """write_baseline=True 时同一事务内写 V1 哨兵基线。"""
    monkeypatch.setattr(mod, "_ensure_experience_card_columns", _noop)
    monkeypatch.setattr(mod, "_ensure_card_versions_table", _noop)
    executed = []

    class Cur:
        def __init__(self):
            self.executed = executed
            self.lastrowid = 99

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params=None):
            self.executed.append((sql, params))

    class Conn:
        def cursor(self, dictionary=False):
            return Cur()

    @contextmanager
    def fake_transaction():
        yield Conn()

    monkeypatch.setattr(mod, "transaction", fake_transaction)
    card_id = mod.insert_card(
        {
            "user_id": 1,
            "title": "手动卡",
            "raw_text": "内容",
            "source": "manual",
            "tags": ["Python"],
            "write_baseline": True,
        }
    )
    assert card_id == 99
    baseline_sql, baseline_params = executed[1]
    assert baseline_sql.strip().startswith("INSERT INTO card_versions")
    assert baseline_params[1:4] == ("original", "original", 0)
    assert baseline_params[4] == "手动卡"
    assert "V1" in baseline_params[7]


def test_insert_card_write_baseline_flag_not_persisted(monkeypatch):
    """write_baseline 是控制键，不得写入 experience_card 列。"""
    executed = []
    monkeypatch.setattr(mod, "_ensure_experience_card_columns", _noop)
    monkeypatch.setattr(mod, "_ensure_card_versions_table", _noop)

    class Cur:
        lastrowid = 5

        def __init__(self):
            self.executed = executed

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params=None):
            self.executed.append((sql, params))

    class Conn:
        def cursor(self, dictionary=False):
            return Cur()

    @contextmanager
    def fake_transaction():
        yield Conn()

    monkeypatch.setattr(mod, "transaction", fake_transaction)
    card_id = mod.insert_card({"title": "t", "raw_text": "r", "write_baseline": True})
    assert card_id == 5
    insert_sql = executed[0][0]
    assert "write_baseline" not in insert_sql


# ============================================================
# db 层：update_card(confirm=True) 定稿事务
# ============================================================


def _patch_transaction(monkeypatch, executed, rows, rowcount=1):
    """以假事务上下文替换 db_experience.transaction。"""

    class Cur:
        def __init__(self):
            self.executed = executed
            self._rows = list(rows)
            self._fetch = []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        @property
        def rowcount(self):
            return self._rowcount

        @rowcount.setter
        def rowcount(self, value):
            self._rowcount = value

        def execute(self, sql, params=None):
            self.executed.append((sql, params))
            s = sql.strip()
            if s.startswith("SELECT id, title, raw_text, tags, is_confirmed"):
                self._fetch = list(self._rows)
            if s.startswith("UPDATE experience_card SET is_confirmed"):
                self._rowcount = 1

        def fetchone(self):
            return self._fetch.pop(0) if self._fetch else None

    cur = Cur()
    cur.rowcount = rowcount

    class Conn:
        autocommit = True

        def cursor(self, dictionary=False):
            return cur

        def commit(self):
            pass

        def close(self):
            pass

    @contextmanager
    def fake_transaction():
        yield Conn()

    monkeypatch.setattr(mod, "_ensure_experience_card_columns", _noop)
    monkeypatch.setattr(mod, "_ensure_card_versions_table", _noop)
    monkeypatch.setattr(mod, "transaction", fake_transaction)
    return cur


def test_update_card_confirm_finalizes_draft_with_baseline(monkeypatch):
    """草稿卡（is_confirmed=0）confirm 时写基线并置位。"""
    executed = []
    _patch_transaction(
        monkeypatch,
        executed,
        rows=[
            {
                "id": 5,
                "title": "卡",
                "raw_text": "内容",
                "tags": None,
                "is_confirmed": 0,
            }
        ],
    )
    ok = mod.update_card(5, {"title": "卡2"}, user_id=1, confirm=True)
    assert ok is True
    statements = [sql.strip() for sql, _ in executed]
    assert statements[0].startswith("UPDATE experience_card SET")
    assert statements[1].startswith("SELECT id, title, raw_text, tags, is_confirmed")
    baseline_sql, baseline_params = executed[2]
    assert baseline_sql.strip().startswith("INSERT INTO card_versions")
    assert baseline_params[1:4] == ("original", "original", 0)
    assert statements[-1].startswith("UPDATE experience_card SET is_confirmed=1")


def test_update_card_confirm_is_idempotent_on_confirmed(monkeypatch):
    """已定稿卡 confirm 为幂等空操作（不重复写基线）。"""
    executed = []
    _patch_transaction(
        monkeypatch,
        executed,
        rows=[
            {
                "id": 5,
                "title": "卡",
                "raw_text": "内容",
                "tags": None,
                "is_confirmed": 1,
            }
        ],
    )
    ok = mod.update_card(5, {"title": "卡2"}, user_id=1, confirm=True)
    assert ok is True
    assert not any(
        sql.strip().startswith("INSERT INTO card_versions") for sql, _ in executed
    )


def test_update_card_confirm_not_found_returns_false(monkeypatch):
    """confirm 时卡片不存在返回 False（API 映射 404）。"""
    triggered = []
    _patch_transaction(monkeypatch, triggered, rows=[])
    assert mod.update_card(99, {"title": "x"}, user_id=1, confirm=True) is False
    # 不应写基线/置位
    assert not any("INSERT INTO card_versions" in sql for sql, _ in triggered)


def test_update_card_confirm_applies_ownership_filter(monkeypatch):
    """confirm 路径的主表 UPDATE 与 SELECT 都带 user_id 过滤；越权命中无行返回 False。"""
    executed = []
    _patch_transaction(
        monkeypatch,
        executed,
        rows=[],  # 模拟其他用户：SELECT 带 user_id 过滤后命中无行
        rowcount=0,
    )
    ok = mod.update_card(5, {"title": "x"}, user_id=7, confirm=True)
    assert ok is False
    assert all("AND user_id=%s" in sql for sql, _ in executed)
    assert not any("INSERT INTO card_versions" in sql for sql, _ in executed)


def test_update_card_without_confirm_keeps_draft(monkeypatch):
    """内部自动 STAR 写入不带 confirm，草稿不会被误定稿。"""
    executed = []
    _patch_transaction(
        monkeypatch,
        executed,
        rows=[
            {
                "id": 5,
                "title": "卡",
                "raw_text": "内容",
                "tags": None,
                "is_confirmed": 0,
            }
        ],
    )
    ok = mod.update_card(5, {"is_active": True}, user_id=1, confirm=False)
    assert ok is True
    assert not any(
        sql.strip().startswith("INSERT INTO card_versions") for sql, _ in executed
    )


# ============================================================
# db 层：_row_to_card
# ============================================================


def test_row_to_card_exposes_confirm_and_fields():
    row = {
        "id": 1,
        "user_id": 1,
        "title": "t",
        "raw_text": "r",
        "tags": "[]",
        "ai_structured": None,
        "summary": "",
        "content": "",
        "company": "c",
        "role": "r",
        "period": "p",
        "background": None,
        "problem": None,
        "solution": None,
        "execution": None,
        "result": None,
        "dimensions": "[]",
        "source": "resume_upload",
        "card_type": "work",
        "version": 1,
        "is_active": 1,
        "is_confirmed": 0,
        "fields": None,
        "created_at": None,
        "updated_at": None,
    }
    card = mod._row_to_card(row)
    assert card["is_confirmed"] is False
    assert card["fields"] == {}


def test_row_to_card_parses_fields_json():
    row = {
        "id": 1,
        "user_id": 1,
        "title": "t",
        "raw_text": "r",
        "tags": "[]",
        "ai_structured": None,
        "summary": "",
        "content": "",
        "source": "resume_upload",
        "card_type": "work",
        "version": 1,
        "is_active": 1,
        "is_confirmed": 1,
        "fields": '{"direction": ["算法"]}',
    }
    card = mod._row_to_card(row)
    assert card["fields"] == {"direction": ["算法"]}


# ============================================================
# API 层：confirmUpload 入库草稿 + PATCH 定稿透传
# ============================================================


def test_upload_confirm_inserts_drafts_is_confirmed_false(monkeypatch):
    """confirmUpload 入库草稿 is_confirmed=False。"""
    captured = {}
    monkeypatch.setattr(
        "app.api.experience.db_tools.find_card_by_company_role", lambda *a: None
    )

    def fake_insert_card(data):
        captured["data"] = data
        return 77

    monkeypatch.setattr("app.api.experience.db_tools.insert_card", fake_insert_card)
    monkeypatch.setattr(
        "app.api.experience.db_tools.get_card",
        lambda *a: {"id": 77, "is_confirmed": False},
    )
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/jobcraft/experience/upload/confirm",
        json={
            "items": [
                {
                    "selected": True,
                    "company": "A",
                    "role": "工程师",
                    "raw_text": "x",
                    "title": "经历",
                }
            ]
        },
        headers=_HEADERS,
    )
    assert resp.status_code == 200
    assert captured["data"]["is_confirmed"] is False
    assert captured["data"]["source"] == "resume_upload"


def test_patch_card_confirm_flag_forwards_to_db(monkeypatch):
    """PATCH 携带 is_confirmed:true 时以 confirm=True 调用 update_card。"""
    captured = {}

    def fake_update_card(card_id, updates, user_id, **k):
        captured["updates"] = updates
        captured["confirm"] = k.get("confirm")
        return True

    monkeypatch.setattr("app.api.experience.db_tools.update_card", fake_update_card)
    monkeypatch.setattr("app.api.experience.db_tools.get_card", lambda *a: {"id": 1})
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.patch(
        "/api/jobcraft/experience/cards/1",
        json={"title": "新标题", "is_confirmed": True},
        headers=_HEADERS,
    )
    assert resp.status_code == 200
    assert captured["confirm"] is True
    assert "is_confirmed" not in captured["updates"], (
        "is_confirmed 不应作为普通字段写入"
    )
