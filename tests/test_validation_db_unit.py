"""T-M9-1 validations 模块单元测试（mock db_conn，不连真库）。

覆盖三层（模式照 test_expression_db_unit.py）：
1. DAO 写入 insert_user_confirmation_in_conn：target_type 映射、幂等
   INSERT ... FROM DUAL WHERE NOT EXISTS、参数序与枚举值、evidence_refs
   JSON 序列化（ensure_ascii=False）；
2. DAO 投影 get_validation_summary：白名单拒绝、L0/L1 推导、strength 分组
   计数、explanation 文案、expression.usage_count 仅 expression 目标查询；
3. API GET /api/jobcraft/validation-summary：缺参 422 / 非法 400 /
   正常 200 且 8 字段齐全。
"""

import json
import os

import pytest

from app.tools import db_validation as mod

SOURCE_REFS = [
    {
        "id": "fc:1",
        "source_type": "user_confirmation",
        "source_id": "7",
        "locator": "复盘确认",
    }
]


class _FakeCursor:
    """只记录 execute 的假游标（insert 路径只写不读）。"""

    def __init__(self, rowcount: int = 1):
        self.executed = []
        self.rowcount = rowcount

    def execute(self, sql, params=None):
        self.executed.append((" ".join(sql.split()), params))


class TestMapValidationTargetType:
    """feedback → validation targetType 映射（Q1-A 设计决定 2）。"""

    @pytest.mark.parametrize(
        "name",
        ["standardized_expression", "direction_expression", "job_expression"],
    )
    def test_expression_variants_fold_to_expression(self, name):
        assert mod.map_validation_target_type(name) == "expression"

    @pytest.mark.parametrize(
        "name",
        ["experience", "self_introduction", "answer_drill", "direction_knowledge"],
    )
    def test_same_name_passthrough(self, name):
        assert mod.map_validation_target_type(name) == name

    @pytest.mark.parametrize(
        "name", ["experience_story", "expression_strategy", "unknown_kind", ""]
    )
    def test_not_applicable_returns_none(self, name):
        """not applicable → None，调用方跳过不写（§31 when applicable）。"""
        assert mod.map_validation_target_type(name) is None


class TestInsertUserConfirmation:
    """insert_user_confirmation_in_conn：幂等 SQL + 参数契约。"""

    def _insert(self, cursor, **over):
        kwargs = {
            "user_id": 1,
            "feedback_target_type": "experience",
            "target_id": "42",
            "source_id": "7",
            "evidence_refs": SOURCE_REFS,
        }
        kwargs.update(over)
        return mod.insert_user_confirmation_in_conn(cursor, **kwargs)

    def test_insert_is_idempotent_and_params_in_order(self):
        cursor = _FakeCursor()
        assert self._insert(cursor) is True
        sql, params = cursor.executed[0]
        assert "INSERT INTO validations" in sql
        assert "WHERE NOT EXISTS" in sql
        assert "FROM DUAL" in sql
        # 写入列 9 个 + uk_validation 同序 NOT EXISTS 段 5 个
        assert params[:9] == (
            1,
            "experience",
            "42",
            "user_confirmation",
            "7",
            "user_confirmed",
            "moderate",
            json.dumps(SOURCE_REFS, ensure_ascii=False),
            None,
        )
        assert params[9:] == (
            "user_confirmation",
            "7",
            "experience",
            "42",
            "user_confirmed",
        )

    def test_enum_values_are_fixed_for_user_confirmation(self):
        cursor = _FakeCursor()
        self._insert(cursor)
        _, params = cursor.executed[0]
        assert params[3] == "user_confirmation"  # source_type
        assert params[5] == "user_confirmed"  # signal_type
        assert params[6] == "moderate"  # strength = USER_CONFIRMATION_STRENGTH

    def test_standardized_expression_maps_to_expression(self):
        cursor = _FakeCursor()
        self._insert(cursor, feedback_target_type="standardized_expression")
        _, params = cursor.executed[0]
        assert params[1] == "expression"
        assert params[11] == "expression"  # NOT EXISTS 段同步映射

    def test_not_applicable_type_skips_execute(self):
        cursor = _FakeCursor()
        assert self._insert(cursor, feedback_target_type="experience_story") is False
        assert cursor.executed == []

    def test_rowcount_zero_reports_not_inserted(self):
        """同一证据重复追加时（NOT EXISTS 命中）返回 False。"""
        cursor = _FakeCursor(rowcount=0)
        assert self._insert(cursor) is False

    def test_evidence_refs_serialized_without_ascii_escape(self):
        cursor = _FakeCursor()
        self._insert(cursor)
        _, params = cursor.executed[0]
        assert "复盘确认" in params[7]
        assert params[7] == json.dumps(SOURCE_REFS, ensure_ascii=False)


