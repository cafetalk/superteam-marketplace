# 任务追踪（Linear）

t-rex 用 **Linear** 做任务追踪。本章定义"何时建 issue / issue 怎么写 / 状态怎么走 / 怎么与代码串联"。

## 总览：Issue 是贯穿任务全生命周期的活文档

```text
任务想法 ────► 建 issue ────► 设计 ────► 开发 ────► 提测 ────► 提测 MR merged
              (Backlog)      (Todo)    (In Progress)(In Review)      (Done)
                  │             │           │            │              │
                  └─────────────┴───────────┴────────────┴──────────────┘
                            description 持续成长（不只在 comment 里）
```

**核心原则**：**先建 issue，后细化**。不允许"先做完再回填 issue"。

**研发 Done 边界**：研发任务在**提测 MR (`dev_*` → `review_*`) merge 那一刻就 Done**。后续 QA 整合（→ `beta_*`）、k8s beta env 测试、发布上 master 都不在研发 issue 的范围内 —— 测试 / 发布是独立流程（见 `common/07` / `common/04`），各自由 QA / 研发负责人推动，必要时另开 issue 跟踪。

## 何时建 issue【强制】

**任务刚开始规划时就建**（不等设计文档完工）。

触发点：
- 任何 idea / 需求开始有形（哪怕只是一句话标题）
- PRD / RFC 产出（issue 与文档互相链接）
- Bug 被发现 / 报告（含小 bug，用于历史与统计）
- 线上变更（含 hotfix / 配置变更）
- 跨团队 / 跨服务对接
- 用户 / PM / 运营在等结果，需要状态可见

`〔t-rex 现状〕`：以"先建 issue，后细化"为原则；**不允许**"先做完再回填 issue"以让看板好看。

## 何时**不**建 issue【推荐】

1. 5–15 分钟的 typo / format / 重命名 / 注释补全 → 直接 commit
2. 已被某个进行中 issue 充分覆盖的子任务 → 用 issue description 的 checklist 或建 **sub-issue**
3. 已被 Project / Initiative 描述充分包含的"显然子工作"

## 粒度【推荐】

| 量级 | 处理 |
|---|---|
| **0.5–3 个人日** | ✅ 一个 issue |
| **> 3 个人日** | 拆 sub-issues；或升格为 Project |
| **< 0.5 个人日** | 与相关工作合批（一个 issue 多 commit）；或不建 issue 直接 commit |

经验值：**一个 issue ≈ 一个 `review_*` 分支 ≈ 一个 MR**。

## 层级

```text
Initiative                   # 跨 quarter 战略主题
  └── Project                # 多周 feature / 工作流（如 T-Rex Advertiser Onboarding）
        └── Issue            # 0.5–3 人日的 deliverable (TREX-xxx)
              └── Sub-issue  # 个人级拆分（可选）
```

**`trex` project（backlog）定位**：装"未归属到具体 Project 的"工作 —— 工具、规范、技术债、跨 project 任务。例：`TREX-395` (本 skill 自身实现) 就归在这里。

## Issue 必备字段【强制】

| 字段 | 要求 |
|---|---|
| **Title** | 祈使句，< 60 字符；可加 namespace 前缀（如 `[Skill]` / `[Hotfix]` / `[RFC]` / `[Bug]`） |
| **Description** | 至少含 **WHY**（背景 + 价值）+ **WHAT**（可验证的交付物）；HOW 可后补 |
| **Acceptance criteria** | bullet 列表 "done when ..." |
| **Project** | 必须归属（找不到具体 Project 则归 `trex` backlog） |
| **Assignee** | 单人主负责（即便协作） |
| **Labels** | 至少一个分类（`feature` / `bug` / `tooling` / `chore` / `docs` / `rfc` / `skill` / ...） |

**可选**：Estimate / Priority / DueDate / Cycle。

## Description 成长模型【强制】

随阶段更新 **description**（不是只在 comment 里）。Description 是任务的当前真相，comment 是过程记录。

| 阶段 | description 应包含 |
|---|---|
| **创建时**（Backlog） | WHY 草稿 + WHAT 草稿 + acceptance criteria 草稿（可以都是 TBD） |
| **设计阶段** | + 设计文档 / RFC 链接（路径或 URL）+ 关键决策摘要 |
| **开发阶段**（In Progress） | + 分支名（`dev_*`）+ 主要 commit / MR 链接 |
| **提测**（In Review） | + 提测 MR 链接（`dev_*` → `review_*`）+ 提测单链接 |
| **提测 merged**（Done） | + 实际行为差异（若与初稿不同）+ 后续 follow-up（如 QA 反馈、上 master 跟踪 issue）|

