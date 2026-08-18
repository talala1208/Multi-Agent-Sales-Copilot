import { v4 as uuidv4 } from "uuid";
import { Message, ToolMessage } from "@langchain/langgraph-sdk";

export const DO_NOT_RENDER_ID_PREFIX = "do-not-render-";

export function ensureToolCallsHaveResponses(messages: Message[]): Message[] {
  const newMessages: ToolMessage[] = [];

  messages.forEach((message, index) => {
    if (message.type !== "ai" || message.tool_calls?.length === 0) {
      // 若不是 AI 消息，或没有 tool call，可忽略。
      return;
    }
    // 若有 tool call，确保下一条消息是 tool 消息
    const followingMessage = messages[index + 1];
    if (followingMessage && followingMessage.type === "tool") {
      // 下一条已是 tool 消息，可忽略。
      return;
    }

    // 下一条不是 tool 消息，必须创建新的 tool 消息
    newMessages.push(
      ...(message.tool_calls?.map((tc) => ({
        type: "tool" as const,
        tool_call_id: tc.id ?? "",
        id: `${DO_NOT_RENDER_ID_PREFIX}${uuidv4()}`,
        name: tc.name,
        content: "Successfully handled tool call.",
      })) ?? []),
    );
  });

  return newMessages;
}
