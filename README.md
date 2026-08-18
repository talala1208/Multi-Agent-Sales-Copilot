# Chinook Sales Assistant

从 LangChain Academy `sales_assistant_sandbox` 拆出的独立项目：主 agent 跑在 Daytona 沙箱里，模型走 DashScope 兼容模式。

## 需要什么

- Python 3.11–3.14、[uv](https://docs.astral.sh/uv/)
- Node.js + [pnpm](https://pnpm.io/)（chat UI）
- `.env` 里配置 `DASHSCOPE_API_KEY`、`DAYTONA_API_KEY`、`LANGSMITH_API_KEY`
- 周报联网研究需要 `TAVILY_API_KEY`（可空）

## 启动

```bash
cp .env.example .env   # 填入 key
uv sync
./start.sh
```

- LangGraph：http://127.0.0.1:2024
- Chat UI：http://localhost:3000
- Mock mail MCP：http://127.0.0.1:5002

退出 `start.sh` 会停掉邮件服务、UI，以及名为 `thread-*` 的 Daytona 沙箱。

## 诊断

服务起来之后另开终端：

```bash
uv run python test_diagnostic.py
```
