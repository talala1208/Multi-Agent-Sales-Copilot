"""停止并清理项目运行中的 Daytona 沙箱。

由 start.sh 在关闭时调用，在退出 langgraph dev 后立即停止沙箱计费并
删除本次用过的 thread 沙箱。仅处理名为 "thread-*"（agent.py 中的命名约定）
且当前为 STARTED 的沙箱 — 从不触碰工作区中的其他沙箱。仅在 stop 成功后才
尝试 delete，避免 stop 失败时仍强行删除。
"""
from __future__ import annotations

from pathlib import Path

from dotenv import dotenv_values

from daytona import(
    Daytona, 
    DaytonaConfig, 
    SandboxState,
)


# 从与本脚本同目录的 .env 读取，避免依赖当前工作目录或外层 shell 里的无关 key。
ENV_PATH = Path(__file__).resolve().parent / ".env"


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
            continue
        try:
            daytona.delete(sb, timeout=60)
            print(f"Deleted sandbox {sb.name}")
        except Exception as exc:
            print(f"Could not delete sandbox {sb.name}: {exc}")


if __name__ == "__main__":
    main()