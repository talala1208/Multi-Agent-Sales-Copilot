# Agent Chat UI

> 为 Chinook Sales Assistant 增加了 `/api/sandbox-files` 与 `/api/sandbox-download` 路由、
> 异步任务状态徽章和沙箱文件面板。
>
> 在本项目中通过根目录的 `./start.sh` 一并启动。

Agent Chat UI 是一个 Next.js 应用，可通过聊天界面与任意带有 `messages` 键的 LangGraph 服务对话。

> [!NOTE]
> 视频安装指南见 [此处](https://youtu.be/lInrwVnZ83o)。

## 安装

> [!TIP]
> 不想本地运行？可使用已部署站点：[agentchat.vercel.app](https://agentchat.vercel.app)

克隆仓库，或使用 [`npx` 命令](https://www.npmjs.com/package/create-agent-chat-app)：

```bash
npx create-agent-chat-app
```

或

```bash
git clone https://github.com/langchain-ai/agent-chat-ui.git

cd agent-chat-ui
```

安装依赖：

```bash
pnpm install
```

运行应用：

```bash
pnpm dev
```

应用地址：`http://localhost:3000`。

## 使用

应用运行后（或使用已部署站点），会提示输入：

- **Deployment URL**：要对话的 LangGraph 服务 URL，可为生产或开发地址。
- **Assistant/Graph ID**：图名称，或聊天界面拉取和提交 run 时使用的 assistant ID。
- **LangSmith API Key**：（仅连接已部署 LangGraph 服务时需要）向 LangGraph 服务认证时使用的 LangSmith API 密钥。
- **Built with Agent Builder**：Agent Builder 部署时开启。会自动将认证方案设为 `langsmith-api-key`。

输入后点击 `Continue`，将进入聊天界面。

## 环境变量

可通过以下环境变量跳过初始设置表单：

```bash
NEXT_PUBLIC_API_URL=http://localhost:2024
NEXT_PUBLIC_ASSISTANT_ID=agent
NEXT_PUBLIC_AUTH_SCHEME=
```

> [!NOTE]
> 若连接 LangSmith Agent Builder 部署，请设置 `NEXT_PUBLIC_AUTH_SCHEME=langsmith-api-key`。

> [!TIP]
> 若需连接生产 LangGraph 服务，请参阅 [生产部署](#生产部署)。

使用方式：

1. 将 `.env.example` 复制为 `.env`
2. 在 `.env` 中填写值
3. 重启应用

设置这些变量后，应用将使用它们而不再显示设置表单。

## 在聊天中隐藏消息

可通过两种方式控制 Agent Chat UI 中消息的可见性：

**1. 禁止实时流式显示：**

若不想在 LLM 调用*流式输出时*显示消息，在聊天模型配置中添加 `langsmith:nostream` 标签。UI 通常用 `on_chat_model_stream` 事件渲染流式消息；该标签会阻止被标记模型发出这些事件。

_Python 示例：_

```python
from langchain_anthropic import ChatAnthropic

# 通过 .with_config 添加标签
model = ChatAnthropic().with_config(
    config={"tags": ["langsmith:nostream"]}
)
```

_TypeScript 示例：_

```typescript
import { ChatAnthropic } from "@langchain/anthropic";

const model = new ChatAnthropic()
  // 通过 .withConfig 添加标签
  .withConfig({ tags: ["langsmith:nostream"] });
```

**注意：** 即使以此方式隐藏流式输出，若消息在 LLM 调用完成后写入图状态且未进一步修改，仍会在聊天中显示。

**2. 永久隐藏消息：**

若希望消息*永不*在聊天 UI 中显示（流式期间和写入状态后均不显示），在将消息加入图状态*之前*，为其 `id` 字段加上 `do-not-render-` 前缀，并在聊天模型配置中添加 `langsmith:do-not-render` 标签。UI 会显式过滤所有以该前缀开头的消息。

_Python 示例：_

```python
result = model.invoke([messages])
# 写入状态前给 ID 加前缀
result.id = f"do-not-render-{result.id}"
return {"messages": [result]}
```

_TypeScript 示例：_

```typescript
const result = await model.invoke([messages]);
// 写入状态前给 ID 加前缀
result.id = `do-not-render-${result.id}`;
return { messages: [result] };
```

这样可保证消息在界面上完全不可见。

## 渲染 Artifact

Agent Chat UI 支持在聊天中渲染 artifact，显示在聊天右侧边栏。可从 `thread.meta.artifact` 获取 artifact 上下文。示例工具 hook：

```tsx
export function useArtifact<TContext = Record<string, unknown>>() {
  type Component = (props: {
    children: React.ReactNode;
    title?: React.ReactNode;
  }) => React.ReactNode;

  type Context = TContext | undefined;

  type Bag = {
    open: boolean;
    setOpen: (value: boolean | ((prev: boolean) => boolean)) => void;

    context: Context;
    setContext: (value: Context | ((prev: Context) => Context)) => void;
  };

  const thread = useStreamContext<
    { messages: Message[]; ui: UIMessage[] },
    { MetaType: { artifact: [Component, Bag] } }
  >();

  return thread.meta?.artifact;
}
```

之后可用 `useArtifact` hook 的 `Artifact` 组件渲染额外内容：

```tsx
import { useArtifact } from "../utils/use-artifact";
import { LoaderIcon } from "lucide-react";

export function Writer(props: {
  title?: string;
  content?: string;
  description?: string;
}) {
  const [Artifact, { open, setOpen }] = useArtifact();

  return (
    <>
      <div
        onClick={() => setOpen(!open)}
        className="cursor-pointer rounded-lg border p-4"
      >
        <p className="font-medium">{props.title}</p>
        <p className="text-sm text-gray-500">{props.description}</p>
      </div>

      <Artifact title={props.title}>
        <p className="whitespace-pre-wrap p-4">{props.content}</p>
      </Artifact>
    </>
  );
}
```

## 生产部署

准备上线时，需调整连接方式及对部署的认证。默认配置面向本地开发，客户端直连 LangGraph 服务。生产环境不可行，因为需要每位用户拥有自己的 LangSmith API 密钥并自行配置 LangGraph。

### 生产配置

要对 Agent Chat UI 做生产化，需在以下两种方式中择一认证 LangGraph 请求：

### 快速开始 — API 透传

最快的方式是使用 [API Passthrough](https://github.com/bracesproul/langgraph-nextjs-api-passthrough) 包（[NPM 链接](https://www.npmjs.com/package/langgraph-nextjs-api-passthrough)）。该包可简单代理 LangGraph 请求并处理认证。

本仓库已包含所需代码，只需配置环境变量：

```bash
NEXT_PUBLIC_ASSISTANT_ID="agent"
# LangGraph 服务的部署 URL
LANGGRAPH_API_URL="https://my-agent.default.us.langgraph.app"
# 网站 URL + "/api"，用于连接 API 代理
NEXT_PUBLIC_API_URL="https://my-website.com/api"
# LangSmith API 密钥，由 API 代理注入请求
LANGSMITH_API_KEY="lsv2_..."
```

各环境变量含义：

- `NEXT_PUBLIC_ASSISTANT_ID`：聊天界面拉取和提交 run 时使用的 assistant ID。仍需 `NEXT_PUBLIC_` 前缀，因为不是密钥，客户端提交请求时会用到。
- `LANGGRAPH_API_URL`：LangGraph 服务 URL，应为生产部署地址。
- `NEXT_PUBLIC_API_URL`：网站 URL + `/api`，用于连接 API 代理。例如 [Agent Chat 演示](https://agentchat.vercel.app) 可设为 `https://agentchat.vercel.app/api`。请改为你的生产 URL。
- `LANGSMITH_API_KEY`：向 LangGraph 服务认证时使用的 LangSmith API 密钥。不要加 `NEXT_PUBLIC_` 前缀，这是密钥，仅在服务端由 API 代理注入请求时使用。

详细文档请参阅 [LangGraph Next.js API Passthrough](https://www.npmjs.com/package/langgraph-nextjs-api-passthrough)。

### 高级配置 — 自定义认证

在 LangGraph 部署中使用自定义认证是更完善的方式，允许客户端发起请求而无需 LangSmith API 密钥，并可指定自定义访问控制。

在 LangGraph 部署中配置后，请阅读 LangGraph 自定义认证文档：[Python](https://langchain-ai.github.io/langgraph/tutorials/auth/getting_started/)、[TypeScript](https://langchain-ai.github.io/langgraphjs/how-tos/auth/custom_auth/)。

配置完成后，对 Agent Chat UI 做如下修改：

1. 配置额外 API 请求，从 LangGraph 部署获取认证令牌，用于客户端认证。
2. 将 `NEXT_PUBLIC_API_URL` 设为生产 LangGraph 部署 URL。
3. 将 `NEXT_PUBLIC_ASSISTANT_ID` 设为聊天界面使用的 assistant ID。
4. 修改 [`useTypedStream`](src/providers/Stream.tsx)（`useStream` 的扩展），通过 headers 将认证令牌传给 LangGraph 服务：

```tsx
const streamValue = useTypedStream({
  apiUrl: process.env.NEXT_PUBLIC_API_URL,
  assistantId: process.env.NEXT_PUBLIC_ASSISTANT_ID,
  // ... 其他字段
  defaultHeaders: {
    Authentication: `Bearer ${addYourTokenHere}`, // 在此传入认证令牌
  },
});
```
