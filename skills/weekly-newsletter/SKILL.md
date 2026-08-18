---
name: weekly-newsletter
description: "通过调研分销商头部音乐类型并组装样式化 HTML 页面，制作每周「本周音乐」客户周报。被问及创建、撰写或发送每周周报或音乐资讯 roundup 时使用。"
---

# 每周周报

这是一项后台任务。启动后让路 — newsletter-agent 会自行调研所有类型并组装完成的 HTML。

## 1. 选定类型

- 若 Jane 指定了类型，使用那些。否则请 **chinook-analyst** 提供目录中按收入排名前 4 的类型并作为专题。

## 2. 后台启动

- 调用 `start_async_task(subagent_type="newsletter-agent", description=...)`
  **一次**，在 `description` 中写入类型列表（例如「调研并组装本周周报，类型：Rock、Latin、Jazz、Classical」）。立即返回任务 ID，不会阻塞。
- 告知 Jane 周报正在后台制作，然后 **停止**。不要轮询 — 等她下次询问时再检查。
- **不要** 自己调研类型或组装周报 — 这完全是 newsletter-agent 的工作。

## 3. 当被问及是否就绪

- 获取 task_id：调用 `list_async_tasks()` 并读取 newsletter-agent 条目的 `task_id:` 字段。不要依赖对话中更早的 task_id — 它可能已滚出上下文或被摘要掉；
  `list_async_tasks` 从持久状态读取，而非记忆。
- 调用 `check_async_task(task_id)`。
- 若 `status` 尚未终结（`success` 或 `error`），向 Jane 汇报进度并停止 — 等她下次再询问。
- 若 `status` 为 `error`，告知 Jane 本周无法完成周报并停止 — 没有 HTML 可保存。
- 若 `status` 为 `success`，`result` 是完成的 HTML，原样使用 — 此处无需 Markdown 转换，newsletter-agent 已完成。
  立即在同一轮继续第 4 步 — 不要先向 Jane 要许可。她已在第 1 步要求周报；已完成的后台任务不是需要重新确认的新决策。

## 4. 保存（一次）

- 可能对同一 task_id 被多次询问（例如 Jane 在你已保存后又问「好了吗？」）— 不要保存重复文件。确定性检查，不要靠对话记忆（可能被摘要掉）：调用 `glob("/outputs/newsletter-*-<task_id 前 8 位>.html")`。若已匹配文件，告知 Jane 已保存在该路径并停止。
- 否则用代码解释器获取时间戳：
  `new Date().toISOString().slice(0, 19).replace(/:/g, '-')` — 这是日期加时间，不只是日期，以免同一天真正的新周报请求覆盖上一份。
- 将第 3 步的 HTML **原样** `write_file` — 不编辑、不添加说明 — 到
  `/outputs/newsletter-<timestamp>-<task_id 前 8 位>.html`。

## 完成

告知 Jane 周报的保存位置。若刚保存的 HTML 提到某类型未纳入（newsletter-agent 在某类型调研失败时会自行注明），用自己的话转告 Jane。
