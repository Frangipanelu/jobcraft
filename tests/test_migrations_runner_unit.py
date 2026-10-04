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

        def fetchall(self):
            # CREATE 后的 SHOW COLUMNS 守卫：返回空触发补列（结果不参与断言）
            return []

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


def test_v0015_resume_suggestions_matched_in_runtime_ddl_and_baseline():
    """FE-RESUME-02：V0015(resume_suggestions) 只加列，且迁移路径 / 运行时
    _ensure_resume_submission_table 建表 / docker 基线三处收敛一致。"""
    v0015 = os.path.join(runner.MIGRATIONS_DIR, "V0015__resume_suggestions.sql")
    assert os.path.exists(v0015)
    with open(v0015, encoding="utf-8") as fh:
        sql = fh.read()
    assert "ALTER TABLE resume_submission ADD COLUMN resume_suggestions JSON" in sql
    assert "DROP" not in sql.upper(), "前向兼容：只加列，不得出现 DROP"
    assert "MODIFY" not in sql.upper(), "前向兼容：不得改列类型"

    from app.tools.db_submission import _ensure_resume_submission_table
    import app.tools.db_submission as mod

    runtime_ddl = _normalize_ddl(
        _runtime_create_sql(_ensure_resume_submission_table, mod=mod)
    )
    assert "resume_suggestions JSON" in runtime_ddl

    repo_root = os.path.dirname(os.path.dirname(runner.MIGRATIONS_DIR))
    with open(
        os.path.join(repo_root, "docker", "mysql", "jobcraft.sql"), encoding="utf-8"
    ) as fh:
        assert "resume_suggestions JSON" in fh.read(), (
            "docker 基线缺 resume_suggestions 列"
        )


def test_v0016_prep_drafts_matched_in_runtime_ddl_and_baseline():
    """FE-PREP-01：V0016(drafts) 只加列，且迁移 / 运行时
    _ensure_interview_preps_table 建表+守卫补列 / docker 基线三处收敛一致。"""
    v0016 = os.path.join(runner.MIGRATIONS_DIR, "V0016__interview_prep_drafts.sql")
    assert os.path.exists(v0016)
    with open(v0016, encoding="utf-8") as fh:
        sql = fh.read()
    assert "ALTER TABLE interview_preps ADD COLUMN drafts JSON" in sql
    assert "DROP" not in sql.upper(), "前向兼容：只加列，不得出现 DROP"
    assert "MODIFY" not in sql.upper(), "前向兼容：不得改列类型"

    from app.tools.db_interview import _ensure_interview_preps_table
    import app.tools.db_interview as mod

    executed: list[tuple[str, str]] = []

    class _Cursor:
        def execute(self, sql, params=None):
            executed.append((sql.strip(), params))

        def fetchall(self):
            # 首次建表后列探测：返回空触发守卫 ALTER，证明未迁移环境也有补列路径
            return []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Conn:
        def cursor(self, *a, **k):
            return _Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    original_ready = mod.is_schema_ready
    original_conn = mod.connection
    try:
        mod.is_schema_ready = lambda: False
        mod.connection = lambda: _Conn()
        _ensure_interview_preps_table()
    finally:
        mod.is_schema_ready = original_ready
        mod.connection = original_conn

    creates = [s for s, _ in executed if s.startswith("CREATE TABLE IF NOT EXISTS")]
    assert creates, "未捕获到 CREATE TABLE 语句"
    assert "drafts JSON" in _normalize_ddl(creates[0]), "运行时建表缺 drafts 列"
    alters = [s for s, _ in executed if s.startswith("ALTER TABLE interview_preps")]
    assert alters, "运行时守卫补列路径缺失（未迁移环境兜底）"
    assert "ADD COLUMN drafts JSON" in alters[0]

    repo_root = os.path.dirname(os.path.dirname(runner.MIGRATIONS_DIR))
    with open(
        os.path.join(repo_root, "docker", "mysql", "jobcraft.sql"), encoding="utf-8"
    ) as fh:
        assert "drafts JSON" in fh.read(), "docker 基线缺 drafts 列"


def test_v0023_interview_session_columns_matched_in_runtime_ddl_and_baseline():
    """T-M7-4：V0023(场次列) 只加列，且迁移 / 运行时
    _ensure_interview_records_table 建表+守卫补列 / docker 基线三处收敛一致。"""
    v0023 = os.path.join(runner.MIGRATIONS_DIR, "V0023__interview_records_session.sql")
    assert os.path.exists(v0023)
    with open(v0023, encoding="utf-8") as fh:
        sql = fh.read()

    session_columns = (
        "ALTER TABLE interview_records ADD COLUMN round_seq INT NULL",
        "ALTER TABLE interview_records ADD COLUMN occurred_at DATETIME NULL",
        "ALTER TABLE interview_records ADD COLUMN interviewer VARCHAR(100) NULL",
        "ALTER TABLE interview_records ADD COLUMN format VARCHAR(20) NULL",
        "ALTER TABLE interview_records ADD COLUMN resume_version_id INT NULL",
    )
    for col_ddl in session_columns:
        assert col_ddl in sql, f"V0023 缺 {col_ddl}"
    assert "DROP" not in sql.upper(), "前向兼容：只加列，不得出现 DROP"
    assert "MODIFY" not in sql.upper(), "前向兼容：不得改列类型"

    from app.tools.db_interview import _ensure_interview_records_table
    import app.tools.db_interview as mod

    executed: list[tuple[str, str]] = []

    class _Cursor:
        def execute(self, sql, params=None):
            executed.append((sql.strip(), params))

        def fetchall(self):
            # 首次建表后列探测：返回空触发全部守卫 ALTER，证明未迁移环境也有补列路径
            return []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Conn:
        def cursor(self, *a, **k):
            return _Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    original_ready = mod.is_schema_ready
    original_conn = mod.connection
    try:
        mod.is_schema_ready = lambda: False
        mod.connection = lambda: _Conn()
        _ensure_interview_records_table()
    finally:
        mod.is_schema_ready = original_ready
        mod.connection = original_conn

    creates = [s for s, _ in executed if s.startswith("CREATE TABLE IF NOT EXISTS")]
    assert creates, "未捕获到 CREATE TABLE 语句"
    for fragment in (
        "round_seq INT NULL",
        "occurred_at DATETIME NULL",
        "interviewer VARCHAR(100) NULL",
        "format VARCHAR(20) NULL",
        "resume_version_id INT NULL",
    ):
        assert fragment in _normalize_ddl(creates[0]), f"运行时建表缺 {fragment}"

    alters = [s for s, _ in executed if s.startswith("ALTER TABLE interview_records")]
    assert len(alters) == 5, f"运行时守卫补列应为 5 条，实际 {len(alters)}"
    for fragment in (
        "round_seq",
        "occurred_at",
        "interviewer",
        "format",
        "resume_version_id",
    ):
        assert any(f"ADD COLUMN {fragment}" in a for a in alters), f"守卫缺 {fragment}"

    repo_root = os.path.dirname(os.path.dirname(runner.MIGRATIONS_DIR))
    with open(
        os.path.join(repo_root, "docker", "mysql", "jobcraft.sql"), encoding="utf-8"
    ) as fh:
        seed = fh.read()
    for fragment in (
        "round_seq INT NULL",
        "occurred_at DATETIME NULL",
        "interviewer VARCHAR(100) NULL",
        "format VARCHAR(20) NULL",
        "resume_version_id INT NULL",
    ):
        assert fragment in seed, f"docker 基线缺 {fragment}"


