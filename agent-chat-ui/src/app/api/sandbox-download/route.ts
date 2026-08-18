import { NextRequest, NextResponse } from "next/server";

import { getSandboxOutputsDir, getThreadSandbox } from "@/lib/daytona-sandbox";

// 非 agent 路径：直接从该 thread 的 Daytona 沙箱读文件，不经过 LLM。
export const runtime = "nodejs";

const THREAD_ID_RE = /^[a-zA-Z0-9-]{1,100}$/;

const CONTENT_TYPES: Record<string, string> = {
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  gif: "image/gif",
  svg: "image/svg+xml",
  pdf: "application/pdf",
  csv: "text/csv",
  txt: "text/plain",
  md: "text/markdown",
  json: "application/json",
  html: "text/html",
};

// 允许课上的 /outputs/...，实际读 workDir/outputs/...。拒绝 . / .. 与非常规文件名。
const OUTPUT_PREFIX = "/outputs/";
const SEGMENT_RE = /^[A-Za-z0-9._-]+$/;
const MAX_PATH_LENGTH = 255;

function isSafeRelativeOutput(rel: string): boolean {
  if (!rel || rel.length > MAX_PATH_LENGTH) {
    return false;
  }
  return rel.split("/").every(
    (segment) => segment !== "." && segment !== ".." && SEGMENT_RE.test(segment),
  );
}

function resolveOutputPath(path: string, outputsDir: string): string | null {
  const prefix = outputsDir.replace(/\/$/, "");
  let rel = "";
  if (path.startsWith(OUTPUT_PREFIX)) {
    rel = path.slice(OUTPUT_PREFIX.length);
  } else if (path.startsWith(`${prefix}/`)) {
    rel = path.slice(prefix.length + 1);
  } else {
    return null;
  }
  if (!isSafeRelativeOutput(rel)) {
    return null;
  }
  return `${prefix}/${rel}`;
}

export async function GET(request: NextRequest) {
  const threadId = request.nextUrl.searchParams.get("threadId");
  const path = request.nextUrl.searchParams.get("path");

  if (!threadId || !THREAD_ID_RE.test(threadId)) {
    return NextResponse.json({ error: "Invalid threadId" }, { status: 400 });
  }
  if (!path) {
    return NextResponse.json({ error: "Invalid path" }, { status: 400 });
  }

  try {
    const sandbox = await getThreadSandbox(threadId);
    const outputsDir = await getSandboxOutputsDir(sandbox);
    const remotePath = resolveOutputPath(path, outputsDir);
    if (!remotePath) {
      return NextResponse.json({ error: "Invalid path" }, { status: 400 });
    }
    const content = await sandbox.fs.downloadFile(remotePath);
    const extension = remotePath.split(".").pop()?.toLowerCase() ?? "";
    const filename = remotePath.split("/").pop() ?? "download";
    const contentType = CONTENT_TYPES[extension] ?? "application/octet-stream";
    const disposition = contentType.startsWith("image/") ? "inline" : "attachment";
    const body = Uint8Array.from(content);

    return new NextResponse(body, {
      headers: {
        "Content-Type": contentType,
        "Content-Disposition": `${disposition}; filename="${filename}"`,
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.log("sandbox-download", message);
    if (message.includes("DAYTONA_API_KEY")) {
      return NextResponse.json(
        { error: "DAYTONA_API_KEY not configured" },
        { status: 500 },
      );
    }
    const lower = message.toLowerCase();
    if (
      lower.includes("not found") ||
      lower.includes("no such file") ||
      lower.includes("does not exist")
    ) {
      return NextResponse.json({ error: "File not found" }, { status: 404 });
    }
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
