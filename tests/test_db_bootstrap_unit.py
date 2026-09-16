"""TASK-P1-10 `_ensure_*` 启动引导单元测试。

验证 db_bootstrap 把运行时 DDL 收敛为启动一次性执行：
- run_schema_bootstrap 按序执行全部 _ensure_* 并置位 schema-ready；
- 失败不置位（请求路径降级为逐调用执行）；
- 置位后 _ensure_* 短路为空操作（不再触发任何 DB 访问）。
不依赖真实 MySQL。
"""

# 先加载 db_tools 的 re-export 链（db_user/db_experience/db_job/db_submission/db_interview），
# 规避 db_experience ↔ db_tools 的循环引用（二者直接 import 会 ImportError）。
from app.tools import db_bootstrap, db_conn, db_tools, db_user  # noqa: F401


def _reset():
    db_conn.reset_schema_ready()
    assert not db_conn.is_schema_ready()


def test_schema_ready_flag_roundtrip():
    _reset()
    assert not db_conn.is_schema_ready()
    db_conn.mark_schema_ready()
    assert db_conn.is_schema_ready()
    db_conn.reset_schema_ready()
    assert not db_conn.is_schema_ready()


def test_run_schema_bootstrap_executes_all_steps_in_order(monkeypatch):
    _reset()
    called: list[str] = []

    for module_path, func_name in db_bootstrap._BOOTSTRAP_STEPS:
        import importlib

        mod = importlib.import_module(module_path)
        monkeypatch.setattr(
            mod,
            func_name,
            lambda _m=module_path, _f=func_name: called.append(f"{_m}.{_f}"),
        )

    ok = db_bootstrap.run_schema_bootstrap()

    expected = [f"{m}.{f}" for m, f in db_bootstrap._BOOTSTRAP_STEPS]
    assert ok is True
    assert called == expected
    assert db_conn.is_schema_ready()


def test_run_schema_bootstrap_is_idempotent(monkeypatch):
    _reset()
    called: list[str] = []

    for module_path, func_name in db_bootstrap._BOOTSTRAP_STEPS:
        import importlib

        mod = importlib.import_module(module_path)
        monkeypatch.setattr(mod, func_name, lambda: called.append(func_name))

    db_bootstrap.run_schema_bootstrap()
    db_bootstrap.run_schema_bootstrap()

    # 第二次调用直接短路，不再重复执行
    assert len(called) == len(db_bootstrap._BOOTSTRAP_STEPS)


def test_run_schema_bootstrap_failure_does_not_mark_ready(monkeypatch):
    _reset()
    import importlib

    mod = importlib.import_module(db_bootstrap._BOOTSTRAP_STEPS[0][0])
    monkeypatch.setattr(
        mod,
        db_bootstrap._BOOTSTRAP_STEPS[0][1],
        lambda: (_ for _ in ()).throw(RuntimeError("db down")),
    )

    ok = db_bootstrap.run_schema_bootstrap()

    assert ok is False
    assert not db_conn.is_schema_ready()


def test_ensure_short_circuits_when_schema_ready(monkeypatch):
    """置位后 _ensure_* 不再触发任何 DDL/连接。"""
    _reset()
    db_conn.mark_schema_ready()

    monkeypatch.setattr(
        "app.tools.db_user.execute",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应执行 DDL")),
    )
    db_user._ensure_users_table()
    monkeypatch.setattr(
        "app.tools.db_experience.connection",
        lambda: (_ for _ in ()).throw(AssertionError("不应打开连接")),
    )
    import importlib

    mod = importlib.import_module("app.tools.db_experience")
    mod._ensure_experience_card_columns()
    mod._ensure_card_versions_table()


def test_ensure_still_runs_ddl_when_not_ready(monkeypatch):
    """未置位时保持改造前行为：_ensure_* 正常执行 DDL。"""
    _reset()
    executed: list[str] = []
    monkeypatch.setattr(
        "app.tools.db_user.execute", lambda sql, params=None: executed.append(sql)
    )
    db_user._ensure_users_table()
    assert executed and "CREATE TABLE IF NOT EXISTS users" in executed[0]


def test_worker_and_lifespan_hooks_reference_bootstrap():
    """server lifespan 与任务 worker 都应接线 run_schema_bootstrap。"""
    import inspect

    from app.api import server
    from app.tasks import worker

    lifespan_src = inspect.getsource(server.lifespan)
    assert "run_schema_bootstrap" in lifespan_src

    run_worker_src = inspect.getsource(worker.run_worker)
    assert "run_schema_bootstrap" in run_worker_src