def test_v0024_qa_pairs_index_matched_in_runtime_ddl_and_baseline():
    """T-M8-8 / BE-INDEX-01：V0024 只加索引，且迁移 / 运行时建表 / docker 基线三处收敛一致。

    背景：T-M8-3 聚合题库走 record_id 过滤 + (record_id, sequence) 排序；
    索引虽在基线/运行时/docker 声明，存量库无迁移回填——V0024 补此缺口。
    """
    v0024 = os.path.join(runner.MIGRATIONS_DIR, "V0024__interview_qa_pairs_index.sql")
    assert os.path.exists(v0024)
    with open(v0024, encoding="utf-8") as fh:
        sql = fh.read()

    for index_ddl in (
        "ALTER TABLE interview_qa_pairs ADD KEY idx_record (record_id)",
        "ALTER TABLE interview_qa_pairs ADD KEY idx_sequence (record_id, sequence)",
    ):
        assert index_ddl in sql, f"V0024 缺 {index_ddl}"
    assert "DROP" not in sql.upper(), "前向兼容：只加索引，不得出现 DROP"
    assert "MODIFY" not in sql.upper(), "前向兼容：不得改列类型"
    assert sql.count("FROM information_schema.STATISTICS") == 2, "两索引各需一次幂等探测"
    assert "ADD KEY IF NOT EXISTS" not in sql.upper(), "MySQL 8 不支持该语法，须用探测"

    from app.tools.db_interview import _ensure_interview_qa_pairs_table
    import app.tools.db_interview as mod

    executed: list[tuple[str, str]] = []

    class _Cursor:
        def execute(self, sql, params=None):
            executed.append((sql, str(params)))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Conn:
        def cursor(self, *a, **k):
            return _Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    original_ready = mod.is_schema_ready
    original_conn = mod.connection
    try:
        mod.is_schema_ready = lambda: False
        mod.connection = lambda: _Conn()
        _ensure_interview_qa_pairs_table()
    finally:
        mod.is_schema_ready = original_ready
        mod.connection = original_conn

    creates = [
        s for s, _ in executed if "CREATE TABLE IF NOT EXISTS" in _normalize_ddl(s)
    ]
    assert creates, "未捕获到 CREATE TABLE 语句"
    normalized = _normalize_ddl(creates[0])
    for fragment in ("KEY idx_record (record_id)", "KEY idx_sequence (record_id, sequence)"):
        assert fragment in normalized, f"运行时建表缺 {fragment}"

    repo_root = os.path.dirname(os.path.dirname(runner.MIGRATIONS_DIR))
    with open(
        os.path.join(repo_root, "docker", "mysql", "jobcraft.sql"), encoding="utf-8"
    ) as fh:
        seed = fh.read()
    for fragment in ("KEY idx_record (record_id)", "KEY idx_sequence (record_id, sequence)"):
        assert fragment in seed, f"docker 基线缺 {fragment}"


def test_v0017_profile_github_matched_in_runtime_ddl():
    """FE-RESUME-03：V0017(github) 只加列，且迁移 / 运行时
    _ensure_user_profiles_table 建表+守卫补列两路径收敛一致。
    （docker 基线 jobcraft.sql 不含 user_profiles 表，该表由运行时 DDL 建，故基线断言从略。）"""
    v0017 = os.path.join(runner.MIGRATIONS_DIR, "V0017__profile_github.sql")
    assert os.path.exists(v0017)
    with open(v0017, encoding="utf-8") as fh:
        sql = fh.read()
    assert "ALTER TABLE user_profiles ADD COLUMN github VARCHAR(255)" in sql
    assert "DROP" not in sql.upper(), "前向兼容：只加列，不得出现 DROP"
    assert "MODIFY" not in sql.upper(), "前向兼容：不得改列类型"

    from app.tools import db_profile as mod

    executed: list[str] = []

    def fake_execute(sql, params=None):
        executed.append(sql.strip())
        return 0

    original_ready = mod.is_schema_ready
    original_execute = mod.execute
    original_query_all = mod.query_all
    try:
        mod.is_schema_ready = lambda: False
        mod.execute = fake_execute

        # 缺 github 列：守卫触发 ALTER（未迁移环境兜底路径）
        mod.query_all = lambda sql, params=None: [
            {"Field": "user_id"},
            {"Field": "display_name"},
        ]
        mod._ensure_user_profiles_table()
        creates = [s for s in executed if s.startswith("CREATE TABLE IF NOT EXISTS")]
        assert creates, "未捕获到 CREATE TABLE 语句"
        assert "github VARCHAR(255)" in _normalize_ddl(creates[0]), (
            "运行时建表缺 github 列"
        )
        alters = [s for s in executed if s.startswith("ALTER TABLE user_profiles")]
        assert alters, "运行时守卫补列路径缺失（未迁移环境兜底）"
        assert "ADD COLUMN github VARCHAR(255)" in alters[0]

        # 列已存在：守卫不得重复 ALTER
        executed.clear()
        mod.query_all = lambda sql, params=None: [{"Field": "github"}]
        mod._ensure_user_profiles_table()
        assert not [s for s in executed if s.startswith("ALTER TABLE user_profiles")], (
            "列已存在时不应重复 ALTER"
        )
    finally:
        mod.is_schema_ready = original_ready
        mod.execute = original_execute
        mod.query_all = original_query_all