@pytest.fixture
def fake_db(monkeypatch):
    """把 db_validation 的 db_conn 封装替换为可控假实现（不连真库）。"""
    state = {"rows": [], "expr_usage": None, "sqls": []}

    def _query_all(sql, params=None):
        state["sqls"].append((" ".join(sql.split()), params))
        return list(state["rows"])

    def _query_one(sql, params=None):
        state["sqls"].append((" ".join(sql.split()), params))
        if "FROM expression" in sql and state["expr_usage"] is not None:
            return {"usage_count": state["expr_usage"]}
        return None

    monkeypatch.setattr(mod, "query_all", _query_all)
    monkeypatch.setattr(mod, "query_one", _query_one)
    # schema 已就绪 → ensure 短路，不建连接
    monkeypatch.setattr(mod, "is_schema_ready", lambda: True)
    return state


class TestGetValidationSummary:
    """读时派生 Level 投影（API_SPEC §17.4 / DATA_MODEL §24.2，Q1-A 本期 L0/L1）。"""

    def test_invalid_target_type_raises_before_any_query(self, fake_db):
        with pytest.raises(ValueError, match="target_type 仅允许"):
            mod.get_validation_summary(1, "experience_story", "42")
        assert fake_db["sqls"] == []

    def test_empty_table_returns_level_zero(self, fake_db):
        out = mod.get_validation_summary(1, "experience", "42")
        assert out == {
            "target_type": "experience",
            "target_id": "42",
            "level": 0,
            "usage_count": 0,
            "strong_signals": 0,
            "moderate_signals": 0,
            "weak_signals": 0,
            "explanation": "尚无验证信号（L0 未验证）",
        }

    def test_usage_count_ge_one_reaches_level_one(self, fake_db):
        fake_db["expr_usage"] = 3
        out = mod.get_validation_summary(1, "expression", "42")
        assert out["level"] == 1
        assert out["usage_count"] == 3
        assert out["explanation"] == "已使用 3 次（L1 已验证）"

    def test_user_confirmed_alone_reaches_level_one(self, fake_db):
        fake_db["rows"] = [{"strength": "moderate", "signal_type": "user_confirmed"}]
        out = mod.get_validation_summary(1, "experience", "42")
        assert out["level"] == 1
        assert out["usage_count"] == 0
        assert out["explanation"] == "用户确认 1 次（L1 已验证）"

    def test_usage_and_confirmation_join_with_semicolon(self, fake_db):
        fake_db["expr_usage"] = 2
        fake_db["rows"] = [
            {"strength": "moderate", "signal_type": "user_confirmed"},
            {"strength": "moderate", "signal_type": "user_confirmed"},
        ]
        out = mod.get_validation_summary(1, "expression", "42")
        assert out["level"] == 1
        assert out["explanation"] == "已使用 2 次；用户确认 2 次（L1 已验证）"

    def test_strength_group_counts(self, fake_db):
        fake_db["rows"] = [
            {"strength": "strong", "signal_type": "successful_use"},
            {"strength": "moderate", "signal_type": "user_confirmed"},
            {"strength": "moderate", "signal_type": "repeated_acceptance"},
            {"strength": "weak", "signal_type": "follow_up"},
        ]
        out = mod.get_validation_summary(1, "experience", "42")
        assert out["strong_signals"] == 1
        assert out["moderate_signals"] == 2
        assert out["weak_signals"] == 1
        assert out["level"] == 1  # 存在 user_confirmed 行

    def test_expression_target_reads_usage_count(self, fake_db):
        fake_db["expr_usage"] = 1
        mod.get_validation_summary(1, "expression", "42")
        expr_sqls = [(s, p) for s, p in fake_db["sqls"] if "FROM expression" in s]
        assert expr_sqls, "expression 目标应查询 expression.usage_count"
        sql, params = expr_sqls[0]
        assert "user_id=%s" in sql, "usage_count 查询必须带 user_id 归属过滤"
        assert params == ("42", 1)  # (id=%s, user_id=%s)

    def test_expression_row_missing_returns_level_zero(self, fake_db):
        """expression 行缺失（query_one 返回 None）→ 覆盖 `if expr_row:` False 分支。"""
        assert fake_db["expr_usage"] is None  # 默认桩：expression 查询返回 None
        out = mod.get_validation_summary(1, "expression", "42")
        assert out["level"] == 0
        assert out["usage_count"] == 0
        assert out["explanation"] == "尚无验证信号（L0 未验证）"

    def test_non_expression_target_never_touches_expression(self, fake_db):
        mod.get_validation_summary(1, "experience", "42")
        assert not any("FROM expression" in s for s, _ in fake_db["sqls"])
        val_sqls = [x for x in fake_db["sqls"] if "FROM validations" in x[0]]
        assert val_sqls, "应按 target 查询 validations"
        assert val_sqls[0][1] == (1, "experience", "42")


