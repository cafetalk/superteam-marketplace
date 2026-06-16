---
name: superteam-trex-delivery
description: Use when recording a t-rex 提测 (test handoff) or assembling a 发布文档 (release doc) — generates versioned markdown records in the trex-releases repo + each service repo, replacing the DingTalk spreadsheet. Two stages: submit (one submission = one dev branch / one microservice, keyed <date>_<name>, may reference multiple Linear issues) and release (per Linear project). Not for the superteam sub-project itself.
---

# superteam-trex-delivery

把 t-rex 的提测单 + 发布文档合并成进 git 的 markdown 记录，废弃钉钉 `.axls` 表格。

## 命令 (v2 — changes.yaml 数据模型, v1.4.0)

**核心模型**: agent 读 diff 填一份 `changes.yaml`（唯一数据源, 只列涉及 service + 涉及维度, 维度受 `templates/change-dimensions.yaml` 22 维约束）→ 确定性渲染 3 层 `release.md`。config/脚本内容渲染代码块, 不塞表格。档 3（操作人/检查/灰度/回滚）留 manual 区, agent 不填, 重跑保留。

**release.md 三章节结构**（#1 per-service / #3 iteration 统一）：`# 变更项`（维度表）· `# 提测代码`（提测分支 + MR 记录：主 MR + 修复问题的 MR）· `# 关联任务`（迭代 + 任务列表）。#3 另有 `# 发布执行`（灰度/回滚/操作人/checklist，manual 区）。`changes.yaml` 每个 service 支持 `mr:`（主 MR）+ 可选 `fix_mrs: [...]`（修复问题的 MR；缺省渲染「无」）。

- **校验**：`uv run scripts/validate.py --changes <changes.yaml> [--iteration <it>]`（合规 exit 0 / 非法 exit 1 + 错误明细, CI 可挂）
- **提测 (v2)**：`uv run scripts/submit.py --changes <releases/{it}/submissions/{task}/changes.yaml> --releases-root <trex-releases clone> --repo-map <service>=<repo path> [--repo-map ...] [--no-mr] [--no-push] [--dry-run]`
  - 校验 changes.yaml（非法 abort）→ 渲染 #2 `submissions/{task}/release.md`（task 跨服务汇总）+ 每 service 渲染 #1 `<repo>/releases/{it}/{task}/release.md`（写进各微服务 review_ 分支工作区）。`--repo-map` 缺某 service → 只渲 #2 跳 #1（warn）。
- **发布汇总 (v2)**：`release.run_v2(releases_root, iteration)` — glob `submissions/*/changes.yaml` → 渲染 #3 `releases/{it}/release.md`（系统变更总表 + 各系统详情, AUTO 区重生成, manual 区[灰度/回滚/checklist]重跑保留）。orphan（有 release.md 无 changes.yaml）warn+skip。

### 旧命令 (v1.3.x, 手写 markdown 路径, 仍兼容)
- 提测：`uv run scripts/submit.py --dev-branch dev_<date>_<name> --issue TREX-1 [--issue TREX-2 ...] --releases-root <trex-releases clone> [--repo <微服务 repo> [--reviewer <gitlab-username>]] [--batch|--date ...] [--dry-run] [--yes|--no-push|--no-mr]`（产出 `releases/<release-item>/submissions/<date>_<name>/submission.md`）
  - **一次提测(submission) = 一个 dev 分支 / 一个微服务**，submission key = `<date>_<name>`（`dev_<date>_<name>` 去 `dev_` 前缀）。**可关联多个 Linear issue**（`--issue` 可重复），全部写进 `关联 Linear` 并全部置 In Review。
  - **MR 模式**：给 `--repo` 时，submit 顺手建 `review_*` 分支 + `dev_*→review_*` 提测 MR（description 每个 issue 一行 `Tracks Linear <id>`、指定 team lead reviewer），用 MR 结果回填 mr_url/review 分支/受影响系统(=该微服务)，并把每个 issue 置 In Review（best-effort）；`--repo` 同时是 per-repo 明细的落点（`<repo>/releases/<release-item>/<date>_<name>.md`）。`--dry-run` 只打印计划不调 GitLab。reviewer 解析序：`--reviewer` > `references/team-leads.json` 命中 > 报错。
- 汇总发布：`uv run scripts/release.py --batch 20260605-world-cup --releases-root <...> [--dry-run] [--yes|--no-push|--no-mr]`（产出 `releases/<release-item>/RELEASE.md`）
- 回迁钉钉：`uv run scripts/backfill.py --workbook <发布文档 nodeId>=<batch> [--workbook ...] --releases-root <...> [--dry-run]`
  （可重复 `--workbook`；「最近 N 个批次」的 nodeId 需先用 dingtalk MCP `list_nodes` 取「提测版本」子文件夹，再传入）

## 约定
- batch = `<date>-<project-slug>`（date 来自首个 issue 的 Linear Project target date，缺则 `--date`/`--batch`）
- submission = 一个 dev 分支，key = `<date>_<name>`（路径 `submissions/<date>_<name>/submission.md`），可关联多个 Linear issue、对应一个微服务；RELEASE.md auto 区重生成、manual 区保留
- git 安全栏：显式 stage（永不 `git add -A`）、首建批次分支需确认、`--dry-run` 不落盘
- SOP 见 handbook `common/08-release-record.md`；维度填写参考见 `references/dimensions.md`

## v1 已知边界
- **MR/分支/受影响系统** 现由 `submit` 的 MR 模式（给 `--repo`）直接开提测 MR 提供：skill 替工程师建 MR，故天然握有 MR URL / review 分支 / 所在 repo（= 受影响系统），自动回填提测单。（历史背景：早先靠 Linear `list_diffs` 反查 MR 行不通——本 workspace 该接口返回空；改由 submit 主动开 MR 后此路径作废。）不走 MR 模式时仍可只产出提测单主体、由人/agent 补系统矩阵。
- **per-repo 明细**（`<repo>/releases/<release-item>/<date>_<name>.md`）写进微服务 repo（= `--repo`）工作区，由工程师随代码在 `review_*` 一起提交；skill 只自动 push `trex-releases`。
- **trex-releases 推送**：记录分支用 `auto_<date>_<keyword>`（合规于 t-rex push rule 的 `auto` 前缀；keyword 取 batch slug 清成 ASCII）。
