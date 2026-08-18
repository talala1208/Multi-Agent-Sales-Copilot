# Chinook Sales Assistant — 项目规格说明

| 字段 | 值 |
|------|-----|
| 项目名称 | Chinook Sales Assistant |
| 版本 | 0.1.0 |
| 状态 | 可演示 / 简历展示 |
| 诊断令牌 | `CHINOOK-READY`（见 `test/test_diagnostic.py`） |

---

## 1. 背景与目标

### 1.1 业务背景

Chinook 是在线音乐分销商。销售支持代表 **Jane Peacock**（`EmployeeId = 3`）负责一批 B2B 客户：回复询价、维护客户资料、了解辖区业绩，并定期向客户发送音乐资讯周报。

### 1.2 产品目标

构建一个 **多 Agent 销售协作者**，使 Jane 通过自然语言对话完成上述工作，同时满足：

1. **职责分离** — 主 Agent 协调，不直接操作数据库或邮件；外部系统访问集中在专家子 Agent。
2. **人机协同** — 客户写入与邮件草稿保存必须经 Jane 审批，禁止静默落库或发信。
3. **可审计产出** — 报价台账、辖区报告、周报 HTML 写入沙箱 `/outputs/`，可在 UI 下载。
4. **隔离执行** — Agent 读写与代码执行发生在按对话线程划分的 Daytona 沙箱内，降低对主机的信任要求。
5. **长任务不阻塞** — 周报制作在后台独立图中运行，主对话可继续处理其他请求。

### 1.3 非目标（当前版本不做）

- 真实 Gmail / SMTP 发信（使用本地 Mock Mail MCP）
- 多销售代表租户隔离（固定 Jane，`SupportRepId = 3`）
- 生产级权限模型与审计日志
- 自动发送邮件或未经审批的任何写入

---

## 2. 用户与角色

| 角色 | 说明 |
|------|------|
| **Jane Peacock** | 人类决策者；审批敏感写入，审阅草稿与报告 |
| **主 Agent** | 销售助手协调者；加载 `AGENTS.md` 与 `skills/`，委派专家 |
| **专家子 Agent** | 数据库、邮件、报价审核、音乐调研等垂直能力 |
| **开发者 / 演示者** | 通过 `start.sh` 启动栈，运行诊断测试 |

「她的客户群」/「我们的客户」在数据层指 `Customer.SupportRepId = 3` 的客户集合。

---

## 3. 功能需求

### 3.1 询价报价（RFQ）

**触发**：用户询问价格、报价、批量购买，或 Mock 收件箱中有 RFQ 邮件。

**流程**（技能 `rfq-quote`）：

| 步骤 | 行为 | 负责方 |
|------|------|--------|
| 1 | 检索并阅读 RFQ 邮件 | inbox-manager |
| 2 | 按邮箱/姓名查找客户；不存在则 `add_customer`（审批） | chinook-analyst |
| 3 | 查询目录单价、畅销曲目等 | chinook-analyst |
| 4 | 用代码解释器计算行小计、折扣、总额 | 主 Agent（QuickJS） |
| 5 | 复核算术与价格合理性 | quote-reviewer |
| 6 | 起草回复并 `mail_create_draft`（审批） | inbox-manager |
| 7 | 追加记录到 `/outputs/quotes_ledger.md` | 主 Agent |

**业务规则**：

- 价格必须来自数据库，禁止编造。
- 默认批量折扣：≥50 首曲目 10%（须在报价中写明）。
- 曲目标准单价通常约 $0.99，以查询结果为准。

### 3.2 辖区报告

**触发**：辖区报告、销售汇总、客户群业绩等询问。

**产出**：

- `/outputs/territory_report-<timestamp>.md` — Markdown 报告
- `/outputs/territory_chart-<timestamp>.png` — 按类型收入饼图（matplotlib）

**数据范围**：仅 Jane 的客户（`SupportRepId = 3`）的收入、头部客户、类型分布、趋势。

### 3.3 每周音乐周报

**触发**：创建/撰写/发送「本周音乐」客户周报。

**流程**（技能 `weekly-newsletter`）：

1. 选定类型（Jane 指定或 chinook-analyst 按收入 Top 4）。
2. **一次**调用 `start_async_task(subagent_type="newsletter-agent", description=...)`，立即返回 `task_id`。
3. Jane 再次询问时：`list_async_tasks` → `check_async_task`。
4. 成功则将 HTML 写入 `/outputs/newsletter-<timestamp>-<task_id[:8]>.html`（防重复保存）。

