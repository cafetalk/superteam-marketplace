# GitLab 组织与本地工作区

## GitLab 组织结构【强制】

```text
gitlab.com/
└── Keccak256-evg/                  # 根 group
    ├── t-rex/                      # 业务 group
    │   ├── backend-java/           # ⭐ Java 后端微服务 sub-group  (6 项)
    │   │   ├── trex-core           (URL: drex-core)
    │   │   ├── trex-passport       (URL: drex-passport)
    │   │   ├── trex-web
    │   │   ├── trex-endpoint       (URL: drex-endpoint)
    │   │   ├── trex-event          (URL: drex-event)
    │   │   └── trex-admin
    │   │
    │   ├── backend-python/         # ⭐ Python 后端微服务 sub-group  (3 项)
    │   │   ├── trex-hexagonal      (URL: hexagonal)
    │   │   ├── trex-persona-feast  (URL: persona-feast)
    │   │   └── trex-prism-engine   (URL: yield-engine)
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
    │   └── skills/                 # AI / 工具 skill sub-group（含本 handbook 自身）
    │       ├── superteam
    │       └── superteam-mcp-server
    │
    ├── gwave-dev/                  # 内部脚手架 / 基础设施
    │   └── evg-scaffold            # 见 backend/02-architecture.md
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
| **历史 / 跨域基础设施** | `gwave-dev/` | `evg-scaffold` |

详细服务清单见 `backend/01-microservices.md`。

`〔t-rex 现状〕`：
- **22 个后端项目**已 100% 归位到上述 sub-group（2026-05-13 迁移完毕）
- GitLab **display name** 已统一到 `trex-*` / `anchor-*` 前缀，但**仓库 URL path** 仍保留原始名字（如 `trex-core` 的 URL path 是 `drex-core`）—— 是否启动 path rename 见 `backend/01-microservices.md` TODO

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
└── skills/                         # 镜像 t-rex/skills/
    ├── superteam/
    └── superteam-mcp-server/
```

**clone 时建议用 GitLab URL path（display name 可能 rename 后与 path 不一致）**：

```bash
cd {your_workspace}/backend-java
git clone git@gitlab.com:Keccak256-evg/t-rex/backend-java/drex-core.git trex-core
# 注意：URL path 是 drex-core，但本地目录用 display name trex-core 更直观
```

`〔t-rex 现状〕`：历史仓库可能仍位于 sub-group 之外或 `gwave-dev` 之下，迁移按需推进，不强制立即归位。

## 维护

- 本章约束 = GitLab admin 配置 + 团队共识
- 变更需同步更新 `backend/01-microservices.md` 中的仓库链接
- 新增 sub-group 需要同步更新本章 + microservices 清单
