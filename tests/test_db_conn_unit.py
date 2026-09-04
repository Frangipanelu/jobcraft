"""
TASK-REF-DB-001 统一 DB 封装单元测试

不依赖真实 MySQL，通过替换 app.tools.db_conn.connect 为内存假连接/游标，
验证 query_one / query_all / query_scalar / execute / execute_lastrowid 的
返回形态与对 cursor 方法的调用。
"""

from unittest.mock import patch


class _FakeCursor:
    def __init__(self, *, row=None, rows=None, rowcount=0, lastrowid=0):
        self._row = row
        self._rows = rows
        self._rowcount = rowcount
        self._lastrowid = lastrowid
        self.executed = []
        self.dictionary = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def rowcount(self):
        return self._rowcount

    @property
    def lastrowid(self):
        return self._lastrowid

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows if self._rows is not None else []


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, dictionary=False):
        self._cursor.dictionary = dictionary
        return self._cursor


def _connect_patcher(conn):
    return patch("app.tools.db_conn.connect", return_value=conn, autospec=True)


def test_connect_defaults_to_jc_config(monkeypatch):
    """不传参时 connect() 使用 jobcraft 库配置（经 get_db_config）。"""
    import app.tools.db_conn as db_conn

    captured = {}

    def fake_get_db_config(overrides=None):
        captured["overrides"] = overrides
        return {"host": "h", "database": "d"}

    monkeypatch.setattr(db_conn, "_jc_config", lambda: {"database": "jobcraft"})
    with patch(
        "app.tools.db_conn._raw_connect", return_value="conn", autospec=True
    ) as raw:
        result = db_conn.connect()
    assert result == "conn"
    raw.assert_called_once()
    assert raw.call_args.kwargs == {"database": "jobcraft"}


def test_query_one_returns_dict_row():
    from app.tools import db_conn

    cur = _FakeCursor(row={"id": 1, "name": "x"})
    conn = _FakeConn(cur)
    with _connect_patcher(conn):
        row = db_conn.query_one("SELECT * FROM t WHERE id=%s", (1,))
    assert row == {"id": 1, "name": "x"}
    assert cur.dictionary is True


def test_query_one_none_when_no_row():
    from app.tools import db_conn

    cur = _FakeCursor(row=None)
    conn = _FakeConn(cur)
    with _connect_patcher(conn):
        row = db_conn.query_one("SELECT * FROM t WHERE id=%s", (1,))
    assert row is None


def test_query_all_returns_list():
    from app.tools import db_conn

    rows = [{"id": 1}, {"id": 2}]
    cur = _FakeCursor(rows=rows)
    conn = _FakeConn(cur)
    with _connect_patcher(conn):
        result = db_conn.query_all("SELECT * FROM t")
    assert result == rows
    assert cur.dictionary is True


def test_query_scalar_returns_first_col():
    from app.tools import db_conn

    cur = _FakeCursor(row=(42,))
    conn = _FakeConn(cur)
    with _connect_patcher(conn):
        value = db_conn.query_scalar("SELECT COUNT(*) FROM t")
    assert value == 42
    assert cur.dictionary is False


def test_query_scalar_none_when_no_row():
    from app.tools import db_conn

    cur = _FakeCursor(row=None)
    conn = _FakeConn(cur)
    with _connect_patcher(conn):
        value = db_conn.query_scalar("SELECT MAX(x) FROM t")
    assert value is None


def test_execute_returns_rowcount():
    from app.tools import db_conn

    cur = _FakeCursor(rowcount=3)
    conn = _FakeConn(cur)
    with _connect_patcher(conn):
        count = db_conn.execute("DELETE FROM t WHERE id=%s", (1,))
    assert count == 3
    assert cur.dictionary is False


def test_execute_lastrowid_returns_id():
    from app.tools import db_conn

    cur = _FakeCursor(lastrowid=7)
    conn = _FakeConn(cur)
    with _connect_patcher(conn):
        row_id = db_conn.execute_lastrowid("INSERT INTO t (a) VALUES (%s)", (1,))
    assert row_id == 7


