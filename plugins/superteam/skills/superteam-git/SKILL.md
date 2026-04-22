---
name: superteam-git
description: Use when querying local git context — commit history, branch info, code changes
---

# Git 洞察

查询本地多个工程的 Git 活动，聚焦代码提交分析与影响评估。也支持关联 Linear 任务的智能提交流程。

## 发现规则

- 输入一个或多个 `workspace` 根目录（环境变量 `SUPERTEAM_GIT_WORKSPACE` 可用系统路径分隔符写多个：macOS/Linux 为 `:`，Windows 为 `;`；CLI 可重复 `--workspace`）
- 递归扫描子目录
- 命中 `.git` 即判定为一个仓库
- 命中后不再继续向该目录下钻取
- 默认同仓库内仅扫描**时间窗口内有提交的本地分支**（`git_branch_scope=active`），合并后按 commit 去重；可用 `--branch-scope head` 仅当前检出分支，或 `--branch-scope all` 使用 `git log --all`

## 使用方式

```bash
python skills/superteam-git/scripts/query_git.py --workspace ~/code --week this
python skills/superteam-git/scripts/query_git.py --workspace ~/a --workspace ~/b --week last --format text
python skills/superteam-git/scripts/query_git.py --workspace ~/code --since-date 2026-03-24 --until-date 2026-03-30
python skills/superteam-git/scripts/query_git.py --branch-scope head --week this
python skills/superteam-git/scripts/query_git.py "查看我3.15号到4.1号的记录"
```

### 自定义时间范围

- 支持 `--since-date YYYY-MM-DD` + `--until-date YYYY-MM-DD`
- 提供自定义日期后，将覆盖 `--week this/last`
- 也支持自然语言时间（如 `3.15到4.1`、`3月15号到4月1号`）
- 不传 `--workspace` 时，默认读取 `SUPERTEAM_GIT_WORKSPACE`（安装脚本会提示配置）；支持多个根目录，用路径分隔符连接（与 `$PATH` 相同规则）

## 输出

- `summary`: 仓库数量、提交数量、增删行统计
- `repos`: 每个仓库的聚合统计
- `commits`: 提交明细（hash、作者、时间、message、改动量）
- `feature_tags` / `feature_summary`: 基于 message + 改动文件 + patch 的功能类型分析

## 回答规范（必须）

输出必须包含：

1. 总项目数
2. 总提交数
3. 各项目明细（for each project）：
   - 项目名
   - 提交次数
   - 提交行数（新增/删除）
   - 提交代码带来的功能、技术影响、业务影响（必须详细）
   - 直接描述"改了什么代码、实现了什么功能"，不要输出证据文件清单
   - 输出以"项目级汇总"为主，避免逐提交流水账

---

# 提交代码（Commit with Linear Task）

当用户提到「提交代码」「commit」「提交」或类似意图时，执行以下流程。

## 顺序（必须）：先有任务 id，再写 commit

1. **在生成最终 commit message、执行 `git commit` 之前**，必须已经拿到 **`TASK_ID`（如 ACB-91）与 `TASK_URL`**：或来自用户选择的已有任务，或来自「创建新任务」成功返回值。
2. **禁止**先 `git commit`、再补 Linear 任务、再指望事后 amend（除非用户明确要求 `git commit --amend` 修正 footer）。
3. 正文与 footer 一次写全：`Ref: <TASK_ID>`、`Link: <TASK_URL>` 与 type/body 一并进入同一次提交。

## Agent 终端与外网权限（必须）

- **拉 Linear 列表/详情**：优先用 **当前 Agent 宿主已接入的 Linear MCP**（见 **superteam-linear** SKILL「数据源优先级」），通常**不依赖** Agent 终端外网。
- **回退或脚本路径**：在终端执行 `query_linear.py`、`preflight_linear_issue.py`、`save_linear_issue_once.py` 时，凡会访问 **Linear Hosted MCP** 的命令**必须先申请外网权限**再执行（例如终端执行参数中的 `full_network` / `network`，以当前 Agent 运行时文档为准）。未放行外网时，上述脚本易出现长时间无输出或超时。

- **一般仅需本地**：`git status`、`git diff`、`git commit`、仅扫描本地仓库的 `query_git.py`。
- **需要外网**：回退用的 Linear 相关**终端脚本**；下文「提测合并」中的 `git fetch` / `git push`、GitLab API、`glab`、创建 MR 等。

