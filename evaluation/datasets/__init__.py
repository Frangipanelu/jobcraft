"""
Evaluation 数据集加载辅助。

gold 数据集为 jsonl，每行一条 case（1 岗位 + 多经历 + 人工标注），
结构与 evaluation/run_matching_eval.py 期望的输入一致。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_DATASET = Path(__file__).parent / "matching_cases.jsonl"
REAL_JD_DATASET = Path(__file__).parent / "real_jd_cases.jsonl"


def load_cases(path: Path | None = None) -> list[dict[str, Any]]:
    """加载 gold 数据集，返回 case dict 列表。

    :param path: 数据集路径，缺省用默认数据集
    :return: 每行一个 dict 的列表
    """
    p = path or DEFAULT_DATASET
    lines = p.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def load_real_cases(path: Path | None = None) -> list[dict[str, Any]]:
    """加载真实/草稿 JD 语料（v0.5 §二十六 real-JD 分层评测）。

    结构同 jd_cases，额外字段：
    - ``source``：jd021 原始来源（如 "real:boss" / "draft"）
    - ``gold_pending``：True 表示 gold 尚未人工完成（框架占位）

    :param path: 数据集路径，缺省 real_jd_cases.jsonl
    :return: case 列表
    """
    p = path or REAL_JD_DATASET
    if not p.exists():
        p.touch()
    return load_cases(p)
