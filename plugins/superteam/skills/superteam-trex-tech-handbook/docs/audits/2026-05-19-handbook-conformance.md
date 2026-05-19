# Handbook 一致性审计 — 2026-05-19

## 背景

M2 sprint 第一刀。M1.5（76 → 9 TODO 清理）把 handbook 内容压实了，但其中很多陈述是基于"我读过 / 我推测 / 历史这样写"，**未必匹配 GitLab 仓库当前实际状态**。本次按 8 项 checklist 从 GitLab API 拉真实数据交叉验证，输出此报告 + 修复 handbook 错误条目。

## 审计范围 / 方法

- 数据源：GitLab API（pom.xml / 仓库 tree / push_rule / 文件搜索）
- 抽样：14 个 Java 后端仓（6 backend-java + 8 anchor）+ scaffold/ + ops/gitlab-cis
- 不爬：Python repos、Foundry contract repos、前端 repos（M2 范围外）
- 自动化：`/tmp/audit.py` + `/tmp/audit2.py` + `/tmp/audit3.py`（一次性脚本；产物即此报告）

## 结果概览

| # | 检查项 | 结果 | 是否需要 handbook 修复 |
|---|---|---|---|
| 1 | trex-framework Maven 坐标 | ✅ MATCH | — |
| 2 | trex-scaffold 9 模块清单 | ✅ MATCH | — |
| 3 | `kiki-observability-tracing` 覆盖度 | ⚠️ PARTIAL | 注释补 trex-admin 例外 |
| 4 | trex-core 错误码段位 4/5/6xxx 含义 | ❌ **WRONG** | **YES** — 07-exception 段位描述需重写 |
| 5 | trex-web JUnit 3.8.1 残留 | ✅ MATCH（事实成立） | — |
| 6 | backend-java 模块切法 | ⚠️ PARTIAL（trex-passport 模块名错） | **YES** — 01-microservices trex-passport 条目修 |
| 7 | ops/gitlab-cis/gwave-dev yamls 覆盖 | ⚠️ PARTIAL | 注释补 trex-admin yaml 缺失 |
| 8 | Push Rule branch regex | ❌ **WRONG** | **YES** — common/appendix/project-prefix.md 重写 |

**摘要**：5 项 ✅/✅ "事实成立"、3 项 ⚠️ "部分对、需注释"、**2 项 ❌ "明显错"，本 PR 内修**。

---

## 详细发现

### Check 1: trex-framework Maven 坐标 ✅

**handbook 称**（`02-architecture.md`）:
```xml
<groupId>com.kikitrade</groupId>
<artifactId>kiki-framework</artifactId>
<version>2.5.0-SNAPSHOT</version>
```

**实际**（API 拉 `t-rex/scaffold/trex-framework/pom.xml`）:
```
groupId    : com.kikitrade
artifactId : kiki-framework
version    : 2.5.0-SNAPSHOT
```

完全一致。

### Check 2: trex-scaffold 9 模块清单 ✅

**handbook 称**（`02-architecture.md` 模块表）：9 个 `evg-scaffold-*` 模块。

**实际**（API 拉 tree）：

```
evg-scaffold-common / -endpoint / -endpoint-client / -event / -event-client /
-feast-client / -inner-event / -telegram / -vampire-attack
```

全部 9 项一一对应。

### Check 3: kiki-observability-tracing 覆盖度 ⚠️ PARTIAL

**handbook 称**（`10-quality-ops.md`）：所有服务通过 `kiki-observability-tracing-spring-boot-starter` 接入 Zipkin。

**实际**（GitLab `/search?scope=blobs` 命中数）：

| 仓 | hit 数 | 状态 |
|---|---:|---|
| trex-core | 2 | ✅ |
| trex-passport | 1 | ✅ |
| trex-web | 1 | ✅ |
| trex-endpoint | 1 | ✅ |
| trex-event | 1 | ✅ |
| **trex-admin** | **0** | ❌ **缺失** |
| anchor-core | 3 | ✅ |
| anchor-web | 3 | ✅ |

