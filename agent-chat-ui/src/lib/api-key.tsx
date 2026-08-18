export function getApiKey(): string | null {
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem("lg:chat:apiKey") ?? null;
  } catch {
    // 无操作
  }

  return null;
}
