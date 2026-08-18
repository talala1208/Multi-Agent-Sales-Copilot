# python/m5/sales_assistant_sandbox/async_research.py
"""newsletter-agent 异步子 agent 的 AsyncSubAgentMiddleware 配置。"""

from deepagents.middleware.async_subagents import AsyncSubAgentMiddleware


def build_async_research_middleware() -> AsyncSubAgentMiddleware:
    """配置 `AsyncSubAgentMiddleware`，接入同部署的 newsletter-agent 图，
    使用未修改的默认 `start_async_task` 工具 — newsletter-agent 不需要
    传入父线程上下文，启动调用无需额外参数。"""
    return AsyncSubAgentMiddleware(
        async_subagents=[
            {
                "name": "newsletter-agent",
                "description": (
                    "Research this week's featured music genres and assemble the "
                    "styled HTML newsletter in the background. Launch it once per "
                    "newsletter request and keep working; check back on it later "
                    "with `check_async_task`/`list_async_tasks` to get the finished "
                    "HTML."
                ),
                "graph_id": "newsletter-agent",
            }
        ]
    )
