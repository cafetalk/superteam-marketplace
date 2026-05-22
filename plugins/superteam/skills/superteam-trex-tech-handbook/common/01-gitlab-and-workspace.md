# GitLab 组织与本地工作区

## GitLab 组织结构【强制】

```text
gitlab.com/
└── Keccak256-evg/                  # 根 group
    ├── t-rex/                      # 业务 group
    │   ├── backend-java/           # ⭐ Java 后端微服务 sub-group  (6 项)
    │   │   ├── trex-core
    │   │   ├── trex-passport
    │   │   ├── trex-web
    │   │   ├── trex-endpoint
    │   │   ├── trex-event
    │   │   └── trex-admin
    │   │
    │   ├── backend-python/         # ⭐ Python 后端微服务 sub-group  (3 项)
    │   │   ├── trex-hexagonal
    │   │   ├── trex-persona-feast
    │   │   └── trex-prism-engine
    │   │
    │   ├── anchor/                 # ⭐ anchor 子领域 sub-group  (13 项 / 混栈)
    │   │   ├── anchor-core         # Java
    │   │   ├── anchor-endpoint     # Java
    │   │   ├── anchor-event        # Java
    │   │   ├── anchor-insight-nft  # Java + contract
    │   │   ├── anchor-insight-thirdpart  # Java
    │   │   ├── anchor-insight-token      # Java + adapter
    │   │   ├── anchor-insight-zktls      # Node / TS / zkTLS
    │   │   ├── anchor-team         # Java
    │   │   ├── anchor-web          # Java (Gateway)
    │   │   ├── anchor-admin        # Node / TS
    │   │   ├── anchor-dashboard    # Node / TS
    │   │   ├── anchor-sdk          # Node / TS
    │   │   └── anchor-labs         # Foundry / Solidity
    │   │
    │   ├── agentic/                # ⭐ Agent 系统 / AI 工具 sub-group  (5 项；2026-05-19 由 `skills/` rename)
    │   │   ├── superteam           # Claude Code skill bundle (含本 handbook 自身)
    │   │   ├── superteam-web       # Web frontend
    │   │   ├── superteam-mcp-server # MCP backend
    │   │   ├── code-audit          # AI agent (代码审查)
    │   │   └── report-hub          # AI 报告聚合
    │   │
    │   ├── quest/                  # ⭐ quests 产品线 sub-group  (8 项 / 全 Java; 2026-05-21 新建)
    │   │   ├── kcustomer           # Dubbo 领域服务: 用户 / 客户
    │   │   ├── kmember             # Dubbo 领域服务: 会员
    │   │   ├── kactivity           # Dubbo 领域服务: 活动
    │   │   ├── kevent              # Dubbo 领域服务: event collector & dispatcher
    │   │   ├── quests-web          # HTTP 对外 + Telegram/Dingtalk webhook (BFF)
    │   │   ├── quests-gateway      # S2S 内部接口 (gateway-module-* with S2Api delegates)
    │   │   ├── manage-java         # 后台管理 (ELADmin 二次开发)
    │   │   └── manage-web          # 后台前端
    │   │
    │   └── scaffold/               # ⭐ 基础设施 / lib / 工程脚手架 (6 项)
    │       ├── trex-framework      # parent POM + runtime starters（取代历史 gwave-dev/kiki-framework）
    │       ├── trex-scaffold       # 新建工程脚手架（取代历史 gwave-dev/evg-scaffold）
    │       ├── knotify             # 通知 lib（计划下沉到 trex-widget）
    │       ├── kseq                # 序列 lib（计划下沉到 trex-widget）
    │       ├── kurl                # URL 工具 lib（计划下沉到 trex-widget）
    │       └── dtm                 # 分布式事务管理器 (9 模块, 含 kiki-dtm-spring-boot-starter)
    │
    └── ops/
        └── gitlab-cis              # 集中托管的 CI 规则（见 common/04-ci-and-release.md）
```

### 子组归属规约【强制】

