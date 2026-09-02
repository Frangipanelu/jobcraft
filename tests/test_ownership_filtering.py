"""
数据所有权过滤（R2）单元测试

覆盖两层面：
1. DAO 层：by-id 方法在传入 user_id 时，SQL 追加 `AND user_id=%s`，越权返回空。
2. API 层：控制器把 current_user 透传给 by-id DAO，避免因未传导致越权读取。

不依赖真实 DB——DAO 测试 monkeypatch `mysql.connector.connect`，
API 测试 monkeypatch db_tools 捕获 user_id 实参。
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ============================================================
# DAO 层：SQL 应包含 user_id 过滤
# ============================================================


class _FakeCursor:
    def __init__(self, rowcount=0, row=None, rows=None):
        self._rowcount = rowcount
        self._row = row
        self._rows = rows
        self.last_sql = None
        self.last_args = None
        self.executed = []

    @property
    def rowcount(self):
        return self._rowcount

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, args=None):
        self.last_sql = sql
        self.last_args = args
        self.executed.append((sql, args))

    def fetchone(self):
        return self._row

    def fetchall(self):
        # SHOW COLUMNS 等列信息查询：返回带列名的元组，避免 None 迭代报错
        if self._rows is not None:
            return self._rows
        return [("id", "int")]


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, dictionary=False):
        return self._cursor


def _capture(cursor_holder):
    def fake_connect(**kwargs):
        return _FakeConn(cursor_holder[0])

    return fake_connect


_ENSURE_HELPERS = {}


def _patch_ensure_helper(monkeypatch, module_path, holder):
    """把该模块用到的 *_ensure* 帮助函数置为 no-op，避免触发真实 DB 查询/ALTER。"""
    import importlib

    mod = importlib.import_module(module_path)
    for name in list(vars(mod).keys()):
        if name.startswith("_ensure"):
            monkeypatch.setattr(f"{module_path}.{name}", lambda *a, **k: None)
    # db_interview 的 delete 还会调用 _ensure_interview_qa_pairs_table
    monkeypatch.setattr(
        "app.tools.db_interview._ensure_interview_qa_pairs_table", lambda *a, **k: None
    )


@pytest.mark.parametrize(
    "module_path,func_name,args,kwargs,expect_sql",
    [
        (
            "app.tools.db_experience",
            "get_card",
            (100,),
            {"user_id": 7},
            "AND user_id=%s",
        ),
        (
            "app.tools.db_experience",
            "delete_card",
            (100,),
            {"user_id": 7},
            "AND user_id=%s",
        ),
        (
            "app.tools.db_job",
            "get_job_analysis",
            (100,),
            {"user_id": 7},
            "AND user_id=%s",
        ),
        (
            "app.tools.db_job",
            "delete_job_analysis",
            (100,),
            {"user_id": 7},
            "AND user_id=%s",
        ),
        (
            "app.tools.db_submission",
            "get_submission",
            (100,),
            {"user_id": 7},
            "AND user_id=%s",
        ),
        (
            "app.tools.db_submission",
            "delete_submission",
            (100,),
            {"user_id": 7},
            "AND user_id=%s",
        ),
        (
            "app.tools.db_interview",
            "get_interview_record",
            (100,),
            {"user_id": 7},
            "AND user_id=%s",
        ),
    ],
)
def test_by_id_dao_appends_user_id_filter(
    monkeypatch, module_path, func_name, args, kwargs, expect_sql
):
    """get_*/delete_* 在传入 user_id 时，SQL 必须包含 user_id 过滤条件。"""
    from app.tools import db_tools

    cursor = _FakeCursor(rowcount=1, row=None)
    holder = [cursor]
    monkeypatch.setattr("mysql.connector.connect", _capture(holder))

    func = getattr(db_tools, func_name)
    with patch(f"{module_path}.connect", _capture(holder)):
        _patch_ensure_helper(monkeypatch, module_path, holder)
        func(*args, **kwargs)

    assert cursor.executed, "应至少执行一条 SQL"
    # 校验任意一句 SQL 携带 user_id 过滤（delete_* 会先跑关联表 DELETE）
    matched = [
        (sql, a) for sql, a in cursor.executed if expect_sql in sql and 7 in (a or ())
    ]
    assert matched, f"未找到带 user_id 过滤的 SQL: {[s for s, _ in cursor.executed]}"


def test_get_card_without_user_id_no_filter(monkeypatch):
    """未传 user_id 时保持原语义，不强制过滤（兼容非敏感读取）。"""
    from app.tools.db_experience import get_card

    cursor = _FakeCursor(row=None)
    holder = [cursor]

    def fake_connect(**kwargs):
        return _FakeConn(cursor)

    _patch_ensure_helper(monkeypatch, "app.tools.db_experience", holder)
    with patch("app.tools.db_experience.connect", fake_connect):
        get_card(100)

    assert cursor.last_sql is not None
    assert "AND user_id=%s" not in cursor.last_sql


def test_update_card_appends_user_id_filter(monkeypatch):
    """update_card 支持按 user_id 过滤，避免越权更新。"""
    from app.tools.db_experience import update_card

    cursor = _FakeCursor(rowcount=1)
    holder = [cursor]

    def fake_connect(**kwargs):
        return _FakeConn(cursor)

    _patch_ensure_helper(monkeypatch, "app.tools.db_experience", holder)
    with patch("app.tools.db_experience.connect", fake_connect):
        update_card(100, {"is_active": False}, user_id=7)

    assert "AND user_id=%s" in cursor.last_sql
    assert 7 in cursor.last_args


def test_update_submission_appends_user_id_filter(monkeypatch):
    """update_submission 支持按 user_id 过滤。"""
    from app.tools.db_submission import update_submission

    cursor = _FakeCursor(rowcount=1)
    holder = [cursor]

    def fake_connect(**kwargs):
        return _FakeConn(cursor)

    _patch_ensure_helper(monkeypatch, "app.tools.db_submission", holder)
    with patch("app.tools.db_submission.connect", fake_connect):
        update_submission(100, {"status": "x"}, user_id=7)

    assert "AND user_id=%s" in cursor.last_sql
    assert 7 in cursor.last_args


def test_get_interview_prep_by_job_appends_user_id_filter(monkeypatch):
    """get_interview_prep_by_job 支持按 user_id 过滤。"""
    from app.tools.db_interview import get_interview_prep_by_job

    cursor = _FakeCursor(row=None)
    holder = [cursor]

    def fake_connect(**kwargs):
        return _FakeConn(cursor)

    _patch_ensure_helper(monkeypatch, "app.tools.db_interview", holder)
    with patch("app.tools.db_interview.connect", fake_connect):
        get_interview_prep_by_job(100, 7)

    assert "AND user_id=%s" in cursor.last_sql
    assert 7 in cursor.last_args


def test_delete_interview_record_appends_user_id_filter(monkeypatch):
    """delete_interview_record 支持按 user_id 过滤。"""
    from app.tools.db_interview import delete_interview_record

    cursor = _FakeCursor(rowcount=1)
    holder = [cursor]

    def fake_connect(**kwargs):
        return _FakeConn(cursor)

    _patch_ensure_helper(monkeypatch, "app.tools.db_interview", holder)
    with patch("app.tools.db_interview.connect", fake_connect):
        delete_interview_record(100, 7)

    matched = [
        (sql, a)
        for sql, a in cursor.executed
        if "AND user_id=%s" in sql and 7 in (a or ())
    ]
    assert matched, f"未找到带 user_id 过滤的 DELETE: {[s for s, _ in cursor.executed]}"


# ============================================================
# API 层：控制器把 current_user 透传给 by-id DAO
# ============================================================


def _call_endpoint_direct(module_import, func_name, **kwargs):
    """直接调用控制器函数，验证其把 current_user 传入 db_tools 调用。"""
    import importlib

    mod = importlib.import_module(module_import)
    fn = getattr(mod, func_name)
    # 记录 db_tools 调用实参
    seen = {}

    class _Recorder:
        def get_card(self, *a, **k):
            seen["get_card"] = (a, k)
            return {"id": a[0], "user_id": 1, "is_active": True}

        def get_job_analysis(self, *a, **k):
            seen["get_job_analysis"] = (a, k)
            return {"id": a[0], "user_id": 1}

        def get_submission(self, *a, **k):
            seen["get_submission"] = (a, k)
            return {"id": a[0], "user_id": 1}

        def get_card_versions_by_card_id(self, *a, **k):
            return []

    orig = mod.db_tools
    mod.db_tools = _Recorder()
    try:
        fn(**kwargs)
    finally:
        mod.db_tools = orig
    return seen


def test_experience_versions_passes_current_user():
    """experience get_card 控制器必须把 current_user 传入 DAO（越权时 get_card 返回 None → 404）。"""
    seen = _call_endpoint_direct(
        "app.api.experience", "jobcraft_experience_versions", card_id=5, current_user=99
    )
    args, _ = seen["get_card"]
    assert args == (5, 99)


def test_job_analysis_get_passes_current_user():
    """job_analysis get_job_analysis 控制器必须把 current_user 传入 DAO。"""
    seen = _call_endpoint_direct(
        "app.api.job_analysis", "jobcraft_job_get", job_id=5, current_user=99
    )
    args, _ = seen["get_job_analysis"]
    assert args == (5, 99)


def test_submission_get_passes_current_user():
    """submission get_submission 控制器必须把 current_user 传入 DAO。"""
    seen = _call_endpoint_direct(
        "app.api.submission",
        "jobcraft_submission_get",
        submission_id=5,
        current_user=99,
    )
    args, _ = seen["get_submission"]
    assert args == (5, 99)