**newsletter-agent 内部**：

- 对每个类型并行委派 `genre-researcher`。
- `genre-researcher` 用 Tavily 搜索，完整搜索结果写入 `/research/<genre>/sources.md`，回复中仅返回 ~120–180 词段落。
- 组装 Markdown → `markdown_to_html` → 回复纯 HTML。

**依赖**：`TAVILY_API_KEY` 未配置时，genre 搜索工具不可用，周报调研能力降级。

### 3.4 客户维护

- 只读查询：随时通过 chinook-analyst 的 `query_chinook`。
- 新增客户：仅 `add_customer`，且触发人机协同中断。

---

## 4. 系统架构

### 4.1 逻辑分层

```
┌─────────────────────────────────────────────────────────┐
│  Presentation：agent-chat-ui（对话、Agent Inbox、文件）   │
├─────────────────────────────────────────────────────────┤
│  Orchestration：LangGraph（agent + newsletter-agent）    │
├─────────────────────────────────────────────────────────┤
│  Agent Layer：Deep Agents 主图 + 子 Agent + 中间件        │
├─────────────────────────────────────────────────────────┤
│  Execution：Daytona 沙箱 / StoreBackend / QuickJS        │
├─────────────────────────────────────────────────────────┤
│  Integration：DashScope、Tavily、Mock Mail MCP、SQLite   │
└─────────────────────────────────────────────────────────┘
```

### 4.2 LangGraph 图注册

`langgraph.json`：

| graph_id | 入口 | 说明 |
|----------|------|------|
| `agent` | `agent.py:make_graph` | 异步上下文工厂；真实 run 绑定 thread 沙箱 |
| `newsletter-agent` | `newsletter_agent_graph.py:graph` | 静态图；由 `AsyncSubAgentMiddleware` 后台启动 |

### 4.3 主图工厂 `make_graph`

**自省调用**（`execution_runtime is None`）：使用 `StateBackend`，无真实沙箱，图拓扑与真实 run 一致。

**真实 run**：

1. 按 `thread_id` 查找或创建 Daytona 沙箱（名称 `thread-{thread_id}`）。
2. 首次创建或 skills 目录为空时，播种 `AGENTS.md` 与 `skills/**`。
3. 虚拟路径 `/outputs`、`/skills` 等重写为沙箱工作目录下的实际路径。
4. 组装 `create_deep_agent`：邮件 MCP 工具、`markdown_to_html`、子 Agent、Skills、Memory、中间件。

**中间件栈**：

| 中间件 | 作用 |
|--------|------|
| `CodeInterpreterMiddleware` | QuickJS；`ptc` 含 `execute`、`write_file` |
| `AsyncSubAgentMiddleware` | 可选；`TAVILY_API_KEY` 存在时注册 newsletter-agent |

### 4.4 子 Agent 规格

定义于 `subagents.py`，通过 `build_subagents(backend, mail_tools, root)` 构建。

#### chinook-analyst

- **工具**：`query_chinook`、`introspect_schema`、`add_customer`
- **记忆**：`{root}/agents/chinook-analyst/AGENTS.md`（`MemoryMiddleware`）
- **模型**：`model`（flash）
- **中断**：`add_customer` → approve / edit / reject

#### inbox-manager

- **工具**：Mock Mail MCP 全套（`mail_list_messages`、`mail_read_message`、`mail_create_draft`）
- **模型**：`model`
- **中断**：`mail_create_draft` → approve / edit / reject
- **条件**：仅当 `mail_tools` 非空时注册

#### quote-reviewer

- **工具**：无
- **模型**：`strong_model`（max）
- **职责**：报价算术与价格合理性

#### genre-researcher（仅 newsletter-agent 图内）

- **工具**：`internet_search`（Tavily，条件加载）
- **模型**：`model`
- **产出**：Markdown 段落 + `/research/<genre>/sources.md`

### 4.5 沙箱与文件系统

| 路径（虚拟） | 内容 |
|--------------|------|
| `/AGENTS.md` | 主 Agent 操作手册 |
| `/skills/**` | RFQ、辖区、周报技能剧本 |
| `/outputs/**` | 报价台账、报告、图表、周报 HTML |
| `/agents/chinook-analyst/AGENTS.md` | 分析师 schema 记忆 |
| `/research/**` | genre-researcher 搜索原文（newsletter 图 StoreBackend） |

