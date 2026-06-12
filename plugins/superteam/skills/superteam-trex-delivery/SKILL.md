---
name: superteam-trex-delivery
description: Use when recording a t-rex 提测 (test handoff) or assembling a 发布文档 (release doc) — generates versioned markdown records in the trex-releases repo + each service repo, replacing the DingTalk spreadsheet. Two stages: submit (one submission = one dev branch / one microservice, keyed <date>_<name>, may reference multiple Linear issues) and release (per Linear project). Not for the superteam sub-project itself.
---

# superteam-trex-delivery

把 t-rex 的提测单 + 发布文档合并成进 git 的 markdown 记录，废弃钉钉 `.axls` 表格。

## 命令
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
