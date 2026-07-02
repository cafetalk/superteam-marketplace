---
name: superteam-report
description: Use when generating weekly reports — personal Markdown reports from GitLab/MR/agent data, or team-wide Linear Cycle reports for all Teams in the workspace
---

# 智能周报生成

根据 `superteam-linear` 与 `superteam-git` 数据，自动生成 Markdown 格式周报。

## 命令入口

可直接使用 `superteam-report` 命令（例如在支持 slash skill 的客户端中使用 `/superteam-report`）。

`/superteam-report` 不带参数时，默认生成“上周（周一到周日）”周报；如需本周可在 query 中包含“本周”，或传 `--week this`。

**路由关键词（`superteam/scripts/route.py`）**：单独说「**周报**」默认走**个人**脚本；含「团队 / 迭代 / 全团队…」等团队向短语时走团队脚本（二者不会同时执行）。**Pulse 快照**：`pulse 快照` / `trex pulse` / `TREX-493` / `sprint 日报` 等 → `snapshot_sprint.py`；`member 快照` / `成员负载快照` 等 → `snapshot_member.py`（仅显式触发；`pulse-daily` 不跑成员负载）。

当前升级为 v3 模式（**数据脚本 + LLM 生成**）：脚本只负责采集结构化数据，周报正文由 skills 内 LLM 基于全量数据进行分析与写作。

默认做法：先取 JSON 原始数据，再由 LLM 输出 Markdown 周报（非脚本固定模板）。

**团队迭代周报**（全 workspace 各 Team 的当前 Cycle）为另一入口：见下文「团队迭代周报（Linear）」；由 `scripts/generate_team_weekly_report.py` 生成，不经过个人周报的 LLM 模板流程。

内置前提条件校验：默认要求 `superteam-linear` 可访问；若 Linear MCP 不可用，将返回“前提条件未满足”并中止周报生成（可通过 `--require-linear false` 关闭）。

执行前会先做网络前置检查（`mcp.linear.app` DNS/外网可达性）；检查不通过时会先提示“需要申请网络权限”。

## 首次设置（workspace）

周报里的 Git 数据来自 `superteam-git`。它会扫描一个或多个 workspace 根目录下的多个仓库，所以每个人都要配置自己的工作目录（可多根目录）。

### 在哪里设置

在 `~/.superteam/config` 中增加：

```ini
SUPERTEAM_GIT_WORKSPACE=/你的代码根目录
```

多个根目录用系统路径分隔符连接（macOS/Linux 为 `:`，Windows 为 `;`），例如：

```ini
SUPERTEAM_GIT_WORKSPACE=/Users/yourname/code:/Users/yourname/work
```

### 这个配置有什么用

- 让周报只统计你的真实项目仓库，避免扫错目录
- 避免漏掉你常用代码目录中的提交
- 显著提升周报中的提交量、改动分析、任务-代码关联准确性

### 未设置时的行为

- 系统会提示你当前未配置 `SUPERTEAM_GIT_WORKSPACE`
- 并**中止周报生成**（不再使用任何默认目录兜底）
- 明确提示你先完成配置后再重试，避免因扫错目录导致错误周报

## Agent Wrapper 调用规范（必须）

当用户触发 `/superteam-report` 时，AI 必须按下面顺序执行（禁止跳过）：

1. **先走可外网执行通道**调用脚本，而不是直接假设本地网络可用。  
2. 若执行器支持权限申请，先申请网络权限（建议完整网络）；若出现权限弹窗，引导用户选择 `Always allow in this workspace`。  
3. 先执行（**必须**）：

```bash
python3 skills/superteam-report/scripts/generate_report.py --format json
```

4. 从 JSON 中读取并使用以下字段进行 LLM 分析（**必须使用全量，不得只取前几条**）：

- `sources.superteam-linear.completed`
- `sources.superteam-linear.in_progress`
- `sources.superteam-linear.todo`
- `sources.superteam-git.summary`
- `sources.superteam-git.commits`（全量）
- `sources.superteam-git.project_summaries`
- `sources.superteam-git.global_analysis`

