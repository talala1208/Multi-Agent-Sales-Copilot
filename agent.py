# python/m5/sales_assistant_sandbox/agent.py
"""Chinook 销售助手。

整个文件系统 — 技能、记忆以及 agent 写入或运行的任何内容 —
都位于按线程划分的 Daytona 沙箱内。创建沙箱时，会从本地磁盘一次性
将技能和 AGENTS.md 播种进去。运行时没有 agent 可读写的本地文件系统路径，
因此不可信执行结果无法桥接回主机。

图表没有专用工具：agent 用 write_file 写 Python 脚本，再用 execute 运行
（因后端支持沙箱命令执行而自动添加），与运行其他生成代码的方式相同。

启动方式：
    ./start.sh
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shlex
from pathlib import Path
from dotenv import load_dotenv
from daytona import(
    Daytona, 
    DaytonaConfig, 
    CreateSandboxFromSnapshotParams, 
    SandboxState,
    DaytonaNotFoundError,
)
from langchain_daytona import DaytonaSandbox

from async_research import build_async_research_middleware
from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from langchain_core.runnables import RunnableConfig
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_quickjs import CodeInterpreterMiddleware
from langgraph_sdk.runtime import ServerRuntime
from subagents import build_subagents
from tools.html import markdown_to_html

from models import strong_model

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

# Daytona 沙箱用户写不了容器根 `/`，一律用工作目录（通常是 /home/daytona）。
DEFAULT_ROOT = "/home/daytona"
_LESSON_PREFIXES = ("/AGENTS.md", "/outputs", "/skills", "/agents", "/research")


def _writable_root(sandbox) -> str:
    work_dir = (sandbox.get_work_dir() or "").rstrip("/")
    if work_dir in {"", "/"}:
        work_dir = (sandbox.get_user_home_dir() or "").rstrip("/")
    if work_dir in {"", "/"}:
        raise RuntimeError("Daytona sandbox has no writable work directory")
    return work_dir


def _lesson_to_root(text: str, root: str) -> str:
    rewritten = text
    for virt in _LESSON_PREFIXES:
        rewritten = rewritten.replace(virt, f"{root}{virt}")
    return rewritten


def _system_prompt(root: str) -> str:
    return (
        "You are a sales assistant for Jane Peacock, a Sales Support Agent at "
        "Chinook, an online music distributor. Follow your operating manual (loaded "
        f"from your memory) and use the matching playbook from {root}/skills/ for each task.\n\n"
        "Your entire filesystem — skills, memory, and anything you write — lives "
        "inside an isolated sandbox; there is no separate local filesystem. To "
        "produce a chart, write a Python script with write_file and run it with "
        "execute (e.g. `pip install matplotlib && python3 <script>`), saving the "
        f"image under {root}/outputs/."
    )


MAIL_SERVER = {"transport": "streamable-http", "url": "http://127.0.0.1:5002/mcp"}

_enable_search = bool(os.environ.get("TAVILY_API_KEY"))
if not _enable_search:
    logger.info("TAVILY_API_KEY not set — newsletter research subagent disabled.")


def _lookup_or_create(name: str) -> tuple:
    """返回线程级沙箱的 (sandbox, freshly_created)。

    复用就绪沙箱、重启已停止沙箱、等待过渡状态，或创建新沙箱 —
    无论结果如何查找模式相同，使线程的后续轮次落在与首次相同的沙箱中。
    """
    
    config = DaytonaConfig(api_key=os.getenv("DAYTONA_API_KEY"))
    daytona = Daytona(config)

    try:
        sb = daytona.get(name)
    except DaytonaNotFoundError:
        sb = None
    
    if sb is not None:
        if sb.state == SandboxState.STARTED:
            logger.info("Reusing sandbox %s", name)
            return sb, False
        if sb.state == SandboxState.STOPPED:
            logger.info("Restarting stopped sandbox %s", name)
            daytona.start(sb, timeout=15)
            return sb, False
        daytona.start(sb, timeout=15)
        return sb, False
    
    sb = daytona.create(
        CreateSandboxFromSnapshotParams(
            name=name,
            language="python",
        )
    )
    logger.info("Created sandbox %s", name)
    return sb, True
    


def _seed_skills_and_memory(backend: DaytonaSandbox, root: str) -> None:
    """把本地 skills 和 AGENTS.md 上传到沙箱工作目录。"""
    def _bytes(path: Path) -> bytes:
        raw = path.read_bytes()
        if path.suffix.lower() in {".md", ".txt"}:
            return _lesson_to_root(raw.decode("utf-8"), root).encode("utf-8")
        return raw

    files: list[tuple[str, bytes]] = [(f"{root}/AGENTS.md", _bytes(HERE / "AGENTS.md"))]
    parents: set[str] = {f"{root}/skills", f"{root}/outputs"}
    for path in (HERE / "skills").rglob("*"):
        if path.is_file():
            dest = f"{root}/skills/{path.relative_to(HERE / 'skills').as_posix()}"
            files.append((dest, _bytes(path)))
            parent = str(Path(dest).parent)
            while parent not in {"/", ""}:
                parents.add(parent)
                parent = str(Path(parent).parent)
    dirs = " ".join(shlex.quote(p) for p in sorted(parents, key=lambda p: (p.count("/"), p)))
    mkdir = backend.execute(f"mkdir -p {dirs}")
    if mkdir.exit_code not in (0, None):
        raise RuntimeError(f"Failed to create seed directories: {mkdir.output}")
    results = backend.upload_files(files)
    failures = [
        f"{path}: {result.error}"
        for (path, _), result in zip(files, results)
        if result.error
    ]
    if failures:
        raise RuntimeError("Failed to seed sandbox files: " + "; ".join(failures))


async def _sandbox_backend_for_thread(thread_id: str) -> tuple[DaytonaSandbox, str]:
    """查找（或创建）该线程的沙箱；若为新沙箱则播种文件。"""
    sandbox, freshly_created = await asyncio.to_thread(_lookup_or_create, f"thread-{thread_id}")
    root = await asyncio.to_thread(_writable_root, sandbox)
    backend = DaytonaSandbox(sandbox=sandbox)
    listing = None if freshly_created else await asyncio.to_thread(backend.ls, f"{root}/skills")
    needs_seed = freshly_created or (listing is not None and (listing.error or not listing.entries))
    if needs_seed:
        await asyncio.to_thread(_seed_skills_and_memory, backend, root)
    return backend, root


# 按线程划分的沙箱模式：
# https://docs.langchain.com/langsmith/graph-rebuild#context-manager-factory
#
# 工厂接受 ServerRuntime，以便服务端区分是在处理真实 run（execution_runtime 非 None）
# 还是在处理自省调用（get_schema、get_graph、assistants.read 等）。当 execution_runtime
# 为 None 时跳过沙箱设置，回退到内存后端 — 图拓扑相同，无沙箱，完全无法访问真实文件系统。
# 真实 run 按 thread_id 查找各自的线程级沙箱。
@contextlib.asynccontextmanager
async def make_graph(config: RunnableConfig, runtime: ServerRuntime):
    if runtime.execution_runtime:
        thread_id = config.get("configurable", {}).get("thread_id")
        backend, root = await _sandbox_backend_for_thread(thread_id)
    else:
        backend = StateBackend()
        root = DEFAULT_ROOT

    client = MultiServerMCPClient({"mock-mail": MAIL_SERVER})
    mail_tools = await client.get_tools()
    middleware = [CodeInterpreterMiddleware(ptc=["execute", "write_file"])]
    if _enable_search:
        middleware.append(build_async_research_middleware())
    yield create_deep_agent(
        model=strong_model,
        tools=[markdown_to_html] + mail_tools,
        system_prompt=_system_prompt(root),
        subagents=build_subagents(backend, mail_tools=mail_tools, root=root),
        skills=[f"{root}/skills"],
        memory=[f"{root}/AGENTS.md"],
        backend=backend,
        middleware=middleware,
        name="chinook-sales-assistant",
    )
