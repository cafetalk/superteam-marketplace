# 提测 / 发布记录落 git SOP

本章规范"**提测单 + 发布文档怎么落地、归档到哪里**"。结论：进 git 的 markdown 记录，
由 `superteam-trex-delivery` skill 维护，**废弃钉钉 `.axls` 复杂表格**。本章只管"记录载体"，
不重复 `common/03`（提测流程）/ `common/04`（发布流程）的流程铁律。

`〔t-rex 术语〕`：
- **提测单** = 单个 Linear issue（`TREX-<id>`）的提测记录（变更范围 / 受影响系统 / 自测 / 回滚预案）
- **发布文档** = 一个批次（一次 prod 发布）的汇总文档 `RELEASE.md`（版本 / 灰度 / 回滚 + 各系统变更总表）
- **批次（batch）** = `<date>-<project-slug>`；date 取 Linear Project target date，slug 取 Project 名 kebab-case

## 归档位置【强制】

`〔t-rex 现状〕`：提测单与发布文档统一落 GitLab 仓 **`Keccak256-evg/t-rex/coordinator/trex-releases`**：

```text
releases/<batch>/RELEASE.md                 ← 批次发布文档（aggregate 产物）
releases/<batch>/<TREX-id>/handoff.md       ← 单个工程师的提测单（handoff 产物）
```

- **Linear issue comment 只留链接**，指向 `trex-releases` 里对应的 `handoff.md`；记录正文不再 paste 在 comment 里。
- 各业务 repo（如 `persona-feast` / `drex-core`）落 per-repo 改动明细 `releases/<batch>/<TREX-id>.md`，与 `trex-releases` 的提测单互链。skill 把该文件写进业务 repo **工作区**，由工程师**随代码在 `dev_*` 分支一起提交**（提测 MR `dev_*→review_*` 携带它进 review）；skill 只自动 commit/push `trex-releases`，不替业务 repo push。
- 钉钉 `.axls` 表格 **停止维护**；历史最近 2 个批次由 `backfill` 一次性回迁进 `trex-releases`。

## SOP【强制】

记录仓 **镜像代码生命周期**：提测期记录走 `dev_*→review_*`（不进 master），发布时才 `beta_*→master`。
`trex-releases/master` = 已发布记录的唯一真相。

```text
[提测阶段]  per submission（一个 dev 分支 / 一个微服务，可关联多 issue）
  填 changes.yaml → submit --changes <...> --releases-root <clone> --repo-map <svc>=<path>
        │
        ▼
  渲染 #1 各服务 release.md（落服务 repo 工作区，随代码在 dev_* 提交，提测 MR dev_→review_ 携带）
  + #2 submissions/<task>/release.md（落 trex-releases）
        │  记录提交在本轮公共 dev_<date>_<name> 分支
        ▼
  记录 MR：dev_<date>_<name> → review_<date>_<name>（与代码提测同名同拍，不进 master）

[发布阶段]  per 批次（一次 prod 发布）
  release --batch <iteration> --beta beta_<date>_<keyword> --releases-root <...>
        │
        ▼
  汇总本批 changes.yaml → releases/<iteration>/release.md
  （AUTO 区 = 变更项/提测代码/关联任务，重生成；# 发布执行 manual 区人工填、重跑保留）
        │
        ▼
  记录 MR：beta_<date>_<keyword> → master（与代码发布 beta→master 同拍）
```

### 提测产出 = 两个平级文件【强制】

- `release.md` — skill 从 `changes.yaml` 渲染（变更项/数据契约/提测代码/关联任务），勿手改。
- `submission.md` — **dev agent 手写**，承载 release.md 没有的提测信息，章节：
  `字段表（提测人/Linear/提测分支/主MR）` · `# 变更范围` · `# 关联 MR` · `# 自测记录` · `# 回滚预案` · `# 测试同学关注点`。
  与 release.md 同目录、同 `dev_*` 分支随代码提交，提测 MR `dev_→review_` 携带。

## 维度矩阵【强制】

受影响系统 / 部署变更**只列本次实际涉及的维度**（替代钉钉每系统 sheet 的 20 行全量矩阵）。
20 个 canonical 维度清单 + 填写说明见 skill 的 `references/dimensions.md`。
每个维度填单一「内容」列（按环境取值用 `{placeholder}`，表后渲占位符取值表 `key/dev/beta/prod`）+ 操作人 + 检查（☐/☑）。

## git 安全栏【强制】

`superteam-trex-delivery` 跨 repo 写记录，遵守仓库 git 纪律：

1. **显式 stage**：永不 `git add -A` / `git add .` / `git add -u`；只 stage 明确的记录文件
2. **记录分支 = 本轮公共 dev 分支名**：`trex-releases` 的记录提交用本轮的 `dev_<date>_<name>`（从 submit_branch `review_*` 派生，与各微服务仓分支名一致，见 `common/03`〔跨服务分支命名〕），不再另造 `auto_*`。首建该分支时打印 diff 等人确认（`--yes` 跳过）
3. **`--dry-run` 预览**：只本地生成 markdown 供预览，不做任何 git
4. **跨 repo 失败隔离**：某业务 repo per-repo 明细写失败只记入结果，不中断其余 repo（业务 repo 由工程师自行提交，skill 不 push 它们）

## 与其它章的关系

- `common/03-test-handoff.md` —— 提测**流程**（`dev_*` → `review_*` MR + team lead 审）；本章只接管提测单的**载体与归档**
- `common/04-ci-and-release.md` —— 发布**流程**（`beta_*` → `master` + 灰度 + 回滚）；发布单 = 本章的 `RELEASE.md`
- `common/05-task-tracking.md` —— Linear issue 生命周期；提测单 / 发布文档与 issue 通过链接关联

## 推荐【推荐】

- 提测后**及时补全** handoff.md 的变更范围 / 维度，别留骨架；aggregate 靠 `### <系统名>` 反解，骨架也能汇总但信息不全
- 发布文档 `RELEASE.md` 的 manual 区（版本号 / 灰度 / 回滚 checklist）由值班人维护，重跑 aggregate 不会被覆盖
- 工具 / 命令细节见 skill `superteam-trex-delivery`（`SKILL.md`）

## 维护

- 记录目录约定 / 维度清单变更需同步 `superteam-trex-delivery` skill（`scripts/dimensions.py` + `references/dimensions.md`）
- 流程铁律变更回到 `common/03` / `common/04`，本章只跟随