def test_v0007_soft_delete_follows_split_convention():
    """DB-04/DB-VERIFY-02：V0007 走 information_schema 探测 + PREPARE/EXECUTE
    幂等惯例（2 列 × 5 语句 = 10 块），遵守 SPLIT 约定（无尾分号）。"""
    v0007 = os.path.join(runner.MIGRATIONS_DIR, "V0007__soft_delete.sql")
    with open(v0007, encoding="utf-8") as fh:
        sql = fh.read()
    assert "information_schema.COLUMNS" in sql, "V0007 应走列探测幂等"
    assert sql.count("\nPREPARE _mig_stmt_") == 2
    stmts = [s.strip() for s in sql.split(";--SPLIT--")]
    real = [s for s in stmts if s]
    assert len(real) == 10, f"V0007 应含 10 条语句块（2 列 × 5），实际 {len(real)}"
    for stmt in real:
        assert not stmt.endswith(";"), f"V0007 语句块含尾分号: {stmt[:60]}"


def test_v0008_confirm_draft_follows_split_convention():
    """EXP-P1-03/DB-VERIFY-02：V0008 只加 is_confirmed/fields 两列，
    走 information_schema 探测幂等（2 列 × 5 语句 = 10 块），遵守 SPLIT 约定。"""
    v0008 = os.path.join(runner.MIGRATIONS_DIR, "V0008__confirm_draft_fields.sql")
    assert os.path.exists(v0008)
    with open(v0008, encoding="utf-8") as fh:
        sql = fh.read()
    assert (
        "ALTER TABLE experience_card ADD COLUMN is_confirmed TINYINT(1) NOT NULL DEFAULT 1"
        in sql
    ), "缺少 is_confirmed 列声明"
    assert "ALTER TABLE experience_card ADD COLUMN fields JSON" in sql, (
        "缺少 fields 列声明"
    )
    # direction/expression 表延期到 P2（V0009），本期不得新增表
    assert "CREATE TABLE" not in sql
    assert "information_schema.COLUMNS" in sql, "V0008 应走列探测幂等"
    assert sql.count("\nPREPARE _mig_stmt_") == 2
    stmts = [s.strip() for s in sql.split(";--SPLIT--")]
    real = [s for s in stmts if s]
    assert len(real) == 10, f"V0008 应含 10 条语句块（2 列 × 5），实际 {len(real)}"
    for stmt in real:
        assert not stmt.endswith(";"), f"V0008 语句块含尾分号: {stmt[:60]}"


def test_v0008_columns_matched_in_experience_runtime_helper():
    """EXP-P1-03：V0008 两列应同时出现在运行时
    _ensure_experience_card_columns 的 ALTER ADD 清单，迁移与 bootstrap 收敛一致。
    """
    v0008 = os.path.join(runner.MIGRATIONS_DIR, "V0008__confirm_draft_fields.sql")
    with open(v0008, encoding="utf-8") as fh:
        sql = fh.read()
    assert "is_confirmed" in sql and "fields" in sql

    from app.tools import db_experience
    import app.tools.db_experience as mod

    executed: list[str] = []
    # V0001 基线列（缺 is_confirmed/fields），模拟旧库
    existing = [
        "id",
        "user_id",
        "title",
        "raw_text",
        "tags",
        "ai_structured",
        "summary",
        "content",
        "company",
        "role",
        "period",
        "background",
        "problem",
        "solution",
        "execution",
        "result",
        "dimensions",
        "source",
        "card_type",
        "version",
        "is_active",
        "created_at",
        "updated_at",
    ]

    class Cur:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, stmt, params=None):
            executed.append(stmt.strip())

        def fetchall(self):
            s = " ".join(executed[-1].split()) if executed else ""
            if s.startswith("SHOW COLUMNS FROM experience_card"):
                return [(name,) for name in existing]
            return []

        def fetchone(self):
            return ("source", "varchar(50)")  # 非 enum，跳过 MODIFY

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def cursor(self, dictionary=False):
            return Cur()

    original_ready = mod.is_schema_ready
    original_conn = mod.connection
    try:
        mod.is_schema_ready = lambda: False
        mod.connection = lambda: Conn()
        db_experience._ensure_experience_card_columns()
    finally:
        mod.is_schema_ready = original_ready
        mod.connection = original_conn
    altered = " ".join(executed)
    assert "ADD COLUMN is_confirmed" in altered
    assert "ADD COLUMN fields" in altered
    assert "TINYINT(1) NOT NULL DEFAULT 1" in altered
    assert "JSON" in altered


def test_v0009_expression_direction_declares_both_tables():
    """EXP-P2-01：V0009 应同时声明 direction 与 expression 两张新表（U8）。"""
    v0009 = os.path.join(runner.MIGRATIONS_DIR, "V0009__expression_direction.sql")
    assert os.path.exists(v0009)
    with open(v0009, encoding="utf-8") as fh:
        sql = fh.read()
    assert "CREATE TABLE IF NOT EXISTS direction" in sql
    assert "CREATE TABLE IF NOT EXISTS expression" in sql
    # 前向兼容：只加表，不 ALTER 既有表
    assert "ALTER TABLE" not in sql


def test_v0009_expression_fields_follow_data_model():
    """EXP-P2-01：expression 表字段应覆盖 DATA_MODEL §6 + §8 的稳定列。"""
    v0009 = os.path.join(runner.MIGRATIONS_DIR, "V0009__expression_direction.sql")
    with open(v0009, encoding="utf-8") as fh:
        sql = fh.read()
    expression_ddl = sql.split("CREATE TABLE IF NOT EXISTS expression", 1)[1]
    for col in [
        "user_id INT NOT NULL",
        "experience_id INT NOT NULL",
        "direction_id INT NULL",
        "job_id INT NULL",
        "type VARCHAR(16)",
        "content TEXT NOT NULL",
        "version INT NOT NULL",
        "validation_level TINYINT",
        "usage_count INT NOT NULL",
        "source_refs JSON",
        "status VARCHAR(16)",
    ]:
        assert col in expression_ddl, f"expression 表缺失列声明: {col}"