5. LLM 输出周报正文（Markdown）时必须满足：

- 采用**固定简版模板**（见 5.2），不要自由发挥版式；
- 保留“核心证明 + 功能总汇总”，减少冗长细节；
- 对每个“完成任务”给出最少 1 条、最多 2 条关联 commit 作为证明（含依据）；
- 需要保留“本周提交明细（全部）”，但每条只保留一行（hash + subject）；
- 在形成“代码改动汇总/技术影响”前，必须对关键 commit 执行代码深读（`git show <commit>`）；至少覆盖每个任务已关联 commit，以及每项目改动量 Top 提交；
- 周报里给出的“功能改动/技术影响”必须可回溯到具体代码证据（文件、函数、条件分支或接口变更），禁止模板化泛化文案；
- 禁止输出 JSON 原文给用户，输出时按正常 Markdown 渲染（禁止包代码块）。

5.1 LLM 代码深读步骤（必须）：

1) 先基于 `sources.superteam-git.commits` 做任务↔提交关联（Ref、标题、关键词）。  
2) 对关联命中的 commit 执行：

```bash
git -C <repo_path> show --no-color --stat --patch <commit_sha>
```

3) 若单个 commit 过大，至少读取：变更文件列表、关键 hunks、新增/修改函数定义与条件分支。  
4) 再输出“做了什么功能改动、为何这么改、影响了哪些模块/调用方”。  

5.2 固定输出模板（简版，必须）

必须按以下结构输出（标题顺序不可变）：

1) `# 🚀 研发周报 | <姓名>` + 周期/同步日期/关联迭代  
2) `## 可视化摘要`（固定 6 行指标表）  
3) `### 📊 一、工程与代码影响力指标`  
   - 总增删、净变化、主要项目（Top2）  
   - 每个项目 1 行“功能总汇总”（不要超过 2 句）  
4) `### 🎯 二、核心技术交付（核心证明）`  
   - 每个完成任务固定 2 行：
     - `证明提交：repo@hash1, repo@hash2(可选)`
     - `证明依据：Ref 命中 / 标题命中 / 代码证据（文件/函数）`
5) `### 🔵 三、本周功能总汇总`  
   - 按功能域列 3-6 条（例如：周报发布、任务关联、多工作区扫描）  
   - 每条格式：`功能 -> 关键改动 -> 影响`
6) `### 📚 四、本周提交明细（全部）`  
   - 全量 commit，一行一个：`repo@hash subject`
7) `### ⚠️ 五、风险与下周计划`  
   - 风险 1-3 条 + 下周计划 1-3 条（简洁）

长度控制（必须）：

- 正文总长度建议 800~1800 中文字符；
- 每个任务证明段最多 4 行；
- 禁止输出“未从改动中识别出明确技术主题（需人工复核）”这类兜底空话，若证据不足应明确写“证据不足：<原因>”。

6. 若 JSON 返回 `status=precondition_failed`，按前提条件失败流程输出，不得伪造空结果。

7. 若后续需要兼容旧模式，可选执行（非默认）：

```bash
python3 skills/superteam-report/scripts/generate_report.py --format markdown
```

7.1 **可视化摘要（必须）**：在完整周报前补一个简短“可视化摘要”区块（Markdown 表格即可），至少包含：
   - 周期
   - 完成任务数
   - 进行中任务数
   - 代码增删（`+x/-y`）
   - 净变化
   - 主要项目（Top2）

8. 若返回包含 `ENOTFOUND mcp.linear.app` / `fetch failed` / `local mcp closed stdout unexpectedly`，必须明确告知“当前为网络权限/可达性问题”，并提示用户授权后重试。  
9. 只有在 Linear 前提条件满足后，才输出完整周报；否则输出前提条件失败报告，不得伪造空任务结果。  
10. 若后续需要“发布到钉钉”的机器可读参数，可在**后台额外调用一次**：

```bash
python3 skills/superteam-report/scripts/generate_report.py --format json
```

但这次 JSON 仅用于 agent 内部解析，不直接展示给用户。