沙箱按 **LangGraph thread_id** 隔离；`stop_sandboxes.py` / `start.sh` cleanup 清理 `thread-*` 沙箱。

### 4.6 Chat UI 集成

基于 LangGraph Agent Chat UI 定制：

- LangGraph SDK 流式对话
- **Agent Inbox**：处理 `interrupt_on` 工具的中断与审批
- **沙箱文件面板**：通过 API 列出/下载 Daytona 沙箱内 `/outputs` 文件
- Markdown 渲染支持沙箱产出路径

---

## 5. 数据与信任边界

### 5.1 Chinook 数据库

- **路径**：`data/chinook.db`（标准 Chinook 示例库）
- **只读查询**：`sqlite3` URI `mode=ro` + SQL 关键字黑名单 + 单语句限制
- **写入**：仅 `add_customer` → 参数化 INSERT，仅 `Customer` 表，强制 `SupportRepId = REP_EMPLOYEE_ID`（3）
- **邮箱去重**：插入前 `lower(Email)` 查重

### 5.2 Mock 邮件

- **服务**：`mcp/mock_mail_server.py`，端口 5002，FastMCP streamable-http
- **持久化**：`mcp/mail_store.json`（运行时生成，gitignore）
- **种子**：`mcp/seeds/incoming_rfq.json` 等
- **约束**：`mail_create_draft` 仅写入草稿区，无发送工具

### 5.3 模型层

- **提供商**：阿里云 DashScope OpenAI 兼容端点
- **适配**：`DashScopeChatOpenAI` 将 Anthropic/LangChain content blocks 转为 OpenAI 形态（百炼兼容）
- **默认**：`strong_model` = qwen3.8-max；子 Agent 分析师/邮件用 flash 档

---

## 6. 工具契约

### 6.1 SQL 工具（`tools/sql.py`）

#### `query_chinook(sql: str) -> str`

- 仅允许单条 `SELECT` / `WITH` 查询
- 返回 JSON 数组或 `{"error": ...}`

#### `introspect_schema() -> str`

- 返回所有用户表的 `CREATE TABLE` 拼接文本

#### `add_customer(...) -> str`

- 必填有效 `email`
- 成功：`{"status":"created","customer_id":...}`
- 需人机审批后执行

### 6.2 HTML 工具（`tools/html.py`）

#### `markdown_to_html(markdown: str) -> str`

- Markdown → 经 `nh3` 清洗的 HTML
- newsletter-agent 最终产出依赖此工具

### 6.3 搜索工具（`tools/search.py`）

#### `internet_search(query: str) -> str`

- Tavily 客户端；需 `TAVILY_API_KEY`
- 供 genre-researcher 使用

### 6.4 Mock Mail MCP

| 工具 | 参数 | 返回 |
|------|------|------|
| `mail_list_messages` | `query`（可选） | 邮件摘要列表 |
| `mail_read_message` | `message_id` | 完整正文 |
| `mail_create_draft` | `to`, `subject`, `body` | 草稿 ID；触发审批 |

### 6.5 异步任务工具（Deep Agents 内置）

| 工具 | 说明 |
|------|------|
| `start_async_task` | 启动 `newsletter-agent` 图，立即返回 `task_id` |
| `list_async_tasks` | 列出持久化任务状态 |
| `check_async_task` | 按 `task_id` 查询；`success` 时 `result` 为 HTML |

---

## 7. 人机协同（Human-in-the-Loop）

### 7.1 门控工具

| 工具 | 子 Agent | 允许决策 |
|------|----------|----------|
| `add_customer` | chinook-analyst | approve, edit, reject |
| `mail_create_draft` | inbox-manager | approve, edit, reject |

### 7.2 设计原因

通用子 Agent 会继承主 Agent 工具；将门控工具 **仅** 挂在对应专家上，确保写入路径必经审批 UI，而非聊天内口头确认。

### 7.3 Agent 行为约束

- 专家应在调用门控工具 **之前** 不要在 prose 中先问许可；中断即审批流程。
- 主 Agent 不得在聊天中假装已保存草稿或已添加客户。

---

## 8. 异步周报架构决策

### 8.1 为何 newsletter-agent 是独立图

