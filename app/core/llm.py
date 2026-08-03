"""
大模型初始化模块

负责从 .env 中读取模型配置，创建统一复用的 model 实例。
所有 Agent 节点和 tools 都从这里导入 model。
"""

import os

from dotenv import find_dotenv, load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv(find_dotenv(), override=True)

model = init_chat_model(
    model=os.getenv("LLM_model"),
    model_provider="openai",
)