- 14 个 Java 后端仓里 7/8 抽样命中（剩余 6 个未抽样的 anchor-* Java 同源同构，推测 100% 命中）
- **trex-admin（reborn）尚未接入 tracing starter** —— 与 "reborn 已合主干" 状态匹配（新仓常见 starter 接入是滞后任务）
- `kiki-framework` 的 parent POM 在 dependencyManagement 中**声明**了该 starter，但 trex-admin 没有显式 `<dependency>` 引用 → 不会被 Spring Boot 自动启用

**建议**：handbook 不改约束（仍要求强制接入），但**在 trex-admin 条目里加 〔现状〕** 标注 "tracing starter 尚未接入，是 reborn 期内未完成项"。

### Check 4: trex-core 错误码段位 ❌ WRONG

**handbook 称**（`07-exception-and-logging.md`）:

```
- 4xxx — Core 通用
- 5xxx — YouTube 模块
- 6xxx — Campaign 模块
```

**实际**（`trex-core/core-api/.../com/drex/core/api/common/CoreResponseCode.java` 23 个 enum）：

| 段位 | 实际占用 | 含义推断 |
|---|---|---|
| `0xxx` | 1 (SUCCESS) | 成功 |
| **`4xxx`** | 10 codes | `INVALID_PARAMETER` / `INVALID_BUSINESS_ID` / `REWARD_*` / `DATA_*` / `REXY_BASKET_EMPTY` / `REPLY_TEXT_INVALID` / `TOO_MANY_REQUEST` → **Core 通用 + reward + rexy + reply 等混合**，不只是 "Core 通用" |
| **`5xxx`** | 11 codes | 全部 `SQUAD_TASK_*` → **Squad Task 模块（NOT YouTube）** |
| **`6xxx`** | 1 code | `CAMPAIGN_SETTLE_NOT_END` → Campaign 模块，**但只有 1 个码**（基本未启用） |

**结论**：
- 5xxx 的含义早已从 "YouTube" 漂移到 "Squad Task"（业务变更）
- 4xxx 不只是 "Core 通用"，跨多个域（reward / rexy / reply）—— 段位本身未严格按域切分
- 6xxx Campaign 段实际未怎么用

**handbook 修复**（在本 PR 内）：07-exception 章 §错误码分段规约 重写为：
- `0xxx` — 成功 (`SUCCESS`)
- `4xxx` — 通用错误（参数 / 数据 / 限流）+ 部分业务（reward / rexy / reply）；尚未严格按域切分
- `5xxx` — Squad Task 模块（**早期文档称 "YouTube" 已 stale**）
- `6xxx` — Campaign 模块（实际仅 1 个码，业务大头在 5xxx）
- 各服务自管段位（仍强制）

### Check 5: trex-web JUnit 3.8.1 残留 ✅

**handbook 称**（`08-testing.md`）："trex-web 仍有 JUnit 3.8.1 残留（`drex-module-activity/pom.xml`）"。

**实际**（拉 `drex-module-activity/pom.xml`）：
```xml
<groupId>junit</groupId>
<artifactId>junit</artifactId>
<version>3.8.1</version>
```

事实成立。无需 handbook 修改。

### Check 6: backend-java 模块切法 ⚠️ PARTIAL

抽样 6 个 backend-java 仓的 top-level 模块：

| 仓 | handbook 记录 | 实际 |
|---|---|---|
| trex-core | `core-api / core-dal / core-graphql / core-model / core-service / core-web` | ✅ 6 个模块 + `features/` + `technical_design/` |
| **trex-passport** | **`customer-api / customer-dal / customer-model / customer-service / customer-web`（注意：模块名 `customer-*` 而非 `passport-*`）** | ❌ 实际是 **`drex-passport-{api/dal/model/service/web}`** —— handbook 完全弄错 |
| trex-web | `drex-module-{activity/common/core/customer}` + `drex-web-start` | ⚠️ 多一个 `drex-module-onboarding`（handbook 未列） |
| trex-endpoint | `drex-endpoint-{api/dal/service/web}` | ✅ 完全一致 |
| trex-event | `drex-event-server`（单模块） | ✅ 一致 |
| trex-admin | `trex-admin-{common/dal/graphql/security/start}` | ✅ 完全一致 |

