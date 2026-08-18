import { NextRequest, NextResponse } from "next/server";

import { getSandboxOutputsDir, getThreadSandbox } from "@/lib/daytona-sandbox";

// 直接列出该 thread Daytona 沙箱的 outputs/（workDir 下），不依赖助手回复是否写出路径。
export const runtime = "nodejs";

const THREAD_ID_RE = /^[a-zA-Z0-9-]{1,100}$/;

type SandboxFile = { name: string; size: number; modifiedAt: string };

type DaytonaFileInfo = {
  name?: string;
  path?: string;
  size?: number;
  isDir?: boolean;
  isDirectory?: boolean;
  modTime?: string;
  mod_time?: string;
  modifiedTime?: string;
};

function toSandboxFile(entry: DaytonaFileInfo, outputsRoot: string): SandboxFile | null {
  if (entry.isDir || entry.isDirectory) {
    return null;
  }
  const full = entry.path || entry.name || "";
  const prefix = outputsRoot.replace(/\/$/, "");
  let rel = full;
  if (full.startsWith(`${prefix}/`)) {
    rel = full.slice(prefix.length + 1);
  } else if (full.startsWith("/outputs/")) {
    rel = full.slice("/outputs/".length);
  } else if (full.startsWith("outputs/")) {
    rel = full.slice("outputs/".length);
  }
  if (!rel) {
    return null;
  }
  const modified = entry.modTime ?? entry.mod_time ?? entry.modifiedTime ?? "";
  return {
    name: rel,
    size: entry.size ?? 0,
    modifiedAt: String(modified),
  };
}

function isMissingOutputDir(message: string): boolean {
  const lower = message.toLowerCase();
  return (
    lower.includes("not found") ||
    lower.includes("no such file") ||
    lower.includes("does not exist") ||
    lower.includes("path_not_found")
  );
}

export async function GET(request: NextRequest) {
  const threadId = request.nextUrl.searchParams.get("threadId");

  if (!threadId || !THREAD_ID_RE.test(threadId)) {
    return NextResponse.json({ error: "Invalid threadId" }, { status: 400 });
  }

  try {
    const sandbox = await getThreadSandbox(threadId);
    const outputsRoot = await getSandboxOutputsDir(sandbox);
    const entries = (await sandbox.fs.listFiles(outputsRoot)) as DaytonaFileInfo[];
    const files = entries
      .map((entry) => toSandboxFile(entry, outputsRoot))
      .filter((file): file is SandboxFile => file !== null);
    return NextResponse.json({ files, outputsDir: outputsRoot });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.log("sandbox-files", message);
    if (message.includes("DAYTONA_API_KEY")) {
      return NextResponse.json(
        { error: "DAYTONA_API_KEY not configured" },
        { status: 500 },
      );
    }
    if (isMissingOutputDir(message)) {
      return NextResponse.json({ files: [] });
    }
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