## 生成后发布流程（必须）

周报生成后，必须进入“确认-修改-发布”流程。发布目标为钉钉文档**根目录下的周目录**：

- 根目录链接：`https://alidocs.dingtalk.com/i/nodes/ZgpG2NdyVXrr9A0bCAkYARkl8MwvDqPk?utm_scene=team_space`

### 1) 先询问是否修改（必须用 AskQuestion）

展示生成的周报正文后，必须使用 `AskQuestion`，不允许只用文本问答：

```json
{
  "questions": [{
    "id": "weekly_report_action",
    "prompt": "周报已生成，请选择下一步：",
    "options": [
      {"id": "edit", "label": "我要修改内容"},
      {"id": "publish", "label": "内容OK，直接发布到钉钉"},
      {"id": "cancel", "label": "先不发布"}
    ],
    "allow_multiple": false
  }]
}
```

- 选择 `edit`：让用户给出修改意见，完成修改后再次进入本步骤。
- 选择 `cancel`：结束流程，不发布。
- 选择 `publish`：进入步骤 2。

### 2) 检查钉钉 MCP 可用性（只检查，不代配置）

发布前必须检查钉钉 MCP 可用性。建议先调用 `list_nodes`（使用 `folderId` 为**根目录** nodeId）验证连通与权限。

- 若 MCP 不可用（未安装/未授权/调用失败）：
  - 明确提示用户：当前无法发布到钉钉文档。
  - 仅引导用户自行完成 MCP 配置与授权后重试。
  - **不要**由 AI 代替用户做 MCP 安装或账号配置。

### 3) 文档命名规则（必须）

按“所在周 + 姓名”命名，扩展名为 `.md`：

- `W<周序号>-<姓名>.md`
- 示例：`W14-李佳林.md`

说明：
- 周序号按周报窗口所在周计算（如 2026.03.30 - 2026.04.05 属于 W14）。
- 姓名优先使用 Linear 返回的成员名；无则用用户指定名称。
- 发布目录按“年份后两位 + W + 周序号”定位，如：2026 年第 15 周发布到 `26W15` 文件夹。

### 4) 调用 create_document 发布（必须）

先用 `list_nodes` 在根目录下定位本周目录（如 `26W15`），再使用钉钉 MCP `create_document`：

- `name`: 按上面的文件名
- `folderId`: 本周目录（`26Wxx`）对应的 nodeId（由根目录 `list_nodes` 结果定位）
- `markdown`: 周报 Markdown 正文（必须使用真实换行）

创建成功后返回：
- 文档标题
- 文档链接（URL）
- 所在目录（本周目录，如 `26W15`）

## 定位

team member 通过 superteam 主动请求（如"帮我生成本周周报"），系统自动汇总本周工作数据并生成结构化周报。

## 状态

> **v3 可用** — 脚本负责数据聚合，LLM 负责周报分析与写作；仍支持 `superteam-linear` + `superteam-git`。

## 输入

- 时间范围（`--week this|last`，默认根据 query 识别）
- 成员（`--member`，默认 `me`）

## 输出

- Markdown 格式周报，至少包含：
  - Linear：已完成任务、进行中任务
  - Git：项目级代码改动、提交明细、全局改动主题
  - 任务-代码关联（含关联依据）

## 可用数据源

| 数据源 | 说明 | 状态 |
|--------|------|------|
| superteam-linear | 成员任务、状态、完成时间 | ✅ 已接入 |
| superteam-git | 周期内提交、功能改动、影响分析 | ✅ 已接入 |

## 团队迭代周报（Linear）

团队迭代周报由 `skills/superteam-report/scripts/generate_team_weekly_report.py` 生成，面向 **当前 Linear workspace**。它按报告周（`--week`，默认上一自然周）合并各 Team 命中的 Cycle 任务，输出一份 Markdown 团队周报；正文止于 **团队风险**，风险项必须附判断依据。

### 适用场景

