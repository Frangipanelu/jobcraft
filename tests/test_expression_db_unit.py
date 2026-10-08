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
        if (
            isinstance(self._row, dict)
            and args
            and sql.strip().startswith("UPDATE expression SET status=")
            and args
            and args[0] in ("candidate", "active", "deprecated")
        ):
            self._row["status"] = args[0]

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

    def _query_scalar(sql, params=None):
        cursor.executed.append((sql, params))
        return holder.get("scalar", 0)

    monkeypatch.setattr(mod, "query_one", _query_one)
    monkeypatch.setattr(mod, "query_all", _query_all)
    monkeypatch.setattr(mod, "query_scalar", _query_scalar)
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


class TestSourceRefNormalize:
    """source_refs 契约规整（DATA_MODEL §3.2，P2C-06）。"""

    def test_legacy_card_shape_maps_to_experience(self):
        refs = [{"type": "card", "card_id": 10}]
        out = mod._normalize_source_refs(refs)
        assert out == [
            {
                "id": "experience:10",
                "source_type": "experience",
                "source_id": "10",
                "locator": None,
            }
        ]

    def test_canonical_shape_passes_through(self):
        refs = [
            {
                "id": "experience:10",
                "source_type": "experience",
                "source_id": "10",
            }
        ]
        assert mod._normalize_source_refs(refs) == [
            {
                "id": "experience:10",
                "source_type": "experience",
                "source_id": "10",
                "locator": None,
            }
        ]

    def test_missing_id_gets_inferred(self):
        refs = [{"source_type": "experience", "source_id": "10", "locator": "v1"}]
        out = mod._normalize_source_refs(refs)
        assert out[0]["id"] == "experience:10"
        assert out[0]["locator"] == "v1"

    def test_unrecognized_entries_dropped(self):
        refs = [{"foo": "bar"}, "junk", None]
        assert mod._normalize_source_refs(refs) == []

    def test_non_list_input_returns_empty(self):
        assert mod._normalize_source_refs(None) == []
        assert mod._normalize_source_refs("oops") == []


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


class TestListUserExpressions:
    """T-M3-4 跨卡方向结构化检索（list_user_expressions）。"""

    def test_base_query_filters_user_and_pages(self, fake_db):
        fake_db["cursor"]._rows = [_fake_expression_row()]
        out = mod.list_user_expressions(7, limit=20, offset=40)
        assert len(out) == 1
        sql, params = fake_db["cursor"].executed[-1]
        assert sql.startswith("SELECT * FROM expression WHERE user_id=%s")
        assert "ORDER BY updated_at DESC, id DESC" in sql
        assert sql.rstrip().endswith("LIMIT %s OFFSET %s")
        assert "direction_id" not in sql
        assert params == (7, 20, 40)

    def test_direction_type_status_filters_in_order(self, fake_db):
        fake_db["cursor"]._rows = []
        mod.list_user_expressions(
            7, direction_id=3, expr_type="direction", status="active", limit=10
        )
        sql, params = fake_db["cursor"].executed[-1]
        assert "WHERE user_id=%s AND direction_id=%s AND type=%s AND status=%s" in sql
        assert params == (7, 3, "direction", "active", 10, 0)

    def test_invalid_type_rejected(self, fake_db):
        with pytest.raises(ValueError, match="type 仅允许"):
            mod.list_user_expressions(7, expr_type="bad")
        assert fake_db["cursor"].executed == []

    def test_invalid_status_rejected(self, fake_db):
        with pytest.raises(ValueError, match="status 仅允许"):
            mod.list_user_expressions(7, status="frozen")
        assert fake_db["cursor"].executed == []

    def test_default_no_status_filter_keeps_deprecated_visible(self, fake_db):
        """不传 status 时 SQL 不含 status= 过滤（deprecated 保留行可见，保留≠删除）。"""
        fake_db["cursor"]._rows = []
        mod.list_user_expressions(7)
        sql, _ = fake_db["cursor"].executed[-1]
        assert "status=" not in sql


class TestCountUserExpressions:
    """T-M3-4 list 同条件计数（分页 total）。"""

    def test_counts_with_filters(self, fake_db):
        fake_db["scalar"] = 42
        assert mod.count_user_expressions(7, direction_id=3) == 42
        sql, params = fake_db["cursor"].executed[-1]
        assert (
            sql
            == "SELECT COUNT(*) FROM expression WHERE user_id=%s AND direction_id=%s"
        )
        assert params == (7, 3)

    def test_counts_without_filters(self, fake_db):
        fake_db["scalar"] = None
        assert mod.count_user_expressions(7) == 0

    def test_invalid_type_rejected(self, fake_db):
        with pytest.raises(ValueError, match="type 仅允许"):
            mod.count_user_expressions(7, expr_type="bad")
        assert fake_db["cursor"].executed == []


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


