"""genre-researcher 子 agent（每周周报）的网页搜索工具。

Tavily 的薄封装。仅属于调研子 agent。
需在环境中设置 TAVILY_API_KEY；若缺失则简单不注册该工具（见 subagents.py），
其余助手仍可运行。
"""

from __future__ import annotations

import os
import time

from langchain_core.tools import tool
from requests.exceptions import ConnectionError as RequestsConnectionError
from tavily import TavilyClient

_MAX_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 2


@tool
def internet_search(query: str, max_results: int = 8) -> dict:
    """搜索近期新闻。用于调研某音乐类型的新动态 —
    新发行、知名艺人、趋势和活动。"""
    # 每次调用新建客户端，而非共享模块级单例 — newsletter-agent 的类型
    # 调研会在一轮中并发触发多个调用（LangGraph 的 ToolNode 在线程中
    # 并行收集 tool call），共享 TavilyClient 连接池会拿到远端已关闭的
    # keep-alive 套接字，表现为 ConnectionResetError。重试可覆盖剩余偶发重置。
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    last_error: RequestsConnectionError | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return client.search(query, max_results=max_results, topic="news")
        except RequestsConnectionError as e:
            last_error = e
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_RETRY_DELAY_SECONDS)
    raise last_error
