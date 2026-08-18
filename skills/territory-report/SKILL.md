---
name: territory-report
description: "生成销售辖区报告 — 收入、头部客户、头部类型及 Jane 客户群趋势，并附图表。被问及辖区报告、销售汇总、业绩数字或「我的客户群情况如何」时使用。"
---

# 辖区报告

这是一项指标任务。数字来自数据库；图表由数据渲染。

## 1. 收集指标

请 **chinook-analyst** 提供 Jane 的客户群数据（`SupportRepId = 3`）：

- 总收入和发票数量。
- 按收入排名的头部客户（含金额）。
- 按类型划分的收入（Jane 的客户）。
- 明显趋势（如有用，例如按年度的收入）。

获取精确数字；如需合并结果，用 **代码解释器** 计算。

## 2. 撰写报告

- 用代码解释器获取时间戳：
  `new Date().toISOString().slice(0, 19).replace(/:/g, '-')` — 这是日期加时间，不只是日期，以免同一天再次请求时静默覆盖早先报告。
- 用 `write_file` 将清晰的 Markdown 报告写入
  `/outputs/territory_report-<timestamp>.md`：标题汇总、头部客户列表、按类型收入表。

## 3. 图表

用 `write_file` 写一段简短 Python 脚本，用 matplotlib 将按类型收入绘制成饼图，保存到
`/outputs/territory_chart-<timestamp>.png`（与第 2 步相同时间戳），然后用 `execute` 运行（若尚未安装 matplotlib 则先安装）。在报告中用裸文件名引用图片
（例如 `![按类型收入](territory_chart-<timestamp>.png)`），不要用绝对路径 `/outputs/...` — Jane 下载报告和图表时，两者会落在同一本地文件夹且无 `outputs` 子目录，相对文件名才能正确解析；绝对路径仅适用于下方聊天回复中的嵌入。

## 完成

告知 Jane 报告和图表的保存位置，并给出收入 headline 数字。在回复中用 Markdown 图片嵌入图表 —
`![按类型收入](/outputs/territory_chart-<timestamp>.png)` — 使用该精确绝对路径（与第 3 步相同的时间戳文件名），不要只在文字里提文件名，以便在聊天中内联渲染，而不只是显示为下载链接。
