---
name: superteam-report
description: Use when a team member asks to generate a weekly report — produces Markdown weekly reports from GitLab commits, MR records, and agent usage data
---

# 智能周报生成

根据 `superteam-linear` 与 `superteam-git` 数据，自动生成 Markdown 格式周报。

## 命令入口

可直接使用 `superteam-report` 命令（例如在支持 slash skill 的客户端中使用 `/superteam-report`）。

`/superteam-report` 不带参数时，默认生成“上周（周一到周日）”周报；如需本周可在 query 中包含“本周”，或传 `--week this`。

当前升级为 v3 模式（**数据脚本 + LLM 生成**）：脚本只负责采集结构化数据，周报正文由 skills 内 LLM 基于全量数据进行分析与写作。

默认做法：先取 JSON 原始数据，再由 LLM 输出 Markdown 周报（非脚本固定模板）。

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

## 待设计事项

- [ ] 多成员汇总模式（团队周报）
- [ ] 历史周报存储与检索
- [ ] 下周计划自动建议
