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
