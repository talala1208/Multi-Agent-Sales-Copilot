"""停止本课程正在运行的沙箱。

由 start.sh 在关闭时调用，使学生关闭 langgraph dev 后立即停止沙箱计费，
而不必等待 idle_ttl_seconds。仅处理名为 "thread-*"（agent.py 中的命名约定）
且当前为 "ready" 的沙箱 — 从不触碰工作区中的其他沙箱。
"""
from __future__ import annotations

from pathlib import Path

from dotenv import dotenv_values

from daytona import(
    Daytona, 
    DaytonaConfig, 
    SandboxState,
)


# Load the key explicitly from python/.env rather than relying on the
# ambient shell environment, which may hold an unrelated LANGSMITH_API_KEY
# (e.g. from an outer shell/session) that silently points at the wrong
# workspace — this bit us once already when building this lesson.
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def main() -> None:
    api_key = dotenv_values(ENV_PATH).get("DAYTONA_API_KEY")
    daytona = Daytona(DaytonaConfig(api_key=api_key))
    page = daytona.list(page=1, limit=100)
    targets = [
        sb
        for sb in page.items
        if (sb.name or "").startswith("thread-") and sb.state == SandboxState.STARTED
    ]
    for sb in targets:
        try:
            daytona.stop(sb, timeout=60)
            print(f"Stopped sandbox {sb.name}")
        except Exception as exc:
            print(f"Could not stop sandbox {sb.name}: {exc}")


if __name__ == "__main__":
    main()