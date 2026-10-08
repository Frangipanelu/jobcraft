"""jd_classification 表 upsert/查询/批量 grouped 单元测试（T-M3-2 / Q7=c / T-M4-4）。

不依赖真实 DB——monkeypatch app.tools.db_jd_classification 的 db_conn
封装函数，用假实现捕获 SQL/参数并返回可控行。
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest
from mysql.connector import Error as MySQLError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import db_jd_classification as mod


def _fake_classification_row(**over):
    """构造一条 jd_classification 数据库行（模拟 query_one 返回值）。"""
    row = {
        "id": 1,
        "user_id": 7,
        "job_analysis_id": 55,
        "direction_id": 3,
        "job_function": "用户增长",
        "primary_role": "增长运营",
        "industry": "电商",
        "product": "商业化,增长",
        "scenario": "拉新,留存",
        "skills": "SQL,Python",
        "confidence": "medium",
        "source": "manual",
        "status": "confirmed",
        "created_at": datetime(2026, 10, 2, 9, 0, 0),
        "updated_at": datetime(2026, 10, 2, 9, 30, 0),
    }
    row.update(over)
    return row


class _FakeCursor:
    """记录 execute/query 的假实现；错误列表在对应调用时依次弹出。"""

    def __init__(self):
        self._row = None
        self.executed: list = []
        self.execute_errors: list = []
        self.select_errors: list = []
        self.rowcount = 1


@pytest.fixture
def fake_db(monkeypatch):
    """把 db_conn 封装函数替换为可控假实现，返回持有假状态的容器。"""
    holder = {"cursor": _FakeCursor(), "rowcount": 1}
    cur = holder["cursor"]

    def _execute(sql, params=None):
        cur.executed.append((sql, params))
        if cur.execute_errors:
            raise cur.execute_errors.pop(0)
        return holder["rowcount"]

    def _query_one(sql, params=None):
        cur.executed.append((sql, params))
        if cur.select_errors:
            raise cur.select_errors.pop(0)
        return cur._row

    def _query_all(sql, params=None):
        cur.executed.append((sql, params))
        if "FROM direction" in sql:
            if holder.get("dir_error"):
                raise holder["dir_error"]
            return holder.get("dir_rows", [])
        if holder.get("cls_error"):
            raise holder["cls_error"]
        return holder.get("cls_rows", [])

    monkeypatch.setattr(mod, "execute", _execute)
    monkeypatch.setattr(mod, "query_one", _query_one)
    monkeypatch.setattr(mod, "query_all", _query_all)
    holder.setdefault("cls_rows", [])
    holder.setdefault("dir_rows", [])
    return holder


def _table_missing() -> MySQLError:
    return MySQLError(
        msg="Table 'jobcraft.jd_classification' doesn't exist", errno=1146
    )


class TestRowMapper:
    def test_maps_fields_and_isoformat(self):
        out = mod._row_to_classification(_fake_classification_row())
        assert out["id"] == 1
        assert out["job_analysis_id"] == 55
        assert out["direction_id"] == 3
        assert out["job_function"] == "用户增长"
        assert out["product"] == "商业化,增长"
        assert out["confidence"] == "medium"
        assert out["source"] == "manual"
        assert out["status"] == "confirmed"
        assert out["created_at"] == "2026-10-02T09:00:00"
        assert out["updated_at"] == "2026-10-02T09:30:00"

    def test_enum_defaults_when_missing(self):
        """缺省行（未写枚举列）回退列默认：source=manual / status=proposed。"""
        row = {
            "id": 2,
            "user_id": 7,
            "job_analysis_id": 56,
            "job_function": "内容运营",
        }
        out = mod._row_to_classification(row)
        assert out["direction_id"] is None
        assert out["confidence"] == ""
        assert out["source"] == "manual"
        assert out["status"] == "proposed"
        assert out["created_at"] is None


class TestCleanFields:
    def test_whitelist_and_strip(self):
        clean = mod._clean_fields(
            {"job_function": "  用户增长 ", "hacker": "x", "status": "confirmed"}
        )
        assert clean == {"job_function": "用户增长", "status": "confirmed"}

    def test_all_dimensions_empty_rejected(self):
        with pytest.raises(ValueError, match="至少填写一维"):
            mod._clean_fields({"industry": "  "})

    def test_invalid_confidence_rejected(self):
        with pytest.raises(ValueError, match="confidence 仅允许"):
            mod._clean_fields({"job_function": "运营", "confidence": "mid"})

    def test_invalid_source_rejected(self):
        with pytest.raises(ValueError, match="source 仅允许"):
            mod._clean_fields({"job_function": "运营", "source": "llm"})

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status 仅允许"):
            mod._clean_fields({"job_function": "运营", "status": "archived"})

    def test_non_int_direction_id_rejected(self):
        with pytest.raises(ValueError, match="direction_id 必须为整数"):
            mod._clean_fields({"job_function": "运营", "direction_id": "abc"})


class TestUpsert:
    def test_upsert_full_replace(self, fake_db):
        fake_db["cursor"]._row = _fake_classification_row()
        out = mod.upsert_jd_classification(
            7,
            55,
            {
                "direction_id": 3,
                "job_function": " 用户增长 ",
                "industry": "电商",
                "confidence": "medium",
                "source": "manual",
                "status": "confirmed",
            },
        )
        assert out["job_analysis_id"] == 55
        inserts = [
            (s, p)
            for s, p in fake_db["cursor"].executed
            if s.strip().upper().startswith("INSERT")
        ]
        assert len(inserts) == 1
        sql, params = inserts[0]
        assert "ON DUPLICATE KEY UPDATE" in sql
        assert "status=VALUES(status)" in sql
        for col in (
            "user_id",
            "job_analysis_id",
            "direction_id",
            "job_function",
            "primary_role",
            "industry",
            "product",
            "scenario",
            "skills",
            "confidence",
            "source",
            "status",
        ):
            assert col in sql, f"INSERT 缺列 {col}"
        assert params[0] == 7
        assert params[1] == 55
        assert params[2] == 3
        assert params[3] == "用户增长"  # trim
        assert params[10] == "manual"
        assert params[11] == "confirmed"
        # 回读按 job_analysis_id + user_id
        read_sql, read_params = fake_db["cursor"].executed[-1]
        assert "WHERE job_analysis_id=%s" in read_sql
        assert "AND user_id=%s" in read_sql
        assert read_params == (55, 7)

    def test_missing_table_translates_to_migration_hint(self, fake_db):
        fake_db["cursor"].execute_errors = [_table_missing()]
        with pytest.raises(ValueError, match="migrations.runner migrate"):
            mod.upsert_jd_classification(7, 55, {"job_function": "运营"})

    def test_readback_missing_raises(self, fake_db):
        fake_db["cursor"]._row = None
        with pytest.raises(ValueError, match="回读失败"):
            mod.upsert_jd_classification(7, 55, {"job_function": "运营"})

    def test_validation_runs_before_execute(self, fake_db):
        with pytest.raises(ValueError, match="至少填写一维"):
            mod.upsert_jd_classification(7, 55, {})
        assert not fake_db["cursor"].executed


class TestGet:
    def test_by_analysis_with_user_filter(self, fake_db):
        fake_db["cursor"]._row = _fake_classification_row()
        out = mod.get_jd_classification(55, user_id=7)
        assert out is not None
        assert out["status"] == "confirmed"
        sql, params = fake_db["cursor"].executed[-1]
        assert "AND user_id=%s" in sql
        assert params == (55, 7)

    def test_missing_returns_none(self, fake_db):
        fake_db["cursor"]._row = None
        assert mod.get_jd_classification(999, user_id=7) is None

    def test_missing_table_translates_to_migration_hint(self, fake_db):
        fake_db["cursor"].select_errors = [_table_missing()]
        with pytest.raises(ValueError, match="migrations.runner migrate"):
            mod.get_jd_classification(55, user_id=7)


class TestListGrouped:
    """T-M4-4：按 job_analysis_ids 批量读分类 + 方向名解析（历史表格/报告详情）。"""

    @staticmethod
    def _selects(fake_db, table: str) -> list:
        return [
            (sql, params)
            for sql, params in fake_db["cursor"].executed
            if f"FROM {table}" in sql
        ]

    def test_empty_ids_skips_query(self, fake_db):
        assert mod.list_jd_classifications_grouped([]) == {}
        assert fake_db["cursor"].executed == []

    def test_hits_map_rows_with_direction_labels(self, fake_db):
        fake_db["cls_rows"] = [
            _fake_classification_row(id=1, job_analysis_id=55, direction_id=3),
            _fake_classification_row(id=2, job_analysis_id=56, direction_id=None),
        ]
        fake_db["dir_rows"] = [{"id": 3, "name": "电商零售", "code": "DIR-1"}]

        out = mod.list_jd_classifications_grouped([55, 56], user_id=7)

        assert sorted(out) == [55, 56]
        assert out[55]["direction_name"] == "电商零售"
        assert out[55]["direction_code"] == "DIR-1"
        assert out[55]["industry"] == "电商"
        # 无 direction_id 的行同样带键（None），前端读取不判空
        assert out[56]["direction_name"] is None
        assert out[56]["direction_code"] is None
        # user 隔离：分类查询带 user_id 绑定
        cls_sql, cls_params = self._selects(fake_db, "jd_classification")[0]
        assert "AND user_id=%s" in cls_sql
        assert cls_params == (55, 56, 7)

    def test_missed_ids_absent_from_mapping(self, fake_db):
        fake_db["cls_rows"] = [_fake_classification_row(job_analysis_id=55)]
        out = mod.list_jd_classifications_grouped([55, 999])
        assert list(out) == [55]

    def test_direction_id_zero_skips_direction_query(self, fake_db):
        fake_db["cls_rows"] = [_fake_classification_row(direction_id=0)]
        out = mod.list_jd_classifications_grouped([55])
        assert out[55]["direction_name"] is None
        assert out[55]["direction_code"] is None
        assert self._selects(fake_db, "direction") == []

    def test_direction_row_missing_keeps_none(self, fake_db):
        fake_db["cls_rows"] = [_fake_classification_row(direction_id=3)]
        fake_db["dir_rows"] = []
        out = mod.list_jd_classifications_grouped([55])
        assert out[55]["direction_id"] == 3
        assert out[55]["direction_name"] is None

    def test_missing_classification_table_degrades_to_empty(self, fake_db):
        fake_db["cls_error"] = _table_missing()
        assert mod.list_jd_classifications_grouped([55]) == {}

    def test_missing_direction_table_keeps_classifications(self, fake_db):
        fake_db["cls_rows"] = [_fake_classification_row(direction_id=3)]
        fake_db["dir_error"] = _table_missing()
        out = mod.list_jd_classifications_grouped([55])
        assert out[55]["industry"] == "电商"
        assert out[55]["direction_name"] is None

    def test_other_error_reraises(self, fake_db):
        err = MySQLError(msg="Lost connection", errno=2003)
        fake_db["cls_error"] = err
        with pytest.raises(MySQLError):
            mod.list_jd_classifications_grouped([55])
