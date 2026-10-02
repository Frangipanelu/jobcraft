"""direction 表 CRUD 与 DIR-n 编码单元测试（T-M3-1 / Q7=c / U-P2a′）。

不依赖真实 DB——monkeypatch app.tools.db_direction 的 db_conn 封装函数，
用假 cursor 捕获 SQL/参数并返回可控行。
"""

import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest
from mysql.connector import Error as MySQLError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import db_direction as mod


class _FakeCursor:
    """记录 execute 的假 cursor；返回由测试预设的数据。

    insert_errors：每遇到一次 INSERT 依次弹出并抛出（模拟唯一键/缺列错误）。
    """

    def __init__(self):
        self._row = None
        self._rows = []
        self._rowcount = 1
        self._lastrowid = 11
        self.insert_errors: list = []
        self.executed: list = []

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
        if sql.strip().upper().startswith("INSERT") and self.insert_errors:
            raise self.insert_errors.pop(0)
        self._rowcount = 1

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


def _fake_direction_row(**over):
    """构造一条 direction 数据库行（模拟 query_all/query_one 返回值）。"""
    row = {
        "id": 1,
        "user_id": 7,
        "code": "DIR-1",
        "name": "策略运营-跨境电商",
        "job_function": "策略运营",
        "primary_role": "策略分析师",
        "industry": "跨境电商",
        "product": "商业化,增长",
        "scenario": "定价,投放",
        "skills": "SQL,Python",
        "status": "active",
        "created_at": datetime(2026, 10, 1, 10, 0, 0),
        "updated_at": datetime(2026, 10, 1, 10, 5, 0),
    }
    row.update(over)
    return row


def _dup_error(key: str) -> MySQLError:
    return MySQLError(msg=f"Duplicate entry 'x' for key 'direction.{key}'", errno=1062)


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, dictionary=False):
        return self._cursor

    def commit(self):
        return None

    def rollback(self):
        return None


@pytest.fixture
def fake_db(monkeypatch):
    """把 db_conn 封装函数替换为可控假实现，返回持有假 cursor/状态的容器。"""
    cursor = _FakeCursor()
    holder = {"cursor": cursor, "rowcount": 1, "txn_count": 0}

    @contextmanager
    def _txn():
        holder["txn_count"] += 1
        conn = _FakeConn()
        conn._cursor = cursor
        yield conn

    def _query_one(sql, params=None):
        cursor.executed.append((sql, params))
        return cursor.fetchone()

    def _query_all(sql, params=None):
        cursor.executed.append((sql, params))
        return cursor.fetchall()

    def _execute(sql, params=None):
        cursor.executed.append((sql, params))
        if sql.strip().upper().startswith("INSERT") and cursor.insert_errors:
            raise cursor.insert_errors.pop(0)
        cursor._rowcount = holder["rowcount"]
        return holder["rowcount"]

    monkeypatch.setattr(mod, "query_one", _query_one)
    monkeypatch.setattr(mod, "query_all", _query_all)
    monkeypatch.setattr(mod, "execute", _execute)
    monkeypatch.setattr(mod, "transaction", _txn)
    return holder


class TestRowMapper:
    def test_maps_six_dims_and_isoformat(self):
        row = _fake_direction_row()
        out = mod._row_to_direction(row)
        assert out["id"] == 1
        assert out["code"] == "DIR-1"
        assert out["name"] == "策略运营-跨境电商"
        assert out["job_function"] == "策略运营"
        assert out["primary_role"] == "策略分析师"
        assert out["industry"] == "跨境电商"
        assert out["product"] == "商业化,增长"
        assert out["scenario"] == "定价,投放"
        assert out["skills"] == "SQL,Python"
        assert out["status"] == "active"
        assert out["created_at"] == "2026-10-01T10:00:00"
        assert out["updated_at"] == "2026-10-01T10:05:00"

    def test_missing_p3_columns_degrade_to_empty(self):
        """未迁移库读路径不炸：V0018 新列缺省为空串（写路径另有迁移提示）。"""
        row = {"id": 1, "user_id": 7, "name": "旧方向", "status": "active"}
        out = mod._row_to_direction(row)
        assert out["code"] == ""
        assert out["job_function"] == ""
        assert out["skills"] == ""
        assert out["created_at"] is None