## 重复任务风险（两类，不要混为一谈）

### A) 与「已有 issue」撞车（历史列表里早有一条类似的）

常见原因：

1. **未先选已有任务**：列表里其实已有同主题任务，但习惯性点了「创建新任务」。
2. **标题高度相似**：多人用相近中文/英文描述同一需求，Linear 不会自动拦截。
3. **未拉全量再选**：`list_issues` 的 `first` 过小，旧任务没出现在选项里，用户误以为没有而新建。

对策：**预检脚本** `preflight_linear_issue.py`（见下节）。

### B) 同一轮「创建新任务」里出现两条一模一样的新单（你要的场景）

典型原因（与历史无关，两条都是刚建的、标题相同）：

1. **Agent 在同一流程里调用了两次** `save_issue`（重复执行工具块、自动重试、多步计划各跑一遍等）。
2. **用户以为失败又点了一次** / 会话重试导致第二次创建。
3. **MCP / 网络超时**：客户端重试，上游实际已成功一次。

对策：**禁止**在「创建新任务」路径下直接调用裸 `query_linear.py … save_issue`。必须改用 **`save_linear_issue_once.py`**：在默认 **180 秒**内，对同一规范化标题 + 同一 `assignee` **只真正创建一次**；重复调用会返回第一次的 issue（`reused: true`），避免第二条相同新单。

确需在极短时间内故意建两条同标题任务时，脚本支持 `--force-new`（少用）。

> **说明**：Linear 端不会替你合并「连续两次 save_issue」；B 类要靠 **save_linear_issue_once 去重 + Agent 只走该入口**。

### `query_linear.py` 的 stdout 与脚本解析

- `mcp-remote` 会在同一流里输出 **日志行 + JSON-RPC**，最后再输出一层 **`skill: superteam-linear` 的工具结果 JSON**。
- `save_linear_issue_once.py` 与 `preflight_linear_issue.py` 使用 **`query_linear_stdout_json.py`（括号平衡扫描）** 提取该包裹对象，**禁止**再依赖「从最后一个 `{` 截断解析」——否则会误匹配不完整的 RPC 片段，出现 `no result in MCP response` 等假失败。

### 若创建任务脚本报错（必须核对，防重复建单）

1. **`save_linear_issue_once.py` 已内置回收**：当 `save_issue` 在 Linear 侧已成功但响应解析失败时，脚本会**自动**再调 `list_issues`，在 **`--recover-within-seconds`（默认 300）** 内、**规范化标题 + `team` 一致**的 issue 中取 **createdAt 最新**的一条，写入去重缓存并 **stdout 返回 `recovered: true`**。Agent 应将该输出视为成功，用其中 `issue.id` / `issue.url` 写 commit footer，**不要**立刻再次执行创建脚本。
2. 若脚本仍报错且无 `recovered`：再用宿主 Linear MCP 或 `query_linear.py --tool list_issues` **人工核对**是否已有同标题新单（超时重试时上游可能已成功）。
3. **若已存在**：取该条的 **id / url** 作为 `TASK_ID` / `TASK_URL`，**禁止**再次 `save_issue`。
4. **若确认不存在**且回收与列表均无记录：可**单次**应急执行 `query_linear.py --tool save_issue`（仍需先完成预检）；同一轮流程内仍**不得**连续两次裸 `save_issue`。

## 限制（必须）：新建任务前预检

当用户选择「创建新任务」并得到拟用标题后，**在调用 `save_issue` 之前必须**执行预检脚本（解析 stdout 的 JSON）：

```bash
python {SKILL_DIR}/scripts/preflight_linear_issue.py --title "用户给出的标题"
```

根据返回字段处理（**禁止跳过**）：

| `risk` | `recommendation` | Agent 必须做的事 |
|--------|------------------|------------------|
| `high` / `medium` | `link_existing` | **不得**创建新单。必须用 `AskQuestion` 列出 `open_matches` 中每条（id + 标题 + 状态），让用户改选已有任务；仅当用户**明确**选择「仍要新建（已知重复风险）」时，才允许执行 `save_linear_issue_once.py`。 |
| `low` | `confirm_or_link` | 用 `AskQuestion` 展示可能相关的 open 任务，默认引导关联已有；用户坚持新建才可执行 `save_linear_issue_once.py`。 |
| `none` | `ok_to_create` | 可执行 `save_linear_issue_once.py`（若存在 `closed_matches`，文案提示「曾有已完成同主题任务」即可，不强制拦截）。 |

