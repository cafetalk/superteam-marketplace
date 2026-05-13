# 分支命名 + Commit message + Push Rule

本章规则由 **GitLab Push Rule 强制**：违反则 push 被直接拒绝。Push Rule regex 是 **org-wide 共享模版**（所有 t-rex 项目共用一份），同时容纳 trex team 的新规约 + 其他团队的老规约。完整 regex 与项目前缀清单见 `appendix/project-prefix.md`。

## trex team 分支命名【强制】

新规约 —— 去掉项目前缀，简洁版。

**公式**：

```text
<stage>_<date>_<name>
```

- `stage` ∈ `{ pre, auto, dev, alpha, beta, feature, hotfix, review }`（8 个；老规约里的 `duom` 不再使用）；其中 `dev` / `review` / `beta` 是 t-rex 主 pipeline 的核心 stage
- `date` **必填**：6 位 `YYMMDD`（**trex 项目推荐**）或 8 位 `YYYYMMDD`
- `name` **必填**：2–30 字符，限 `[.A-Za-z0-9\-]`

**示例**：

| 用途 | 分支名 | 部署目标 |
|---|---|---|
| 日常开发（个人特性分支）| `dev_260512_campaign` | k8s dev env（auto deploy） |
| 提交审核（审核通过快照）| `review_260513_campaign` | 无（仅审核通过的代码快照）|
| QA 整合（同版本多 review 合并）| `beta_260513_campaign` | k8s beta env（auto deploy）|
| 多人协作大特性 | `feature_260512_advertiser-onboarding` | 视场景 |
| 紧急修复 | `hotfix_260512_balance-bug` | 视场景 |
| 预发 | `pre_260512_q3-release` | 视场景 |
| 自动化产出 | `auto_260512_codegen-sync` | 视场景 |

**说明**：`<keyword>` 在 `beta_<date>_<keyword>` 由测试人员根据**版本主题**决定（例如 `campaign` / `onboarding`）；该分支是同一版本多个 `review_*` 的整合产物，是发布的入口分支。

**长期分支白名单**（无 stage 前缀，K8s 三环境基线）：

```text
dev | beta | master
```

**【强制】** 三条线（trex team 新约定）：
- **`dev`** —— K8s **dev 环境基线分支**（开发联调）；通过 `review_*` MR 合入流程详见 `common/03`
- **`beta`** —— K8s **beta 环境基线分支**（测试人员部署）；具体版本部署用 `beta_<date>_<keyword>`
- **`master`** —— K8s **prod 环境基线分支**（真实用户）；只允许通过 `beta_<date>_<keyword>` 发布 MR 进入

两个核心 MR：
- **提测 MR**：`dev_<date>_<name>` → `review_<date>_<name>` —— team lead 审核（见 `common/03`）
- **发布 MR**：`beta_<date>_<keyword>` → `master` —— 发布 CI 自动建，研发负责人审核（见 `common/04`）

中间步骤：QA 把多个同版本 `review_*` 整合到 `beta_<date>_<keyword>`（见 `common/07`）。

**反例**：

```text
❌ feature/add-campaign            （斜杠 / 不允许）
❌ DEV_260512_campaign             （stage 大写）
❌ dev_2605_campaign               （日期不是 6 位 YYMMDD 或 8 位 YYYYMMDD）
❌ dev_260512                      （name 必填，不能省）
❌ dev                             （`dev` 是长期分支，短期开发用 `dev_<date>_<name>`）
❌ trexdev_260512_campaign         （新规约不带项目前缀；trexdev 走 →【兼容/老规约】节）
```

## Commit message【强制】

**格式**：

```text
<prefix>: <subject>

<optional body>

<optional trailers>
```

**允许的 `<prefix>`**：

```text
init | feat | alter | fix | perf | refactor | docs | style | test | build | revert | ci | chore | release | workflow
```

**另允许的整行起始（Merge 自动行）**：`Merge` / `Reverted` / `Revert`

**完整 Push Rule Commit Message regex**：

```regex
^((init|feat|alter|fix|perf|refactor|docs|style|test|build|revert|ci|chore|release|workflow):|Merge|Merge|Reverted|Revert)[\s\S]+
```

**示例**：

```text
✅ feat: 接入大数据 audience 计算 RPC
✅ fix: 修正空投幂等校验在并发下漏判的问题
✅ docs: 补充 trex-tech-handbook 提测 SOP
```

**反例**：

```text
❌ Add campaign service                   （无前缀）
❌ feat:接入新接口                        （冒号后缺空格）
❌ FEAT: ...                              （大写）
❌ feature: ...                           （"feature" 不在 prefix 枚举中）
```

## git worktree【推荐】

**对每个新分支推荐创建独立的 git worktree，而不是在主 checkout 上 `git checkout` 切来切去**。

**优点**：
- 不丢失当前工作进度（无需 stash 或提前 commit 半成品）
- 多任务可并行：每个 worktree 独立目录、独立构建产物
- 避免切分支引起的 `target/` / IDE 索引 / Maven 本地缓存污染

**推荐路径**：`{repo}/.worktrees/<branch-name>/`，且确保 `.worktrees/` 已在 `.gitignore` 中。

**创建**：

```bash
git worktree add .worktrees/dev_260512_xxx -b dev_260512_xxx
cd .worktrees/dev_260512_xxx
```

**完成清理**（分支已 merge 之后）：

