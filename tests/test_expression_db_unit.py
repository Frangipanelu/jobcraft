"""表达式 CRUD 与版本链单元测试（EXP-P2-02）。

不依赖真实 DB——monkeypatch app.tools.db_expression 的 db_conn 封装函数，
用假 cursor 捕获 SQL/参数并返回可控行。
"""

import json
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import db_expression as mod


class _FakeCursor:
    """记录 execute 的假 cursor；返回由测试预设的数据。"""

    def __init__(self, row=None, rows=None, rowcount=0, lastrowid=5):
        self._row = row
        self._rows = rows
        self._rowcount = rowcount
        self._lastrowid = lastrowid
        self.executed: list[tuple] = []

    @property
    def rowcount(self):
        return self._rowcount

    @property
    def lastrowid(self):
        return self._lastrowid

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, args=None):
        self.executed.append((sql, args))
        self._rowcount = 1

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows or []


def _fake_expression_row(**over):
    """构造一条 expression 数据库行（模拟 query_all/query_one 返回值）。"""
    row = {
        "id": 1,
        "user_id": 7,
        "experience_id": 10,
        "direction_id": None,
        "job_id": None,
        "type": "standardized",
        "content": "推动 AI 产品从 0 到 1，ARR 增长 300%",
        "version": 3,
        "validation_level": 1,
        "usage_count": 2,
        "source_refs": [{"type": "card", "card_id": 10}],
        "status": "active",
        "created_at": datetime(2026, 9, 23, 12, 0, 0),
        "updated_at": datetime(2026, 9, 23, 12, 5, 0),
    }
    row.update(over)
    return row


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, dictionary=False):
        return self._cursor

    def commit(self):
        return None

    @property
    def autocommit(self):
        return False

    @autocommit.setter
    def autocommit(self, value):
        pass


@pytest.fixture
def fake_db(monkeypatch):
    """把 db_conn 封装函数替换为可控假实现，返回持有假 cursor/状态的容器。"""
    cursor = _FakeCursor()
    holder = {"cursor": cursor, "lastrowid": 5, "rowcount": 1}

    @contextmanager
    def _txn():
        conn = _FakeConn()
        conn._cursor = cursor
        yield conn

    def _query_one(sql, params=None):
        cursor.executed.append((sql, params))
        return cursor.fetchone()

    def _query_all(sql, params=None):
        cursor.executed.append((sql, params))
        return cursor.fetchall()

    def _lastrowid(sql, params=None):
        cursor.executed.append((sql, params))
        return holder["lastrowid"]

    def _execute(sql, params=None):
        cursor.executed.append((sql, params))
        cursor._rowcount = holder["rowcount"]
        return holder["rowcount"]

    monkeypatch.setattr(mod, "query_one", _query_one)
    monkeypatch.setattr(mod, "query_all", _query_all)
    monkeypatch.setattr(mod, "execute", _execute)
    monkeypatch.setattr(mod, "execute_lastrowid", _lastrowid)
    monkeypatch.setattr(
        mod,
        "transaction",
        lambda: _txn(),
    )
    return holder


class TestRowMapper:
    def test_maps_json_and_version_fields(self):
        row = _fake_expression_row()
        out = mod._row_to_expression(row)
        assert out["id"] == 1
        assert out["type"] == "standardized"
        assert out["version"] == 3
        assert out["validation_level"] == 1
        assert out["usage_count"] == 2
        assert isinstance(out["source_refs"], list)
        assert out["status"] == "active"
        assert out["created_at"] == "2026-09-23T12:00:00"
        assert out["direction_id"] is None

    def test_null_source_refs_becomes_empty_list(self):
        row = _fake_expression_row(source_refs=None)
        assert mod._row_to_expression(row)["source_refs"] == []


class TestCreateValidation:
    def test_invalid_type_rejected(self, fake_db):
        with pytest.raises(ValueError, match="type 仅允许"):
            mod.create_expression(
                {"user_id": 7, "experience_id": 10, "type": "bad", "content": "x"}
            )

    def test_invalid_status_rejected(self, fake_db):
        with pytest.raises(ValueError, match="status 仅允许"):
            mod.create_expression(
                {
                    "user_id": 7,
                    "experience_id": 10,
                    "type": "standardized",
                    "content": "x",
                    "status": "bogus",
                }
            )

    def test_empty_content_rejected(self, fake_db):
        with pytest.raises(ValueError, match="content 不能为空"):
            mod.create_expression(
                {
                    "user_id": 7,
                    "experience_id": 10,
                    "type": "standardized",
                    "content": "   ",
                }
            )