- 完整周报（多类型调研 + HTML 组装）耗时较长，需与主对话解耦。
- `AsyncSubAgentMiddleware` 通过 LangGraph SDK 在新 thread 启动图，主 Agent 不阻塞。

### 8.2 为何 genre-researcher 在图内同步并行

- 单次 newsletter run 内用 `task` 工具并行调用多个 genre-researcher，无需跨 thread 汇总。
- 搜索原文写入 `/research/`，避免膨胀 editor 上下文。

### 8.3 存储

- newsletter-agent 使用 `StoreBackend`，namespace = `(thread_id, "research")`。
- 异步任务结果由 LangGraph Store 持久化，供 `check_async_task` 读取。

### 8.4 完成通知

- **无** 跨 thread 推送；Jane 主动询问时主 Agent 轮询任务状态。

---

## 9. 产出文件规范

| 文件模式 | 说明 |
|----------|------|
| `/outputs/quotes_ledger.md` | 报价台账（追加行） |
| `/outputs/territory_report-<timestamp>.md` | 辖区 Markdown 报告 |
| `/outputs/territory_chart-<timestamp>.png` | 辖区饼图 |
| `/outputs/newsletter-<timestamp>-<task[:8]>.html` | 周报 HTML |

**时间戳格式**：`new Date().toISOString().slice(0, 19).replace(/:/g, '-')`（含时分秒，避免同日覆盖）。

**周报防重**：保存前 `glob("/outputs/newsletter-*-<task[:8]>.html")` 检查是否已存在。

---

## 10. 运行与部署

### 10.1 进程拓扑（`start.sh`）

1. Mock Mail MCP → `:5002`
2. agent-chat-ui → `:3000`
3. `langgraph dev --n-jobs-per-worker 10` → `:2024`

### 10.2 环境变量

见 `.env.example`：

| 变量 | 必需 | 用途 |
|------|------|------|
| `DASHSCOPE_API_KEY` | 是 | LLM |
| `DAYTONA_API_KEY` | 是 | 沙箱 |
| `LANGSMITH_API_KEY` | 推荐 | 追踪 |
| `LANGSMITH_TRACING` | 可选 | 开启追踪 |
| `LANGSMITH_PROJECT` | 可选 | 项目名 |
| `TAVILY_API_KEY` | 可选 | 周报搜索 |

### 10.3 依赖（Python）

核心：`deepagents==0.7.0`、`langgraph`、`langchain-daytona`、`daytona`、`langchain-quickjs`、`langchain-mcp-adapters`、`tavily-python`、`matplotlib` 等（见 `pyproject.toml`）。

### 10.4 诊断

`test/test_diagnostic.py` 分层验证：

- LangGraph 连通
- 沙箱与文件播种
- 子 Agent 委派
- SQL 只读与审批写入
- 邮件 MCP
- 异步周报（若 Tavily 可用）

---

## 11. 安全与风险

| 风险 | 缓解 |
|------|------|
| 模型生成恶意 SQL | 只读 URI + 关键字过滤 + 单语句；写入仅参数化 INSERT |
| 未授权客户写入 | `SupportRepId` 服务端固定；`add_customer` 审批 |
| 误发邮件 | 仅草稿工具；无 send；`mail_create_draft` 审批 |
| 沙箱逃逸 | Agent 文件与执行限定 Daytona；无主机路径桥接 |
| API Key 泄露 | `.env` gitignore；上传前检查 |

---

## 12. 扩展方向（未实现）

- 真实 Gmail OAuth MCP 替换 Mock Mail
- 多销售代表与 RBAC
- 报价 PDF 生成与附件草稿
- 周报定时任务与邮件群发（仍须审批）
- 向量检索增强客户/曲目推荐

---

## 13. 术语表

| 术语 | 定义 |
|------|------|
| Deep Agent | LangChain Deep Agents 框架中的可编排 Agent 图 |
| Skill | `skills/*/SKILL.md` 中的任务剧本，带 YAML frontmatter |
| Memory | `AGENTS.md` 等持久文本，由 `MemoryMiddleware` 注入上下文 |
| Agent Inbox | Chat UI 中处理 LangGraph interrupt 的审批界面 |
| RFQ | Request for Quote，客户询价 |
| Chinook | 开源 SQLite 示例音乐分销商数据库 |

---

## 14. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-08-18 | 初版 SPEC：对齐当前代码（Daytona 沙箱、DashScope、异步 newsletter-agent、Mock Mail） |
