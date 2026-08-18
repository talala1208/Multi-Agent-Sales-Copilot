"""newsletter-agent：作为异步子 agent 启动的独立图。

在 langgraph.json 中注册为独立入口，使主 agent 的 `AsyncSubAgentMiddleware`
可通过 LangGraph SDK 启动并立即返回，而不阻塞进程内子 agent 调用。

与早期设计（见 git 历史：genre_researcher_graph.py）不同，本图自行完成
*完整*周报任务 — 调研所有类型并组装完成的 HTML — 而非主 agent 需汇总的
四次并行异步启动之一。内部以常规*同步*方式（`task` 工具，与主 agent 其他
专家相同机制）委派 genre-researcher 子 agent：这些调用在本图单次 run 内
进程内并行发生，无需跨线程汇总。

此处无完成通知中间件（见 git 历史：completion_notifier.py）— 主 agent 以常规
方式得知任务完成：下次被询问时调用 `check_async_task`/`list_async_tasks`，
而非被跨线程 run 唤醒。这使本图可以是静态对象而非每 run 的异步工厂。

存储：`StoreBackend` 按本 run 的 thread_id 命名空间，在 namespace lambda 内
通过 `get_config()` 惰性解析 — 仅在真实 run 中后端实际执行 store 操作时调用，
而非构图时，因此构建本图无需工厂/`config` 参数。每次 `start_async_task` 在此
创建新线程，thread_id 已是唯一、无冲突的命名空间 — 无需跨图转发 ID。
省略 `store=` 会在运行时解析为 `get_store()`，与主图使用同一 store 实例
（两图共享同一部署）。genre-researcher 子 agent 继承相同后端（子 agent 除非
自行设置否则继承父后端），其 `/research/<genre>/sources.md` 转储也落在本 run
命名空间内。
"""

from __future__ import annotations

import os

from deepagents import create_deep_agent
from deepagents.backends.store import StoreBackend
from langgraph.config import get_config
from subagents import GENRE_PROMPT
from tools.html import markdown_to_html

from models import model, strong_model

# 本模块始终被 langgraph 平台导入（langgraph.json 中注册的图），
# 无论主 agent 是否暴露其启动工具 — 因此导入 tools.search（在导入时
# 从 TAVILY_API_KEY 实例化 Tavily 客户端）也必须在此条件化，与 agent.py
# 的 `_enable_search` 守卫一致，尽管已无工厂体可延迟导入。
_enable_search = bool(os.environ.get("TAVILY_API_KEY"))
if _enable_search:
    from tools.search import internet_search

    _genre_researcher_tools = [internet_search]
else:
    _genre_researcher_tools = []

NEWSLETTER_AGENT_PROMPT = """You assemble Chinook's weekly "This Week in \
Music" customer newsletter. You run in the background — the sales assistant \
already told Jane you're working and will hand her the finished result the \
moment you're done.

You will be given a list of genres to cover. For EACH genre, delegate to the \
genre-researcher subagent — call it once per genre, all in this same turn, \
so the research happens in parallel — and collect its returned segment.

Once every genre-researcher call has returned:
1. Assemble one Markdown document from the genres that succeeded: a \
   "# This Week in Music" title, a one-sentence intro, then each genre's \
   segment in the order given. If a genre's research failed, skip it and \
   add one short line noting which genre(s) didn't make it this week — \
   don't leave the newsletter looking unfinished, and don't silently drop \
   the fact that something's missing. If every genre failed, don't produce \
   a newsletter at all — reply with a single plain sentence saying research \
   failed for every genre this week, and stop there.
2. Call `markdown_to_html` on the assembled Markdown.

Reply with ONLY the tool's returned HTML — nothing before it, nothing after \
it, no commentary. Your reply is written directly to a file verbatim; any \
extra sentence you add around the HTML ends up inside that file too."""

_genre_researcher = {
    "name": "genre-researcher",
    "description": (
        "Research one music genre and write a newsletter segment about "
        "what's new in it. Call once per genre, in parallel."
    ),
    "system_prompt": GENRE_PROMPT,
    "tools": _genre_researcher_tools,
    "model": model,
}

_backend = StoreBackend(
    namespace=lambda rt: (get_config()["configurable"]["thread_id"], "research")
)

graph = create_deep_agent(
    model=strong_model,
    tools=[markdown_to_html],
    system_prompt=NEWSLETTER_AGENT_PROMPT,
    subagents=[_genre_researcher],
    backend=_backend,
    name="newsletter-agent",
)