def test_connection_context_runs_and_closes():
    """connection() 是上下文管理器，正常退出时关闭连接。"""
    from app.tools import db_conn

    cur = _FakeCursor()
    conn = _FakeConn(cur)
    with _connect_patcher(conn):
        with db_conn.connection() as c:
            assert c is conn
            with c.cursor() as cur2:
                cur2.execute("SELECT 1")
    assert cur.executed == [("SELECT 1", None)]


# ============================================================
# TASK-REF-DB-002 — DB 可观测指标接线
# ============================================================


class _FakeBound:
    def __init__(self, store, labels):
        self._store = store
        self._labels = labels

    def inc(self, *a):
        self._store.append(("inc", self._labels, a))

    def observe(self, *a):
        self._store.append(("observe", self._labels, a))


class _FakeHistogram:
    def __init__(self, store):
        self._store = store

    def labels(self, **labels):
        return _FakeBound(self._store, labels)


class _FakeGauge:
    def __init__(self, store):
        self._store = store

    def inc(self):
        self._store.append("inc")

    def dec(self):
        self._store.append("dec")


def test_sql_meta_derives_operation_and_table():
    from app.tools.db_conn import _sql_meta

    cases = [
        ("SELECT * FROM experience_card WHERE id=%s", ("select", "experience_card")),
        ("INSERT INTO submissions (a) VALUES (%s)", ("insert", "submissions")),
        ("REPLACE INTO ai_cache (k) VALUES (%s)", ("insert", "ai_cache")),
        ("UPDATE experience_card SET x=1 WHERE id=%s", ("update", "experience_card")),
        ("DELETE FROM interview_records WHERE id=%s", ("delete", "interview_records")),
        ("ALTER TABLE job_analysis ADD COLUMN x INT", ("ddl", "job_analysis")),
        (
            "CREATE TABLE IF NOT EXISTS ai_tasks (id INT)",
            ("ddl", "ai_tasks"),
        ),
        ("SHOW COLUMNS FROM job_analysis", ("select", "job_analysis")),
        ("SELECT COUNT(*) FROM t", ("select", "t")),
        ("", ("other", "unknown")),
    ]
    for sql, expected in cases:
        assert _sql_meta(sql) == expected, sql


def test_query_helper_observes_duration_metric(monkeypatch):
    from app.tools import db_conn

    observations = []
    monkeypatch.setattr(
        db_conn, "db_query_duration_seconds", _FakeHistogram(observations)
    )
    monkeypatch.setattr(db_conn, "db_connections_active", _FakeGauge([]))

    cur = _FakeCursor(row={"id": 1})
    with _connect_patcher(_FakeConn(cur)):
        db_conn.query_one("SELECT * FROM experience_card WHERE id=%s", (1,))

    assert any(
        entry
        for entry in observations
        if entry[1] == {"operation": "select", "table": "experience_card"}
        and entry[0] == "observe"
    )


def test_helper_tracks_active_conn_inc_and_dec(monkeypatch):
    from app.tools import db_conn

    gauge_calls = []
    monkeypatch.setattr(db_conn, "db_query_duration_seconds", _FakeHistogram([]))
    monkeypatch.setattr(db_conn, "db_connections_active", _FakeGauge(gauge_calls))

    cur = _FakeCursor(rows=[])
    with _connect_patcher(_FakeConn(cur)):
        db_conn.query_all("SELECT * FROM t")
    assert gauge_calls == ["inc", "dec"]


def test_connection_tracks_active_conn_inc_and_dec(monkeypatch):
    from app.tools import db_conn

    gauge_calls = []
    monkeypatch.setattr(db_conn, "db_connections_active", _FakeGauge(gauge_calls))

    cur = _FakeCursor()
    with _connect_patcher(_FakeConn(cur)):
        with db_conn.connection() as c:
            with c.cursor() as cur2:
                cur2.execute("SELECT 1")
    assert gauge_calls == ["inc", "dec"]
