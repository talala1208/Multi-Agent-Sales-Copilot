"use client";

import { useEffect, useRef, useState } from "react";
import { useStreamContext } from "@/providers/Stream";
import type { AsyncTask } from "@/providers/Stream";
import type { Message } from "@langchain/langgraph-sdk";
import {
  LoaderCircle,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronUp,
  Download,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getContentString } from "./utils";
import { findOutputPaths } from "./output-path";

const POLL_INTERVAL_MS = 5000;
const DONE_DISPLAY_MS = 8000;

// 与 deepagents 的 AsyncSubAgentMiddleware 相同的终结状态集合
//（async_subagents.py 中的 _TERMINAL_STATUSES）— 所有被跟踪任务
// 进入其中之一后，无需继续轮询。
const TERMINAL = new Set(["success", "error", "cancelled", "timeout", "interrupted"]);

// 「就绪」是独立的持久状态，不只是「调研完成且无事可做」：
// 无完成通知器时，主线程不会自动唤醒，此徽章是告诉用户
// 该询问周报的唯一信号。须保持显示直到用户实际询问（或调研失败），
// 不能一闪即逝。
type ReportPhase = "assembling" | "done" | "ready" | null;

function TaskStatusIcon({ status }: { status: string }) {
  if (!TERMINAL.has(status)) {
    return (
      <LoaderCircle className="size-3 shrink-0 animate-spin text-muted-foreground" />
    );
  }
  if (status === "success") {
    return <CheckCircle2 className="size-3 shrink-0 text-green-600" />;
  }
  return <XCircle className="size-3 shrink-0 text-red-500" />;
}