**handbook 修复**（在本 PR 内）：
- `01-microservices.md` trex-passport 条目：模块清单从 `customer-*` 改成 `drex-passport-*`，删 "模块名 customer-* 而非 passport-*" 的反向注释（已经反过来了）
- trex-web 条目：模块清单加上 `drex-module-onboarding`

### Check 7: ops/gitlab-cis/gwave-dev yamls 覆盖 ⚠️ PARTIAL

`ops/gitlab-cis` 仓 `gwave-dev/` 共 100 个 yaml；t-rex 相关：

| 仓 | yaml 存在 |
|---|---|
| trex-core (`drex-core.yaml`) | ✅ |
| trex-passport (`drex-passport.yaml`) | ✅ |
| trex-web (`drex-web.yaml`) | ✅ |
| trex-endpoint (`drex-endpoint.yaml`) | ✅ |
| trex-event (`drex-event.yaml`) | ✅ |
| **trex-admin** | ❌ 无 `trex-admin.yaml` 也无 `drex-admin.yaml` |
| trex-framework (`kiki-framework.yaml`) | ✅ |
| trex-scaffold (`evg-scaffold.yaml`) | ✅ |

**结论**：
- 6 个 backend-java 服务里 5 个有 CI yaml；**trex-admin 缺**（与 Check 3 一致 —— reborn 接入 starter 和 CI 是双管 pending）
- ops 仓内文件名仍是历史 **`drex-*.yaml`**（path 已 rename，但 ops CI 命名未跟随）—— PR-2a 已在 `04-ci-and-release.md` 加注释，**无需再改**
- ops 仓自身的目录结构（除 `gwave-dev/` 外，根级还有 `drex/`/`quests/`/`talent/` 等多家 sub-group 共用一个 ops 仓）

**建议**：handbook 不改约束，但 trex-admin 条目应该加 〔现状〕"CI yaml 尚未接入"。

### Check 8: Push Rule branch regex ❌ WRONG（**最严重的 finding**）

**handbook 称**（`common/appendix/project-prefix.md` 第 12 行）：长 600+ 字符的 "org 共享模版 regex"，**含三大块**：
1. 项目前缀老形式：`(drex|anchor|dreamtemple|kiki|...|slg)(pre|auto|dev|alpha|beta|feature|hotfix|review|duom)(|_(\d{8}|\d{4})_<name>)`
2. 老长期分支白名单：`drex_master / osp_master / talent_master / kiki_master / ...`（13 个 `<project>_master`）+ `aspen-pre` + `beta_aspen_red` + `zeek_pre_master`
3. **trex team 新规约追加**：`(pre|auto|dev|alpha|beta|feature|hotfix|review)_(\d{6}|\d{8})_<name>`（含 6 位日期）

**实际**（API 拉 `push_rule` —— 抽样 5 个 backend 仓**全部完全一致**，长度 **仅 120 字符**）：

```
(((pre|auto|dev|alpha|beta|feature|hotfix|review)(|_(\d{8}|\d{4})_[\.A-Za-z0-9\-]{2,30}))|^dev$|^beta$|^master$|^main$)
```

**断层对比**：

| 维度 | handbook 称 | 实际 backend 仓 |
|---|---|---|
| **regex 长度** | 600+ 字符 | **120 字符** |
| **项目前缀老形式**（drexdev / anchordev / kikifeature 等 20+ 种） | ✅ 列在 regex 里 | ❌ **不存在** |
| **老长期分支白名单**（drex_master / osp_master / 等 16 条） | ✅ 列在 regex 里 | ❌ **不存在**（除 master/main/dev/beta 外都被拒） |
| **trex team 新规约 6 位日期**（`\d{6}`） | ✅ 列在 regex 里 | ❌ **不存在**（只接受 `\d{8}` 或 `\d{4}`） |
| **8 位日期 + 4 位日期** | ✅ 部分列出 | ✅ 是 |

**这意味着**：

1. **`drexdev_20260507_adv_dashboard` 类老前缀分支** —— 仓里有大量存量（trex-core 当前活跃 top 20 分支里 13 个是该形式），**但当前 regex 会拒收新建的同形式分支**（grandfathered，不能新增）
2. **6 位日期 `YYMMDD`** —— handbook 多处建议用 `dev_260512_xxx` 这类格式，**实际 backend 仓会被 push rule 拒收**！只有 8 位 `YYYYMMDD` 或 4 位 `MMDD` 才合规
3. **`<project>_master` 长期分支** —— handbook 说迁移过渡期保留，实际 regex 已不允许（除 `master/main/dev/beta`）