| 项目类型 | sub-group | 示例 |
|---|---|---|
| **新 Java 后端微服务** | `t-rex/backend-java/` | `trex-core`, `trex-passport` |
| **新 Python 后端微服务** | `t-rex/backend-python/` | `trex-hexagonal`, `trex-persona-feast` |
| **anchor 子领域项目（任何栈）** | `t-rex/anchor/` | `anchor-*`（含 Java / Node / Foundry） |
| **Agent 系统 / AI 工具** | `t-rex/agentic/` | `superteam`, `superteam-web`, `superteam-mcp-server`, `code-audit`, `report-hub` |
| **quests 产品线（任何栈）** | `t-rex/quest/` | `kcustomer`, `kmember`, `kactivity`, `kevent`, `quests-web`, `quests-gateway`, `manage-java`, `manage-web` |
| **基础设施 / lib / 工程脚手架** | `t-rex/scaffold/` | `trex-framework`, `trex-scaffold`, `knotify`, `kseq`, `kurl`, `dtm` |

详细服务清单见 `backend/01-microservices.md`。

`〔t-rex 现状〕`：
- **30 个后端项目** + 6 个基础设施 + 5 个 agentic 项目 分布在上述 6 个 sub-group（持续扩张中）
- **scaffold/ sub-group 2026-05-19 新建**，把基础设施 / lib 工程从 `gwave-dev/` fork 过来或 transfer（详见 `docs/ops/2026-05-13-subgroup-migration.md`）
- **`skills/` sub-group 2026-05-19 rename 为 `agentic/`** —— 反映实际内容是 agent 系统（MCP server / Claude skills / AI agents），不只是 Claude Code 意义上的 skill bundle。原 `skills/*` URL GitLab redirect 短期仍可用，但推荐用新 path
- **`quest/` sub-group 2026-05-21 新建** —— 承载 quests 产品线（任务-资产关系系统）的 8 个 Java 项目；其中 quests-web / quests-gateway 继承的 **`kweb` parent POM** 仍位于 `gwave-dev/kweb`（不迁，作为跨团队共享底座；详见 `backend/02-architecture.md` §kweb）
- GitLab **display name** 与 **URL path** 已全部对齐（2026-05-14 完成，TREX-449）

## 本地工作区目录建议【推荐】

**目录结构对齐 GitLab sub-group**，便于：
- 工具按路径反推仓库归属
- 跨仓 grep / IDE 索引
- 与同事沟通时路径唯一

```text
{your_workspace}/                   # 例：~/work
├── backend-java/                   # 镜像 gitlab.com/Keccak256-evg/t-rex/backend-java/
│   ├── trex-core/
│   ├── trex-passport/
│   ├── trex-web/
│   ├── trex-endpoint/
│   ├── trex-event/
│   └── trex-admin/
│
├── backend-python/                 # 镜像 t-rex/backend-python/
│   ├── trex-hexagonal/
│   ├── trex-persona-feast/
│   └── trex-prism-engine/
│
├── anchor/                         # 镜像 t-rex/anchor/
│   ├── anchor-core/
│   ├── anchor-web/
│   └── ... (13 项)
│
├── agentic/                        # 镜像 t-rex/agentic/ — agent 系统 / AI 工具
│   ├── superteam/
│   ├── superteam-web/
│   ├── superteam-mcp-server/
│   ├── code-audit/
│   └── report-hub/
│
├── quest/                          # 镜像 t-rex/quest/ — quests 产品线
│   ├── kcustomer/
│   ├── kmember/
│   ├── kactivity/
│   ├── kevent/
│   ├── quests-web/
│   ├── quests-gateway/
│   ├── manage-java/
│   └── manage-web/
│
└── scaffold/                       # 镜像 t-rex/scaffold/ — 基础设施 / lib
    ├── trex-framework/
    ├── trex-scaffold/
    ├── knotify/
    ├── kseq/
    ├── kurl/
    └── dtm/
```

**clone 用 GitLab URL path**（2026-05-14 起 backend-java 8 个仓的 URL path 已 rename 到 `trex-*`，与 display name 对齐 —— 历史 `drex-*` URL 由 GitLab redirect 短期仍可用，但推荐用新 path）：

```bash
cd {your_workspace}/backend-java
git clone git@gitlab.com:Keccak256-evg/t-rex/backend-java/trex-core.git
```

`〔t-rex 现状〕`：历史仓库可能仍位于 sub-group 之外或 `gwave-dev` 之下，迁移按需推进，不强制立即归位。

## 维护

- 本章约束 = GitLab admin 配置 + 团队共识
- 变更需同步更新 `backend/01-microservices.md` 中的仓库链接
- 新增 sub-group 需要同步更新本章 + microservices 清单
