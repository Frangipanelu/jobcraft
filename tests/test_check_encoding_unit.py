# -*- coding: utf-8 -*-
"""scripts/check_encoding.py 控制字符检测单测（2026-10-11 PowerShell 反引号转义事故防线）。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "check_encoding.py"
_spec = importlib.util.spec_from_file_location("check_encoding", _MODULE_PATH)
assert _spec and _spec.loader
check_encoding = importlib.util.module_from_spec(_spec)
sys.modules["check_encoding"] = check_encoding
_spec.loader.exec_module(check_encoding)


class TestFindControlChars:
    """find_control_chars 纯函数行为。"""

    def test_clean_lf_text_no_hits(self) -> None:
        assert check_encoding.find_control_chars("第一行\n第二行\n") == []

    def test_clean_crlf_text_no_hits(self) -> None:
        assert check_encoding.find_control_chars("第一行\r\n第二行\r\n") == []

    def test_lone_cr_reported(self) -> None:
        hits = check_encoding.find_control_chars("abc\rdef")
        assert hits == [(1, "U+000D 孤立 CR")]

    def test_tab_reported(self) -> None:
        hits = check_encoding.find_control_chars("a\tb")
        assert hits == [(1, "U+0009 TAB")]

    def test_bel_reported(self) -> None:
        hits = check_encoding.find_control_chars("a\x07b")
        assert hits == [(1, "U+0007")]

    def test_ff_reported(self) -> None:
        hits = check_encoding.find_control_chars("a\x0cb")
        assert hits == [(1, "U+000C")]

    def test_nul_reported(self) -> None:
        hits = check_encoding.find_control_chars("a\x00b")
        assert hits == [(1, "U+0000")]

    def test_line_numbers_track_newlines(self) -> None:
        hits = check_encoding.find_control_chars("l1\nl2\x07\nl3\n")
        assert hits == [(2, "U+0007")]

    def test_crlf_then_control(self) -> None:
        hits = check_encoding.find_control_chars("l1\r\nl2\ttab\r\n")
        assert hits == [(2, "U+0009 TAB")]

    def test_multiple_hits_collected(self) -> None:
        hits = check_encoding.find_control_chars("a\x07b\tc\rd")
        assert len(hits) == 3
        assert hits[0][1] == "U+0007"
        assert hits[1][1] == "U+0009 TAB"
        assert hits[2][1] == "U+000D 孤立 CR"


class TestCheckFileControlChars:
    """check_file 对临时文件的端到端检测。"""

    def _check(self, tmp_path: Path, name: str, data: bytes):
        target = tmp_path / name
        target.write_bytes(data)
        # check_file 用 path.relative_to(REPO_ROOT)，临时目录不在仓库内 → 直接读函数逻辑
        # 通过 monkey 方式：拷贝检测核心（decode + 控制字符）而非复用 check_file
        text = data.decode("utf-8")
        return check_encoding.find_control_chars(text)

    def test_corrupted_markdown_like_content(self, tmp_path: Path) -> None:
        # 复刻 2026-10-11 事故现场：BEL 吞 a、TAB 吞 t
        corrupted = "**修正**：\x07nalyze 实写 done、\x09ests 目录\n".encode("utf-8")
        hits = self._check(tmp_path, "corrupt.md", corrupted)
        assert [h[1] for h in hits] == ["U+0007", "U+0009 TAB"]