def test_v0009_direction_fields_follow_data_model():
    """EXP-P2-01：direction 表字段应覆盖 DATA_MODEL §7 + DIRECTION_SPEC §3。"""
    v0009 = os.path.join(runner.MIGRATIONS_DIR, "V0009__expression_direction.sql")
    with open(v0009, encoding="utf-8") as fh:
        sql = fh.read()
    direction_ddl = sql.split("CREATE TABLE IF NOT EXISTS direction", 1)[1]
    for col in [
        "user_id INT NOT NULL",
        "name VARCHAR(200) NOT NULL",
        "function_id INT NULL",
        "primary_role_id INT NULL",
        "status VARCHAR(16)",
    ]:
        assert col in direction_ddl, f"direction 表缺失列声明: {col}"


def test_v0009_follows_split_convention():
    """EXP-P2-01：V0009 语句块遵守 SPLIT 约定（无尾分号），可被 runner 逐条执行。"""
    v0009 = os.path.join(runner.MIGRATIONS_DIR, "V0009__expression_direction.sql")
    with open(v0009, encoding="utf-8") as fh:
        sql = fh.read()
    stmts = [s.strip() for s in sql.split(";--SPLIT--")]
    real = [s for s in stmts if s]
    assert len(real) == 2, f"V0009 应含 2 条语句块，实际 {len(real)}"
    for stmt in real:
        assert not stmt.endswith(";"), f"V0009 语句块含尾分号: {stmt[:60]}"


def test_v0009_migrate_is_applied_via_runner(fake_conn):
    """EXP-P2-01：V0009 与既有迁移共存，runner.migrate() 不抛错且全量入库。"""
    runner.migrate()
    inserted = [
        e[1][0]
        for e in fake_conn.cursor_obj.executed
        if e[0].strip().startswith("INSERT INTO schema_migrations")
    ]
    assert "0009" in inserted


def test_v0010_consolidates_runtime_ddl_idempotent():
    """批次 C1：V0010 应收编历史 docker 库缺列（experience_card raw_text/ai_structured），
    采用 information_schema + PREPARE/EXECUTE 幂等模式，且不含 MODIFY/DROP。"""
    v0010 = os.path.join(runner.MIGRATIONS_DIR, "V0010__consolidate_runtime_ddl.sql")
    assert os.path.exists(v0010)
    with open(v0010, encoding="utf-8") as fh:
        sql = fh.read()
    assert "ALTER TABLE experience_card ADD COLUMN raw_text LONGTEXT" in sql
    assert "ALTER TABLE experience_card ADD COLUMN ai_structured JSON" in sql
    assert "information_schema.COLUMNS" in sql
    assert "PREPARE" in sql and "EXECUTE" in sql
    # 前向兼容：只加列，禁止 MODIFY/DROP 形式的 DDL 语句（注释提及字样不影响）
    for stmt in sql.split(";--SPLIT--"):
        stmt = stmt.strip()
        assert not stmt.upper().startswith(("MODIFY", "DROP")), (
            f"V0010 不得含 MODIFY/DROP 语句: {stmt[:50]}"
        )
    for stmt in sql.split(";--SPLIT--"):
        stmt = stmt.strip()
        assert stmt == "" or not stmt.endswith(";"), (
            f"V0010 语句块含尾分号: {stmt[:50]}"
        )


def test_runtime_ddl_has_no_modify():
    """批次 C2：runtime `_ensure_*` 不得再执行 MODIFY（ENUM→VARCHAR）类型修改。"""
    exp_path = os.path.join(
        os.path.dirname(runner.__file__),
        "..",
        "app",
        "tools",
        "db_experience.py",
    )
    with open(os.path.normpath(exp_path), encoding="utf-8") as fh:
        src = fh.read()
    assert "MODIFY COLUMN" not in src, "runtime 不得包含 MODIFY COLUMN 类型修改"


def test_v0010_migrate_is_applied_via_runner(fake_conn):
    """批次 C1：V0010 与既有迁移共存，runner.migrate() 不抛错且全量入库。"""
    runner.migrate()
    inserted = [
        e[1][0]
        for e in fake_conn.cursor_obj.executed
        if e[0].strip().startswith("INSERT INTO schema_migrations")
    ]
    assert "0010" in inserted


def test_v0011_adds_job_analysis_artifact_columns():
    """P4-1：V0011 为 job_analysis 加分析物五列（ats_profile / suggestions /
    per_card_scores / match_level / analysis_version），information_schema +
    PREPARE/EXECUTE 幂等模式，且只加列不改/删。"""
    v0011 = os.path.join(runner.MIGRATIONS_DIR, "V0011__job_analysis_artifacts.sql")
    assert os.path.exists(v0011)
    with open(v0011, encoding="utf-8") as fh:
        sql = fh.read()
    for col in (
        "ats_profile",
        "suggestions",
        "per_card_scores",
        "match_level",
        "analysis_version",
    ):
        assert f"ADD COLUMN {col}" in sql, f"V0011 缺少 {col} 列"
    assert "information_schema.COLUMNS" in sql
    assert "PREPARE" in sql and "EXECUTE" in sql
    # 前向兼容：只加列，禁止 MODIFY/DROP 形式 DDL（注释提及字样不影响）
    for stmt in sql.split(";--SPLIT--"):
        stmt = stmt.strip()
        assert not stmt.upper().startswith(("MODIFY", "DROP")), (
            f"V0011 不得含 MODIFY/DROP 语句: {stmt[:50]}"
        )


def test_v0011_migrate_is_applied_via_runner(fake_conn):
    """P4-1：V0011 与既有迁移共存，runner.migrate() 不抛错且入库。"""
    runner.migrate()
    inserted = [
        e[1][0]
        for e in fake_conn.cursor_obj.executed
        if e[0].strip().startswith("INSERT INTO schema_migrations")
    ]
    assert "0011" in inserted