附加规则：

- **`policy.block_save_issue_without_user_confirm` 为 `true` 时**：没有用户在 `AskQuestion` 里点选「仍要新建」类选项，**禁止**执行 `save_linear_issue_once.py`（也不得裸调 `save_issue`）。
- **同一次提交流程内**：对「创建新任务」路径**只允许调用** `save_linear_issue_once.py` **一次**（内部已防双次 `save_issue`）；**禁止**再额外直接调用裸 `save_issue`（含 **宿主 Linear MCP 的 `save_issue`**）。若怀疑已创建成功，用 **MCP 或** `query_linear.py` 的 `get_issue` / `list_issues` 核对，而不是再建一条。

## 前置检查

1. 在**当前项目根目录**下执行 `git status` 检查是否有未提交的改动。
2. 若无改动（工作区干净），提示用户「当前没有可提交的改动」，结束。
3. 若有改动，继续以下流程。

## 1. 获取当前用户负责的 Linear 任务

**只拉取分配给当前用户的任务**。须遵循 **superteam-linear** SKILL 的「数据源优先级」：

### 1a. 优先：当前 Agent 宿主的 Linear MCP

调用 **本会话已接入的 Linear MCP** 的 `list_issues`，建议参数：

- `assignee`: `"me"`
- `includeArchived`: `false`
- `limit`: `80`（MCP 使用 `limit`，不是 `first`；建议 **≥50**，与预检脚本默认心智一致）
- **不传 `state`**（取回后在客户端过滤）

从工具返回体中取出 **issues 数组**（字段名以实际返回为准，通常与 `query_linear.py` 的 `result.issues` 同级结构）。若调用失败、无 MCP、或未认证，进入 **1b**。

### 1b. 回退：`query_linear.py`

脚本路径与本 SKILL.md **同级**的 `../superteam-linear/scripts/query_linear.py`。

> `{SKILL_DIR}` 指本 SKILL.md 所在的目录。

```bash
python {SKILL_DIR}/../superteam-linear/scripts/query_linear.py \
  --tool list_issues \
  --args-json '{"assignee": "me", "includeArchived": false, "first": 80}'
```

**关键参数**（与 1a 语义对齐，`first` ↔ MCP 的 `limit`）：

- `"assignee": "me"` — 只查当前认证用户自己的任务。
- `"includeArchived": false` — 排除已归档任务。
- `"first": 80` — 建议 **≥50**，避免任务较多时旧单未出现在选项里导致误建新单。
- **不传 `state`**（API 只支持单值），取回后在客户端过滤。

解析 stdout JSON 后，从 **`result.issues`** 数组中：
1. **排除** `status` 为 `"Done"` 或 `"Canceled"` 的任务。
2. **跳过** `id` 或 `title` 为空的条目。
3. 保留的任务取 `id`（如 `ACB-49`）、`title`、`status`。

## 2. 让用户选择关联的 Linear 任务

**必须使用 `AskQuestion` 工具**以交互式选择 UI 展示任务列表，让用户直接点选，而不是打印文本让用户手动输入序号。

构造方式：
- **只用**过滤后的任务（已排除 Done/Canceled 和空数据的），将每条作为一个 option。
- `id` 设为任务的 identifier（如 `ACB-49`），`label` 设为 `<identifier> - <title> (<status>)`。
- **确保每个 option 的 `id` 和 `label` 都非空**，跳过任何空值条目，避免出现空白选项。
- 最后追加一个额外 option：`id` 设为 `__create_new__`，`label` 设为 `创建新任务`。
- `allow_multiple` 设为 `false`（单选）。

示例调用：

```json
{
  "questions": [{
    "id": "linear_task",
    "prompt": "请选择本次提交关联的 Linear 任务：",
    "options": [
      {"id": "ACB-45", "label": "ACB-45 - 调试各种 provider 内容 (In Progress)"},
      {"id": "ACB-49", "label": "ACB-49 - Git log 本地抽取关联任务 (Todo)"},
      {"id": "ACB-41", "label": "ACB-41 - Provider TEE/TLS 双模式设计 (In Review)"},
      {"id": "__create_new__", "label": "创建新任务"}
    ],
    "allow_multiple": false
  }]
}
```