**为何用户在本 handbook 仓 push 6 位日期分支成功？**

→ `Keccak256-evg/t-rex/skills/superteam`（handbook 自身仓）的 push rule **branch_name_regex 为空**（无任何限制）。所以本仓内 6 位日期能用，**但跨仓到 backend 服务就会失败**。

**实际 trex-core 活跃分支抽样**（branches API `sort=updated_desc`）：

```
drexdev_20260507_adv_dashboard        ← 存量，不能新建同形式
dev_20260518_TREX-464                  ← ✅ 合规（8 位日期）
drexbeta_20260512_test                 ← 存量
drexreview_20260429_onboarding         ← 存量
drexdev_20260512_reborn                ← 存量
```

**未解疑点 / 需用户判断**（不在本 PR 自动修复）：

1. handbook 描述的"600+ 字符 regex 是 org 共享模版"是**aspirational**（团队希望它长这样）还是**该曾经落地但被 ops 后续收紧**？
2. 若是 aspirational，**fix 路线**：（a）handbook 缩到实际 regex；或（b）ops 把 GitLab regex 扩到 handbook 描述？
3. trex team 新规约推荐的 **6 位日期**与 backend 仓现行规则**冲突**。修法二选一：
   - **修 handbook**：建议改成 8 位 `YYYYMMDD`（与实际 regex 兼容）
   - **修 ops**：让 ops 扩展 regex 接受 6 位
4. 用户在本 superteam 仓内用的 6 位日期 push 习惯，**仅适用本仓**（无 push rule），跨仓使用前需先决策上面第 3 点

**本 PR 暂不自动修复 Check 8**：handbook 这处涉及团队规约层面的决策，不是 AI 单方面能补的。Audit 把发现摆桌面，等用户决策。

---

## 本 PR 内 handbook 修复清单（4 项；Check 8 留作单独决策）

| # | 文件 | 修复 |
|---|---|---|
| 1 | `backend/07-exception-and-logging.md` | 错误码段位描述：5xxx YouTube → Squad Task；4xxx 范围扩展；6xxx 实际仅 1 码 |
| 2 | `backend/01-microservices.md` trex-passport | 模块名 `customer-*` → `drex-passport-*` |
| 3 | `backend/01-microservices.md` trex-web | 模块清单加 `drex-module-onboarding` |
| 4 | `backend/01-microservices.md` trex-admin | 加〔现状〕"tracing starter 尚未接入；CI yaml 尚未接入" |

**Check 8（Push Rule regex 重大失配）单独走流程** —— 不本 PR 修，因涉及团队规约决策（aspirational 还是落地？6 位日期是否保留？是 fix handbook 还是 fix ops？）。

---

## 本 PR 不修的事项

- **观察项漂移**（如错误码 5xxx 含义从 YouTube 变 Squad Task）的根因分析 —— 业务变更档案，不在 handbook 范围
- **未抽样的 6 个 anchor-* Java 仓的 conformance** —— anchor 子域归 anchor team owner 维护，本审计只验主域
- **Push Rule 第 2 / 第 3 个未解疑点** —— 需要用户确认决策来源后再修
- **未来 audit 节奏** —— 是 1 次性还是定期？handbook 内是否加一节"如何重跑 audit"？建议 M2 收尾时讨论

## 复跑方法

```bash
# 重跑全套 8 项 check (可独立运行)
python3 /tmp/audit.py   # check 1, 2, 3 (root pom), 4, 5, 6, 7, 8 (sample 2 repos)
python3 /tmp/audit2.py  # check 3 deep (sub-poms + search) + 4 enum names + 6 trex-passport + 8 sample 5 repos
python3 /tmp/audit3.py  # actual branch names on trex-core/trex-passport + ops/gitlab-cis layout
```

脚本临时放 `/tmp/`，未入仓 —— 后续如果定期 audit，再考虑落地到 `scripts/`。

---

**Audit by**: claude (sonnet 4.7) + allen.qin (oversight)
**Date**: 2026-05-19
