// messages/ai.tsx（内联下载链接）与 async-task-status.tsx（「报告就绪」检查）
// 共享，使两者都能识别沙箱实际产出的 Daytona outputs 路径。
export const OUTPUT_PATH_RE =
  /(?:\/home\/daytona)?\/outputs\/[A-Za-z0-9._-]+\.[A-Za-z0-9]+/g;

export function findOutputPaths(text: string): string[] {
  return Array.from(new Set(text.match(OUTPUT_PATH_RE) ?? []));
}
