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
    │   ├── skills/                 # AI / 工具 skill sub-group（含本 handbook 自身）
    │   │   ├── superteam
    │   │   └── superteam-mcp-server
    │   │
    │   └── scaffold/               # ⭐ 基础设施 / lib / 工程脚手架 (4 项)
    │       ├── trex-framework      # parent POM + runtime starters（取代历史 gwave-dev/kiki-framework）
    │       ├── trex-scaffold       # 新建工程脚手架（取代历史 gwave-dev/evg-scaffold）
    │       ├── knotify             # 通知 lib（计划下沉到 trex-widget）
    │       └── kseq                # 序列 lib（计划下沉到 trex-widget）
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
| **AI / 工具 skill** | `t-rex/skills/` | `superteam` |
| **基础设施 / lib / 工程脚手架** | `t-rex/scaffold/` | `trex-framework`, `trex-scaffold`, `knotify`, `kseq` |

详细服务清单见 `backend/01-microservices.md`。

`〔t-rex 现状〕`：
- **22 个后端项目**已 100% 归位到上述 sub-group（2026-05-13 迁移完毕）
- **scaffold/ sub-group 2026-05-19 新建**，把基础设施 / lib 工程从 `gwave-dev/` fork 过来或 transfer（详见 `docs/ops/2026-05-13-subgroup-migration.md`）
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
├── skills/                         # 镜像 t-rex/skills/
│   ├── superteam/
│   └── superteam-mcp-server/
│
└── scaffold/                       # 镜像 t-rex/scaffold/ — 基础设施 / lib
    ├── trex-framework/
    ├── trex-scaffold/
    ├── knotify/
    └── kseq/
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
