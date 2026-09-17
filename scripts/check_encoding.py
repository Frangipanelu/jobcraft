"""扫描仓库中的文件编码问题（CJK 损坏 / 非 UTF-8 / mojibake）。

背景：Windows PowerShell 5.1 的 ``Set-Content`` / ``Out-File`` / ``>`` / ``Add-Content``
默认按 ANSI（中文系统为 GBK）写入，会把 UTF-8 源码里的中文写成乱码；而 mojibake 往往仍能
通过编译与类型检查，难以在 CI 中暴露。故提供本脚本作为提交前的编码防线。

检测项：

1. 无法按 UTF-8 解码（``UnicodeDecodeError``）——源文件被 ANSI/GBK 重写。
2. 含替换字符 ``U+FFFD``——解码失败的残留。
3. 含常见 mojibake 片段（如 ``锟斤拷`` / ``ï¿½`` / ``â€`` / ``Ã©``）。

退出码：0 全部通过；1 存在错误级问题。

用法::

    python scripts/check_encoding.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".next",
    ".opencode",
    ".pytest_cache",
    ".ruff_cache",
    ".turbo",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "htmlcov",
    "node_modules",
    "output",
    "screenshots",
    "updated",
    "venv",
}

CHECK_EXTENSIONS = {
    ".bash",
    ".cjs",
    ".cfg",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsonc",
    ".jsx",
    ".md",
    ".mdx",
    ".mjs",
    ".ps1",
    ".psm1",
    ".py",
    ".pyi",
    ".scss",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yml",
    ".yaml",
}

SKIP_FILENAMES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}

SKIP_RELATIVE_PATHS = {
    Path("scripts/check_encoding.py"),
}

# 仅对代码/配置类文件提示 BOM；.txt 等测试夹具可能有意带 BOM，不做要求。
BOM_CHECK_EXTENSIONS = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsonc",
    ".jsx",
    ".mjs",
    ".cjs",
    ".py",
    ".pyi",
    ".scss",
    ".sh",
    ".ts",
    ".tsx",
    ".toml",
    ".yaml",
    ".yml",
}

REPLACEMENT_CHAR = "\ufffd"

# 注意：本脚本自身包含这些片段，故在 SKIP_RELATIVE_PATHS 中排除自身，否则会自我误报。
MOJIBAKE_MARKERS = (
    "锟斤拷",
    "ï¿½",
    "â€",
    "Ã©",
    "Ã¨",
    "Ã¤",
    "Ã¶",
    "Ã¼",
    "Ã§",
    "Ã±",
    "Ã¥",
    "Ã¦",
    "Ã¸",
    "Ã¢",
    "Â·",
)


class Finding:
    """单条编码问题记录。"""

    def __init__(self, path: Path, line: int, reason: str, level: str = "error") -> None:
        """初始化记录。

        Args:
            path: 相对仓库根的文件路径。
            line: 行号（1 起；0 表示整文件级问题）。
            reason: 人类可读的问题描述。
            level: ``error`` 或 ``warn``。
        """
        self.path = path
        self.line = line
        self.reason = reason
        self.level = level

    def format(self) -> str:
        """格式化为 ``path:line: reason`` 形式。"""
        location = f"{self.path}:{self.line}" if self.line else str(self.path)
        return f"[{self.level}] {location}: {self.reason}"


def iter_candidate_files() -> list[Path]:
    """枚举需要检查的文本文件。"""
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(REPO_ROOT)
        if relative in SKIP_RELATIVE_PATHS:
            continue
        if any(part in SKIP_DIRS for part in relative.parts[:-1]):
            continue
        if path.name in SKIP_FILENAMES:
            continue
        if path.suffix.lower() not in CHECK_EXTENSIONS:
            continue
        files.append(path)
    return files


def first_line_with(text: str, needle: str) -> int:
    """返回 ``needle`` 首次出现的行号（1 起），未命中返回 0。"""
    index = text.find(needle)
    if index < 0:
        return 0
    return text.count("\n", 0, index) + 1


def check_file(path: Path) -> list[Finding]:
    """检查单个文件，返回问题列表。

    Args:
        path: 待检查文件的绝对路径。

    Returns:
        该文件的编码问题列表（可能为空）。
    """
    relative = path.relative_to(REPO_ROOT)
    raw = path.read_bytes()

    has_bom = raw.startswith(b"\xef\xbb\xbf")
    payload = raw[3:] if has_bom else raw

    findings: list[Finding] = []

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        line = payload.count(b"\n", 0, exc.start) + 1
        findings.append(
            Finding(relative, line, "非 UTF-8 编码（疑似被 PowerShell ANSI 写入覆盖）")
        )
        return findings

    if has_bom and path.suffix.lower() in BOM_CHECK_EXTENSIONS:
        findings.append(Finding(relative, 0, "文件含 UTF-8 BOM（建议去除）", level="warn"))

    if REPLACEMENT_CHAR in text:
        findings.append(
            Finding(
                relative,
                first_line_with(text, REPLACEMENT_CHAR),
                "含替换字符 U+FFFD（编码损坏残留）",
            )
        )

    for marker in MOJIBAKE_MARKERS:
        if marker in text:
            findings.append(
                Finding(
                    relative,
                    first_line_with(text, marker),
                    f"疑似 mojibake 片段 {marker!r}（UTF-8/ANSI 双重编码）",
                )
            )

    return findings


def main() -> int:
    """执行全仓扫描并打印结果。"""
    files = iter_candidate_files()
    findings: list[Finding] = []
    for path in files:
        findings.extend(check_file(path))

    errors = [item for item in findings if item.level == "error"]
    warns = [item for item in findings if item.level == "warn"]

    for item in findings:
        print(item.format())

    if errors:
        print(f"\nFAILED: {len(errors)} encoding error(s) in {len(files)} scanned file(s).")
        return 1

    print(f"OK: {len(files)} file(s) scanned, no encoding errors ({len(warns)} warning(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