class TestTransitionStatus:
    def _row(self, **over):
        row = _fake_expression_row(experience_id=10, type="standardized")
        row.update(over)
        return row

    def test_activate_demotes_chain_siblings(self, fake_db):
        fake_db["cursor"]._row = self._row(status="candidate")
        out = mod.transition_status(1, "active", user_id=7)
        assert out["status"] == "active"
        sqls = [s for s, _ in fake_db["cursor"].executed]
        update_sqls = [s for s in sqls if s.strip().startswith("UPDATE")]
        assert len(update_sqls) == 2
        assert "AND id<>%s" in update_sqls[0]

    def test_deprecate_allowed_from_active(self, fake_db):
        fake_db["cursor"]._row = self._row(status="active")
        out = mod.transition_status(1, "deprecated", user_id=7)
        assert out["status"] == "deprecated"
        sqls = [s for s, _ in fake_db["cursor"].executed]
        assert len([s for s in sqls if s.strip().startswith("UPDATE")]) == 1

    def test_illegal_transition_rejected(self, fake_db):
        fake_db["cursor"]._row = self._row(status="active")
        with pytest.raises(ValueError, match="不允许从 active 迁移到"):
            mod.transition_status(1, "active", user_id=7)

    def test_unknown_expression_raises(self, fake_db):
        fake_db["cursor"]._row = None
        with pytest.raises(LookupError, match="不存在或不属于用户"):
            mod.transition_status(999, "deprecated", user_id=7)

    def test_invalid_status_rejected(self, fake_db):
        fake_db["cursor"]._row = self._row(status="candidate")
        with pytest.raises(ValueError, match="status 仅允许"):
            mod.transition_status(1, "hacked", user_id=7)


class TestDelete:
    def test_delete_calls_execute_with_owner(self, fake_db):
        assert mod.delete_expression(1, user_id=7) is True
        assert any(
            "DELETE FROM expression" in s and "AND user_id=%s" in s
            for s, _ in fake_db["cursor"].executed
        )


class TestActiveExpressionContent:
    def test_returns_latest_active_content(self, fake_db):
        """回流读取按 validation_level/usage_count 降序选取（M9-Q2-A），version/id 兜底。"""
        fake_db["cursor"]._row = {"content": "激活表达 v2"}
        out = mod.get_active_expression_content(10, user_id=7)
        assert out == "激活表达 v2"
        sql, params = fake_db["cursor"].executed[-1]
        assert "status='active'" in sql
        assert "validation_level DESC" in sql
        assert "usage_count DESC" in sql
        assert "version DESC" in sql
        assert "id DESC" in sql
        assert params == (10, 7, "standardized")

    def test_returns_none_when_no_active(self, fake_db):
        fake_db["cursor"]._row = None
        assert mod.get_active_expression_content(10, user_id=7) is None

    def test_uses_standardized_type_by_default(self, fake_db):
        fake_db["cursor"]._row = {"content": "x"}
        mod.get_active_expression_content(10, user_id=7)
        sql, params = fake_db["cursor"].executed[-1]
        assert "type=%s" in sql
        assert params[2] == "standardized"


class TestIncrementUsage:
    def test_increments_active_version_usage_count(self, fake_db):
        """P2C-02：只对 active 最新版本自增 usage_count。"""
        mod.increment_active_expression_usage(10, user_id=7)
        sql, params = fake_db["cursor"].executed[-1]
        assert "usage_count = usage_count + 1" in sql
        assert "status='active'" in sql
        assert "ORDER BY version DESC LIMIT 1" in sql
        assert params == (10, 7, "standardized")

    def test_uses_standardized_type_by_default(self, fake_db):
        mod.increment_active_expression_usage(10, user_id=7)
        sql, params = fake_db["cursor"].executed[-1]
        assert "type=%s" in sql
        assert params[2] == "standardized"

    def test_single_table_update_keeps_order_by_limit_legal(self, fake_db):
        """BE-EXPR-01 复核（误报）：ORDER BY/LIMIT 仅多表 UPDATE 禁用。

        语句必须保持单表 UPDATE（无 JOIN/逗号多表），ORDER BY version DESC
        + LIMIT 1 才合法且只命中 active 链最新版本；MySQL 8.4.9 实测通过。
        """
        mod.increment_active_expression_usage(10, user_id=7)
        sql, _ = fake_db["cursor"].executed[-1]
        assert sql.lstrip().upper().startswith("UPDATE EXPRESSION SET")
        upper = sql.upper()
        assert "JOIN" not in upper
        assert upper.count("UPDATE") == 1
        assert "ORDER BY version DESC LIMIT 1" in sql
