# 提测流程 SOP

本章规范"**提测**" —— 研发把 `dev_<date>_<name>` 上的工作通过 MR 提交给 team lead 审核，审核通过后落到 `review_<date>_<name>` 分支等待 QA 整合。**核心强制规范**。

`〔t-rex 术语〕`：
- **提测** = 研发建 MR `dev_<date>_<name>` → `review_<date>_<name>`；team lead 审核通过即"提测完成"
- **测试** = QA 整合多个 `review_*` 到 `beta_<date>_<keyword>`，部署 k8s beta env 测试（见 `common/07-testing-process.md`）
- **发布** = `beta_<date>_<keyword>` → `master` MR；发布 CI 自动建，研发负责人审核（见 `common/04-ci-and-release.md`）

## SOP【强制】

```text
[1] dev_<date>_<name> 上开发 + 本地自检
        │
        │  push dev_<date>_<name>
        ▼
        k8s dev env 自动部署（联调）
        │
        │  superteam-trex-delivery 的 submit 代建 MR
        ▼
[2] 建提测 MR: dev_<date>_<name> → review_<date>_<name>
        │
        │  - 由 `superteam-trex-delivery` 的 `submit` 代建（见 common/08）：
        │      submit --dev-branch dev_<date>_<name> --issue TREX-1 [--issue TREX-2 ...] --repo <微服务 repo>
        │  - review_* 若不存在，submit 从 master tip 建
        │  - MR description 每个 issue 一行：Tracks Linear TREX-<id>
        │  - reviewer/assignee = 该 repo team lead（references/team-leads.json，缺则 --reviewer）
        │  - Linear issue → In Review（submit best-effort）
        ▼
[3] team lead 审核
        │
        ├── 有 comment → 回到 [1] 在 dev_<date>_<name> 修复 → MR 自动 refresh diff → re-review
        │
        └── approve → merge MR
                │
                ▼
[4] review_<date>_<name> 含审核通过代码快照 = **提测完成**
        │
        │  Linear issue → Done（研发交付完成；后续 QA / 发布 不在研发 issue 范围内）
        ▼
[5] (转 common/07) QA 整合多个 review_<date>_<name> → beta_<date>_<keyword> 部署 k8s beta env 测试
```

### 详细步骤

| Step | 动作 | 关键产物 |
|---|---|---|
| 1 | **开发**：在 worktree 中的 `dev_<date>_<name>` 分支开发；push 触发 k8s **dev env 自动部署**用于联调；自测、跑单测、commit 消息合规 | `dev_<date>_<name>` 远端分支 + k8s dev env 部署 |
| 2 | **建提测 MR**：由 `superteam-trex-delivery` 的 `submit` 代建（`submit --dev-branch dev_<date>_<name> --issue TREX-1 [--issue TREX-2 ...] --repo <微服务 repo>`，见 `common/08`）：建 `review_<date>_<name>`（不存在则从 master tip 切）+ **源 `dev_<date>_<name>`、目标 `review_<date>_<name>`** 的 MR；一次提测(submission)=一个 dev 分支/一个微服务，可关联多个 Linear issue（`--issue` 可重复，全部 In Review）；description 每个 issue 一行 `Tracks Linear TREX-<id>`；reviewer = 该 repo team lead（`references/team-leads.json`，缺则 `--reviewer` 指定；assignee 留作者/开发） | GitLab MR + submission.md |
| 3 | **team lead 审核**：通过即"提测完成"；若 comment，开发者在 `dev_<date>_<name>` 上修复 + 新 commit + push，MR 自动 refresh，team lead re-review | review approved |
| 4 | **merge**：team lead 或开发者 merge MR；`review_<date>_<name>` 拥有审核通过快照 | review 分支 = 审核通过代码 |
| 5 | **进入 QA 整合环节**：见 `common/07-testing-process.md` §QA 整合；多个 `review_<date>_<name>` 由 QA 自行整合到 `beta_<date>_<keyword>` | beta_<date>_<keyword> 分支 |

## 铁律【强制】

