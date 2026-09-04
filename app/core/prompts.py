"""Prompt 外部化加载器。

所有 Agent / LLM 调点的系统与用户 prompt 收敛到项目根 `prompts/<域>/` 目录，
使用纯文本模板并以 `_v{N}` 版本化。本模块提供统一加载 + 填充入口。

模板语法：
- 占位符用双花括号 `{{name}}`（如 `{{raw_text}}`），由调用方以 `name=value` 传入，
  填充时替换为对应实参。
- 模板中的字面单花括号 `{` / `}` 原样保留，无需转义（如 JSON 示例可直接书写）。
"""

import re
from pathlib import Path

# prompts/ 位于项目根（app/core/prompts.py 的上上级）
PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

# 占位符：{{name}}
_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def prompt_path(subdir: str, name: str, *, version: int = 1) -> Path:
    """返回某个版本化 prompt 模板的文件路径。

    :param subdir: prompts/ 下的子目录，如 "experience" / "jd" / "interview" / "core"
    :param name: 模板名（不含版本后缀与扩展名）
    :param version: 版本号，默认 1
    :return: 模板文件绝对路径
    """
    return PROMPTS_DIR / subdir / f"{name}_v{version}.txt"


def _fill(template: str, kwargs: dict) -> str:
    """把模板中的 `{{name}}` 占位符替换为 kwargs 中的值。

    :param template: 模板文本
    :param kwargs: 占位符实参
    :return: 填充后的文本
    :raises KeyError: 模板引用了未提供的占位符
    """

    def _repl(match: "re.Match[str]") -> str:
        key = match.group(1)
        if key not in kwargs:
            raise KeyError(f"prompt 缺少占位符实参: {key}")
        return str(kwargs[key])

    return _PLACEHOLDER_RE.sub(_repl, template)


def load_prompt(subdir: str, name: str, *, version: int = 1, **kwargs: object) -> str:
    """读取并填充一个版本化 prompt 模板。

    :param subdir: 子目录名
    :param name: 模板名
    :param version: 版本号
    :param kwargs: 模板占位符对应的实参
    :return: 填充后的完整 prompt 文本
    """
    template = prompt_path(subdir, name, version=version).read_text(encoding="utf-8")
    return _fill(template, kwargs) if kwargs else template