// 在本标签页外创建的 run（另一标签页，或重载后发送的跟进消息）
// 不会推入本标签页的 SSE 流 — 仅本浏览器提交的 run 会。
// 因此本徽章直接轮询线程状态，而不依赖 `stream.values`（本浏览器
// 流的快照，线程从别处推进时会立即过时）。
//
// 除「N 个任务运行中」外，还区分「正在组装报告」
//（所有调研任务已终结，但线程仍忙 — weekly-newsletter 技能的最终组装轮）
// 与「报告就绪」（全部终结、线程空闲，且最后一条 AI 消息出现 /outputs/*.html 路径）。
// 「组装中」需第二次调用 `threads.get` 获取线程自身状态，因为
// 已完成但空闲且尚无报告的线程（如所有类型失败）若只看 async_tasks
// 与「仍在组装」无法区分。
export function AsyncTaskStatus({ threadId }: { threadId: string | null }) {
  const stream = useStreamContext();
  const [tasks, setTasks] = useState<Record<string, AsyncTask>>({});
  const [reportPhase, setReportPhase] = useState<ReportPhase>(null);
  const [reportPath, setReportPath] = useState<string | null>(null);
  const [justFinished, setJustFinished] = useState(false);
  const [expanded, setExpanded] = useState(false);
  // 本徽章已解析报告结果的 task-id 集合（排序、拼接）—
  // 找到路径，或确认无可组装内容。在轮询 effect 重跑间持久化
  //（不同于 poll() 中的局部闭包变量），以免同线程上后续无关忙碌期
  //（如另一技能的 tool call）为已交付或已放弃的报告复活「正在组装周报」。
  const resolvedTaskKeyRef = useRef<string | null>(null);

  useEffect(() => {
    if (!threadId) {
      setTasks({});
      setReportPhase(null);
      setReportPath(null);
      setJustFinished(false);
      return;
    }
    const activeThreadId = threadId;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    // 局部变量，非 React state：跟踪*本*监视会话是否曾见过
    // 非终结任务或进行中的组装，以便仅在真实状态转换时闪烁「完成」，
    // 而非每次轮询 tick。
    let hadWorkInFlight = false;

    async function poll() {
      try {
        const state = await stream.client.threads.getState(activeThreadId);
        const values = state.values as Record<string, unknown> | undefined;
        const cachedTasks = (values?.async_tasks ?? {}) as Record<string, AsyncTask>;
        const messages = (values?.messages ?? []) as Message[];
        if (cancelled) return;

        // 缓存的 `status` 字段仅在服务端作为 check_async_task/list_async_tasks
        // 调用的副作用推进（见 deepagents 的 _fetch_live_status）—
        // 无通知器设计下无人调用这些工具，可能永远停在 "running"。
        // 改为直接拉取每个非终结任务的实时 run 状态，
        // 单任务拉取失败时回退到缓存值。
        const nextTasks: Record<string, AsyncTask> = { ...cachedTasks };
        await Promise.all(
          Object.entries(cachedTasks)
            .filter(([, t]) => !TERMINAL.has(t.status))
            .map(async ([id, t]) => {
              try {
                const run = await stream.client.runs.get(t.thread_id, t.run_id);
                nextTasks[id] = { ...t, status: run.status };
              } catch {
                // 保留缓存状态
              }
            }),
        );
        if (cancelled) return;

        setTasks(nextTasks);
        const taskList = Object.values(nextTasks);
        const taskKey = taskList
          .map((t) => t.task_id)
          .sort()
          .join(",");
        const stillRunning = taskList.some((t) => !TERMINAL.has(t.status));
        const allTerminal = taskList.length > 0 && !stillRunning;

        let path: string | null = null;
        if (allTerminal) {
          const lastAi = [...messages].reverse().find((m) => m.type === "ai");
          if (lastAi) {
            const found = findOutputPaths(getContentString(lastAi.content));
            if (found.length) path = found[found.length - 1];
          }
        }
        setReportPath(path);

        if (stillRunning) {
          hadWorkInFlight = true;
          setReportPhase(null);
          timer = setTimeout(poll, POLL_INTERVAL_MS);
          return;
        }

        if (allTerminal && path) {
          resolvedTaskKeyRef.current = taskKey;
          setReportPhase("done");
          if (hadWorkInFlight) {
            setJustFinished(true);
            setTimeout(() => setJustFinished(false), DONE_DISPLAY_MS);
          }
          hadWorkInFlight = false;
          return;
        }

        if (allTerminal) {
          // 已在更早轮询中解析过此精确任务集（找到报告，或
          // 确认无可组装）— 同线程上后续无关忙碌期（完全不同的技能）
          // 不是本报告重新打开，不要为此重新进入「组装中」。
          if (resolvedTaskKeyRef.current === taskKey) {
            setReportPhase(null);
            hadWorkInFlight = false;
            return;
          }
          // 失败的任务集永远不会被组装 — 无需再等待，
          // 立即解析并让渲染时失败检查（直接基于 `tasks`，非 reportPhase）接管。
          if (taskList.some((t) => t.status !== "success")) {
            resolvedTaskKeyRef.current = taskKey;
            setReportPhase(null);
            hadWorkInFlight = false;
            return;
          }
          // 调研完成但尚无报告路径 — 检查线程是在主动组装，
          // 还是空闲等待用户询问。
          const thread = await stream.client.threads.get(activeThreadId);
          if (cancelled) return;
          if (thread.status === "busy") {
            hadWorkInFlight = true;
            setReportPhase("assembling");
            timer = setTimeout(poll, POLL_INTERVAL_MS);
            return;
          }
          // 所有调研成功、线程空闲、尚无报告 — 这就是
          // 「现在询问」信号，应保持显示（继续轮询）而非解析/隐藏，
          // 直到用户下一条消息开始组装或产出报告。
          hadWorkInFlight = true;
          setReportPhase("ready");
          timer = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch {
        if (!cancelled) timer = setTimeout(poll, POLL_INTERVAL_MS);
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
    // 每轮结束时重跑，以防启动了新任务 —
    // `stream.isLoading` 在本浏览器自己的启动轮完成后立即变 false，
    // 此时新 task ID 才会首次出现。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId, stream.isLoading]);

  const taskList = Object.values(tasks);
  const running = taskList.filter((t) => !TERMINAL.has(t.status));
  const showSpinner = running.length > 0 || reportPhase === "assembling";
  // 无运行中任务时，剩余任务按定义均为终结状态
  //（见上方 `running`）— 「终结」不等于「成功」，需显式检查
  // 而非默认成功标题/图标。
  const hasFailure =
    running.length === 0 &&
    taskList.length > 0 &&
    taskList.some((t) => t.status !== "success");

  if (running.length === 0 && !reportPhase && !justFinished) return null;

  const headline =
    running.length > 0
      ? `${taskList.length - running.length}/${taskList.length} researching`
      : reportPhase === "assembling"
        ? "Assembling report..."
        : reportPhase === "done"
          ? "Report ready"
          : reportPhase === "ready"
            ? "Research done — ask for your newsletter"
            : hasFailure
              ? "Research failed"
              : "Research complete";

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className={cn(
          "flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs",
          showSpinner
            ? "text-muted-foreground"
            : hasFailure
              ? "border-red-200 bg-red-50 text-red-700"
              : reportPhase === "ready"
                ? "border-amber-200 bg-amber-50 text-amber-700"
                : "border-green-200 bg-green-50 text-green-700",
        )}
      >
        {showSpinner ? (
          <LoaderCircle className="size-3 animate-spin" />
        ) : hasFailure ? (
          <XCircle className="size-3" />
        ) : (
          <CheckCircle2 className="size-3" />
        )}
        <span>{headline}</span>
        {expanded ? (
          <ChevronUp className="size-3" />
        ) : (
          <ChevronDown className="size-3" />
        )}
      </button>

      {expanded && (
        <div className="absolute right-0 z-10 mt-1 w-64 rounded-md border bg-white p-2 shadow-md">
          <ul className="flex flex-col gap-1.5">
            {taskList.map((t) => (
              <li key={t.task_id} className="flex items-center gap-2 text-xs">
                <TaskStatusIcon status={t.status} />
                <span className="truncate">{t.label || t.agent_name}</span>
              </li>
            ))}
            {(reportPhase === "assembling" || reportPath) && (
              <li className="flex items-center gap-2 border-t pt-1.5 text-xs font-medium">
                {reportPhase === "assembling" ? (
                  <LoaderCircle className="size-3 shrink-0 animate-spin text-muted-foreground" />
                ) : (
                  <CheckCircle2 className="size-3 shrink-0 text-green-600" />
                )}
                <span className="truncate">
                  {reportPhase === "assembling"
                    ? "Assembling newsletter"
                    : "Newsletter"}
                </span>
                {reportPath && threadId && (
                  <a
                    href={`/api/sandbox-download?threadId=${encodeURIComponent(threadId)}&path=${encodeURIComponent(reportPath)}`}
                    className="ml-auto text-muted-foreground hover:text-foreground"
                  >
                    <Download className="size-3" />
                  </a>
                )}
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