1. **MR 必经**：代码进入 `review_<date>_<name>` 必须经过 `dev_*` → `review_*` MR + team lead 审核
2. **名字对齐**：review 分支的 `日期 + name` 必须与对应 dev_* 完全一致：
   - 正例：`dev_260512_campaign` → `review_260512_campaign`
   - 反例：`dev_260512_campaign` → `review_260513_campaign_v2`
3. **review_<date>_<name> 是审核通过快照**，merge 后由 QA 整合接管；研发不主动改动 review_* 分支
4. **bug 回流不开新 issue**：QA 在 beta env 发现 bug → 原开发者在 `dev_<date>_<name>` 修 → 走 §bug 回流 SOP

## 跨服务分支命名【推荐】

一次开发**同时改多个微服务**时，**建议各服务用同一个 `dev_<date>_<name>` 分支名**（不做硬性要求，但建议一致）。

- 好处：一个分支名就能在所有相关仓里定位本轮全部改动；review_* / commit / MR 一一对应；可读、可追溯。
- 正例（PRISM 跨 3 仓）：`trex-hexagonal` / `trex-web` / `trex-core` 都用 `dev_260603_prism-v2`。
- 这个**公共 dev 分支名**也就是 `superteam-trex-delivery` 在 `trex-releases` 里**这次提交所用的记录分支名**（见 `common/08`）—— 记录仓与各微服务仓分支名保持一致，不再另造 `auto_*` 名。

## 自检（建 MR 前）

完整 9 大组 / 35+ 项 Code review 自检 checklist 见 `common/06-development-flow.md` §6。

**绝对 blocker 5 项**（任意 1 项不过不允许建 MR）：

- [ ] 单测 100% 通过：`./mvnw test`
- [ ] commit msg + 分支名通过 Push Rule（见 `common/02`）
- [ ] 接口契约（OpenAPI / GraphQL / Dubbo）已与上下游验证
- [ ] 敏感字段已脱敏（见 `backend/07`）
- [ ] Linear issue description 已更新到 "开发阶段"（见 `common/05`）

## 提测单【强制】

每次建提测 MR 时，**必须同步填写提测单**。模板：`backend/appendix/templates/test-handoff.md`

### 必填字段（7 个）

| # | 字段 | 说明 |
|---|---|---|
| 1 | **提测人** | `@<gitlab-handle>` |
| 2 | **关联 Linear** | `TREX-<id>`（可多个，逗号分隔；与 MR description 各 `Tracks Linear` 行一致） |
| 3 | **MR 链接** | 完整 GitLab MR URL |
| 4 | **目标分支** | `review_<date>_<name>`（与源 dev_<date>_<name> 配对） |
| 5 | **变更范围** | 功能列表 + 影响面（接口 / DB 表 / OTS 表 / Nacos 配置 / 上下游服务） |
| 6 | **自测记录** | k8s dev env 已通过 case + 已知问题 / 已知风险 |
| 7 | **回滚预案** | 若 beta 整合后发现问题，怎么回退（DB / 配置 / 接口契约层面） |

可选字段（按需）：单测覆盖率 / 性能基线 / 第三方依赖 / 跨团队协作联系人。

### 归档位置

`〔t-rex 现状〕`：提测单**写入 `trex-releases` 仓**（`releases/<release-item>/submissions/<date>_<name>/submission.md`，submission key=`<date>_<name>`、可关联多个 Linear issue，由 `superteam-trex-delivery` 的 `submit` 生成，详见 `common/08-release-record.md`）。**每个关联 Linear issue 的 comment 仅留指向该 submission.md 的链接**；记录正文不再 paste 在 comment 里。钉钉 `.axls` 表格停止维护。

## bug 回流 SOP【强制】

`review_<date>_<name>` merge → QA 整合到 `beta_<date>_<keyword>` → 部署 k8s beta env → QA 测试期间发现 bug 时：