def test_v0026_ddl_matches_runtime_validations_ddl():
    """DDL parity（DB-01）：V0026 迁移建表块与运行时 _VALIDATIONS_DDL 一致，防漂移。"""
    import migrations.runner as runner

    path = os.path.join(runner.MIGRATIONS_DIR, "V0026__validations.sql")
    assert os.path.exists(path), "缺 V0026__validations.sql"
    with open(path, encoding="utf-8") as fh:
        sql = fh.read()
    marker = "CREATE TABLE IF NOT EXISTS validations"
    start = sql.index(marker)
    end = sql.index("utf8mb4", start) + len("utf8mb4")
    migration_ddl = " ".join(sql[start:end].split())
    runtime_ddl = " ".join(mod._VALIDATIONS_DDL.split())
    assert migration_ddl == runtime_ddl, "V0026 与 db_validation._VALIDATIONS_DDL 漂移"


class TestValidationSummaryApi:
    """GET /api/jobcraft/validation-summary（PRD:292 / API_SPEC §17.4）。"""

    URL = "/api/jobcraft/validation-summary"

    @pytest.fixture
    def client(self):
        from tests.test_api_routes_unit import client

        return client

    def test_missing_params_returns_422(self, client):
        assert client.get(self.URL).status_code == 422

    def test_missing_target_id_returns_422(self, client):
        resp = client.get(f"{self.URL}?target_type=expression")
        assert resp.status_code == 422

    def test_invalid_target_type_returns_400(self, client):
        resp = client.get(f"{self.URL}?target_type=experience_story&target_id=42")
        assert resp.status_code == 400

    def test_blank_target_id_returns_400(self, client):
        resp = client.get(f"{self.URL}?target_type=expression&target_id=%20%20")
        assert resp.status_code == 400

    def test_summary_failure_returns_500(self, client, monkeypatch):
        """底层查询抛非预期异常 → 端点兜底 500（不裸抛进 TestClient）。"""

        def _boom(user_id, target_type, target_id):
            raise RuntimeError("db down")

        monkeypatch.setattr("app.api.validation.db_tools.get_validation_summary", _boom)
        resp = client.get(f"{self.URL}?target_type=expression&target_id=42")
        assert resp.status_code == 500

    def test_valid_target_returns_200_with_eight_fields(self, client, monkeypatch):
        captured = {}

        def fake_get_summary(user_id, target_type, target_id):
            captured.update(
                user_id=user_id, target_type=target_type, target_id=target_id
            )
            return {
                "target_type": target_type,
                "target_id": target_id,
                "level": 1,
                "usage_count": 2,
                "strong_signals": 0,
                "moderate_signals": 1,
                "weak_signals": 0,
                "explanation": "已使用 2 次（L1 已验证）",
            }

        monkeypatch.setattr(
            "app.api.validation.db_tools.get_validation_summary", fake_get_summary
        )
        resp = client.get(f"{self.URL}?target_type=expression&target_id=42")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data) == {
            "target_type",
            "target_id",
            "level",
            "usage_count",
            "strong_signals",
            "moderate_signals",
            "weak_signals",
            "explanation",
        }
        assert data["level"] == 1
        assert captured == {
            "user_id": 1,
            "target_type": "expression",
            "target_id": "42",
        }
