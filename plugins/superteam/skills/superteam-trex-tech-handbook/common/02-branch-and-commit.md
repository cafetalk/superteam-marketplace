# 分支命名 + Commit message + Push Rule

本章规则由 **GitLab Push Rule 强制**：违反则 push 被直接拒绝。Push Rule regex 是**每项目独立配置**，t-rex sub-group（`Keccak256-evg/t-rex/*`）下所有项目使用统一标准 regex。完整 regex + 老前缀归档见 `appendix/project-prefix.md`。

## trex team 分支命名【强制】

去掉项目前缀的简洁版。

**公式**：

```text
<stage>_<date>_<name>
```

- `stage` ∈ `{ pre, auto, dev, alpha, beta, feature, hotfix, review }`（8 个；老规约里的 `duom` v3.0 起不再使用）；其中 `dev` / `review` / `beta` 是 t-rex 主 pipeline 的核心 stage
- `date` **必填**：**6 位 `YYMMDD`（新建必须用这个）**；8 位 `YYYYMMDD` / 4 位 `MMDD` 仅 grandfather 现存分支
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
- **`master`** —— K8s **prod 环境基线分支**（真实用户，**prod 部署仅从 `master`**）；只允许通过 `beta_<date>_<keyword>` 发布 MR 进入；详见 `common/04-ci-and-release.md`

两个核心 MR：
- **提测 MR**：`dev_<date>_<name>` → `review_<date>_<name>` —— team lead 审核（见 `common/03`）
- **发布 MR**：`beta_<date>_<keyword>` → `master` —— 发布 CI 自动建，研发负责人审核（见 `common/04`）

中间步骤：QA 把多个同版本 `review_*` 整合到 `beta_<date>_<keyword>`（见 `common/07`）。

**反例**：

```text
❌ feature/add-campaign            （斜杠 / 不允许）
❌ DEV_260512_campaign             （stage 大写）
❌ dev_2605_campaign               （日期长度不对：必须 6 位 YYMMDD，或 grandfather 的 8/4 位）
❌ dev_260512                      （name 必填，不能省）
❌ dev                             （`dev` 是长期分支，短期开发用 `dev_<date>_<name>`）
❌ trexdev_260512_campaign         （**v3.0 禁止**：项目前缀老形式已从 Push Rule 移除）
❌ drexdev_20260512_xxx            （**v3.0 禁止**：同上；现存老分支 grandfather 但新建一律拒）
❌ drex_master                     （**v3.0 禁止**：`<project>_master` 长期分支已从白名单移除；用 bare `master`）
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

## 老前缀归档（**v3.0 禁止新建**）

2026-05-19 v3.0 起，Push Rule regex 不再容纳项目前缀老形式：

- 旧短期形式：`drexdev_20260507_xxx` / `anchorreview_xxx` / `trexbeta_xxx` 等 —— **新建一律 push 被拒**
- 旧长期分支：`drex_master` / `osp_master` / `<project>_master` 系列 + `aspen-pre` / `zeek_pre_master` 等 —— **新建一律拒；现存的需迁移到 bare `master`**

**仓里现存的老前缀分支怎么处理？**

```bash
# 把 drexdev_20260507_adv_dashboard 上的 commits 迁到新规约
git checkout drexdev_20260507_adv_dashboard
git checkout -b dev_260507_adv-dashboard     # 6 位日期 + kebab-case name
git push origin dev_260507_adv-dashboard
# 老分支保留作历史快照，不再 push commits
```

**长期分支迁移**（如还有 `<project>_master`）：
```bash
git push origin drex_master:master     # 创建 bare master（如不存在）
# 在 GitLab Settings → Repository → Default branch 切到 master
git push origin --delete drex_master   # 删老名
```

老 ↔ 新 短期分支对照表（**仅供识别历史分支**；新建不允许）：

| 历史形式（v3.0 禁止新建） | 新规约（v3.0 强制） |
|---|---|
| `<project>dev_<YYYYMMDD>_<name>` | `dev_<YYMMDD>_<name>` |
| `<project>review_<YYYYMMDD>_<name>` | `review_<YYMMDD>_<name>` |
| `<project>beta_<YYYYMMDD>_<name>` | `beta_<YYMMDD>_<name>` |
| `<project>hotfix_<YYYYMMDD>_<name>` | `hotfix_<YYMMDD>_<name>` |
| `<project>feature_<YYYYMMDD>_<name>` | `feature_<YYMMDD>_<name>` |

`〔历史归档〕` 2026-05-13 trex team 首次大规模分支治理（22 仓清理 709 分支 + 重命名 12 长期分支 + master 整合 3 仓）见 `docs/ops/2026-05-13-branch-cleanup.md`。  
2026-05-19 v3.0 push rule 收紧 + 6 位日期落地的 rollout 见 `docs/ops/2026-05-19-push-rule-rollout.md`。

## 维护

- Push Rule regex 完整版 + 老前缀归档 + 变更日志见 `appendix/project-prefix.md`
- regex 变更须经 GitLab admin 修改 Push Rule（**每项目独立**，t-rex sub-group 下 61 个项目要逐一 PUT）+ 同步更新本章 + 在 appendix 加变更日志
- v3.0 起，handbook 与 GitLab 真实 push rule 必须保持一致（通过 conformance audit 验证）