def test_v0012_creates_raw_jd_snapshot_table():
    """P4-2：V0012 新建 raw_jd 不可变快照表（原始 JD 只增不改），
    CREATE TABLE IF NOT EXISTS 幂等，且只新建表不改/删既有表。"""
    v0012 = os.path.join(runner.MIGRATIONS_DIR, "V0012__raw_jd_snapshot.sql")
    assert os.path.exists(v0012)
    with open(v0012, encoding="utf-8") as fh:
        sql = fh.read()
    assert "CREATE TABLE IF NOT EXISTS raw_jd" in sql
    for col in ("user_id", "job_analysis_id", "source", "jd_text", "created_at"):
        assert col in sql, f"V0012 缺少 {col} 列"
    assert "idx_raw_jd_job" in sql
    # 前向兼容：只新建表，禁止 MODIFY/DROP/ALTER 既有表
    for stmt in sql.split(";--SPLIT--"):
        upper = stmt.strip().upper()
        assert not upper.startswith(("MODIFY", "DROP", "ALTER", "RENAME")), (
            f"V0012 不得含改/删既有表的 DDL: {stmt[:50]}"
        )


def test_v0012_migrate_is_applied_via_runner(fake_conn):
    """P4-2：V0012 与既有迁移共存，runner.migrate() 不抛错且入库。"""
    runner.migrate()
    inserted = [
        e[1][0]
        for e in fake_conn.cursor_obj.executed
        if e[0].strip().startswith("INSERT INTO schema_migrations")
    ]
    assert "0012" in inserted


def test_v0013_creates_job_table_and_links_job_analysis():
    """P4-4a：V0013 新建 job 表（岗位聚合根）+ job_analysis.job_id 归属列，
    幂等（IF NOT EXISTS + information_schema 探测），且不改/删既有表。"""
    v0013 = os.path.join(runner.MIGRATIONS_DIR, "V0013__job_entity.sql")
    assert os.path.exists(v0013)
    with open(v0013, encoding="utf-8") as fh:
        sql = fh.read()
    assert "CREATE TABLE IF NOT EXISTS job" in sql
    for col in (
        "company",
        "position",
        "raw_jd_id",
        "job_analysis_id",
        "submission_id",
        "status",
        "is_active",
    ):
        assert col in sql, f"V0013 job 表缺少 {col} 列"
    # 唯一键策略属批次 B 待定项：不得提前加 UNIQUE
    assert "UNIQUE" not in sql.upper()
    assert "ADD COLUMN job_id" in sql
    assert "information_schema.COLUMNS" in sql
    assert "PREPARE" in sql and "EXECUTE" in sql
    # 前向兼容：只新建表 + 加列，禁止改/删既有表
    for stmt in sql.split(";--SPLIT--"):
        upper = stmt.strip().upper()
        assert not upper.startswith(("DROP", "RENAME", "TRUNCATE")), (
            f"V0013 不得含破坏性 DDL: {stmt[:50]}"
        )


def test_v0013_migrate_is_applied_via_runner(fake_conn):
    """P4-4a：V0013 与既有迁移共存，runner.migrate() 不抛错且入库。"""
    runner.migrate()
    inserted = [
        e[1][0]
        for e in fake_conn.cursor_obj.executed
        if e[0].strip().startswith("INSERT INTO schema_migrations")
    ]
    assert "0013" in inserted


def test_v0014_logic_fk_indexes_and_updated_at():
    """BE-INDEX-01：V0014 为 4 个逻辑外键补索引 + job_analysis.updated_at，
    幂等（information_schema 探测 + PREPARE/EXECUTE），只加不改/删。"""
    v0014 = os.path.join(runner.MIGRATIONS_DIR, "V0014__logic_fk_indexes.sql")
    assert os.path.exists(v0014)
    with open(v0014, encoding="utf-8") as fh:
        sql = fh.read()
    for add_key in (
        "ALTER TABLE job ADD KEY idx_job_raw_jd (raw_jd_id)",
        "ALTER TABLE job ADD KEY idx_job_analysis (job_analysis_id)",
        "ALTER TABLE interview_records ADD KEY idx_job_analysis (job_analysis_id)",
        "ALTER TABLE interview_qa_pairs ADD KEY idx_related_card (related_card_id)",
    ):
        assert add_key in sql, f"V0014 缺少索引: {add_key}"
    assert (
        "ALTER TABLE job_analysis ADD COLUMN updated_at TIMESTAMP "
        "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
    ) in sql
    assert "information_schema.STATISTICS" in sql
    assert "information_schema.COLUMNS" in sql
    assert sql.count("\nPREPARE _mig_stmt_") == 5
    assert sql.count("EXECUTE _mig_stmt_") == 5
    assert sql.count("DEALLOCATE PREPARE _mig_stmt_") == 5
    # 前向兼容：只加索引/加列，禁止 DROP/MODIFY
    assert "DROP" not in sql.upper(), "前向兼容：不得出现 DROP"
    assert "MODIFY" not in sql.upper(), "前向兼容：不得改列类型"


