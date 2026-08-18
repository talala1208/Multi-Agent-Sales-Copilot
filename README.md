# **Multi-Agent Sales Copilot**

多 Agent 助手，含 main Agent，多个 sync subAgent 以及一个 async subAgent。
以在线音乐分销商 Chinook 的销售支持场景为例：

- 主协调 Agent 根据用户请求规划及调用工具。
- 代码及文件系统与本地系统隔离，在 **Daytona 沙箱** 中运行。
- 通过 **Deep Agents** 编排 subAgent，配合 **LangGraph** 人机协同审批与异步后台任务，覆盖`询价报价、客户维护、辖区报表与每周音乐周报`等销售场景。

> 业务角色：用户 **Jane** 协助执行 HITL 的关键写入和审批。

---

## 亮点能力


| 能力             | 说明                                                                                      |
| -------------- | --------------------------------------------------------------------------------------- |
| **多 Agent 协作** | 主 Agent 协调数据库、邮件、报价审核、周报四条链路。主 Agent 不直连 SQL / 邮件，具体任务委派给专业 subAgent 执行                 |
| **人机协同**       | `add_customer`、`mail_create_draft` 触发 HITL，Agent Inbox 中断，支持 approve / edit / reject 选项 |
| **隔离沙箱执行**     | 对话 thread 绑定 Daytona 沙箱；skills、memory、文件系统均在沙箱内，不直接连接本地                                 |
| **异步周报**       | `newsletter-agent` 独立 LangGraph 图后台运行，周报生成期间 main Agent 可继续响应用户                         |
| **Skills 工作流** | RFQ 报价、辖区报告、周报生成 等可复用逻辑                                                                 |
| **安全 SQL**     | 只读 URI + 语句校验；客户写入仅参数化 INSERT，且与 Jane 工号绑定（仅 Jane 有权限）                                  |


---



## 系统架构

系统架构

---



## Agent 编排

Agent 编排


| 专家                   | 职责                  | 工具 / 模型                                                 |
| -------------------- | ------------------- | ------------------------------------------------------- |
| **chinook-analyst**  | 目录价格、客户记录、购买历史、辖区指标 | `query_chinook`、`introspect_schema`、`add_customer`（需审批） |
| **inbox-manager**    | 收件箱检索、阅读、保存回复草稿     | Mock Mail MCP（`mail_create_draft` 需人工审批）                |
| **quote-reviewer**   | 报价算术与价格合理性复核        | 无工具，强模型推理                                               |
| **newsletter-agent** | 后台调研类型并组装 HTML 周报   | 独立的异步 Agent + `genre-researcher` 工具并行搜索                 |
| **genre-researcher** | 单类型音乐新闻调研与报告段落撰写    | `internet_search`（Tavily）                               |


---



## 人机协同审批

敏感任务不自动写入或执行 — 工具调用暂停，由 Chat UI 的 Agent Inbox 呈现审批卡片。

人机协同审批

该项目中的人机协同审批点：

- **保存邮件草稿**（`mail_create_draft`）— 草稿不自动发送
- **添加新客户**（`add_customer`）— 未经 Jane 同意不写入数据库

---



## 异步周报流程

异步周报流程

1. 主 Agent 向 chinook-analyst 获取预设的音乐类型（或采用 Jane 指定列表）
2. 调用 `start_async_task(subagent_type="newsletter-agent")` — 立即返回 `task_id`
3. `newsletter-agent` 并行委派多个 `genre-researcher` 调研，将多段结果拼接为 Markdown 后转为 HTML 报告
4. Jane 询问后台任务进度，`check_async_task` 根据结果取回 HTML 报告，写入 `/outputs/newsletter-<timestamp>-<task_id 前 8 位>.html`
5. 用户可通过 Chat UI 界面下载 Daytona 沙箱中生成的文件

---



## 技术栈