- 用户明确要「团队周报 / 迭代周报 / 全团队周报 / Cycle 周报」。
- 需要按 Linear Cycle 汇总项目、成员、负载、风险，而不是生成某个人的研发周报。
- 不适用于个人周报；个人周报走 `generate_report.py` 或 `scripts/run_reports.sh personal`。

### 数据拉取口径

- **Cycle 任务**：各 Team 必须用带 `cycle` 参数的 `list_issues` 拉取报告周 Cycle 内任务；全量 `list_issues(team)` 常缺少 `cycle` 字段，不能替代。跨 Team 按 issue key 去重。
- **项目维度补充**：另拉全 Team 任务，用于项目阶段、项目分工、项目风险等跨 Cycle 判断。
- **状态判定**：除 Team 状态显示名映射外，回退解析 issue 上的 `statusType`、`state.type`，避免旧工作流状态名未进入映射表时被误判。
- **成员口径**：成员数据来自 `list_members()`（与 `superteam-member/scripts/list_members.py` 同源），先排除 `deleted` / `merged` / 无 role；研发名单为 `backend` / `frontend` / `architect`。
- **禁止硬编码项目**：项目清单、阶段、过滤与统计不得按具体 Linear 项目名/id 写死；只能依赖 issue 数量与状态、project 时间、Lead/Milestone、成员角色等通用字段。

### 项目纳入口径

- **项目过滤**：以 `--week` 对应 ISO 周周一为界；解析出的发布日（提测/发布里程碑或 `targetDate`）严格早于该周一的项目，不进入周报项目清单，并从 Cycle 任务中按项目名剔除。当周及之后发布的项目仍纳入。
- **未关联项目**：依赖 issue 上的 `project` / `projectName` 等字段；未关联 Project 的任务归入「未关联项目」。
- **下个里程碑**：取 Linear Project Milestone 中最近一个未到期节点（名称 + 日期）；无未到期 Milestone 时回退下一提测/发布日。
- **当前处理人**：仅当下个里程碑为「项目启动」时，列出该节点下未完成任务的 assignee；其他里程碑显示 `—`。

### 项目阶段与进度口径

- **项目阶段**：按整个项目任务 + 提测/发布里程碑推导，与「本 Cycle 是否做完」无关。
- **启动中**：存在名称含「项目启动」的 Project Milestone，且该 Milestone 下仍有未完成任务；优先于日期口径。
- **开发类阶段**：`启动中` / `开发中` / `联调中` / `设计中` / `延期开发中` 使用开发进度。开发进度优先取本 Cycle 且 assignee 为成员表 `backend` / `frontend` / `architect` 的任务；子集为空时退化为全量。
- **测试类阶段**：`测试中` / `待发布` / `已上线` / `延期上线` 使用测试进度。测试进度优先测试职能指派；为空时回退 Bug 标签/标题口径；再为空则用全量。
- **测试中展示**：项目阶段格追加本 Cycle Bug 数与未关闭数；风险列仍扫描全 Cycle。
- **本 Cycle 已清**：若本 Cycle 已无未完成单，但全项目仍有未完成研发单，阶段为「开发中」时显示 `开发中·本Cycle已清`。

### 输出结构

团队周报按以下顺序生成：

