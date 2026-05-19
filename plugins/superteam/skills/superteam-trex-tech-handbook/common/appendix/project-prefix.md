# Push Rule 完整 regex + 老前缀归档

本文件是 `common/02-branch-and-commit.md` 的参考附录。

`〔注意〕` GitLab Push Rule regex 是**每项目独立配置**，不是 org 共享模版。本文档定义的是 **t-rex sub-group（`Keccak256-evg/t-rex/*`）下所有项目的统一标准 regex**；其他 sub-group / 团队的项目不在本文档管辖范围。

## Push Rule Branch Name regex【强制】

GitLab 项目设置 → Repository → Push Rules → Branch name 配置如下（120 字符）：

```regex
(((pre|auto|dev|alpha|beta|feature|hotfix|review)(|_(\d{8}|\d{6}|\d{4})_[\.A-Za-z0-9\-]{2,30}))|^dev$|^beta$|^master$|^main$)
```

### Regex 拆解

```text
(
   ━━━━━━━━ 短期分支（stage_<date>_<name>）━━━━━━━━

   ((pre|auto|dev|alpha|beta|feature|hotfix|review)
    (|_(\d{8}|\d{6}|\d{4})_[\.A-Za-z0-9\-]{2,30}))
        ▲           ▲
        │           └── name：2–30 字符，限 [.A-Za-z0-9\-]，必填（与 stage_date_name 形式时）
        │
        └── date：8 位 YYYYMMDD（grandfather）/ 6 位 YYMMDD（**新建推荐**）/ 4 位 MMDD（老格式）

   注意 `(|_..._...)` 允许只写 stage 一个词（bare stage）—— 但通常不用，因为同时有下面 4 个长期分支

   ━━━━━━━━ 长期分支白名单 ━━━━━━━━

   | dev | beta | master | main
)
```

### 与旧版差异（2026-05-19 v3.0 改动）

**v2.0 → v3.0 关键变化**：

| 维度 | v2.0（之前 handbook 描述） | v3.0（实际 GitLab 配置） |
|---|---|---|
| **regex 长度** | 600+ 字符 | 120 字符 |
| **项目前缀老形式** `(drex\|anchor\|kiki\|...)(stage)_...` | ✅ 列在 regex 里 | ❌ **移除** —— 老前缀分支不能新建 |
| **`<project>_master` 长期分支白名单** | ✅ 列出 16 个 | ❌ **移除** —— 只保留 `master/main/dev/beta` |
| **日期位数** | 6 / 8 位 | **6 / 8 / 4 位**（新增 6 位作为团队推荐） |
| **stage 枚举** | `(stage_list)\|duom` | `pre / auto / dev / alpha / beta / feature / hotfix / review`（**砍 `duom`**） |

**v3.0 校准依据**：2026-05-19 conformance audit（`docs/audits/2026-05-19-handbook-conformance.md`）发现 v2.0 描述的 regex 从未真正在 GitLab 落地，**实际配置一直是 120 字符短版**；v3.0 是首次让 handbook 与 GitLab 真实状态对齐，**同时**新增 `\d{6}` 支持团队推荐的 6 位日期格式。

## Push Rule Commit Message regex【强制】

```regex
^((init|feat|alter|fix|perf|refactor|docs|style|test|build|revert|ci|chore|release|workflow):|Merge|Reverted|Revert)[\s\S]+
```

`〔t-rex 现状〕`：部分 t-rex 项目（如 `trex-admin`）使用**更严格的 conventional-commits 风格**，含可选 scope + breaking-change marker：

```regex
^((init|feat|...|workflow)(\([^)]+\))?!?:|Merge|Reverted|Revert)[\s\S]+
```

此变种**严格 superset 于**上面的 standard —— 接受 `feat(api): add endpoint` / `fix!: breaking change` 等更精细的 commit message。新项目可酌情采用；handbook 不强制统一。

## trex team 分支命名速查【强制】

| 维度 | 值 |
|---|---|
| 公式 | `<stage>_<date>_<name>` |
| stage | `pre / auto / dev / alpha / beta / feature / hotfix / review`（8 个） |
| date | **6 位 `YYMMDD`（新建必须用这个）**；8 位 `YYYYMMDD` / 4 位 `MMDD` 仅 grandfather 现存分支 |
| name | 2–30 字符 `[.A-Za-z0-9\-]`；必填 |
| 长期分支 | `dev` / `beta` / `master`（3 个） |

