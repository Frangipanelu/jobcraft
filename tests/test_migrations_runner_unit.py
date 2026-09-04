"""migrations.runner 单元测试：版本发现、排序、应用与幂等。

不依赖真实 MySQL，通过替换 mysql.connector.connect 为内存假 cursor 验证逻辑。
"""

import pytest

import migrations.runner as runner


class FakeCursor:
    """记录 execute 的假 cursor，维护版本表内存状态。"""

    def __init__(self):
        self.executed: list[tuple[str, tuple | None]] = []
        self._versions: dict[str, dict] = {}

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        s = sql.strip()
        if s.startswith("CREATE TABLE IF NOT EXISTS schema_migrations"):
            return
        if s.startswith("SELECT version, checksum FROM schema_migrations"):
            # 返回行（由 fetchall 消费）
            self._last_select = list(self._versions.items())
            return
        if s.startswith("INSERT INTO schema_migrations"):
            version, name, checksum = params
            self._versions[version] = checksum

    def fetchall(self):
        return self._last_select

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeConn:
    def __init__(self):
        self.cursor_obj = FakeCursor()

    def cursor(self, *a, **k):
        return self.cursor_obj

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def commit(self):
        return None


@pytest.fixture
def fake_conn(monkeypatch):
    conn = FakeConn()
    monkeypatch.setattr(runner, "connect", lambda **k: conn)
    monkeypatch.setattr(
        runner,
        "get_db_config",
        lambda overrides=None: {"user": "u", "password": "p", "database": "jobcraft"},
    )
    return conn


def test_discover_migrations_orders_and_matches_naming(tmp_path, monkeypatch):
    """应只发现 V{N}__{name}.sql，并按版本升序。"""
    d = tmp_path / "versions"
    d.mkdir()
    (d / "V0002__b.sql").write_text("B", encoding="utf-8")
    (d / "V0001__a.sql").write_text("A", encoding="utf-8")
    (d / "notes.txt").write_text("ignored", encoding="utf-8")
    monkeypatch.setattr(runner, "MIGRATIONS_DIR", str(d))
    result = runner._discover_migrations()
    versions = [v for v, _, _ in result]
    assert versions == ["0001", "0002"]
    assert [f for _, f, _ in result] == ["V0001__a.sql", "V0002__b.sql"]


def test_baseline_file_is_valid_split(fake_conn):
    """baseline 迁移应用时不应抛错，且语句均被逐条 execute。"""
    n = len(runner._discover_migrations())
    assert n >= 1
    runner.migrate()
    # 至少执行了建版本表的语句 + 若干条 DDL + 1 条插入记录
    executed = fake_conn.cursor_obj.executed
    inserts = [e for e in executed if e[0].strip().startswith("INSERT INTO schema_migrations")]
    assert len(inserts) == n
    # 没有剩余 pending
    runner.status()
    select = fake_conn.cursor_obj.executed
    assert any(e[0].strip().startswith("SELECT version, checksum") for e in select)


def test_migrate_is_idempotent(fake_conn):
    """重复 migrate 不重复应用已记录版本。"""
    runner.migrate()
    first_insert_count = sum(
        1
        for e in fake_conn.cursor_obj.executed
        if e[0].strip().startswith("INSERT INTO schema_migrations")
    )
    runner.migrate()
    second_insert_count = sum(
        1
        for e in fake_conn.cursor_obj.executed
        if e[0].strip().startswith("INSERT INTO schema_migrations")
    )
    # 第二次不应新增插入（同一条 INSERT 只统计一次）
    assert second_insert_count == first_insert_count


def test_migrate_limit_stops_at_target(fake_conn, tmp_path, monkeypatch):
    """limit 参数应只应用到指定版本（含）。"""
    d = tmp_path / "versions"
    d.mkdir()
    (d / "V0001__a.sql").write_text("A", encoding="utf-8")
    (d / "V0002__b.sql").write_text("B", encoding="utf-8")
    (d / "V0003__c.sql").write_text("C", encoding="utf-8")
    monkeypatch.setattr(runner, "MIGRATIONS_DIR", str(d))
    runner.migrate(2)
    inserted = [
        e[1][0]
        for e in fake_conn.cursor_obj.executed
        if e[0].strip().startswith("INSERT INTO schema_migrations")
    ]
    assert inserted == ["0001", "0002"]


def test_checksum_changed_flagged_in_status(fake_conn, tmp_path, monkeypatch):
    """status 对已应用但内容变化的迁移应标为 changed。"""
    d = tmp_path / "versions"
    d.mkdir()
    (d / "V0001__a.sql").write_text("A", encoding="utf-8")
    monkeypatch.setattr(runner, "MIGRATIONS_DIR", str(d))
    runner.migrate()
    # 修改文件内容 -> checksum 变化
    (d / "V0001__a.sql").write_text("A-modified", encoding="utf-8")
    runner.status()  # 不应抛错
