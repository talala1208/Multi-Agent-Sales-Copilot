# python/m5/mcp/mail_store.py
"""模拟 Gmail MCP 服务器与 `send_to_inbox` 注入 CLI 共享的简易 JSON 邮箱。

存储刻意简单：一个 JSON 文件，含 ``inbox`` 和 ``drafts`` 两个列表。
使课程的 Gmail 功能可离线运行、无需 OAuth，同时呈现与真实 Gmail MCP
服务器相同的工具面（``list_messages`` / ``read_message`` / ``create_draft``）。
此处无 Gmail 特有逻辑 — 仅够演示助手所需状态。

路径从本文件位置解析，因此无论 MCP 子进程从哪个工作目录启动，存储均可用。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# 邮箱与本模块同目录，位于模块自有目录下。
_STORE_PATH = Path(__file__).resolve().parent / "mail_store.json"
_SEEDS_DIR = Path(__file__).resolve().parent / "seeds"


def _empty_store() -> dict[str, list[dict[str, Any]]]:
    return {"inbox": [], "drafts": []}


def load_store() -> dict[str, list[dict[str, Any]]]:
    """读取邮箱；首次使用时从 ``seeds/`` 播种。

    若尚无存储文件，将 ``seeds/`` 中每个 ``*.json`` 夹具载入收件箱，
    使新 checkout 即有询价请求等待处理。
    """
    if _STORE_PATH.exists():
        with _STORE_PATH.open(encoding="utf-8") as f:
            return json.load(f)

    store = _empty_store()
    for seed in sorted(_SEEDS_DIR.glob("*.json")):
        with seed.open(encoding="utf-8") as f:
            store["inbox"].append(json.load(f))
    save_store(store)
    return store


def save_store(store: dict[str, list[dict[str, Any]]]) -> None:
    """将邮箱持久化到磁盘。"""
    with _STORE_PATH.open("w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)


def next_id(messages: list[dict[str, Any]], prefix: str) -> str:
    """返回下一个顺序 id，如 ``msg-1`` / ``draft-3``。"""
    n = 1 + sum(1 for m in messages if str(m.get("id", "")).startswith(prefix))
    return f"{prefix}-{n}"