### 用户选择已有任务

记录用户所选 option 的 `id` 作为 `TASK_ID`（如 `ACB-49`），并从同一任务对象中提取 `url` 作为 `TASK_URL`。

### 用户选择「创建新任务」

即用户选中 `__create_new__`：

1. 询问用户新任务的**标题**。
2. **（必须）**按上文「限制（必须）：新建任务前预检」运行 `preflight_linear_issue.py`，并按 `risk` / `policy` 走 `AskQuestion`，必要时阻止或二次确认后再创建。
3. 通过预检与用户确认后，**必须**用带去重保护的脚本创建任务（**不要**直接调用裸 `save_issue`）：

```bash
python {SKILL_DIR}/scripts/save_linear_issue_once.py \
  --title "用户给出的标题" \
  --team "<TEAM>" \
  --state "In Progress" \
  --assignee "me"
```

   - `team`：从步骤 1 返回的任务列表中取一条已有任务的 `team` 字段（通常同一团队的任务共用同一 team）；若列表为空或无法获取，则询问用户。
   - 解析 stdout JSON：使用 `issue.id`、`issue.url`；若 `reused: true`，说明去重生效（本次未再打创建接口），仍用返回的 `issue` 写 commit footer，并**不要**再次运行本脚本或裸 `save_issue`。
4. 将 `issue.id` 作为 `TASK_ID`，`issue.url` 作为 `TASK_URL`。

## 3. 分析代码改动并生成 commit message

1. 执行 `git diff`（未暂存改动）和 `git diff --staged`（已暂存改动），全面了解本次修改内容。
2. 根据改动的文件、新增/删除的代码，理解本次修改的目的和影响。
3. 生成符合 **Conventional Commits** 规范的 commit message：
   - 格式：`type: description`（**不使用 scope**，不加括号）
   - 常见 type：`feat`、`fix`、`docs`、`style`、`refactor`、`test`、`chore`
   - 可包含多行 body 描述（空行分隔）
   - 末尾使用标准 footer 追加两行：`Ref: <TASK_ID>` 与 `Link: <TASK_URL>`

### commit message 示例

```
feat: 新增用户头像上传功能

支持 jpg/png 格式，最大 5MB，上传后自动裁剪为圆形

Ref: SUP-7
Link: https://linear.app/xxx/issue/SUP-7
```

```
fix: 修复登录页面超时未重定向的问题

Ref: SUP-12
Link: https://linear.app/xxx/issue/SUP-12
```

## 4. 确认并提交

1. 将生成的完整 commit message 展示给用户。
2. **必须使用 `AskQuestion` 工具**让用户选择操作，而不是让用户打字回复：

```json
{
  "questions": [{
    "id": "commit_action",
    "prompt": "commit message 如上，请选择操作：",
    "options": [
      {"id": "confirm", "label": "确认提交"},
      {"id": "edit",    "label": "我要修改 message"},
      {"id": "cancel",  "label": "取消，不提交"}
    ],
    "allow_multiple": false
  }]
}
```

3. **用户选择「确认提交」**：
   - 执行 `git add .`（或根据用户意图选择性添加文件）
   - 执行 `git commit` 并使用该 message（含末尾的 `TASK_ID`）
4. **用户选择「我要修改 message」**：请用户给出修改后的 message，若末尾未包含 `Ref: <TASK_ID>` 与 `Link: <TASK_URL>`，自动补齐后再提交。
5. **用户选择「取消，不提交」**：终止，不提交。

## 5. 提交完成

提交成功后，向用户展示：
- commit hash
- 完整的 commit message
- 关联的 Linear 任务 identifier 与标题

确认提交已完成。

---

# 提测合并（Merge to Review）

当用户提到「提测」「merge 到 review」「创建 review 合并申请」或类似意图时，执行以下流程。

## 目标

1. 先从 `master` 相关分支创建/更新目标 review 分支（如 `master` / `drex_master` / `anchor_master`）。
2. 再将当前开发分支作为源分支，创建指向该 review 分支的 GitLab Merge Request。
3. **不要选择“合并后删除原分支”**（保留源开发分支）。
4. 最终只返回 MR 链接。

## 0. 前置识别

1. 获取当前分支：