class TestCodeNumber:
    def test_valid_dir_code(self):
        assert mod._parse_code_number("DIR-3") == 3

    def test_non_dir_code_ignored(self):
        assert mod._parse_code_number("D1") == 0
        assert mod._parse_code_number("DIR-x") == 0
        assert mod._parse_code_number("") == 0
        assert mod._parse_code_number(None) == 0

    def test_next_code_skips_non_dir_rows(self, fake_db):
        fake_db["cursor"]._rows = [
            {"code": "DIR-1"},
            {"code": "DIR-3"},
            {"code": "D1"},
            {"code": ""},
        ]
        cur = fake_db["cursor"]
        assert mod._next_code(cur, 7) == "DIR-4"
        sql, params = cur.executed[-1]
        assert "WHERE user_id=%s" in sql
        assert params == (7,)

    def test_next_code_empty_table_is_dir_1(self, fake_db):
        fake_db["cursor"]._rows = []
        assert mod._next_code(fake_db["cursor"], 7) == "DIR-1"


class TestCreateValidation:
    def test_empty_name_rejected(self, fake_db):
        with pytest.raises(ValueError, match="方向名称不能为空"):
            mod.create_direction({"user_id": 7, "name": "   "})

    def test_invalid_status_rejected(self, fake_db):
        with pytest.raises(ValueError, match="status 仅允许"):
            mod.create_direction({"user_id": 7, "name": "方向", "status": "bogus"})


class TestCreate:
    def test_insert_with_generated_code(self, fake_db):
        fake_db["cursor"]._rows = []  # 无既有编码 → DIR-1
        fake_db["cursor"]._row = _fake_direction_row(id=11, code="DIR-1")
        out = mod.create_direction(
            {
                "user_id": 7,
                "name": "  策略运营-跨境电商  ",
                "job_function": " 策略运营 ",
                "skills": "SQL,Python",
            }
        )
        assert out["code"] == "DIR-1"
        insert_sqls = [
            (s, p)
            for s, p in fake_db["cursor"].executed
            if s.strip().upper().startswith("INSERT")
        ]
        assert len(insert_sqls) == 1
        sql, params = insert_sqls[0]
        for col in (
            "user_id",
            "code",
            "name",
            "job_function",
            "primary_role",
            "industry",
            "product",
            "scenario",
            "skills",
            "status",
        ):
            assert col in sql, f"INSERT 缺列 {col}"
        assert params[0] == 7
        assert params[1] == "DIR-1"
        assert params[2] == "策略运营-跨境电商"  # trim
        assert params[3] == "策略运营"
        assert params[9] == "active"
        assert fake_db["txn_count"] == 1

    def test_code_continues_from_max(self, fake_db):
        fake_db["cursor"]._rows = [{"code": "DIR-1"}, {"code": "DIR-4"}]
        fake_db["cursor"]._row = _fake_direction_row(id=12, code="DIR-5")
        out = mod.create_direction({"user_id": 7, "name": "方向"})
        assert out["code"] == "DIR-5"

    def test_missing_column_translates_to_migration_hint(self, fake_db):
        fake_db["cursor"].insert_errors = [
            MySQLError(msg="Unknown column 'code' in 'field list'", errno=1054)
        ]
        with pytest.raises(ValueError, match="migrations.runner migrate"):
            mod.create_direction({"user_id": 7, "name": "方向"})

    def test_duplicate_name_translates_to_value_error(self, fake_db):
        fake_db["cursor"].insert_errors = [_dup_error("uk_direction_user_name")]
        with pytest.raises(ValueError, match="方向名称已存在"):
            mod.create_direction({"user_id": 7, "name": "方向"})

    def test_code_conflict_retries_then_succeeds(self, fake_db):
        fake_db["cursor"].insert_errors = [_dup_error("uk_direction_code")]
        fake_db["cursor"]._row = _fake_direction_row(id=13, code="DIR-2")
        out = mod.create_direction({"user_id": 7, "name": "方向"})
        assert out["id"] == 13
        assert fake_db["txn_count"] == 2

    def test_code_conflict_exhausted_raises(self, fake_db):
        fake_db["cursor"].insert_errors = [
            _dup_error("uk_direction_code"),
            _dup_error("uk_direction_code"),
            _dup_error("uk_direction_code"),
        ]
        with pytest.raises(ValueError, match="方向编码冲突"):
            mod.create_direction({"user_id": 7, "name": "方向"})
        assert fake_db["txn_count"] == 3


class TestGetDirection:
    def test_by_id_with_user_filter(self, fake_db):
        fake_db["cursor"]._row = _fake_direction_row()
        out = mod.get_direction(1, user_id=7)
        assert out is not None
        assert out["code"] == "DIR-1"
        sql, params = fake_db["cursor"].executed[-1]
        assert "AND user_id=%s" in sql
        assert params == (1, 7)

    def test_missing_returns_none(self, fake_db):
        fake_db["cursor"]._row = None
        assert mod.get_direction(999, user_id=7) is None


