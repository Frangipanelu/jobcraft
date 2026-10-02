"""scripts/backfill_cards.py 维护脚本单测（T-M1-5：backfill 端点转脚本）。

覆盖：成功透传 user_id/min_chars、缺 --user-id 拒绝执行、workflow 失败返回退出码 1。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backfill_cards.py"


def _load_script() -> ModuleType:
    """以文件路径加载 scripts/backfill_cards.py（scripts 非包，无 __init__）。"""
    spec = importlib.util.spec_from_file_location("backfill_cards", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def script_mod() -> ModuleType:
    """加载脚本模块。"""
    return _load_script()


class TestBackfillScript:
    """回填维护脚本行为锁。"""

    def test_success_forwards_args(self, script_mod, monkeypatch, capsys):
        """--user-id/--min-chars 原样透传 workflow，退出码 0。"""
        calls: list = []

        def fake_run(user_id: int, min_chars: int = 100):
            calls.append((user_id, min_chars))
            return {"processed": 2}

        monkeypatch.setattr(
            "app.workflows.extract_flow.run_backfill_workflow", fake_run
        )
        code = script_mod.main(["--user-id", "7", "--min-chars", "200"])

        assert code == 0
        assert calls == [(7, 200)]
        out = capsys.readouterr().out.strip()
        assert json.loads(out) == {"processed": 2}

    def test_default_min_chars(self, script_mod, monkeypatch):
        """未传 --min-chars 时默认 100（同原端点）。"""
        calls: list = []
        monkeypatch.setattr(
            "app.workflows.extract_flow.run_backfill_workflow",
            lambda uid, min_chars=100: (
                calls.append((uid, min_chars)) or {"processed": 0}
            ),
        )
        code = script_mod.main(["--user-id", "1"])

        assert code == 0
        assert calls == [(1, 100)]

    def test_missing_user_id_rejected(self, script_mod):
        """缺 --user-id 必须拒绝（无隐式默认用户，argparse 退出码 2）。"""
        with pytest.raises(SystemExit) as exc_info:
            script_mod.main([])

        assert exc_info.value.code == 2

    def test_workflow_failure_returns_1(self, script_mod, monkeypatch, capsys):
        """workflow 抛错 → 退出码 1 且错误输出到 stderr。"""

        def raise_err(*a, **kw):
            raise RuntimeError("boom")

        monkeypatch.setattr(
            "app.workflows.extract_flow.run_backfill_workflow", raise_err
        )
        code = script_mod.main(["--user-id", "1"])

        assert code == 1
        assert "回填失败" in capsys.readouterr().err
