# python/m5/sales_assistant/test_diagnostic.py
"""Chinook 销售助手的分层诊断测试。

按顺序运行所有能力层并打印摘要。先启动两个服务，再在第二个终端运行：

    ./start.sh                          # 终端 1
    uv run python test_diagnostic.py    # 终端 2
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from langgraph_sdk import get_client

# 加载 langgraph.json 指向的同一 .env。
load_dotenv(Path(__file__).parent / ".env")

API_URL = "http://127.0.0.1:2024"
Status = Literal["PASS", "FAIL", "SKIP"]


# ---------------------------------------------------------------------------
# 结果容器
# ---------------------------------------------------------------------------

@dataclass
class Result:
    label: str
    status: Status
    detail: str = ""
    note: str = ""  # SKIP 时在摘要中显示


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _last_ai_text(messages: list) -> str:
    for msg in reversed(messages):
        if msg.get("type") == "ai":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "\n".join(
                    b["text"] for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                )
    return ""


async def _ask(client, prompt: str) -> tuple[str, list]:
    thread = await client.threads.create()
    _, messages = await _ask_in_thread(client, thread["thread_id"], prompt)
    return _last_ai_text(messages), messages


async def _ask_in_thread(client, thread_id: str, prompt: str) -> tuple[str, list]:
    """向已有线程发送跟进消息，每 5 秒打印一个点。"""
    run = await client.runs.create(
        thread_id=thread_id,
        assistant_id=_assistant_id,
        input={"messages": [{"role": "user", "content": prompt}]},
    )
    # 手动轮询，以便等待时打印进度点。
    while True:
        state = await client.runs.get(thread_id, run["run_id"])
        if state["status"] in ("success", "error", "timeout"):
            break
        print(".", end="", flush=True)
        await asyncio.sleep(5)
    state = await client.threads.get_state(thread_id)
    messages = state["values"].get("messages", [])
    return _last_ai_text(messages), messages


def _tool_outputs(messages: list, tool_name: str) -> list[str]:
    return [
        m.get("content", "")
        for m in messages
        if m.get("type") == "tool" and m.get("name") == tool_name
    ]


_assistant_id: str = "agent"

def _reset_inbox() -> None:
    subprocess.run(
        ["uv", "run", "python", "mcp/send_to_inbox.py", "--reset"],
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------

async def test_server_reachable(client) -> Result:
    label = "LangGraph server — reachable at port 2024"
    print(f"  Running: {label}...", end=" ", flush=True)
    try:
        await client.assistants.search()
        print("done")
        return Result(label, "PASS")
    except Exception as exc:
        print("done")
        return Result(label, "FAIL",
                      f"{exc} — is ./start.sh running?")


async def test_hello(client) -> Result:
    label = "Hello — LLM connectivity"
    print(f"  Running: {label}...", end=" ", flush=True)
    try:
        reply, _ = await _ask(client, "Hello! Just say hi back in one sentence.")
        if reply:
            print("done")
            return Result(label, "PASS", textwrap.shorten(reply, 80))
        print("done")
        return Result(label, "FAIL", "(empty reply)")
    except Exception as exc:
        print("done")
        return Result(label, "FAIL", str(exc))


async def test_agents_md(client) -> Result:
    label = "AGENTS.md — memory file loaded"
    print(f"  Running: {label}...", end=" ", flush=True)
    try:
        reply, _ = await _ask(
            client,
            "Repeat the diagnostic token from your operating manual. "
            "It appears as italic text near the top of the file.",
        )
        passed = "CHINOOK-READY" in reply
        print("done")
        return Result(label, "PASS" if passed else "FAIL",
                      textwrap.shorten(reply, 80))
    except Exception as exc:
        print("done")
        return Result(label, "FAIL", str(exc))


async def test_skills_loaded(client) -> Result:
    label = "skills/ — playbooks readable"
    print(f"  Running: {label}...", end=" ", flush=True)
    try:
        reply, _ = await _ask(
            client,
            "What task playbooks or skills do you have available? List their names.",
        )
        keywords = ["rfq", "quote", "newsletter", "territory"]
        passed = any(kw in reply.lower() for kw in keywords)
        print("done")
        return Result(label, "PASS" if passed else "FAIL",
                      textwrap.shorten(reply, 80))
    except Exception as exc:
        print("done")
        return Result(label, "FAIL", str(exc))


async def test_chinook_analyst(client) -> Result:
    label = "chinook-analyst — database query"
    print(f"  Running: {label}...", end=" ", flush=True)
    try:
        reply, _ = await _ask(client, "How many tracks are in the Chinook database?")
        passed = "3503" in reply or "3,503" in reply
        print("done")
        return Result(label, "PASS" if passed else "FAIL",
                      textwrap.shorten(reply, 80))
    except Exception as exc:
        print("done")
        return Result(label, "FAIL", str(exc))


async def test_code_interpreter(client) -> Result:
    label = "Code interpreter — exact arithmetic"
    print(f"  Running: {label}...", end=" ", flush=True)
    try:
        reply, _ = await _ask(
            client,
            "Use the code interpreter to calculate: 37 tracks at $0.99 each. "
            "What is the exact total?",
        )
        passed = "36.63" in reply
        print("done")
        return Result(label, "PASS" if passed else "FAIL",
                      textwrap.shorten(reply, 80))
    except Exception as exc:
        print("done")
        return Result(label, "FAIL", str(exc))


async def test_mail_tool_names(client) -> Result:
    label = "inbox-manager — MCP tool names discovered correctly"
    print(f"  Running: {label}...", end=" ", flush=True)
    try:
        from agent import MAIL_SERVER
        from langchain_mcp_adapters.client import MultiServerMCPClient

        mcp_client = MultiServerMCPClient({"mock-mail": MAIL_SERVER})
        tools = await mcp_client.get_tools()
        names = {t.name for t in tools}
        expected = {"mail_list_messages", "mail_read_message", "mail_create_draft"}
        missing = expected - names
        passed = not missing
        detail = f"found: {sorted(names)}" if passed else f"missing: {sorted(missing)}"
        print("done")
        return Result(label, "PASS" if passed else "FAIL", detail)
    except Exception as exc:
        print("done")
        return Result(label, "FAIL", str(exc))


async def test_inbox_manager(client) -> Result:
    label = "inbox-manager — mail MCP tool call"
    print(f"  Running: {label}...", end=" ", flush=True)
    _reset_inbox()
    try:
        reply, _ = await _ask(client, "Do I have any messages in my inbox?")
        passed = "morgan" in reply.lower() or "message" in reply.lower()
        print("done")
        return Result(label, "PASS" if passed else "FAIL",
                      textwrap.shorten(reply, 80))
    except Exception as exc:
        print("done")
        return Result(label, "FAIL", str(exc))


async def test_hitl_interrupt(client) -> Result:
    label = "Human-in-the-loop — draft triggers interrupt"
    print(f"  Running: {label}...", end=" ", flush=True)
    try:
        thread = await client.threads.create()
        run = await client.runs.create(
            thread_id=thread["thread_id"],
            assistant_id=_assistant_id,
            input={"messages": [{"role": "user", "content":
                "Draft a reply to the email from Morgan Vale saying we will get "
                "back to them within 24 hours. Save the draft."
            }]},
        )
        await client.runs.join(thread["thread_id"], run["run_id"])
        state = await client.threads.get_state(thread["thread_id"])
        tasks = state.get("tasks", [])
        interrupted = any(t.get("interrupts") for t in tasks if isinstance(t, dict))
        print("done")
        return Result(label, "PASS" if interrupted else "FAIL",
                      "interrupt fired" if interrupted else "run completed without interrupt")
    except Exception as exc:
        print("done")
        return Result(label, "FAIL", str(exc))



async def test_sandbox_chart(client) -> Result:
    label = "sandbox chart — agent writes+runs matplotlib, chart lands in sandbox outputs/"
    print(f"  Running: {label}...", end=" ", flush=True)
    try:
        thread = await client.threads.create()
        _, messages = await _ask_in_thread(
            client, thread["thread_id"],
            "Query the Chinook database for total revenue by genre (top 5 genres). "
            "Write and run a Python script to save a pie chart as "
            "/home/daytona/outputs/diag_genre_revenue.png.",
        )
        tool_outs = _tool_outputs(messages, "execute")
        from daytona import Daytona, DaytonaConfig, DaytonaNotFoundError

        daytona = Daytona(DaytonaConfig(api_key=os.getenv("DAYTONA_API_KEY")))
        sb = await asyncio.to_thread(daytona.get, f"thread-{thread['thread_id']}")

        try:
            root = (sb.get_work_dir() or sb.get_user_home_dir() or "").rstrip("/")
            content = await asyncio.to_thread(
                sb.fs.download_file, f"{root}/outputs/diag_genre_revenue.png")
            passed = len(content) > 0
            detail = f"{len(content):,} bytes"
        except Exception as e:
            passed = False
            detail = f"file missing/download failed: {e}; execute returned: {tool_outs}"
        print("done")
        return Result(label, "PASS" if passed else "FAIL", detail)
    except Exception as exc:
        print("done")
        return Result(label, "FAIL", str(exc))


async def test_async_genre_research(client) -> Result:
    label = "newsletter-agent (async) — background launch + ask-again newsletter save"
    print(f"  Running: {label}...", end=" ", flush=True)
    try:
        thread = await client.threads.create()
        thread_id = thread["thread_id"]

        # 固定为两种类型，避免测试先调用 chinook-analyst 查类型，
        # 且只触发两次真实 Tavily 搜索而非四次。
        launch_reply, launch_messages = await _ask_in_thread(
            client, thread_id,
            "Create this week's newsletter for exactly these two genres: "
            "Jazz and Rock. Do not ask chinook-analyst for genres.",
        )

        # 启动轮应恰好触发一个异步任务（整个周报任务）然后停止，
        # 不应阻塞等待 — 通过 SDK 检查，而非从消息文本推断。
        state = await client.threads.get_state(thread_id)
        tasks = state["values"].get("async_tasks", {})
        launched_non_blocking = len(tasks) == 1
        if not launched_non_blocking:
            print("done")
            return Result(label, "FAIL",
                          f"expected exactly 1 async task after launch turn, got {len(tasks)}: {textwrap.shorten(launch_reply, 80)}")

        # 不再有完成通知器 — 不会自动唤醒本线程，
        # 也不会调用 `check_async_task`/`list_async_tasks`，
        # 因此本线程状态中缓存的 `status` 字段不会刷新（deepagents 仅在这些
        # 工具的副作用中刷新 — 见 `deepagents.middleware.async_subagents` 的
        # `_afetch_live_status`）。改为通过 SDK 直接轮询子 agent run 的实时状态，
        # 然后显式询问线程是否就绪，这才触发主 agent 的检查并保存轮次。
        task = next(iter(tasks.values()))
        deadline = asyncio.get_event_loop().time() + 600
        run_status = task["status"]
        while asyncio.get_event_loop().time() < deadline:
            run_state = await client.runs.get(thread_id=task["thread_id"], run_id=task["run_id"])
            run_status = run_state["status"]
            if run_status in ("success", "error", "cancelled", "timeout", "interrupted"):
                break
            print(".", end="", flush=True)
            await asyncio.sleep(5)
        else:
            print("done")
            return Result(label, "FAIL", f"task never reached a terminal status: {run_status}")
        statuses = {task["task_id"]: run_status}

        _, followup_messages = await _ask_in_thread(client, thread_id, "Is the newsletter ready?")

        from daytona import Daytona, DaytonaConfig

        daytona = Daytona(DaytonaConfig(api_key=os.getenv("DAYTONA_API_KEY")))
        sb = await asyncio.to_thread(daytona.get, f"thread-{thread_id}")

        listing = await asyncio.to_thread(
            sb.process.exec, 
            f"find {(sb.get_work_dir() or sb.get_user_home_dir() or '').rstrip('/')}/outputs -maxdepth 1 -type f -name 'newsletter-*.html'",
        )
        newsletter_files = [line for line in (listing.result or "").splitlines() if line.strip()]

        passed = bool(newsletter_files)
        detail = f"newsletter: {newsletter_files}, task statuses: {statuses}" if passed else \
            f"no newsletter after follow-up; task statuses: {statuses}, reply: {textwrap.shorten(_last_ai_text(followup_messages), 80)}"
        print("done")
        return Result(label, "PASS" if passed else "FAIL", detail)
    except Exception as exc:
        print("done")
        return Result(label, "FAIL", str(exc))


# ---------------------------------------------------------------------------
# 运行器
# ---------------------------------------------------------------------------

TESTS = [
    test_server_reachable,
    test_hello,
    test_agents_md,
    test_skills_loaded,
    test_chinook_analyst,
    test_code_interpreter,
    test_mail_tool_names,
    test_inbox_manager,
    test_hitl_interrupt,
    test_sandbox_chart,
    test_async_genre_research,
]


async def main() -> None:
    client = get_client(url=API_URL)

    print(f"\nChinook Sales Assistant — Diagnostic\n{'─' * 42}\n")

    results: list[Result] = []

    for test_fn in TESTS:
        result = await test_fn(client)
        results.append(result)

        # 若服务不可达则立即停止 — 其余测试也会失败。
        if test_fn is test_server_reachable and result.status == "FAIL":
            print("  (server not reachable — skipping remaining tests)")
            break

    # 摘要
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    skipped = sum(1 for r in results if r.status == "SKIP")

    print(f"\n{'─' * 42}")
    print("Summary\n")
    icons = {"PASS": "✓", "FAIL": "✗", "SKIP": "–"}
    for r in results:
        icon = icons[r.status]
        print(f"  {icon}  {r.label}")
        if r.status == "FAIL" and r.detail:
            print(f"       {textwrap.shorten(r.detail, 72)}")
        if r.status == "SKIP" and r.note:
            print(f"       ({r.note})")

    totals = f"{passed} passed"
    if failed:
        totals += f", {failed} failed"
    if skipped:
        totals += f", {skipped} skipped"
    print(f"\n{totals}")
    print(f"{'─' * 42}\n")


if __name__ == "__main__":
    asyncio.run(main())
