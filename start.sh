#!/usr/bin/env bash
# 启动 mock mail、agent-chat-ui，再启动 langgraph dev。
# 在项目根目录运行: ./start.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

for PORT in 5002 3000; do
    OLD_PID=$(lsof -ti ":$PORT" 2>/dev/null || true)
    if [ -n "$OLD_PID" ]; then
        echo "端口 $PORT 已被占用 (PID $OLD_PID) — 正在结束进程 ..."
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
    fi
done

echo "正在启动模拟邮件服务 http://127.0.0.1:5002 ..."
uv run python "$SCRIPT_DIR/mcp/mock_mail_server.py" &
MAIL_PID=$!

echo "正在启动 agent-chat-ui http://localhost:3000 ..."
ENV_FILE="$SCRIPT_DIR/.env" "$SCRIPT_DIR/agent-chat-ui/start.sh" &
UI_PID=$!

cleanup() {
    kill "$MAIL_PID" 2>/dev/null || true
    kill "$UI_PID" 2>/dev/null || true
    pkill -f "next dev" 2>/dev/null || true
    wait "$MAIL_PID" "$UI_PID" 2>/dev/null || true
    echo "正在停止运行中的沙箱 ..."
    uv run python "$SCRIPT_DIR/stop_sandboxes.py" || true
}
trap cleanup EXIT INT TERM

for i in $(seq 1 10); do
    if curl -s --max-time 1 http://127.0.0.1:5002/ >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

echo "邮件服务已启动 (PID $MAIL_PID)，聊天 UI 启动中 (PID $UI_PID)。正在启动 langgraph dev ..."
cd "$SCRIPT_DIR"

uv run langgraph dev --n-jobs-per-worker 10