```text
                ✗ QA 在 k8s beta env 发现 bug
                          │
                          ▼
              comment 到 Linear issue + GitLab MR
              （或转 Linear sub-issue 跟踪）
                          │
                          ▼
              原开发者在 `dev_<date>_<name>` worktree 修复
                          │
                          ▼
                  新 commit + push `dev_<date>_<name>`
                  （k8s dev env 自动 re-deploy）
                          │
                          ▼
              开发者建**新提测 MR** dev_<date>_<name> → review_<date>_<name>
              （MR 自动追加，或新开 MR；按 review_* 是否还在用决定）
                          │
                          ▼
              team lead re-review → merge
                          │
                          ▼
              QA 把 fix 整合进 `beta_<date>_<keyword>`
              （新 MR review_<date>_<name> → beta_<date>_<keyword>）
                          │
                          ▼
              k8s beta env re-deploy → QA 再测
```

**【强制】铁律**：

1. **不重新建 review 分支** —— 同 review_<date>_<name>，commit 累积；MR 可以是新的或追加
2. **不开新 issue 装 bug 修复** —— 仍归属原 issue；多人协作可用 sub-issue
3. **回流期间 Linear issue 状态保持 `In Review`** —— 不退回 In Progress
4. **force-push 用 `--force-with-lease`** —— 不覆盖别人 commits
5. **每轮 merge 后必须重新触发 CI** —— k8s 各 env 部署最新代码
6. **bug 修复跨多个 review_*** —— 各自原开发者各自修，QA 重新整合

## 多人协作责任划分【推荐】

一个 issue 由多人协作（`feature_*` 分支或 issue 拆 sub-issue）时：

| 角色 | 责任 |
|---|---|
| **主负责人**（Linear issue assignee） | 协调进度 / 填提测单 / 沟通 team lead / 最终签字 |
| **协作者**（贡献 commit / sub-issue assignee） | 完成各自 commit + Linear comment 同步进度 |
| **Team lead** | review MR / 不直接编码（除非 fallback） |
| **研发助手（AI）** | 跑 `superteam-trex-delivery submit` 代建 MR（见 `common/08`）、协助分支管理、Linear 状态同步 |

**默认约定**：

- **MR 创建权归主负责人**（协作者不并发建同名 review_* 的 MR）
- 主负责人提测前**与协作者对齐变更范围**
- Sub-issue 拆分时：每个 sub-issue 独立 `dev_<date>_<name>` 分支 + 独立 review_* + 独立 MR；主 issue 等所有 sub-issue 完成才算 Done

## 反例【强制规避】

```text
❌ 提测单缺字段或写 "TBD"                    → review MR 不该建
❌ QA 反馈用钉钉私聊 / 群消息记录            → 断追溯，必须 Linear / MR comment 留痕
❌ beta env 发现 bug 时另开新 issue          → 回流到原 issue（or sub-issue）
❌ 多人协作各自建同名 review 分支的 MR       → 由主负责人统一建
❌ 把 review_<date>_<name> 当工作分支直接 push commit → review 是审核通过的快照，研发只在 dev_<date>_<name> 工作
❌ 跳过 review_*，直接 dev_*_xxx 整合到 beta_*       → 失去 team lead 审核环节
```

## 后续补充事项

`〔t-rex 现状〕`：以下细节仍在团队实践中沉淀，handbook 暂不立硬约束 —— 各自按当前共识执行，若分歧累积再回到本章统一：

- **bug 回流 + 重新提测**：通常复用同一 `review_<date>_<name>`（commit 累积）；只有当 base 漂移很远 / review 历史污染严重时才另起 `+v2`
- **多人协作 commit 协同**：默认 `merge`（保留历史），cherry-pick 仅用于 hotfix 跨分支
- **QA 接收提测通知**：暂无自动 trigger；提测人主动在 Linear comment + 群里 @ QA
- **`review_<date>_<name>` base**：默认从 `master` tip 切（保证最新）；长期 feature 例外

## 维护

- 本章强约束由 GitLab Push Rule + 团队共识共同保证
- 流程变更需团队评审通过后再修订
- 提测单字段调整需同步更新 `backend/appendix/templates/test-handoff.md`
