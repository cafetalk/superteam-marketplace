---
name: superteam-linear
description: Use when querying Linear project management data — issues, projects, cycles via Linear MCP (prefer this session’s host Linear MCP when available; fallback to query_linear.py)
---

# Linear 洞察

通过 **Linear 官方 Hosted MCP** 查询工单、项目、迭代等（只读为主；部分场景含更新）。

## 数据源优先级（Agent 必须）

仍归属 **superteam-linear** 能力与同一套业务语义；**仅「由谁发起 MCP」分先后**：

1. **优先**：**当前 Agent 宿主**为本会话接入、且可通过内置 MCP 通道调用的 **Linear MCP**（例如 `call_mcp_tool` / 宿主等价能力；**不特指某一 IDE**）。首次若 `STATUS` 提示需认证，先走该服务器的 `mcp_auth`（空参数 `{}`），再调业务工具。
2. **回退**：本会话**无**可用 Linear MCP、工具调用失败、返回不可用、或需要与下游脚本 **完全同构的 stdout JSON**（例如管道给其它 CLI）时，执行本目录下的 **`scripts/query_linear.py`**（本机 `npx mcp-remote https://mcp.linear.app/mcp`，需 Node + 外网）。

Hub、`generate_report.py`、`preflight_linear_issue.py`、`save_linear_issue_once.py` 等 **仍只通过子进程调用 `query_linear.py`**；不在仓库内改它们。在 **Agent 对话里** 由模型拉数 / 可选写操作时，按上表优先用宿主 MCP。

## 工具与参数对齐（Agent 调用 MCP 时注意）

宿主暴露的 Linear MCP 工具名与 `query_linear.py --tool` 多为同名（如 `list_issues`、`get_issue`、`save_issue`）。**常见差异**：

| 场景 | `query_linear.py --args-json` | Linear MCP（宿主） |
|------|------------------------------|-------------------|
| 列表条数上限 | `first`（如 `80`） | `limit`（默认 50，最大 250；建议列表选任务时用 **≥50**，与 skill 其它处一致） |
| 归档 | `includeArchived` | `includeArchived`（字段相同） |

其余字段按 MCP 工具 schema 为准；与 CLI 不一致时以 **MCP 侧** 为准并自行映射。

## 脚本（CLI / 自动化 / 回退）

- `scripts/query_linear.py`：启动 `npx -y mcp-remote https://mcp.linear.app/mcp`，调用 `tools/list` / `tools/call` 查询或更新 issues。stdout 为统一 JSON 包一层 `skill` / `type` / `result`，便于脚本解析。
- `scripts/archive_cycle_issues.py`：批量归档脚本。统一走 Linear GraphQL，支持按 `issue ids`、`cycle`、`project`、`project + cycle` 收集候选 issue；默认 `dry-run`，传 `--execute` 才真正归档；只处理 `Done` / `Canceled` 的任务。

### `archive_cycle_issues.py` 用法

```bash
# 按 cycle 预览可归档任务（默认 dry-run）
python3 scripts/archive_cycle_issues.py --cycle "Cycle 42"

# 按 project 预览可归档任务
python3 scripts/archive_cycle_issues.py --project "World Cup"

# 按 issue ids 预览可归档任务（支持逗号分隔）
python3 scripts/archive_cycle_issues.py --issue-id TREX-101,TREX-102

# 按 project + cycle 真正执行归档
python3 scripts/archive_cycle_issues.py --project "World Cup" --cycle "Cycle 42" --execute
```

说明：

- `--issue-id` 不能和 `--project` / `--cycle` 混用。
- `--project`、`--cycle` 可单独使用，也可组合使用。
- `--issue-id` 支持逗号分隔、重复传参、自动去重。
- 默认只预览，不写 Linear。
- 仅 `Done` / `Canceled` 且未归档任务会进入归档候选。
- 归档执行统一使用 `LINEAR_API_KEY` + GraphQL `issueArchive`。

## 配置（`query_linear.py` 路径）

- 需要本机已安装 Node.js（包含 `npx`）。
- 首次运行可能触发 Linear OAuth 授权（`mcp-remote` 会输出登录/授权提示）。
- Agent **仅在使用本回退路径**时，需在受限终端中申请外网权限（见 superteam-git SKILL 说明）。

## 与 Hub 路由

`superteam/scripts/route.py` 中 **研发任务 / Linear** 类关键词只命中 **superteam-linear**（`query_linear.py`）。**superteam-data** 仅覆盖业务数据（活动、投放、badge、provider 等），与 Linear、多维表排期任务 **无路由重叠**。
