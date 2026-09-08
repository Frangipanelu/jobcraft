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


def load_cases(path: Path | None = None) -> list[dict[str, Any]]:
    """加载 gold 数据集，返回 case dict 列表。

    :param path: 数据集路径，缺省用默认数据集
    :return: 每行一个 dict 的列表
    """
    p = path or DEFAULT_DATASET
    lines = p.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]
