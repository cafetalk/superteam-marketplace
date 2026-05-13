# 项目前缀清单 + Push Rule 完整 regex

本文件是 `common/02-branch-and-commit.md` 的参考附录。

`〔注意〕` GitLab Push Rule regex 是 **org 共享模版**（所有 t-rex 项目共用）。**对 regex 的修改必须是纯添加**（不删除老 pattern，否则会破其他团队的工作流）。

## Push Rule Branch Name regex（完整 — 过渡期 / 共享模版）

兼容 trex team 新规约 + 其他团队老规约。GitLab 项目设置 → Repository → Push Rules → Branch name 配置如下：

```regex
(((drex|anchor|dreamtemple|kiki|duom|vibra|trex|as|rosetta|aspen|stanly|osp|talent|zeek|mugen|mon|quests|alien|adgm|dojo3|slg)(pre|auto|dev|alpha|beta|feature|hotfix|review|duom)(|_(\d{8}|\d{4})_[\.A-Za-z0-9\\-]{2,30}))|^dev$|^beta$|^master$|^main$|^duom_master$|^osp_master$|^talent_master$|^beta_aspen_red$|^kiki_master$|^aspen-pre$|^mon_master$|^rosetta_master$|^quests_master$|^zeek_master$|^alien_master$|^dojo3_master$|^zeek_pre_master$|^adgm_master$|^slg_master$|^dreamtemple_master$|^drex_master$|^(pre|auto|dev|alpha|beta|feature|hotfix|review)_(\d{6}|\d{8})_[\.A-Za-z0-9\-]{2,30}$)
```

**vs 老 regex 的唯一差异**：末尾追加一条 alternation：

```regex
|^(pre|auto|dev|alpha|beta|feature|hotfix|review)_(\d{6}|\d{8})_[\.A-Za-z0-9\-]{2,30}$
```

这一条接受 trex team 新规约的"无项目前缀"分支名（必填 6/8 位日期 + 必填 name）。所有原有 pattern 一字未改。

### Regex 拆解

```text
^(
   ━━━━━━━━ 老规约（其他团队 + trex team 历史遗留）━━━━━━━━

   ((drex|anchor|dreamtemple|kiki|duom|vibra|trex|as|rosetta|aspen|stanly|
     osp|talent|zeek|mugen|mon|quests|alien|adgm|dojo3|slg)
    (pre|auto|dev|alpha|beta|feature|hotfix|review|duom)
    (|_(\d{8}|\d{4})_[\.A-Za-z0-9\-]{2,30}))    ← date 4/8 位，可选；name 可选

   ━━━━━━━━ 老长期分支白名单 ━━━━━━━━

   | dev | beta | master | main
   | duom_master | osp_master | talent_master | beta_aspen_red
   | kiki_master | aspen-pre | mon_master | rosetta_master
   | quests_master | zeek_master | alien_master | dojo3_master
   | zeek_pre_master | adgm_master | slg_master | dreamtemple_master
   | drex_master

   ━━━━━━━━ ✅ trex team 新规约（追加）━━━━━━━━

   | (pre|auto|dev|alpha|beta|feature|hotfix|review)
     _ (\d{6}|\d{8})                   ← date 6/8 位，必填
     _ [\.A-Za-z0-9\-]{2,30}           ← name 必填
)$
```

## Push Rule Commit Message regex（完整）

不变，沿用老 regex（其他团队也在用）：

```regex
^((init|feat|alter|fix|perf|refactor|docs|style|test|build|revert|ci|chore|release|workflow):|Merge|Merge|Reverted|Revert)[\s\S]+
```

## trex team 新规约速查

| 维度 | 值 |
|---|---|
| 公式 | `<stage>_<date>_<name>` |
| stage | `pre / auto / dev / alpha / beta / feature / hotfix / review`（8 个；**砍 `duom`**） |
| date | 6 位 `YYMMDD`（trex 推荐）或 8 位 `YYYYMMDD`；**必填** |
| name | 2–30 字符 `[.A-Za-z0-9\-]`；**必填** |
| 长期分支 | `dev` / `beta` / `master`（3 个） |

## 项目前缀清单（老规约 / 其他团队）

| 前缀 | 用途 | trex team 用法 |
|---|---|---|
| `trex` | t-rex 生态历史前缀 | ⚠️ 不再用于新工程（trex team policy: 2026-06-30 起 in-flight 全部迁完） |
| `drex` | drex-core / drex-passport / trex-web 等存量后端 | ⚠️ 历史前缀，老工程仓保留；新分支不用 |
| `anchor` | anchor-pay 等 | 其他团队 |
| `dreamtemple` | — | 其他团队 |
| `kiki` | kiki-framework 等基础设施 | 其他团队 |
| `duom` | — | 其他团队 |
| `vibra` | — | 其他团队 |
| `as` | — | 其他团队 |
| `rosetta` | — | 其他团队 |
| `aspen` | aspen 生态 | 其他团队 |
| `stanly` | — | 其他团队 |
| `osp` | — | 其他团队 |
| `talent` | — | 其他团队 |
| `zeek` | — | 其他团队 |
| `mugen` | — | 其他团队 |
| `mon` | — | 其他团队 |
| `quests` | — | 其他团队 |
| `alien` | — | 其他团队 |
| `adgm` | — | 其他团队 |
| `dojo3` | — | 其他团队 |
| `slg` | — | 其他团队 |

TODO(@allen)：补全每个前缀对应项目 / 主理人 / 仓库链接（用于跨团队协作场景）。

## Stage 枚举对照

| Stage | 老规约 | 新规约 |
|---|---|---|
| `pre` | ✅ | ✅ |
| `auto` | ✅ | ✅ |
| `dev` | ✅ | ✅ |
| `alpha` | ✅ | ✅ |
| `beta` | ✅ | ✅ |
| `feature` | ✅ | ✅ |
| `hotfix` | ✅ | ✅ |
| `review` | ✅ | ✅ |
| `duom` | ✅ | ❌（trex team 新规约砍掉） |

## 变更日志

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-05-12 | 初版：从 GitLab 后台 dump 当前 Push Rule + 标注 `trex` 为新工程统一前缀 |
| v2.0 | 2026-05-13 | trex team 引入"无项目前缀"新规约（`<stage>_<date>_<name>`）。Push Rule regex 末尾追加一条 alternation，老 pattern 一字未改（org 共享模版兼容）。新规约日期 6/8 位必填、name 必填、stage 砍 `duom`。Trex team policy: 2026-06-30 in-flight 老分支收尾。 |

后续 Push Rule 修改必须更新本文件 + 在表内追加一行；regex 修改严格遵守"纯添加"原则。