1. **项目一览**：基于 [Linear Projects](https://linear.app/t-rex-v1/projects/all)，展示 Lead、提测/发布时间、项目阶段、阶段进度、参与人、风险等。表头「进度（完成/进行中/待办+Backlog）」仅统计本 Cycle；「进行中」= Linear 状态类型 `Started`。
2. **按项目**：每个项目输出 HTML 键值表（Leader / 里程碑 / 进度 / 参与人 / 风险）与分工表。分工表列为 **角色 | 负责人 | 任务**，角色与负责人列合并单元格；后端/前端/测试/其他分块；摘要最多 4 条明细，超长描述省略，超出按父单/主题合并。
3. **按成员**：每人先输出「上周工作总结」「下周计划」各一句（由 Cycle 内任务自动归纳），再附独立 HTML 表格：**项目 | 任务ID | 状态 | 任务 | 剩余(天) | 风险**；项目列合并。
4. **成员负载**：估点换算工时 `1→1h、2→2h、3→4h、4→8h、5→16h`；负载 = 当周合计工时 ÷ 40h。仅统计报告周内 `completedAt` 完成、当前进行中/In Review/受阻、以及 Todo 且 due 在本周的任务；更早完成不计；≥100% 标 🔥；按合计工时降序。
5. **团队风险**：§4 后逐类列出触发项并附判断依据，包含受阻、久未更新、未分配、描述过短、高优堆积、逾期、负载偏高、里程碑偏紧、§1 项目风险汇总、启动中等。

### 配置与发布

- **Linear**：无需 Linear API Token。脚本使用本机 Linear MCP（`mcp-remote`）发起 OAuth，并通过 stdio JSON-RPC 调用 Linear MCP 工具。前置条件是已安装 Node.js（包含 `npx`）。
- **Agent 会话**：若由模型代为拉取 Linear 数据，按 **superteam-linear** SKILL；优先使用当前 Agent 宿主已接入的 Linear MCP。
- **钉钉发布**：团队周报默认自动上传。脚本先成功写入本地 Markdown，再上传钉钉；若上传失败会 `exit 1`，但本地文件保留。
- **钉钉目录**：团队周报与个人周报共用同一钉钉父文件夹。上传前会在父目录下解析或创建 `YYYY/YYWww` 层级目录，例如 `2026-W15` → `2026/26W15`。
- **`DINGTALK_MCP_URL`**：优先读环境变量或 `~/.superteam/config`；未设置时尝试从 `~/.cursor/mcp.json` 解析带 `dingtalk` 的 HTTP MCP 地址。配置解析成功后，先 `list_nodes` / 必要时 `create_folder`，再 `create_document`。
- **`DINGTALK_REPORT_FOLDER_ID`**：可选，覆盖父文件夹 nodeId；不设则使用内置默认值。
- **`--no-publish-dingtalk`**：仅生成本地文件，不尝试钉钉上传。
- **SSL 证书问题**：若本机 Python 报 SSL 证书校验失败，可安装 `certifi`；脚本在已安装时会用其 CA 包访问 `mcp-gw.dingtalk.com`。

### 团队周报命令

```bash
python3 skills/superteam-report/scripts/generate_team_weekly_report.py
```

常用参数：

| 参数 | 说明 |
|------|------|
| 不传 `--week` | 自动使用上周（本地日历上一周一至周日）对应的本年度 ISO 周，输出 `reports/team-weekly/<ISO周>.md`，标题标注「上周」 |
| `--week 2026-W15` | 手动指定 ISO 周 |
| `--output ...` | 指定输出文件 |
| `--dry-run` | 只打印将要拉取的 team/cycle 计划，不请求 issues |
| `--format json` | stdout 输出 JSON，含 `markdown`、`publish` 元数据与 `dingtalk` 字段 |
| `--no-publish-dingtalk` | 关闭生成后的自动钉钉上传 |
| `--export-json` | 写入 `reports/team-weekly/json/` 下四类 JSON 分片；默认不写。TREX-493 日 pulse 请用 `snapshot_sprint.py` |
| `--in-progress-snapshot` | 仅导出当前周 Cycle、进行中 Linear 项目、昨日（00:00–23:59）有活动的任务 JSON；默认写入 `reports/project-daily/`；不生成周报、不上传钉钉 |
| `--json-filename-prefix <前缀>` | 覆盖 JSON 文件名前缀 |
| `--json-dir <目录>` | 覆盖 JSON 落盘目录 |
| `--uncycled-include-completed` | 「未划入迭代」计数包含已完成（Done）；默认不含 |
| `--view dashboard\|text` | 迭代进度展示风格，默认 `dashboard` |
| `--chart-style auto\|text\|mermaid\|dingtalk` | `auto` 在未上传钉钉时用 `mermaid`，上传钉钉时用 `dingtalk`；`dingtalk` 为表格 + 字符条，不含 Mermaid |
| `--member-group all\|frontend\|backend\|前端\|后端` | 成员过滤。`backend/后端` 统计 backend + frontend + architect；`frontend/前端` 仅 frontend；`all` 不按 assignee 过滤。钉钉文档名会追加前端/后端后缀以避免覆盖 |

### 定时入口与 Pulse 快照

仓库根目录 `scripts/run_reports.sh` 是定时入口。不带参数或传 `all` 时，只跑 pulse 快照，不生成团队周报。

| 子命令 | 频率 | 实现 |
|--------|------|------|
| 默认 / `all` | 每次 cron | `pulse-daily` → `pulse-task-daily` → `pulse-pai-daily` → `pulse-member-daily`，均入库 PG |
| `pulse-daily` | 每天 | `snapshot_sprint.py --upload`，生成 sprint 项目日快照 |
| `pulse-task-daily` | 每天 | `snapshot_task.py --upload`，生成 task 日快照 |
| `pulse-pai-daily` | 每天，在 sprint 后 | 见 **superteam-report-insight**：`snapshot_pai.py --upload` |
| `pulse-member-daily` | 每天 | `snapshot_member.py --upload`，生成快照日所在自然周成员快照 |
| `pulse-member-weekly` | 每周，历史别名 | 同 `snapshot_member.py`；默认 `all` 已使用 `pulse-member-daily` |
| `team-weekly` | 每周或按需 | `generate_team_weekly_report.py`，配置钉钉 MCP 时自动上传 |
| `personal` | 单独 | `generate_report.py`，不在默认串联中 |

Pulse payload 口径：

- **`snapshot_sprint`**（`type=sprint`, `period=daily`）：与周报 §1 本迭代涉及的项目同源；`payload.projects[]` 含 `cycle_task_count`、`done` / `in_progress` / `todo` / `backlog` / `progress_done_pct` / `status_label` 等分列数字，便于按 `snapshot_date` 画折线。
- **`snapshot_task`**（`type=task`, `period=daily`, `team=trex`）：`completed_today` / `in_review` 用全 workspace（仅 Planned/In Progress 项目）；`product_created_pending`（设计中的需求）在此基础上 **额外纳入 Backlog 状态 Linear Project**，且 issue **labels 含 `Requirement`**、状态为 Todo / Prd Review / Technical Review；`overdue` / `due_soon` / `team_summary` / `by_assignee` 与 `snapshot_member` 完全一致（**快照日所在 ISO 周** Cycle issue、无项目过滤、`members[]` 纳入规则与 `due_tasks` 累加相同）。`summary.overdue_count` / `due_soon_count` = `team_summary`。
- **PAI**（`type=pai`）：见 skill **superteam-report-insight**（`skills/superteam-report-insight/SKILL.md`）。调度编排预留 **superteam-pai**。
- **`snapshot_member`**（`type=member`, `period=weekly`, `team=trex`）：统计周 = `snapshot_date` 所在 ISO 周；`members[]` 覆盖成员表内全部工程/测试角色，**即使当周任务、负载、代码均为 0 也保留空记录**。每人含 `projects[]`、`totals`、`workload`、`due_tasks`、`code`、`risks`；与 sprint/PAI 分离。
- **本地 JSON 保留**：`run_reports.sh pulse-daily` 入库成功后删除超过 `TREX_PULSE_RETAIN_DAYS`（默认 15）自然日的 `~/.superteam/pulse/<date>/` 目录；PostgreSQL 中历史快照不删。

Cron 示例：

```bash
# 每天 8:00：pulse 入库
0 8 * * *  cd /path/to/superteam && bash scripts/run_reports.sh >> ~/.superteam/logs/reports-all.log 2>&1

# 单独生成团队周报
bash scripts/run_reports.sh team-weekly

# 单独跑 pulse 子项
bash scripts/run_reports.sh pulse-daily
bash scripts/run_reports.sh pulse-task-daily
bash scripts/run_reports.sh pulse-pai-daily   # 见 superteam-report-insight
bash scripts/run_reports.sh pulse-member-daily
```

## 待设计事项

- [ ] 历史周报存储与检索
- [ ] 下周计划自动建议
