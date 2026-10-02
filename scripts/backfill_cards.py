"""经历卡回填维护脚本：单卡装整份简历的旧数据拆卡（T-M1-5）。

原 ``POST /api/jobcraft/experience/cards/backfill`` 端点按矩阵 Q1③ 裁决下线，
维护能力由本脚本承接，语义与原端点一致（调用 ``run_backfill_workflow``：
Agent + DB，单次上限 ``MAX_BACKFILL_CARDS``，单卡失败容忍）。

用法（仓库根目录执行）::

    uv run python scripts/backfill_cards.py --user-id 1 --min-chars 100

说明：

- ``--user-id`` 必填：维护脚本不提供隐式默认用户，避免误操作他人数据；
- ``--min-chars`` 对应原 payload ``min_chars``（低于该字数的卡跳过）；
- 需要真实 LLM 调用（全局 1 req/s 限流），请与主窗口错峰执行
  （AGENTS.md 多窗口互斥约束 5：仅主窗口跑 --runslow，其余错峰）。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import List, Optional

logger = logging.getLogger("jobcraft.scripts.backfill_cards")


def build_parser() -> argparse.ArgumentParser:
    """构造命令行解析器。

    Returns:
        argparse.ArgumentParser: 带 ``--user-id``（必填）与 ``--min-chars``
        的解析器；``user_id`` 无默认值，缺失时 argparse 以退出码 2 报错。
    """
    parser = argparse.ArgumentParser(
        description="经历卡回填：把单卡装整份简历的旧数据拆成多卡（维护脚本）",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        required=True,
        help="目标用户 ID（必填，无默认值，防误操作他人数据）",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=100,
        help="低于该字数的经历卡跳过（默认 100，同原端点 min_chars）",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """执行回填并返回进程退出码。

    Args:
        argv: 命令行参数列表；``None`` 时读取 ``sys.argv[1:]``。

    Returns:
        int: 成功 0；workflow 抛错 1；argparse 校验失败以 SystemExit 退出。
    """
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )

    from app.workflows.extract_flow import run_backfill_workflow

    logger.info("开始回填 user_id=%s min_chars=%s", args.user_id, args.min_chars)
    try:
        result = run_backfill_workflow(args.user_id, args.min_chars)
    except Exception as exc:  # noqa: BLE001 — 脚本边界：任何失败都转退出码 1
        logger.exception("回填失败")
        print(f"回填失败: {exc}", file=sys.stderr)
        return 1

    logger.info("回填完成: %s", result)
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
