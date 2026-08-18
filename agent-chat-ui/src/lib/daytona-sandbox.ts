import { Daytona, type Sandbox } from "@daytona/sdk";

/**
 * 按 thread 查找 Daytona 沙箱，命名与 python agent.py 一致：thread-{threadId}。
 * 若沙箱已停止，先 start 再返回，避免下载/列表打到未就绪实例。
 */
export async function getThreadSandbox(threadId: string): Promise<Sandbox> {
  const apiKey = process.env.DAYTONA_API_KEY;
  if (!apiKey) {
    throw new Error("DAYTONA_API_KEY not configured");
  }

  const daytona = new Daytona({ apiKey });
  const sandbox = await daytona.get(`thread-${threadId}`);
  if (sandbox.state !== "started") {
    await daytona.start(sandbox);
  }
  return sandbox;
}

/**
 * Daytona 可写目录是 workDir，产出在 workDir/outputs。
 */
export async function getSandboxOutputsDir(sandbox: Sandbox): Promise<string> {
  const workDir = (await sandbox.getWorkDir())?.replace(/\/$/, "") ?? "";
  const homeDir = (await sandbox.getUserHomeDir())?.replace(/\/$/, "") ?? "";
  const root = workDir && workDir !== "/" ? workDir : homeDir;
  if (!root || root === "/") {
    throw new Error("Daytona sandbox has no writable work directory");
  }
  return `${root}/outputs`;
}