```bash
git rev-parse --abbrev-ref HEAD
```

2. 当前分支需满足常见命名（如 `xxxdev_xxxxxx_xxxx`）。  
3. review 分支名按规则推导：将当前分支名中的 `dev` 替换为 `review`。  
   - 例：`questsdev_20260223_dubbo` → `questsreview_20260223_dubbo`
4. 若当前分支名不含 `dev`，要求用户手动提供目标 review 分支名。

## 1. 列出 master 相关基线分支并让用户选择（必须）

在本地与远端列出所有包含 `master` 的候选分支（例如 `master`、`drex_master`、`anchor_master`）：

```bash
git branch --all --list "*master*" "*_master*"
```

去重后，**必须使用 `AskQuestion` 工具**让用户选择“review 分支应基于哪个 master 相关分支创建/同步”：

- option `id` 可用分支名（例如 `master`、`drex_master`、`anchor_master`）。
- `allow_multiple=false`（单选）。

## 2. 基于所选 master 分支创建/更新 review 分支

设用户选择的基线为 `BASE_MASTER_BRANCH`，推导得到 `TARGET_REVIEW_BRANCH`。

1. 先拉取远端：

```bash
git fetch origin
```

2. 检查 `TARGET_REVIEW_BRANCH` 是否存在（本地/远端）：
   - 若不存在：基于 `origin/BASE_MASTER_BRANCH` 创建 review 分支并推送。
   - 若存在：切到 review 分支并与 `origin/BASE_MASTER_BRANCH` 对齐（按团队策略 fast-forward / merge）。

推荐命令（示例）：

```bash
git checkout -B TARGET_REVIEW_BRANCH origin/BASE_MASTER_BRANCH
git push -u origin TARGET_REVIEW_BRANCH
```

> `checkout -B` 会将本地 review 分支重置到所选 master 基线，适合“提测前从基线重新拉 review 分支”的流程。

## 3. 创建 MR：当前开发分支 -> review 分支（不删源分支）

设：
- 源分支 `SOURCE_BRANCH` = 当前开发分支
- 目标分支 `TARGET_REVIEW_BRANCH` = 第 0/2 步得到的 review 分支

创建 MR 时必须满足：
- 目标分支为 `TARGET_REVIEW_BRANCH`
- 源分支为 `SOURCE_BRANCH`
- **remove_source_branch=false**（不删除源分支）

可使用项目中的 `merge.sh`（若支持传参），或使用 `glab`/GitLab API 创建。  
若脚本会弹出“是否删除源分支”选项，必须选择“否”。

## 4. 同步更新 Linear 任务状态（必须）

在 MR 创建成功后，必须从“本次 merge 涉及的 commit message”中提取所有 `Ref` 任务号，并将这些 Linear 任务更新为 `Done`。

### 4.1 提取 Ref 任务号

获取本次 MR 的提交范围（源分支相对目标分支的差异提交），解析 commit message 中的 `Ref` 行：

- 匹配格式：`Ref: <TASK_ID>`（如 `Ref: ACB-49`、`Ref: SUP-12`）
- 去重后得到 `REF_TASK_IDS`

可参考：

```bash
git log --format=%B TARGET_REVIEW_BRANCH..SOURCE_BRANCH
```

### 4.2 批量更新 Linear 状态为 Done

对 `REF_TASK_IDS` 中每个任务更新为 `Done`：

1. **优先**：**当前 Agent 宿主 Linear MCP** 的 `save_issue`，参数示例：`{"id": "<TASK_ID>", "state": "Done"}`。
2. **回退**：终端执行：

```bash
python {SKILL_DIR}/../superteam-linear/scripts/query_linear.py \
  --tool save_issue \
  --args-json '{"id":"<TASK_ID>","state":"Done"}'
```

规则：
- 仅更新从 `Ref:` 解析出的任务；无 `Ref` 则跳过。
- 某个任务更新失败时，不中断其余任务更新；最后汇总成功/失败列表返回给用户。
- 若任务已是 Done，视为成功（幂等）。

## 5. 返回结果

执行完成后只返回：
- MR URL（可直接点击）
- Linear 状态同步结果（Done 成功的任务列表 + 失败任务列表）
- （可选）源分支、目标 review 分支（一行简述）

若创建失败，返回明确错误和下一步建议（权限、分支不存在、网络等）。