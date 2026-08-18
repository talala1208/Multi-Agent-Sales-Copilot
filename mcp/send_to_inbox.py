"""向模拟邮箱投递消息 — 离线替代「客户刚给你发了邮件」。

无参数运行则从 ``seeds/`` 加载捆绑的 RFQ 夹具；或传入 --from / --subject / --body
注入自定义消息。新消息进入收件箱，助手可用 list_messages 找到。

示例：
    uv run python mcp/send_to_inbox.py
    uv run python mcp/send_to_inbox.py --reset
    uv run python mcp/send_to_inbox.py --from "a@b.example" \\
        --subject "Quote please" --body "Can I get 12 Jazz tracks?"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mail_store import _SEEDS_DIR, _empty_store, load_store, next_id, save_store


def main() -> None:
    parser = argparse.ArgumentParser(description="向模拟收件箱注入消息。")
    parser.add_argument("--from", dest="sender", help="发件人地址。")
    parser.add_argument("--subject", help="邮件主题。")
    parser.add_argument("--body", help="邮件正文。")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="清空邮箱（收件箱 + 草稿）并从 seeds/ 重新播种。",
    )
    args = parser.parse_args()

    if args.reset:
        store = _empty_store()
        for seed in sorted(_SEEDS_DIR.glob("*.json")):
            store["inbox"].append(json.loads(Path(seed).read_text(encoding="utf-8")))
        save_store(store)
        print(f"Mailbox reset. Inbox now has {len(store['inbox'])} message(s).")
        return

    store = load_store()
    if args.sender or args.subject or args.body:
        msg = {
            "id": next_id(store["inbox"], "msg"),
            "from": args.sender or "unknown@example.com",
            "subject": args.subject or "(no subject)",
            "date": "2026-06-14T12:00:00Z",
            "body": args.body or "",
        }
        store["inbox"].append(msg)
        save_store(store)
        print(f"Injected {msg['id']} from {msg['from']!r}.")
    else:
        # 无自定义字段：确保种子夹具存在。
        load_store()  # 首次使用时播种
        store = load_store()
        print(f"Inbox has {len(store['inbox'])} message(s). Use --reset to re-seed.")


if __name__ == "__main__":
    main()