## 老前缀归档（**禁止新建**）

`〔t-rex 现状〕`：2026-05-19 v3.0 之前，t-rex 后端 backend-java 仓有大量使用旧式项目前缀的分支：

```text
drexdev_20260507_adv_dashboard
drexreview_20260429_onboarding
drexbeta_20260512_test
anchordev_*
trexdev_*
...
```

**v3.0 起 GitLab Push Rule 不再接受新建此类分支**（regex 已不含项目前缀部分）。已存在的分支：
- **grandfather**：仓库内现存的老前缀分支**仍可 push 修复**（push rule 是按分支名规则校验，与历史无关；现存分支匹配 regex 的就能 push） —— 等等！这里有问题。

**等等，技术细节澄清**：

新 regex 不接受 `drexdev_*` 形式。GitLab Push Rule **每次 push 都校验分支名**。所以现存的 `drexdev_20260507_adv_dashboard` 分支在 v3.0 后**也不能再 push 新 commit**。

`〔过渡策略〕`：
1. **正在用的 drexdev_* 分支**：把 commits 整合到新 `dev_<YYMMDD>_<name>` 分支（rebase 或 cherry-pick），原老分支允许在仓内存活但不再活跃
2. **已合并的 drexreview_* / drexbeta_***：直接归档（不能 push 即可，分支记录保留）
3. **`<project>_master` 长期分支**：在 v3.0 之前应该已经迁移到 bare `master`；若还有，立即迁移

```bash
# 老前缀迁移示例（必须在 v3.0 push rule 生效后）
git checkout drexdev_20260507_adv_dashboard
git checkout -b dev_260507_adv-dashboard       # 注意：6 位日期 + kebab-case name
git push origin dev_260507_adv-dashboard       # 新分支
# 老分支保留在远端作历史记录，不再 push commits
```

## 老前缀清单（**归档参考；非 regex 内容**）

下表是 2026-05-19 之前 v2.0 regex 容纳的"老规约项目前缀"。**v3.0 起不再受 push rule 支持**。仅供识别历史分支用。

| 前缀 | 历史用途 |
|---|---|
| `trex` | t-rex 生态历史前缀（trex team） |
| `drex` | trex-core / trex-passport / trex-web 等存量后端（GitLab path 已 rename，但分支 + 包名仍含 `drex`） |
| `anchor` | anchor-pay 等 anchor 子域 |
| `dreamtemple` / `kiki` / `duom` / `vibra` / `as` / `rosetta` / `aspen` / `stanly` / `osp` / `talent` / `zeek` / `mugen` / `mon` / `quests` / `alien` / `adgm` / `dojo3` / `slg` | 其他团队历史前缀 |

`〔t-rex 现状〕`：v3.0 起，**所有这些前缀在分支命名层面消失**。包名 (`com.drex.*`)、GitLab path（部分仍 `drex-*`）、模块名（`drex-module-*`）这类**仓内部命名**不受影响 —— v3.0 只管 push rule 一件事。

## Stage 枚举

| Stage | v3.0 是否接受 |
|---|---|
| `pre` | ✅ |
| `auto` | ✅ |
| `dev` | ✅ |
| `alpha` | ✅ |
| `beta` | ✅ |
| `feature` | ✅ |
| `hotfix` | ✅ |
| `review` | ✅ |
| `duom` | ❌ v3.0 砍 |

## 变更日志

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-05-12 | 初版：从 GitLab 后台 dump 当前 Push Rule + 标注 `trex` 为新工程统一前缀 |
| v2.0 | 2026-05-13 | （handbook 文档误描述）声称 trex team 在原 regex 上"末尾追加" `(stage)_(\d{6}\|\d{8})_<name>` —— **后续 audit 发现实际 GitLab 配置从未含此追加** |
| v3.0 | 2026-05-19 | 校准 + 收紧：handbook 与 GitLab 真实状态对齐 + **加入 6 位日期支持** + 砍掉项目前缀老形式 + 砍掉 16 条 `<project>_master` 长期分支。详见本文 §与旧版差异。**配套**：sub-agent 批量更新 61 个 t-rex 项目的 Push Rule 到此 regex，详见 `docs/ops/2026-05-19-push-rule-rollout.md` |

后续 Push Rule 修改必须更新本文件 + 在表内追加一行。
