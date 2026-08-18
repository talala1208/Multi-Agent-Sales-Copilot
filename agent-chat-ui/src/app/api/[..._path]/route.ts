import { initApiPassthrough } from "langgraph-nextjs-api-passthrough";

// 本文件作为 LangGraph 服务请求的代理。
// 更多信息请参阅 [生产部署](https://github.com/langchain-ai/agent-chat-ui?tab=readme-ov-file#going-to-production)。

export const { GET, POST, PUT, PATCH, DELETE, OPTIONS, runtime } =
  initApiPassthrough({
    apiUrl: process.env.LANGGRAPH_API_URL ?? "remove-me", // 默认；未定义时尝试读取 process.env.LANGGRAPH_API_URL
    apiKey: process.env.LANGSMITH_API_KEY ?? "remove-me", // 默认；未定义时尝试读取 process.env.LANGSMITH_API_KEY
    runtime: "edge", // 默认
  });
