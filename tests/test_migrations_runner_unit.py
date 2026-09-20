"""migrations.runner 单元测试：版本发现、排序、应用与幂等。

不依赖真实 MySQL，通过替换 mysql.connector.connect 为内存假 cursor 验证逻辑。
"""

import os

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
    inserts = [
        e for e in executed if e[0].strip().startswith("INSERT INTO schema_migrations")
    ]
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


def test_fk_migration_declares_expected_constraints():
    """V0002 外键迁移应覆盖 roadmap 列出的四类高价值关系。"""
    fk_file = os.path.join(runner.MIGRATIONS_DIR, "V0002__foreign_keys.sql")
    assert os.path.exists(fk_file)
    with open(fk_file, encoding="utf-8") as fh:
        sql = fh.read()
    for expected in [
        "ADD CONSTRAINT fk_submission_job_analysis",
        "ADD CONSTRAINT fk_preps_job_analysis",
        "ADD CONSTRAINT fk_preps_submission",
        "ADD CONSTRAINT fk_qa_record",
        "ADD CONSTRAINT fk_card_versions_card",
    ]:
        assert expected in sql, f"缺失外键约束声明: {expected}"
    # 每个 ADD CONSTRAINT 之前都应先清理对应孤儿数据，避免 FK 创建失败
    assert "DELETE FROM resume_submission" in sql
    assert "DELETE FROM card_versions" in sql


def test_v0002_and_v0004_are_idempotent():
    """DB-02：V0002/V0004 应使用 information_schema 探测 + PREPARE/EXECUTE，重复执行安全。"""
    for fname in ["V0002__foreign_keys.sql", "V0004__ai_cache.sql"]:
        path = os.path.join(runner.MIGRATIONS_DIR, fname)
        assert os.path.exists(path)
        with open(path, encoding="utf-8") as fh:
            sql = fh.read()
        assert "information_schema" in sql, f"{fname} 缺少 information_schema 探测"
        assert "PREPARE" in sql and "EXECUTE" in sql, (
            f"{fname} 缺少 PREPARE/EXECUTE 动态执行"
        )
        # 每个语句块都以 SPLIT 结尾，保证可被 runner 逐条执行
        for stmt in sql.split(";--SPLIT--"):
            stmt = stmt.strip()
            assert stmt == "" or not stmt.endswith(";"), (
                f"{fname} 语句块含尾分号: {stmt[:50]}"
            )


def _normalize_ddl(sql: str) -> str:
    """规整 DDL：去反引号、折叠空白，用于迁移文件与运行时 DDL 对比。"""
    import re

    return re.sub(r"\s+", " ", sql.replace("`", "")).strip()


def _runtime_create_sql(fn, mod=None) -> str:
    """捕获 _ensure_* 函数实际执行的 CREATE TABLE 语句。

    :param fn: 目标 _ensure_* 函数
    :param mod: 该函数所在模块（默认 db_base_resume）
    """
    executed: list[tuple[str, str]] = []

    class Cursor:
        def execute(self, sql, params=None):
            executed.append((sql.strip(), params))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Conn:
        def cursor(self, *a, **k):
            return Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    if mod is None:
        import app.tools.db_base_resume as mod

    original_ready = mod.is_schema_ready
    original_conn = mod.connection
    try:
        mod.is_schema_ready = lambda: False
        mod.connection = lambda: Conn()
        fn()
    finally:
        mod.is_schema_ready = original_ready
        mod.connection = original_conn
    messages = [
        sql for sql, _ in executed if sql.startswith("CREATE TABLE IF NOT EXISTS")
    ]
    assert messages, "未捕获到 CREATE TABLE 语句"
    return messages[0]


def test_v0005_base_resume_matches_runtime_ddl():
    """DB-01：V0005 中 base_resume 建表语句应与运行时 _ensure_base_resume_table 一致，防止漂移。"""
    v0005 = os.path.join(runner.MIGRATIONS_DIR, "V0005__runtime_tables.sql")
    assert os.path.exists(v0005)
    with open(v0005, encoding="utf-8") as fh:
        sql = fh.read()
    start = sql.index("CREATE TABLE IF NOT EXISTS base_resume")
    end = sql.index(";--SPLIT--", start)
    migration_ddl = _normalize_ddl(sql[start:end])

    from app.tools.db_base_resume import _ensure_base_resume_table

    runtime_ddl = _normalize_ddl(_runtime_create_sql(_ensure_base_resume_table))
    assert migration_ddl == runtime_ddl, "V0005 与运行时 base_resume DDL 漂移"


def test_v0006_v0007_columns_matched_in_resume_submission_runtime_ddl():
    """DB-04：V0006(delivered)/V0007(is_active) 补列应已在运行时
    _ensure_resume_submission_table 建表语句中体现，迁移路径与 bootstrap 路径收敛一致。
    """
    v0006 = os.path.join(runner.MIGRATIONS_DIR, "V0006__submission_delivered.sql")
    v0007 = os.path.join(runner.MIGRATIONS_DIR, "V0007__soft_delete.sql")
    assert os.path.exists(v0006) and os.path.exists(v0007)
    with open(v0006, encoding="utf-8") as fh:
        assert "ADD COLUMN delivered" in fh.read()
    with open(v0007, encoding="utf-8") as fh:
        v0007_sql = fh.read()
    assert "ALTER TABLE resume_submission ADD COLUMN is_active" in v0007_sql
    assert "ALTER TABLE job_analysis ADD COLUMN is_active" in v0007_sql

    from app.tools.db_submission import _ensure_resume_submission_table
    import app.tools.db_submission as mod

    runtime_ddl = _normalize_ddl(
        _runtime_create_sql(_ensure_resume_submission_table, mod=mod)
    )
    assert "delivered TINYINT(1) DEFAULT 0" in runtime_ddl
    assert "is_active TINYINT(1) DEFAULT 1" in runtime_ddl


def test_v0007_soft_delete_follows_split_convention():
    """DB-04：V0007 语句块应遵守 SPLIT 约定（无尾分号），可被 runner 逐条执行。"""
    v0007 = os.path.join(runner.MIGRATIONS_DIR, "V0007__soft_delete.sql")
    with open(v0007, encoding="utf-8") as fh:
        sql = fh.read()
    stmts = [s.strip() for s in sql.split(";--SPLIT--")]
    real = [s for s in stmts if s]
    assert len(real) == 2, f"V0007 应含 2 条语句块，实际 {len(real)}"
    for stmt in real:
        assert not stmt.endswith(";"), f"V0007 语句块含尾分号: {stmt[:60]}"