```bash
cd <repo-root>
git worktree remove .worktrees/dev_260512_xxx
git branch -d dev_260512_xxx
```

`〔t-rex 现状〕`：
- `review_*` 分支生命周期短，merge 后即可 `worktree remove`
- `dev_*` 可保留作个人工作历史；远端无需保留

## 兼容 / 老规约（其他团队仍在用）

GitLab Push Rule regex 是 **org 共享模版**，同时容纳：
- trex team 新规约（上面那套，**本团队首选**）
- 其他团队仍在用的老规约（带项目前缀的形式）

老规约形式：

```text
<project><stage>_<date>?_<name>?
```

- `project` ∈ `{ drex, anchor, dreamtemple, kiki, duom, vibra, trex, as, rosetta, aspen, stanly, osp, talent, zeek, mugen, mon, quests, alien, adgm, dojo3, slg }`
- `stage` ∈ `{ pre, auto, dev, alpha, beta, feature, hotfix, review, duom }`（多了 `duom`）
- `date` 可选；4 位 `MMDD` 或 8 位 `YYYYMMDD`（**不接受 6 位**）
- `name` 可选；2–30 字符

老示例（**其他团队**用，trex team 不写新分支用这个）：

```text
trexdev_20260512_campaign
trexreview_20260513_campaign
drexhotfix_0512_balance-bug
```

老长期分支白名单（仍合法，包括 trex team 历史遗留）：

```text
dev | beta | master | main
<project>_master    例：drex_master / osp_master / talent_master / kiki_master / mon_master / 
                       rosetta_master / quests_master / zeek_master / alien_master / dojo3_master / 
                       adgm_master / slg_master / dreamtemple_master / duom_master
aspen-pre | beta_aspen_red | zeek_pre_master
```

**【强制】老规约长期分支 ↔ 新规约长期分支映射**（trex team 内迁移参考）：

| 老规约 | 新规约 | 说明 |
|---|---|---|
| `<project>dev` (无日期 / 无 name) | `dev` | 长期 dev 集成分支（test env 部署源）|
| `<project>beta` (无日期 / 无 name) | `beta` | 长期 beta 灰度 / 预发分支 |
| `<project>_master` | `master` | 长期 prod 主分支 |

老规约 regex 允许 `<project><stage>` 后**省略** `_<date>_<name>` 段（regex 里那个 `(|_...)` 分支），所以 `drexdev` / `drexbeta` / `anchordev` 这种**无日期 bare 形式**是合法的"长期分支等效物"（项目前缀版本）—— 与新规约的 bare `dev` / `beta` 语义相同。

**`drexdev` / `drexbeta` / `anchordev` 等 是历史遗留，不是 stage 简写**。trex team 新工作**统一用 bare `dev` / `beta` / `master`**。

短期分支同步迁移：

| 老规约 | 新规约 |
|---|---|
| `<project>dev_<YYYYMMDD>_<name>` | `dev_<YYMMDD>_<name>` |
| `<project>review_<YYYYMMDD>_<name>` | `review_<YYMMDD>_<name>` |
| `<project>beta_<YYYYMMDD>_<name>` | `beta_<YYMMDD>_<name>` |
| `<project>hotfix_<YYYYMMDD>_<name>` | `hotfix_<YYMMDD>_<name>` |
| `<project>feature_<YYYYMMDD>_<name>` | `feature_<YYMMDD>_<name>` |
| `<project>pre_<YYYYMMDD>_<name>` | `pre_<YYMMDD>_<name>` |
| `<project>alpha_<YYYYMMDD>_<name>` | `alpha_<YYMMDD>_<name>` |
| `<project>auto_<YYYYMMDD>_<name>` | `auto_<YYMMDD>_<name>` |

`〔rename SOP〕` 在线 rename 长期分支：
```bash
# 例：把 drexdev 迁到 dev
git push origin drexdev:dev          # 创建新名（如 dev 不存在）
# 在 GitLab Settings → Repository → Default branch 切到 dev（如需要）
git push origin --delete drexdev     # 删老名
```
对 `<project>_master` → `master` 的迁移同理；注意可能撞我们设的 `Bash(git push *:master)` deny rule，要走 GitLab UI 或临时 unset deny。

## trex team 迁移目标（team policy，非 regex 强制）

- **2026-05-13 起**：trex team 新工作**统一用新规约**（bare `dev` / `beta` / `master` 作长期；短期用 `<stage>_<date>_<name>`）
- **2026-06-30 前**：trex team 完成
  - in-flight 老短期分支 merge 或重命名到新规约
  - **长期分支重命名**：`<project>dev` → `dev`、`<project>beta` → `beta`、`<project>_master` → `master`
- 6/30 之后：trex team 内部不再创建任何带项目前缀的分支；handbook 把"兼容/老规约"节标注为 archival reference（regex 不变，仍兼容其他团队）

`〔历史归档〕` 2026-05-13 trex team 首次大规模分支治理（22 仓清理 709 分支 + 重命名 12 长期分支 + master 整合 3 仓）的事件记录见 `appendix/branch-cleanup-2026-05-13.md`。

## 维护

- Push Rule regex 在 `appendix/project-prefix.md` 内有完整版 + 项目前缀清单 + 变更日志
- regex 变更须经 GitLab admin 修改 Push Rule + 同步更新本章 + 在 appendix 加变更日志
- 因 regex 是 org 共享模版，**任何对 regex 的修改必须是纯添加**（不删除老 pattern，否则会破其他团队）