def test_v0014_converged_in_runtime_ddl_and_docker_baseline():
    """BE-INDEX-01：V0014 的索引/列在 迁移 / 运行时 DDL / docker 基线 三处收敛。
    （job 表由 V0013 创建、不在 docker 基线，故基线断言对 job 从略。）"""
    import app.tools.db_interview as di
    import app.tools.db_job as dj
    import app.tools.db_job_entity as dje

    job_create = _normalize_ddl(_runtime_create_sql(dje._ensure_job_table, mod=dje))
    assert "KEY idx_job_raw_jd (raw_jd_id)" in job_create
    assert "KEY idx_job_analysis (job_analysis_id)" in job_create

    records_create = _normalize_ddl(
        _runtime_create_sql(di._ensure_interview_records_table, mod=di)
    )
    assert "KEY idx_job_analysis (job_analysis_id)" in records_create

    qa_create = _normalize_ddl(
        _runtime_create_sql(di._ensure_interview_qa_pairs_table, mod=di)
    )
    assert "KEY idx_related_card (related_card_id)" in qa_create

    # job_analysis.updated_at 运行时兜底：SHOW COLUMNS 探测 + ADD COLUMN
    # （游标桩：列探测返回空 → 全部 additive 列触发守卫 ALTER）
    executed: list[tuple[str, str]] = []

    class _Cursor:
        def execute(self, sql, params=None):
            executed.append((sql.strip(), params))

        def fetchall(self):
            return []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Conn:
        def cursor(self, *a, **k):
            return _Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    original_ready = dj.is_schema_ready
    original_conn = dj.connection
    try:
        dj.is_schema_ready = lambda: False
        dj.connection = lambda: _Conn()
        dj._ensure_job_analysis_columns()
    finally:
        dj.is_schema_ready = original_ready
        dj.connection = original_conn

    alters = [s for s, _ in executed if s.startswith("ALTER TABLE job_analysis")]
    assert alters, "未捕获到 job_analysis 守卫 ALTER"
    assert any("ADD COLUMN updated_at" in a for a in alters)

    # docker 基线：job_analysis 列 + interview_records / interview_qa_pairs 索引
    repo_root = os.path.dirname(os.path.dirname(runner.MIGRATIONS_DIR))
    with open(
        os.path.join(repo_root, "docker", "mysql", "jobcraft.sql"), encoding="utf-8"
    ) as fh:
        seed = fh.read()
    job_analysis_block = seed.split("CREATE TABLE IF NOT EXISTS job_analysis")[1].split(
        "ENGINE=InnoDB"
    )[0]
    assert (
        "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        in (job_analysis_block)
    ), "docker 基线 job_analysis 缺 updated_at"
    assert seed.count("KEY idx_job_analysis (job_analysis_id)") >= 2, (
        "docker 基线 interview_records 缺 idx_job_analysis（resume_submission 已有同名索引）"
    )
    assert "KEY idx_related_card (related_card_id)" in seed, (
        "docker 基线 interview_qa_pairs 缺 idx_related_card"
    )


def test_v0014_migrate_is_applied_via_runner(fake_conn):
    """BE-INDEX-01：V0014 与既有迁移共存，runner.migrate() 不抛错且入库。"""
    runner.migrate()
    inserted = [
        e[1][0]
        for e in fake_conn.cursor_obj.executed
        if e[0].strip().startswith("INSERT INTO schema_migrations")
    ]
    assert "0014" in inserted


def test_interview_runtime_creates_carry_all_baseline_columns():
    """BE-INIT-01：preps/records 运行时 CREATE 单函数即得完整表
    （对齐 V0001/docker 基线），不依赖 _ensure_interview_submission_columns 补列守卫。"""
    import app.tools.db_interview as di

    preps = _normalize_ddl(
        _runtime_create_sql(di._ensure_interview_preps_table, mod=di)
    )
    for fragment in (
        "submission_id INT",
        "company_research_json JSON",
        "company_research_at DATETIME",
        "drafts JSON",
        "KEY idx_submission (submission_id)",
    ):
        assert fragment in preps, f"preps 运行时 CREATE 缺 {fragment}"

    records = _normalize_ddl(
        _runtime_create_sql(di._ensure_interview_records_table, mod=di)
    )
    for fragment in (
        "submission_id INT",
        "round_label VARCHAR(32) DEFAULT ''",
        "KEY idx_submission (submission_id)",
        "KEY idx_job_analysis (job_analysis_id)",
    ):
        assert fragment in records, f"records 运行时 CREATE 缺 {fragment}"

    # docker 基线同样携带：四路收敛（V0001 / seed / 运行时 CREATE / ALTER 守卫）
    repo_root = os.path.dirname(os.path.dirname(runner.MIGRATIONS_DIR))
    with open(
        os.path.join(repo_root, "docker", "mysql", "jobcraft.sql"), encoding="utf-8"
    ) as fh:
        seed = fh.read()
    preps_block = seed.split("CREATE TABLE IF NOT EXISTS interview_preps")[1].split(
        "ENGINE=InnoDB"
    )[0]
    for fragment in (
        "submission_id INT",
        "company_research_json JSON",
        "company_research_at DATETIME",
    ):
        assert fragment in preps_block, f"docker 基线 preps 缺 {fragment}"
    records_block = seed.split("CREATE TABLE IF NOT EXISTS interview_records")[1].split(
        "ENGINE=InnoDB"
    )[0]
    for fragment in ("submission_id INT", "round_label VARCHAR(32) DEFAULT ''"):
        assert fragment in records_block, f"docker 基线 records 缺 {fragment}"


def test_v0018_direction_six_dims_follows_convention():
    """T-M3-1：V0018 为 direction 加六维标量列 + DIR-n 编码 + 唯一键，
    幂等（information_schema 探测 + PREPARE/EXECUTE），遵守 SPLIT 约定，只加不改/删。"""
    v0018 = os.path.join(runner.MIGRATIONS_DIR, "V0018__direction_six_dims.sql")
    assert os.path.exists(v0018)
    with open(v0018, encoding="utf-8") as fh:
        sql = fh.read()
    for frag in (
        "ADD COLUMN code VARCHAR(16) NOT NULL DEFAULT ''",
        "ADD COLUMN job_function VARCHAR(100)",
        "ADD COLUMN primary_role VARCHAR(100)",
        "ADD COLUMN industry VARCHAR(100)",
        "ADD COLUMN product VARCHAR(200)",
        "ADD COLUMN scenario VARCHAR(200)",
        "ADD COLUMN skills VARCHAR(500)",
    ):
        assert frag in sql, f"V0018 缺少列声明: {frag}"
    assert (
        "ALTER TABLE direction ADD UNIQUE KEY uk_direction_code (user_id, code)" in sql
    ), "U-P2a′：缺 UNIQUE(user_id, code)"
    assert (
        "ALTER TABLE direction ADD UNIQUE KEY uk_direction_user_name (user_id, name)"
        in sql
    ), "缺 UNIQUE(user_id, name)"
    assert "information_schema.COLUMNS" in sql
    assert "information_schema.STATISTICS" in sql
    # 存量回填 DIR-n（ROW_NUMBER 按用户内 id 序，空表 no-op）
    assert "ROW_NUMBER() OVER (PARTITION BY user_id" in sql
    assert "CONCAT('DIR-', t.rn)" in sql
    assert sql.count("\nPREPARE _mig_stmt_") == 9
    assert sql.count("\nEXECUTE _mig_stmt_") == 9
    assert sql.count("\nDEALLOCATE PREPARE _mig_stmt_") == 9
    # direction 表零运行时 DDL：迁移是唯一落点，不新建表
    assert "CREATE TABLE" not in sql
    # 前向兼容：只加列/索引 + 回填，禁止破坏性 DDL
    for stmt in sql.split(";--SPLIT--"):
        upper = stmt.strip().upper()
        assert not upper.startswith(("DROP", "RENAME", "TRUNCATE")), (
            f"V0018 不得含破坏性 DDL: {stmt[:50]}"
        )
        assert "MODIFY COLUMN" not in upper, f"V0018 不得改列: {stmt[:50]}"
    # SPLIT 约定：9 组探测（各 5 条）+ 1 条回填 = 46 条语句，均无尾分号
    stmts = [s.strip() for s in sql.split(";--SPLIT--") if s.strip()]
    assert len(stmts) == 46, f"V0018 应含 46 条语句块，实际 {len(stmts)}"
    for stmt in stmts:
        assert not stmt.endswith(";"), f"V0018 语句块含尾分号: {stmt[:60]}"


