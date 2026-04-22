---
name: superteam-report-team
description: 使用 Linear 的迭代(Cycle)数据为 workspace 内所有 Team 生成团队周报（完成/进行中/下周计划/未划入迭代任务 + 进度、受阻与其它风险）
---

# 团队迭代周报（Linear）

为 **当前 Linear workspace 的全部 Team**，基于各 Team 的 **当前 Cycle** 拉取 issues 并生成一份 Markdown 团队周报：

- 过滤并汇总 **Done / In Progress**：用于“本周完成/进行中”
- **完成 + 进行中**合并为「本周进展」，含**总览**（非 Task 编号类标题归纳）与按负责人明细（`[完成]` / `[进行中]`）
- **下周计划**含**总览** + 按负责人明细（Task 编号类仅出现在明细）
- **迭代进度与风险**：多块指标按逻辑分组展示，组之间用 Markdown **`---`** 分割线区分：**(1) Cycle 规模与进度**（总任务数、按**数量**的完成率、**估点完成率** = 已完成估点÷全部估点、当前 Cycle **时间进度**、**节奏**：**缓慢 / 正常 / 赶超**——在能解析 Cycle 起止时间时，用「点完成率与时间进度的差」与 ±12% 容差比较；无估点或无法解析日历时降级说明）→ **(2) 工作类型标签** → **(3) 估点分组** → **(4) 状态分布** → **(5) Team 补充**；**受阻**与**其他风险**另列
- **数据拉取**：**当前 Cycle 内 issue** 必须用带 `cycle` 参数的 `list_issues`（否则仅按 Team 拉取时 MCP 常不返回 `cycle`，周报会空）；**未划入迭代条数**另用一次全 Team 分页 `list_issues`，但全表列表常**不带** `cycle`/`cycleId`，脚本只统计接口上**可明确判定**「未关联 Cycle」的条目（缺字段的记为「无法判定」并从数字中排除，避免把整 Team 误算成未划入）；默认**不含已完成**，与 Linear「无 Cycle」视图常见筛选一致；`--uncycled-include-completed` 可改回含 Done 的口径
- 对**进行中**任务拉取评论，启发式标出**待讨论/待确认**等线索（需人工复核）
- **未划入迭代的任务**：同上口径（可判定 + 不含已取消、默认不含已完成）；有当前 Cycle 时在「Team 范围补充」展示，无 Cycle 时单独一小节

## 配置

无需 Linear API Token。脚本 `generate_team_weekly_report.py` 使用 **本机 Linear MCP（mcp-remote）** 发起 OAuth 并通过 stdio JSON-RPC 调用 Linear MCP 工具。

在 **Agent 会话** 中若由模型代为拉取 Linear 数据，按 **superteam-linear** SKILL：优先使用 **当前 Agent 宿主已接入的 Linear MCP**；本仓库脚本路径不变。

前置条件：

- 已安装 Node.js（包含 `npx`）

### 发布到钉钉文档（默认自动）

根目录 nodeId 与 `weekly-report` 一致（`skills/weekly-report/scripts/generate_report.py` 中的 `REPORT_FOLDER_ID`，团队周报与个人周报共用同一钉钉父文件夹）。**团队周报**在上传前会在该父目录下解析或创建 `YYYY/YYWww` 层级目录（例如 `2026-W15` → `2026/26W15`），若已存在同名目录则直接写入其中。

- **钉钉 MCP URL**：优先读 `DINGTALK_MCP_URL`（`~/.superteam/config` 或环境变量）；未设置时会尝试从 **`~/.cursor/mcp.json`** 中解析带 `dingtalk` 的 HTTP MCP 地址（兼容误嵌套的 `mcpServers` 结构），与你在 Cursor 里配置的钉钉文档 MCP 一致。**配置解析成功后，写盘会先 `list_nodes` / 必要时 `create_folder` 再 `create_document` 上传**（钉钉内文档名：`<ISO周>-团队周报.md`）。若本机 Python 报 **SSL 证书校验失败**，可安装 `certifi`（脚本在已安装时会用其 CA 包访问 `mcp-gw.dingtalk.com`）。
- **`DINGTALK_REPORT_FOLDER_ID`**（可选）：覆盖**父**文件夹 nodeId；不设则使用内置默认值。
- **`--no-publish-dingtalk`**：仅生成本地文件，不尝试钉钉上传（即使已配置 URL）。

脚本在**已成功写入本地 Markdown 之后**再上传；若上传失败会 **exit 1**，但本地文件仍保留。

## 使用方式

```bash
.venv/bin/python skills/superteam-report-team/scripts/generate_team_weekly_report.py
```

常用参数：

- **不传 `--week`**：自动使用 **上周**（本地日历上一周一至周日）对应的 **本年度 ISO 周**（如 `2026-W14`），输出路径为 `reports/team-weekly/<该周>.md`，标题中标注「上周」。
- `--week 2026-W15`：手动指定 ISO 周（覆盖默认）
- `--output ...`：指定输出文件
- `--dry-run`：只打印将要拉取的 team/cycle 计划，不实际请求 issues
- `--format json`：stdout 输出 JSON，含 `markdown`、`publish` 元数据，以及 `dingtalk` 字段（上传结果或 `skipped` 原因）
- `--no-publish-dingtalk`：关闭生成后的自动钉钉上传
- `--uncycled-include-completed`：「未划入迭代」计数包含已完成（Done）；默认不含
- `--view dashboard|text`：迭代进度展示风格（默认 `dashboard` 可视化增强，`text` 为原始纯文字）
- `--chart-style auto|text|mermaid|dingtalk`：`auto` 在未上传钉钉时用 `mermaid`（本地预览），**将上传钉钉时用 `dingtalk`**：表格 + 字符条（与 `text` 相同，不含 Mermaid）；`mermaid` 全程 ```mermaid 代码块
- `--member-group all|frontend|backend|前端|后端`：按成员表 `role` 过滤统计范围（仅统计匹配职能成员的任务）；同步钉钉时文档名为 `周-团队周报.md` / `周-团队周报-前端.md` / `周-团队周报-后端.md`，避免互相覆盖

