"""
大模型初始化模块

负责从 .env 中读取模型配置，创建统一复用的 model 实例。
所有 Agent 节点和 tools 都从这里导入 model。

`LLM_REQUEST_TIMEOUT`（秒，默认 180）给底层 HTTP 请求加真实超时：
- 防止请求挂起时被调用方"弃线程"后仍残留占用上游额度/并发槽位（评测曾因此触发账号级 429）。
- 生产下长生成场景如超过该值，可调大环境变量。
"""

import os

from dotenv import find_dotenv, load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv(find_dotenv(), override=True)

model = init_chat_model(
    model=os.getenv("LLM_model"),
    model_provider="openai",
    timeout=float(os.getenv("LLM_REQUEST_TIMEOUT", "180")),
)
