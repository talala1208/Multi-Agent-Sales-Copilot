import type { Message } from "@langchain/langgraph-sdk";

/**
 * 从消息内容提取字符串摘要，支持多模态（文本、图片、文件等）。
 * - 若有文本，返回拼接后的文本。
 * - 否则返回第一个非文本模态的标签（如「图片」「其他」）。
 * - 若未知，返回「多模态消息」。
 */
export function getContentString(content: Message["content"]): string {
  if (typeof content === "string") return content;
  const texts = content
    .filter((c): c is { type: "text"; text: string } => c.type === "text")
    .map((c) => c.text);
  return texts.join(" ");
}