class TestCreateInsertParams:
    def test_insert_includes_next_version(self, monkeypatch):
        """新创建应对同组内 max(version)+1（版本链单调递增），参数正确透传。"""
        captured = {}

        def fake_lastrowid(sql, params=None):
            captured["sql"] = sql
            captured["params"] = params
            return 9

        def fake_query_one(sql, params=None):
            if "max(version)" in sql:
                return {"max(version)": 4}
            return None

        monkeypatch.setattr(mod, "execute_lastrowid", fake_lastrowid)
        monkeypatch.setattr(mod, "query_one", fake_query_one)
        out_id = mod.create_expression(
            {
                "user_id": 7,
                "experience_id": 10,
                "type": "standardized",
                "content": "新表达",
                "source_refs": [{"type": "card", "card_id": 10}],
            }
        )
        assert out_id == 9
        assert "INSERT INTO expression" in captured["sql"]
        params = captured["params"]
        assert params[0] == 7
        assert params[1] == 10
        assert params[4] == "standardized"
        assert params[5] == "新表达"
        assert params[6] == 5  # max(4) + 1
        assert params[9] == json.dumps(
            [{"type": "card", "card_id": 10}], ensure_ascii=False
        )
        assert params[10] == "candidate"


class TestGetExpression:
    def test_by_id_with_user_filter(self, fake_db):
        fake_db["cursor"]._row = _fake_expression_row()
        out = mod.get_expression(1, user_id=7)
        assert out is not None
        assert any("AND user_id=%s" in s for s, _ in fake_db["cursor"].executed)

    def test_missing_returns_none(self, fake_db):
        fake_db["cursor"]._row = None
        assert mod.get_expression(999, user_id=7) is None


class TestListByExperience:
    def test_filters_applied_and_sorted(self, fake_db):
        fake_db["cursor"]._rows = [_fake_expression_row()]
        out = mod.get_expressions_by_experience(10, 7, expr_type="standardized")
        assert len(out) == 1
        last_sql = fake_db["cursor"].executed[-1][0]
        assert "WHERE experience_id=%s AND user_id=%s" in last_sql
        assert "AND type=%s" in last_sql
        assert "ORDER BY type, direction_id, job_id, version DESC" in last_sql

    def test_direction_filter_appended(self, fake_db):
        fake_db["cursor"]._rows = []
        mod.get_expressions_by_experience(10, 7, direction_id=3)
        last_sql = fake_db["cursor"].executed[-1][0]
        assert "AND direction_id=%s" in last_sql


class TestVersionChain:
    def test_create_version_bases_on_existing(self, fake_db):
        """create_expression_version 应基于原行组归属创建新版本。"""
        fake_db["cursor"]._row = _fake_expression_row(id=9)
        fake_db["cursor"]._rows = []
        fake_db["lastrowid"] = 9

        calls = []

        with patch.object(
            mod,
            "create_expression",
            side_effect=lambda *a, **kw: calls.append(a[0]) or 9,
        ):
            new_id = mod.create_expression_version(1, "新版本内容", user_id=7)
        assert new_id == 9
        assert calls and calls[0]["experience_id"] == 10
        assert calls[0]["content"] == "新版本内容"
        assert calls[0]["status"] == "candidate"

    def test_create_version_unknown_expression(self, fake_db):
        fake_db["cursor"]._row = None
        with pytest.raises(LookupError, match="不存在或不属于用户"):
            mod.create_expression_version(999, "内容", user_id=7)


class TestStatusUpdate:
    def test_update_status_valid(self, fake_db):
        assert mod.update_status(1, "deprecated", user_id=7) is True

    def test_update_status_invalid_rejected(self, fake_db):
        with pytest.raises(ValueError, match="status 仅允许"):
            mod.update_status(1, "hacked", user_id=7)


class TestDelete:
    def test_delete_calls_execute_with_owner(self, fake_db):
        assert mod.delete_expression(1, user_id=7) is True
        assert any(
            "DELETE FROM expression" in s and "AND user_id=%s" in s
            for s, _ in fake_db["cursor"].executed
        )
