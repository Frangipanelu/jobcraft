"""AI 调用元数据审计持久化（TASK-AI-002）。

在 `llm_json.invoke_structured` 结构化 LLM chokepoint 处记录每次调用的
status/model/input_hash/schema_name/prompt_hash 到 `ai_tasks`，并把结构化
输出写入 `ai_outputs`。

设计约束：
- **尽力而为 / 非阻塞**：审计失败（DB 不可用、表缺失、写入异常）绝不抛出，也绝不影响
  业务 LLM 调用。所有异常在此被捕获并记录日志。
- **前向兼容**：token 用量列（prompt_tokens/completion_tokens/total_tokens）与 from_cache
  列均为可空；AI-003 起由本模块写入 token 用量与缓存命中标记。
- 表结构由迁移 `migrations/versions/V0003__ai_audit.sql` 建立，本模块不做 DDL。
"""

import hashlib
import logging
from typing import Any, Dict, Optional

from mysql.connector import connect

from app.tools.db_tools import _jc_config

logger = logging.getLogger("jobcraft.tools.db_ai")

_STATUS_RUNNING = "running"
_STATUS_SUCCESS = "success"
_STATUS_ERROR = "error"


def sha256_hex(text: str) -> str:
    """对文本做 sha256 十六进制摘要（用于 input_hash / prompt_hash）。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def create_ai_task(
    *,
    feature: str,
    model: str,
    schema_name: str,
    prompt_hash: str,
    input_hash: str,
    prompt_version: str = "",
) -> Optional[int]:
    """记录一次 AI 调用开始，返回 ai_tasks.id；失败返回 None（不抛出）。

    :param feature: 功能标识（debug_label / schema 名）
    :param model: 模型名
    :param schema_name: 输出 Pydantic schema 名
    :param prompt_hash: prompt 文本的 sha256
    :param input_hash: 输入（prompt + schema）的 sha256，用于去重
    :param prompt_version: prompt 模板版本，可空
    :return: 新行 id；记录失败返回 None
    """
    try:
        with connect(**_jc_config()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_tasks
                        (feature, model, schema_name, prompt_version,
                         input_hash, prompt_hash, status, started_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        feature,
                        model,
                        schema_name,
                        prompt_version,
                        input_hash,
                        prompt_hash,
                        _STATUS_RUNNING,
                    ),
                )
                return cur.lastrowid
    except Exception:
        logger.exception("create_ai_task 审计写入失败，忽略")
        return None


def complete_ai_task(
    *,
    task_id: Optional[int],
    status: str,
    latency_ms: int,
    schema_name: str = "",
    error: Optional[str] = None,
    output_json: Optional[Dict[str, Any]] = None,
    schema_version: str = "",
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    from_cache: Optional[int] = None,
) -> None:
    """收尾一次 AI 调用：可选写 ai_outputs，并更新 ai_tasks 状态。

    本函数绝不抛出（尽力而为），失败仅记日志。

    :param task_id: ai_tasks.id；为 None 时跳过（记录开始失败则无需收尾）
    :param status: success / error
    :param latency_ms: 调用耗时（毫秒）
    :param schema_name: 输出 schema 名
    :param error: 失败原因文本（status=error 时）
    :param output_json: 结构化输出 dict（status=success 时）
    :param schema_version: schema 版本，可空
    :param prompt_tokens: 输入 token 数（AI-003 usage），可空
    :param completion_tokens: 输出 token 数（AI-003 usage），可空
    :param total_tokens: 总 token 数（AI-003 usage），可空
    :param from_cache: 1=结果来自 AI 热缓存，0/NULL=实际调用 LLM，可空
    """
    if task_id is None:
        return
    try:
        with connect(**_jc_config()) as conn:
            with conn.cursor() as cur:
                if status == _STATUS_SUCCESS and output_json is not None:
                    cur.execute(
                        """
                        INSERT INTO ai_outputs
                            (task_id, schema_name, schema_version, output_json)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (task_id, schema_name, schema_version, _dump_json(output_json)),
                    )
                cur.execute(
                    """
                    UPDATE ai_tasks
                       SET status = %s, error = %s, latency_ms = %s,
                           prompt_tokens = %s, completion_tokens = %s,
                           total_tokens = %s, from_cache = %s,
                           finished_at = NOW()
                     WHERE id = %s
                    """,
                    (
                        status,
                        error,
                        latency_ms,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                        from_cache,
                        task_id,
                    ),
                )
    except Exception:
        logger.exception("complete_ai_task 审计写入失败，忽略")


def _dump_json(value: Dict[str, Any]) -> str:
    """把结构化输出转成 JSON 字符串，供 JSON 列存储。"""
    import json

    return json.dumps(value, ensure_ascii=False, default=str)