class TestListDirections:
    def test_ordered_by_id_with_status_filter(self, fake_db):
        fake_db["cursor"]._rows = [_fake_direction_row()]
        out = mod.list_directions(7, status="active")
        assert len(out) == 1
        sql, params = fake_db["cursor"].executed[-1]
        assert "AND status=%s" in sql
        assert "ORDER BY id ASC" in sql
        assert params == (7, "active")

    def test_no_status_filter(self, fake_db):
        fake_db["cursor"]._rows = []
        mod.list_directions(7)
        sql, _ = fake_db["cursor"].executed[-1]
        assert "status=%s" not in sql

    def test_invalid_status_rejected(self, fake_db):
        with pytest.raises(ValueError, match="status 仅允许"):
            mod.list_directions(7, status="bogus")


class TestUpdateDirection:
    def test_unknown_direction_returns_none(self, fake_db):
        fake_db["cursor"]._row = None
        assert mod.update_direction(999, 7, {"name": "新名"}) is None
        assert not any(
            s.strip().upper().startswith("UPDATE")
            for s, _ in fake_db["cursor"].executed
        )

    def test_noop_fields_skip_update(self, fake_db):
        fake_db["cursor"]._row = _fake_direction_row()
        out = mod.update_direction(1, 7, {})
        assert out is not None
        assert not any(
            s.strip().upper().startswith("UPDATE")
            for s, _ in fake_db["cursor"].executed
        )

    def test_partial_update_whitelisted(self, fake_db):
        fake_db["cursor"]._row = _fake_direction_row()
        out = mod.update_direction(
            1, 7, {"name": "新方向", "industry": "游戏", "code": "HACK"}
        )
        assert out is not None
        updates = [
            (s, p)
            for s, p in fake_db["cursor"].executed
            if s.strip().upper().startswith("UPDATE")
        ]
        assert len(updates) == 1
        sql, params = updates[0]
        assert "code=" not in sql, "code 不可改"
        assert "industry=%s" in sql
        assert params == ("新方向", "游戏", 1, 7)

    def test_empty_name_rejected(self, fake_db):
        fake_db["cursor"]._row = _fake_direction_row()
        with pytest.raises(ValueError, match="方向名称不能为空"):
            mod.update_direction(1, 7, {"name": "  "})

    def test_invalid_status_rejected(self, fake_db):
        fake_db["cursor"]._row = _fake_direction_row()
        with pytest.raises(ValueError, match="status 仅允许"):
            mod.update_direction(1, 7, {"status": "bogus"})

    def test_duplicate_name_translates_to_value_error(self, fake_db, monkeypatch):
        fake_db["cursor"]._row = _fake_direction_row()

        def _raising_execute(sql, params=None):
            raise _dup_error("uk_direction_user_name")

        monkeypatch.setattr(mod, "execute", _raising_execute)
        with pytest.raises(ValueError, match="方向名称已存在"):
            mod.update_direction(1, 7, {"name": "重名"})


class TestDeleteDirection:
    def test_delete_with_owner(self, fake_db):
        assert mod.delete_direction(1, 7) is True
        sql, params = fake_db["cursor"].executed[-1]
        assert "DELETE FROM direction" in sql
        assert "AND user_id=%s" in sql
        assert params == (1, 7)

    def test_rowcount_zero_returns_false(self, fake_db):
        fake_db["rowcount"] = 0
        assert mod.delete_direction(999, 7) is False


class TestCountReferences:
    def _patch_query_one(self, monkeypatch, responses):
        def _fake_query_one(sql, params=None):
            for marker, row in responses:
                if marker in sql:
                    return row
            return None

        monkeypatch.setattr(mod, "query_one", _fake_query_one)

    def test_owned_with_references(self, monkeypatch):
        self._patch_query_one(
            monkeypatch,
            [
                ("SELECT id FROM direction", {"id": 1}),
                ("COUNT(*)", {"c": 5}),
            ],
        )
        assert mod.count_direction_references(1, 7) == {"expressions": 5}

    def test_owned_without_references(self, monkeypatch):
        self._patch_query_one(
            monkeypatch,
            [
                ("SELECT id FROM direction", {"id": 1}),
                ("COUNT(*)", {"c": 0}),
            ],
        )
        assert mod.count_direction_references(1, 7) == {"expressions": 0}

    def test_not_owned_counts_zero(self, monkeypatch):
        self._patch_query_one(monkeypatch, [("SELECT id FROM direction", None)])
        assert mod.count_direction_references(999, 7) == {"expressions": 0}
