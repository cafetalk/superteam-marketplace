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
- 各业务 repo（如 `persona-feast` / `drex-core`）落 per-repo 改动明细 `releases/<batch>/<TREX-id>.md`，与 `trex-releases` 的提测单互链。skill 把该文件写进业务 repo **工作区**，由工程师**随代码在 `review_*` 分支一起提交**；skill 只自动 commit/push `trex-releases`，不替业务 repo push。
- 钉钉 `.axls` 表格 **停止维护**；历史最近 2 个批次由 `backfill` 一次性回迁进 `trex-releases`。

## SOP【强制】

```text
[提测阶段]  per Linear issue
  研发助手跑 handoff --issue TREX-<id> --releases-root <trex-releases clone>
        │
        ▼
  生成 releases/<batch>/<TREX-id>/handoff.md（含 7 字段 + 受影响系统矩阵骨架）
  + 各业务 repo 工作区的 per-repo 明细（工程师随代码在 review_* 一起提交）
        │  人工补充：变更范围 / 自测记录 / 回滚预案 / 系统变更维度
        ▼
  Linear issue comment 贴 handoff.md 链接

[发布阶段]  per 批次（一次 prod 发布）
  研发负责人跑 aggregate --batch <batch> --releases-root <...>
        │
        ▼
  汇总本批所有 handoff.md → releases/<batch>/RELEASE.md
  （auto 区 = 系统变更总表 + 各系统明细 + 提测单索引，重生成；
    manual 区 = 版本号 / 灰度 / 回滚 checklist，人工填，重跑保留）
```

## 维度矩阵【强制】

受影响系统 / 部署变更**只列本次实际涉及的维度**（替代钉钉每系统 sheet 的 20 行全量矩阵）。
20 个 canonical 维度清单 + 填写说明见 skill 的 `references/dimensions.md`。
每个维度填 `beta` / `prod` 两列 + 操作人 + 检查（☐/☑）。

## git 安全栏【强制】

`superteam-trex-delivery` 跨 repo 写记录，遵守仓库 git 纪律：

1. **显式 stage**：永不 `git add -A` / `git add .` / `git add -u`；只 stage 明确的记录文件
2. **首建批次记录分支需确认**：第一次为某批次建 `auto_<date>_<keyword>` 记录分支时，打印 diff 等人确认（`--yes` 跳过）
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
