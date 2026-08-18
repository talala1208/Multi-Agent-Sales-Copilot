# python/m5/sales_assistant/mcp/mock_mail_server.py
"""本地离线模拟邮件 MCP 服务器。

在 5002 端口通过 HTTP（streamable-http 传输）暴露三个工具：

    mail_list_messages(query)            -> 收件箱邮件摘要
    mail_read_message(message_id)        -> 单封邮件完整正文
    mail_create_draft(to, subject, body) -> 将回复保存到草稿文件夹

状态由 mail_store.py 管理的小型 JSON 文件。在 langgraph dev 之前由 start.sh
启动，以便 make_graph() 在启动时发现工具。
"""

from __future__ import annotations

from mail_store import load_store, next_id, save_store
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mock-mail", host="127.0.0.1", port=5002)


@mcp.tool()
def mail_list_messages(query: str = "") -> list[dict]:
    """列出收件箱中的消息。

    返回每封邮件的摘要（id、发件人、主题、日期、片段）— 非完整正文。
    用 read_message 打开单封。可选 ``query`` 为不区分大小写的子串，
    匹配主题和发件人，主要模拟 Gmail 搜索框；留空则列出全部。
    """
    store = load_store()
    q = query.strip().lower()
    out = []
    for m in store["inbox"]:
        haystack = f"{m.get('subject', '')} {m.get('from', '')}".lower()
        if q and q not in haystack:
            continue
        body = m.get("body", "")
        out.append(
            {
                "id": m.get("id"),
                "from": m.get("from"),
                "subject": m.get("subject"),
                "date": m.get("date"),
                "snippet": body[:140] + ("…" if len(body) > 140 else ""),
            }
        )
    return out


@mcp.tool()
def mail_read_message(message_id: str) -> dict:
    """按 id 返回完整消息（发件人、主题、日期、完整正文）。"""
    store = load_store()
    for m in store["inbox"]:
        if m.get("id") == message_id:
            return m
    return {"error": f"No message with id {message_id!r}."}


@mcp.tool()
def mail_create_draft(to: str, subject: str, body: str) -> dict:
    """将回复保存到草稿文件夹。不会发送。

    模拟真实 Gmail「创建草稿」调用：消息暂存供人工审阅后发送。
    本课程中此工具前有人机协同门，仅在明确批准后才会写入草稿。
    """
    store = load_store()
    draft = {
        "id": next_id(store["drafts"], "draft"),
        "to": to,
        "subject": subject,
        "body": body,
    }
    store["drafts"].append(draft)
    save_store(store)
    return {"status": "draft_saved", "draft_id": draft["id"], "to": to, "subject": subject}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
