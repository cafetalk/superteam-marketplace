# t-rex 生态全景

本 handbook 服务于 t-rex 生态的日常开发，不覆盖 `superteam` 子项目（superteam 有自己的 `CLAUDE.md`）。

## 生态分工

t-rex 生态按职能切分大致如下（具体仓库 / 服务清单见 `backend/01-microservices.md`）：

- **前端** — 用户侧 Web / 项目方 Portal
- **后端** — Java 微服务集群（Gateway / Dubbo 领域服务）
- **数据** — 特征工程、CEX/DEX provider、PMS
- **区块链** — 智能合约、签名验证、TLS Notary 等
- **部署 / 运维** — GitLab CI、Nacos、Aliyun 全家桶

## 本 handbook 的三层结构

```text
trex-tech-handbook/
├── common/        ⭐ 跨前后端通用规范（你正在看的这一层）
├── backend/       Java 后端规范
└── frontend/      占位，下一阶段开启
```

## K8s 环境 ↔ 长期分支【强制】

t-rex 后端跑在 **阿里云 K8s** 上，三套环境，对应三个长期分支：

| K8s 环境 | 长期分支 | 用途 |
|---|---|---|
| **dev** | `dev` | 开发联调 |
| **beta** | `beta` | 测试人员部署 + QA 测试 |
| **prod** | `master` | 真实用户使用 |

**长期分支不直接 push**，所有变更经过短期分支 + MR 流程进入。

## 端到端开发流程速览

完整 pipeline 从研发本地到 prod 部署：

```text
┌─[研发]──────────────────────────────────────────────────────────────────┐
│                                                                         │
│  本地 worktree                远端                          环境         │
│  ─────────────                ────                          ────         │
│                                                                         │
│  {your_workspace}/.worktrees/                                           │
│   └── dev_260513_xxx  ── push ──►  dev_260513_xxx                       │
│             │  日常开发                  │                              │
│             │                            ▼                              │
│             │                       k8s dev env (auto deploy)           │
│             │                                                           │
│             │  研发助手建 MR (提测)                                     │
│             ▼                                                           │
│         ┌─ MR ─►  review_260513_xxx                                     │
│         │                                                               │
│         │  team lead 审核                                               │
│         │                                                               │
│         └─ merge = 提测完成 ►  review_260513_xxx 含审核通过快照         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │  (QA 整合多个同版本 review_*)
                                  ▼
┌─[测试人员]──────────────────────────────────────────────────────────────┐
│                                                                         │
│  review_260513_xxxA  ──MR──►                                            │
│  review_260513_xxxB  ──MR──►   beta_260513_<keyword>                    │
│  review_260513_xxxC  ──MR──►   (keyword 由 QA 取，如 "campaign")        │
│                                       │                                 │
│                            QA 自行 merge 多个 MR                        │
│                                       │                                 │
│                                       ▼                                 │
│                                  统一 beta_<date>_<keyword>             │
│                                       │                                 │
│                                       ▼                                 │
│                                  k8s beta env (auto deploy)             │
│                                       │                                 │
│                                  QA 测试 + sign-off                     │
│                                       │                                 │
│                            QA 提交发布申请                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─[发布 CI 自动]──────────────────────────────────────────────────────────┐
│                                                                         │
│  自动建 MR:  beta_260513_<keyword>  ──►  master                         │
│                                                                         │
│  研发负责人 最终审核                                                    │
│                                                                         │
└─────────────────┬───────────────────────────────────────────────────────┘
                  │
                  ▼
┌─[运维]──────────────────────────────────────────────────────────────────┐
│   master merge 触发 prod 发布流程   ────►   k8s prod env                │
└─────────────────────────────────────────────────────────────────────────┘
```

**两个核心 MR 节点**：

1. **提测 MR**：`dev_<date>_<name>` → `review_<date>_<name>` —— team lead 审核，研发助手负责建 MR（见 `common/03`）
2. **发布 MR**：`beta_<date>_<keyword>` → `master` —— 发布 CI 自动建，**研发负责人**审核（见 `common/04`）

中间 QA 整合（多个 `review_*` → 1 个 `beta_<date>_<keyword>`）见 `common/07`。

**分支生命周期**：

| 分支 | 性质 | 部署目标 | 何时清理 |
|---|---|---|---|
| `dev_<date>_<name>` | 个人工作分支 | k8s dev env (auto) | 提测 MR merge 后可清；个人可保留 |
| `review_<date>_<name>` | 审核通过快照 | 无 | beta 整合完成后可清 |
| `beta_<date>_<keyword>` | QA 版本候选 | k8s beta env (auto) | 发布 MR merge 后清 |
| `dev` | k8s dev env 长期基线 | k8s dev env (baseline) | 不删；只允许 review_* MR 进入（流程 TBD） |
| `beta` | k8s beta env 长期基线 | k8s beta env (baseline) | 不删 |
| `master` | k8s prod env (= 主分支) | k8s prod env | 不删；只允许从 beta_<date>_<keyword> MR 进入 |

**章节索引**：
- 分支命名 / commit msg / Push Rule / git worktree：`common/02`
- 提测 SOP（`dev_*` → `review_*` 的 MR）：`common/03`
- 发布 SOP（`beta_*` → `master` 的 MR + CI auto）：`common/04`
- Linear issue 与上面流程的串联：`common/05`
- **研发过程端到端 SOP + Code review 自检 checklist：`common/06`**
- **测试过程 SOP（含 QA 整合 review_* → beta_*）：`common/07`**

## 何时读哪一层

| 你在做什么 | 先读 |
|---|---|
| 开发任何 t-rex 子项目 | `common/` 全套（强制规范） |
| 开发后端 Java 服务 | `common/` + `backend/` |
| 开发前端 | `common/` + `frontend/`（规范待补） |
| 想看整体流程 | 本章上面的"端到端开发流程速览" |
| 拿到新任务，从 0 到提测 | `common/06-development-flow.md` ⭐ |
| 紧急上线 / 发布 (beta→master) | `common/04-ci-and-release.md` |
| 日常提测 (dev_*→review_*) | `common/02` + `common/03` |
| QA 整合 (review_*→beta_*) + 测试 / sign-off | `common/07-testing-process.md` |
| 新建服务 | `backend/appendix/templates/new-service-checklist.md` |

## 状态

M1（首发）：框架骨架 + 已知现状占位 + `TODO(@allen)` 待补条目。

`〔t-rex 现状〕`：本 handbook 不覆盖 `superteam` 子项目；它有独立的 `CLAUDE.md` + 一套不同的约定（Python + skills 架构）。