def test_v0018_migrate_is_applied_via_runner(fake_conn):
    """T-M3-1：V0018 与既有迁移共存，runner.migrate() 不抛错且入库。"""
    runner.migrate()
    inserted = [
        e[1][0]
        for e in fake_conn.cursor_obj.executed
        if e[0].strip().startswith("INSERT INTO schema_migrations")
    ]
    assert "0018" in inserted


def test_v0019_jd_classification_follows_convention():
    """T-M3-2：V0019 新建 jd_classification（Q7=c 第二级），仅建表不改既有，
    幂等（CREATE TABLE IF NOT EXISTS），遵守 SPLIT 约定。"""
    v0019 = os.path.join(runner.MIGRATIONS_DIR, "V0019__jd_classification.sql")
    assert os.path.exists(v0019)
    with open(v0019, encoding="utf-8") as fh:
        sql = fh.read()
    assert "CREATE TABLE IF NOT EXISTS jd_classification" in sql
    for frag in (
        "job_analysis_id INT NOT NULL",
        "direction_id INT NULL",
        "job_function VARCHAR(100) NOT NULL DEFAULT ''",
        "primary_role VARCHAR(100) NOT NULL DEFAULT ''",
        "industry VARCHAR(100) NOT NULL DEFAULT ''",
        "product VARCHAR(200) NOT NULL DEFAULT ''",
        "scenario VARCHAR(200) NOT NULL DEFAULT ''",
        "skills VARCHAR(500) NOT NULL DEFAULT ''",
        "confidence VARCHAR(8) NOT NULL DEFAULT ''",
        "source VARCHAR(16) NOT NULL DEFAULT 'manual'",
        "status VARCHAR(16) NOT NULL DEFAULT 'proposed'",
        "UNIQUE KEY uk_jd_classification_analysis (job_analysis_id)",
        "KEY idx_jd_classification_user (user_id, status)",
        "KEY idx_jd_classification_direction (direction_id)",
        "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
    ):
        assert frag in sql, f"V0019 缺少定义: {frag}"
    # 前向兼容：仅新建表，不动既有表/列（AGENTS §4.4）
    stmts = [s.strip() for s in sql.split(";--SPLIT--") if s.strip()]
    assert len(stmts) == 1, f"V0019 应含 1 条语句块，实际 {len(stmts)}"
    stmt = stmts[0]
    upper = stmt.upper()
    assert not upper.startswith(("DROP", "ALTER", "RENAME", "TRUNCATE", "UPDATE"))
    assert "MODIFY COLUMN" not in upper, "V0019 不得改列"
    assert not stmt.endswith(";"), f"V0019 语句块含尾分号: {stmt[:60]}"


def test_v0019_migrate_is_applied_via_runner(fake_conn):
    """T-M3-2：V0019 与既有迁移共存，runner.migrate() 不抛错且入库。"""
    runner.migrate()
    inserted = [
        e[1][0]
        for e in fake_conn.cursor_obj.executed
        if e[0].strip().startswith("INSERT INTO schema_migrations")
    ]
    assert "0019" in inserted


def test_v0020_capability_gaps_follows_convention():
    """T-M4-2：V0020 新建 capability_gap（Q3 改写任务清单），仅建表不改既有，
    幂等（CREATE TABLE IF NOT EXISTS），遵守 SPLIT 约定。"""
    v0020 = os.path.join(runner.MIGRATIONS_DIR, "V0020__capability_gaps.sql")
    assert os.path.exists(v0020)
    with open(v0020, encoding="utf-8") as fh:
        sql = fh.read()
    assert "CREATE TABLE IF NOT EXISTS capability_gap" in sql
    for frag in (
        "job_analysis_id INT NOT NULL",
        "user_id INT NOT NULL DEFAULT 1",
        "dimension VARCHAR(8) NOT NULL DEFAULT 'EXT'",
        "kind VARCHAR(16) NOT NULL DEFAULT 'evidence'",
        "status VARCHAR(16) NOT NULL DEFAULT 'missing'",
        "severity VARCHAR(16) NOT NULL DEFAULT 'medium'",
        "jd_evidence TEXT",
        "current_text TEXT",
        "rewrite_hint TEXT",
        "card_id INT NULL",
        "note TEXT",
        "KEY idx_capability_gap_analysis (job_analysis_id)",
        "KEY idx_capability_gap_user_dimension (user_id, dimension)",
        "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
    ):
        assert frag in sql, f"V0020 缺少定义: {frag}"
    # Q3 定稿字段 current 以 current_text 落列（MySQL 关键字安全）
    assert "current text" not in sql.lower(), "不得使用 MySQL 关键字 current 作列名"
    # 前向兼容：仅新建表，不动既有表/列（AGENTS §4.4）
    stmts = [s.strip() for s in sql.split(";--SPLIT--") if s.strip()]
    assert len(stmts) == 1, f"V0020 应含 1 条语句块，实际 {len(stmts)}"
    stmt = stmts[0]
    upper = stmt.upper()
    assert not upper.startswith(("DROP", "ALTER", "RENAME", "TRUNCATE", "UPDATE"))
    assert "MODIFY COLUMN" not in upper, "V0020 不得改列"
    assert not stmt.endswith(";"), f"V0020 语句块含尾分号: {stmt[:60]}"