| 层级       | 技术                                                            |
| -------- | ------------------------------------------------------------- |
| Agent 框架 | [Deep Agents](https://github.com/langchain-ai/deepagents) 0.7 |
| 编排与部署    | LangGraph 1.x、`langgraph dev`、LangSmith 追踪                    |
| 模型       | 阿里云 DashScope                                                 |
| 沙箱       | Daytona                                                       |
| 代码执行     | `langchain-quickjs`                                           |
| 前端       | Next.js Chat UI（LangGraph Agent Chat UI 定制）                   |
| 邮件       | 本地 Mock Mail MCP（FastMCP，HTTP streamable）                     |
| 搜索       | Tavily（周报 genre 调研）                                           |
| 数据       | Chinook SQLite 示例库                                            |


---



## 典型业务/对话场景

以下场景的工作流说明见 `SKILL.md`；**可直接复制的对话示例**见下方 [试试这些对话](#试试这些对话)。

### 询价报价（RFQ）

阅读 Mock 收件箱 RFQ → 确认/新增客户 → 查询目录价 → 代码解释器算总额与折扣 → quote-reviewer 复核 → inbox-manager 保存草稿 → 写入 `quotes_ledger.md`。

详见：`skills/rfq-quote/SKILL.md`

### 辖区报告

chinook-analyst 汇总 Jane 客户群指标 → Markdown 报告 + matplotlib 饼图 → 保存至 `/outputs/territory_report-*.md` 与 `territory_chart-*.png`。

详见：`skills/territory-report/SKILL.md`

### 每周音乐周报

后台 `newsletter-agent` 调研类型并生成 HTML → 主 Agent 轮询任务状态后落盘。

详见：`skills/weekly-newsletter/SKILL.md`

---



## 项目结构

```
├── agent.py                 # main Agent make_graph（Daytona 沙箱 + 子 Agent）
├── newsletter_agent_graph.py# newsletter-agent 独立异步 subAgent
├── subagents.py             # chinook-analyst / inbox-manager / quote-reviewer
├── async_research.py        # AsyncSubAgentMiddleware 配置
├── models.py                # DashScope 模型与 content block 适配
├── tools/                   # SQL、HTML、搜索工具
├── skills/                  # 三类业务技能
├── mcp/                     # Mock 邮件 MCP 服务
├── agent-chat-ui/           # Next.js 聊天 UI
├── data/chinook.db          # Chinook 示例数据库
├── assets/                  # README 架构图（Mermaid 源码 + PNG）
├── spec/SPEC.md             # 项目规格说明（需求、架构、接口）
└── test/test_diagnostic.py  # 分层诊断测试
```

---



## 快速开始



### 环境要求

推荐使用 uv 配置环境

```bash
uv sync
```



### 配置

```bash
cp .env.example .env
```


| 变量                  | 说明                        |
| ------------------- | ------------------------- |
| `DASHSCOPE_API_KEY` | 通义千问 API（或替换为其他 LLM 供应商）  |
| `DAYTONA_API_KEY`   | Daytona 沙箱                |
| `LANGSMITH_API_KEY` | LangSmith 追踪（推荐）          |
| `TAVILY_API_KEY`    | 周报联网调研（可选，不填则禁用 genre 搜索） |




### 启动

- 第一步：

```bash
./start.sh
```

- 第二步：关闭自动弹出的 LangSmith Studio 界面，打开 [Chat UI](http://localhost:3000)，填入 LangSmith API Key 后即可开始对话。


| 服务            | 地址                                             |
| ------------- | ---------------------------------------------- |
| LangGraph API | [http://127.0.0.1:2024](http://127.0.0.1:2024) |
| Chat UI       | [http://localhost:3000](http://localhost:3000) |
| Mock Mail MCP | [http://127.0.0.1:5002](http://127.0.0.1:5002) |


退出 `start.sh` 会停止邮件服务、UI，并清理名为 `thread-*` 的 Daytona 沙箱。

服务就绪后，可直接跳到 **[试试这些对话](#试试这些对话)** 复制示例提问。

### 系统诊断

服务启动后另开终端：

```bash
uv run python test/test_diagnostic.py
```

---



## 试试这些对话

启动后打开 [http://localhost:3000](http://localhost:3000)，复制下面任意一句发送即可。

- 我的客户群业绩怎么样？给我做一份辖区报告。
- 写一下本周的「本周音乐」客户周报。
- 周报做好了吗？（发起周报后，在同一对话里稍后再问）
- 收件箱里有什么新邮件？
- 帮我处理 Morgan Vale 的询价：查价、算总额、复核后起草回复并保存草稿。

保存草稿或添加新客户时会弹出审批卡片；周报联网调研需配置 `TAVILY_API_KEY`。

---



## License

MIT