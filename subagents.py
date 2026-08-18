"""Chinook 销售助手的专家子 agent。

通过函数构建而非在导入时定义，因为 chinook-analyst 的 MemoryMiddleware 需要
与主 agent 相同的*文件系统后端*（使其发现的 schema 与读取的记忆指向同一磁盘文件）。

- chinook-analyst — 负责数据库；将 schema 自举写入自己的 AGENTS.md；新客户写入需人工审批。
- inbox-manager   — 负责邮件（MCP）工具；保存草稿需人工审批。仅在发现邮件工具时存在。
- quote-reviewer  — 在报价发出前对草稿报价做合理性检查。

genre-researcher 仍是进程内（同步）子 agent，但不属于主 agent — 它用在
newsletter-agent 独立图中（见 `newsletter_agent_graph.py`），通过
`AsyncSubAgentMiddleware` 启动，使整个周报任务（调研 + 组装）在后台运行，
而不阻塞主 agent。`GENRE_PROMPT` 保留在本模块并由其导入。

inbox-manager 放在子 agent 中的原因：通用子 agent（始终存在）会继承主 agent 的
工具，因此放在主 agent 上的任何门控工具都可能通过委派被无门控调用。将
`mail_create_draft` 和 `add_customer` 仅放在门控专家上，意味着通往这两类写入
的唯一路径都会经过对应的人工审批门。
"""

from __future__ import annotations

from deepagents import MemoryMiddleware
from deepagents.backends.protocol import BackendProtocol
from tools.sql import add_customer, introspect_schema, query_chinook

from models import model, strong_model

# 门控写入允许三种 agent-inbox 决策。
_APPROVE_EDIT_REJECT = {"allowed_decisions": ["approve", "edit", "reject"]}


ANALYST_PROMPT = """You are the chinook-analyst, the data specialist for the \
Chinook Sales Assistant. You are the only agent that touches the database.

Detailed operating instructions and the database schema live in your memory \
(loaded automatically). Follow them. In short: answer with exact figures from \
`query_chinook`, learn the schema once with `introspect_schema` and record it \
in your memory, and use `add_customer` only when asked to add a genuinely new \
customer (a human approves that write)."""

INBOX_PROMPT = """You are the inbox-manager, the email specialist for the \
Chinook Sales Assistant. You own Jane's inbox and are the only agent that \
touches it.

Your tools (MCP, prefixed with the server name "mail"):
- `mail_list_messages` — list inbox messages (optionally filtered by a query).
- `mail_read_message` — read one message in full by id.
- `mail_create_draft` — save a reply to the drafts folder. It NEVER sends.

When asked to find or read mail, return a tight summary the caller can act on \
(sender, subject, and the key content) — not the raw dump.

When asked to save a draft, just call `mail_create_draft` with the given \
recipient, subject, and body. Saving a draft pauses automatically for Jane to \
approve, edit, or reject — that pause IS the approval, so don't ask for \
permission in prose first; make the call. Never invent a send tool; you only \
ever create drafts."""

REVIEWER_PROMPT = """You are the quote-reviewer. You receive a drafted quote — \
line items (description, quantity, unit price, line total), any discount, and \
the grand total — and you check it before it goes to the customer.

Verify:
- The arithmetic: quantity x unit price for each line, and the grand total.
- Internal consistency: any stated discount is actually applied; nothing is \
double-counted or missing.
- Plausibility: unit prices look like catalogue prices (tracks are normally \
about $0.99); totals aren't off by an order of magnitude.

Reply concisely: either "Looks correct" with a one-line confirmation, or a \
short list of specific corrections. Do not rewrite the customer email — just \
review the numbers and terms."""

GENRE_PROMPT = """You are a music journalist researching one genre for an \
online music distributor's weekly newsletter.

You will be given a single genre and a private research folder to work in.

How to work:
1. Use internet_search to find recent, noteworthy developments in that genre \
   — new releases, notable artists, trends, or events. Run a few searches.
2. Save the COMPLETE, verbatim output of ALL your searches to a single file: \
   write_file("/research/<genre>/sources.md", ...). Do NOT summarize or trim. \
   This keeps the bulky material out of the editor's context.
3. Only then, from what you found, write one tight newsletter segment.

Return ONLY the finished segment as your reply:
- A markdown section: a "## <Genre>" heading followed by ~120-180 words.
- Lively but factual; name specific artists and releases.
- Do NOT paste raw search results into your reply — those live in your files."""


def build_subagents(
    backend: BackendProtocol,
    *,
    mail_tools: list,
    root: str = "/home/daytona",
) -> list[dict]:
    """返回子 agent 规格，接入共享文件系统后端。"""

    chinook_analyst = {
        "name": "chinook-analyst",
        "description": (
            "Query the Chinook database for catalogue prices, customer records, "
            "purchase history, and territory metrics, and add new customers "
            "(with approval). Delegate all database work here."
        ),
        "system_prompt": ANALYST_PROMPT,
        "tools": [query_chinook, introspect_schema, add_customer],
        "model": model,
        # 每个子 agent 独立记忆：自己的 AGENTS.md，与主 agent 相同后端，
        # 写入的 schema 即后续读取的 schema。
        "middleware": [
            MemoryMiddleware(
                backend=backend,
                sources=[f"{root}/agents/chinook-analyst/AGENTS.md"],
            )
        ],
        # 唯一的门控写入 — 插入前暂停等待人工审批。
        "interrupt_on": {"add_customer": _APPROVE_EDIT_REJECT},
    }

    quote_reviewer = {
        "name": "quote-reviewer",
        "description": (
            "Review a drafted quote (line items, discount, total) for correct "
            "arithmetic and sane pricing before it is sent. Send it the numbers."
        ),
        "system_prompt": REVIEWER_PROMPT,
        "model": strong_model,
    }

    inbox_manager = {
        "name": "inbox-manager",
        "description": (
            "Read Jane's inbox and save reply drafts. Delegate any "
            "email work here: finding/reading messages and creating a "
            "draft reply (which pauses for Jane's approval)."
        ),
        "system_prompt": INBOX_PROMPT,
        "tools": mail_tools,
        "model": model,
        "interrupt_on": {"mail_create_draft": _APPROVE_EDIT_REJECT},
    }

    return [chinook_analyst, quote_reviewer, inbox_manager]