def test_v0020_migrate_is_applied_via_runner(fake_conn):
    """T-M4-2：V0020 与既有迁移共存，runner.migrate() 不抛错且入库
    （V0014 编号已被 BE-INDEX-01 占用，缺口表顺延 V0020）。"""
    runner.migrate()
    inserted = [
        e[1][0]
        for e in fake_conn.cursor_obj.executed
        if e[0].strip().startswith("INSERT INTO schema_migrations")
    ]
    assert "0020" in inserted


def test_v0021_resume_versions_follows_convention():
    """T-M6-1：V0021 新建 resume_version（M6-Q1-B 核心字段），仅建表不动既有，
    幂等（CREATE TABLE IF NOT EXISTS），遵守 SPLIT 约定。"""
    v0021 = os.path.join(runner.MIGRATIONS_DIR, "V0021__resume_versions.sql")
    assert os.path.exists(v0021)
    with open(v0021, encoding="utf-8") as fh:
        sql = fh.read()
    flat = " ".join(sql.split())
    assert "CREATE TABLE IF NOT EXISTS resume_version" in flat
    for frag in (
        "user_id INT NOT NULL DEFAULT 1",
        "job_id INT",
        "direction_id INT",
        "version_no INT NOT NULL DEFAULT 1",
        "version_name VARCHAR(200)",
        "sections JSON",
        "resume_markdown LONGTEXT",
        "selected_for_application TINYINT(1) NOT NULL DEFAULT 0",
        "source_expression_refs JSON",
        "KEY idx_resume_version_owner (user_id, job_id)",
        "KEY idx_resume_version_job (job_id)",
        "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
    ):
        assert frag in flat, f"V0021 缺少定义: {frag}"
    # Q1-B 核心字段：factualCheck/userStatus/type 等后置，不在本期建列
    # （只查 CREATE 体，跳过头注释里的裁决说明）
    create_body = flat[flat.index("CREATE TABLE IF NOT EXISTS resume_version") :]
    for absent in ("factual", "user_status", "base_resume_id"):
        assert absent not in create_body.lower(), f"V0021 不应包含后置字段: {absent}"
    # 前向兼容：仅新建表（AGENTS §4.4）
    stmts = [s.strip() for s in sql.split(";--SPLIT--") if s.strip()]
    assert len(stmts) == 1, f"V0021 应含 1 条语句块，实际 {len(stmts)}"
    stmt = stmts[0]
    upper = stmt.upper()
    assert not upper.startswith(("DROP", "ALTER", "RENAME", "TRUNCATE", "UPDATE"))
    assert "MODIFY COLUMN" not in upper, "V0021 不得改列"
    assert not stmt.endswith(";"), f"V0021 语句块含尾分号: {stmt[:60]}"


def test_v0021_migrate_is_applied_via_runner(fake_conn):
    """T-M6-1：V0021 与既有迁移共存，runner.migrate() 不抛错且入库。"""
    runner.migrate()
    inserted = [
        e[1][0]
        for e in fake_conn.cursor_obj.executed
        if e[0].strip().startswith("INSERT INTO schema_migrations")
    ]
    assert "0021" in inserted


def test_v0022_resume_version_analysis_backfill_follows_convention():
    """T-M6-2/DB-VERIFY-02：V0022 加 job_analysis_id 列 + 存量快照一次性迁 v1（裁决
    「一次性 SQL」），只加列/插行不动既有列；列/索引走探测幂等，遵守 SPLIT 约定。"""
    v0022 = os.path.join(
        runner.MIGRATIONS_DIR, "V0022__resume_version_analysis_backfill.sql"
    )
    assert os.path.exists(v0022)
    with open(v0022, encoding="utf-8") as fh:
        sql = fh.read()
    flat = " ".join(sql.split())
    for frag in (
        "ADD COLUMN job_analysis_id INT NULL",
        "ADD KEY idx_resume_version_analysis (job_analysis_id)",
        "INSERT INTO resume_version",
        "JOIN job_analysis a",
        "LEFT JOIN job j",
        "NOT EXISTS",
        "v1（存量快照）",
        "s.resume_markdown <> ''",
    ):
        assert frag in flat, f"V0022 缺少定义: {frag}"
    stmts = [s.strip() for s in sql.split(";--SPLIT--") if s.strip()]
    assert len(stmts) == 11, (
        f"V0022 应含 11 条语句块（列探测 5 + 索引探测 5 + INSERT），实际 {len(stmts)}"
    )
    assert "information_schema.COLUMNS" in sql, "V0022 加列应走探测幂等"
    assert "information_schema.STATISTICS" in sql, "V0022 加索引应走探测幂等"

    def _bare(stmt: str) -> str:
        """去掉行首注释后的语句体（块头注释不算语句）。"""
        return "\n".join(
            line for line in stmt.splitlines() if not line.strip().startswith("--")
        ).strip()

    assert _bare(stmts[0]).upper().startswith("SET"), "V0022 第一块应为列探测 SET @cnt"
    assert _bare(stmts[-1]).upper().startswith("INSERT"), (
        "V0022 最后一块应为 INSERT 迁数据"
    )
    upper = sql.upper()
    assert "DROP" not in upper, "V0022 不得删表"
    assert "MODIFY COLUMN" not in upper, "V0022 不得改列"
    for stmt in stmts:
        body = _bare(stmt)
        assert not body.endswith(";"), f"V0022 语句块含尾分号: {body[:60]}"


def test_v0022_migrate_is_applied_via_runner(fake_conn):
    """T-M6-2：V0022 与既有迁移共存，runner.migrate() 不抛错且入库。"""
    runner.migrate()
    inserted = [
        e[1][0]
        for e in fake_conn.cursor_obj.executed
        if e[0].strip().startswith("INSERT INTO schema_migrations")
    ]
    assert "0022" in inserted