**反例**：
```text
❌ Description 一行 "TBD"，三周后还是 "TBD"
❌ 所有更新只在 comment 里，description 永远是初版
❌ 实现已偏离原 WHAT 但 description 不更新
```

## 状态流转【强制】

| 状态 | 含义 | 进入条件 |
|---|---|---|
| **Backlog** | 想法 / 计划中 | issue 刚建 |
| **Todo** | 已规划好，等开发 | 设计 / 拆分完成；可分配人 |
| **In Progress** | 正在开发 | 开了 `dev_*` 分支并有 commit |
| **In Review** | 已提测 | 创建 `dev_*` → `review_*` 提测 MR |
| **Done** | 研发完成 | 提测 MR merge 到 `review_*`（team lead approve） |

**特殊状态**：
- **Block** — 等外部依赖 / 卡住；**必须**在 comment 写明阻塞点 + 解封条件 + 重评估日期
- **Canceled** — 决定不做；**必须**在 comment 解释原因

**【强制】Done 不等于上 prod**：
- Done 标记的是**研发交付完成**（提测 MR merged）
- 后续 QA 阶段的 bug 回流（见 `common/07` §测试流程）若需开发者修复，仍在原 Linear issue 下挂 sub-issue 或 comment 跟踪，不重开主 issue
- "上 master / 上 prod" 由 QA + 研发负责人独立推进（见 `common/04`），不阻塞研发 issue 的 Done

## 与代码的串联【推荐】

让 issue / 分支 / commit / MR 互相能追溯：

| 串联点 | 做法 |
|---|---|
| Branch ↔ Issue | **分支名不带 Linear ID**（保持简洁，见 `common/02-branch-and-commit.md`）；通过 commit / MR 反向追溯 |
| Commit ↔ Issue | commit msg body 末加一行 trailer：`Tracks Linear TREX-<id>` |
| MR ↔ Issue | MR description 首段写一行：`Tracks Linear TREX-<id>`（Linear 会自动检测并建立双向链接） |
| Issue ↔ Doc / RFC | issue description 引用文档路径或 URL |
| Comment ↔ 同步状态 | 关键节点用 Linear comment 同步（设计完成 / 提测 / merge）；comment 不取代 description 成长 |

### 正例：commit message 末尾

```text
feat: add campaign airdrop rebuild API

Implement /api/campaign/airdrop/rebuild endpoint for ops to manually
rebuild airdrop snapshots in failure scenarios. Integrates with existing
SessionKeyCacheService.

Tracks Linear TREX-401

Co-Authored-By: ...
```

### 正例：MR description 首段

```markdown
Tracks Linear TREX-401

## 变更

- 新增 `/api/campaign/airdrop/rebuild` 端点
- ...
```

## 反例【强制规避】

```text
❌ 任务做完了才回填一个 issue 让看板好看 → 行政开销，无追溯价值
❌ "实现 X 全部" 一个巨型 issue 无拆分 → 无法估时、无法分配、review 不动
❌ 每个 commit 建一个 issue → 爆炸性增长，淹没真信号
❌ 状态长期不更新（assignee 已离职 / 工作已完成 / ticket 还 Open）
❌ description 永远是 "TBD"，关键信息全在 comment 里
❌ 探索 spike 阶段就开 issue，结论是"不做"，issue 永远挂 Backlog
   → 探索用 doc 或临时 Linear comment；只有探索结论产出可执行工作时才开 issue
```

## 团队层面【推荐】

- **每周清扫 Backlog**（建议固定时间）：过期 / 陈旧 / 与现状不符的 issue 转 Canceled 或重写
- **长期 Block 的 issue 必须复审**解封路径或转 Canceled
- **Initiative 与 Project 的归属**至少每 quarter 复审一次
- **Done 的 issue 不要长期开着**（merge 后立刻关）

## 工具

- **Linear MCP**：可用 `superteam-linear` skill 在 AI 工具中读写 Linear（`list_issues` / `save_issue` / `save_comment` 等）
- **GitLab MR ↔ Linear**：MR description 写 `TREX-<id>` Linear 自动识别（不需要专门集成）

## 维护

- 状态机调整需团队共识并更新本章
- 新增 Initiative / 业务 Project 时同步登记到团队 wiki
- 标签（labels）增删需在 Linear 配置中操作，并更新本章字段表
