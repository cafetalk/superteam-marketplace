# 后端微服务清单 ⭐

t-rex 后端 GitLab 共 **22 个项目**，分 3 个 sub-group：

| Sub-group | 数量 | 路径 |
|---|---|---|
| **`backend-java/`** | 6 | https://gitlab.com/Keccak256-evg/t-rex/backend-java |
| **`backend-python/`** | 3 | https://gitlab.com/Keccak256-evg/t-rex/backend-python |
| **`anchor/`** | 13 | https://gitlab.com/Keccak256-evg/t-rex/anchor |

`〔t-rex 现状〕`：本 handbook 当前的 `backend/` 章主体（02–10）针对 **Java 后端**（kiki-framework 体系）。Python 后端规约 + anchor 子领域规约**待补**（M3+），先把清单列全。

## 命名约定观察

22 个项目里，GitLab **display name 已全部 rename 到 `trex-*` / `anchor-*` 前缀**，但 **URL path（仓库路径）保留了原始名字**（部分仍是 `drex-*` / `hexagonal` 等）。点击下面 URL 才是真实仓地址。

TODO(@allen)：是否启动一次 GitLab path rename，把 path 与 display name 对齐（避免 SSH clone URL 与 display 不一致引起混淆）。

## 服务条目模板

```text
### <service-name>
- **业务范围**：一句话
- **技术形态**：Dubbo 领域服务 / Gateway / 工具 / 智能合约 / ...
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/<sub-group>/<path>
- **本地路径建议**：{your_workspace}/<sub-group>/<repo>
- **stack**：Java / Python / Node / Foundry / 混栈
- **多模块结构**：[列出 module]
- **上游 / 下游**：调用方 / 被调
- **负责人**：@<lead>
- **最近更新**：YYYY-MM-DD
```

---

## A. `backend-java/` — Java 微服务（kiki-framework 体系）

### trex-core
- **业务范围**：广告主 / Campaign / Onboarding 等核心领域服务（含 GraphQL 查询层）
- **技术形态**：**Dubbo 领域服务**（按技术分层）
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-java/drex-core
- **本地路径建议**：`{your_workspace}/backend-java/trex-core/`
- **stack**：Java 17 / Spring Boot / Dubbo / MyBatis-Plus / OTS / PostgreSQL / GraphQL（`spring-boot-starter-graphql` + `graphql-java-extended-scalars 22.0`）
- **多模块结构**：`core-api / core-dal / core-graphql / core-model / core-service / core-web`
- **上游**：trex-web（BFF）；其他领域服务的 Dubbo client
- **下游**：trex-passport；OTS（主）；PostgreSQL（辅）；Redis；Nacos
- **负责人**：TODO(@allen)
- **最近更新**：2026-05-13

### trex-passport
- **业务范围**：用户身份 / 社交平台集成 / 登录 / 签名验证 / Session
- **技术形态**：**Dubbo 领域服务**
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-java/drex-passport
- **本地路径建议**：`{your_workspace}/backend-java/trex-passport/`
- **stack**：Java 17 / Spring Boot / kiki-framework / MyBatis-Plus
- **多模块结构**：`customer-api / customer-dal / customer-model / customer-service / customer-web`（注意：模块名 `customer-*` 而非 `passport-*`）
- **上游**：trex-web；其他需鉴权 / 用户信息的领域服务
- **下游**：TODO(@allen)
- **负责人**：TODO(@allen)
- **最近更新**：2026-05-13
- `〔note〕` `trex-passport`（Java backend）与历史 Rust/Foundry `trex-passport`、`anchor-labs`、`anchor-insight-zktls` 容易混淆 —— 当前 `backend-java/drex-passport` 是 Java 版本

### trex-web
- **业务范围**：对外 API / BFF —— 聚合下游 Dubbo 领域服务，给前端 / 项目方 Portal 用
- **技术形态**：**Gateway**（按业务领域分模块）
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-java/trex-web
- **本地路径建议**：`{your_workspace}/backend-java/trex-web/`
- **stack**：Java 17 / Spring Boot / kiki-framework / OpenAPI 2.0.2 / Aliyun OSS SDK 3.18.1
- **多模块结构**：`drex-module-activity / drex-module-common / drex-module-core / drex-module-customer / drex-web-start`（注意：M1 时见到的 `drex-module-growth` 在最新 master 已不在，可能合并 / 重命名）
- **上游**：前端 / 项目方 Portal（HTTP REST）
- **下游**：trex-core, trex-passport, trex-endpoint, trex-event 等 Dubbo 服务；Nacos；Zipkin
- **负责人**：TODO(@allen)
- **最近更新**：2026-05-13

### trex-endpoint
- **业务范围**：TODO(@allen) —— GitLab description 为空；从模块名推测是某种"端点 / 接入"服务
- **技术形态**：**Dubbo 领域服务**（按技术分层）
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-java/drex-endpoint
- **本地路径建议**：`{your_workspace}/backend-java/trex-endpoint/`
- **stack**：Java 17 / Spring Boot / kiki-framework
- **多模块结构**：`drex-endpoint-api / drex-endpoint-dal / drex-endpoint-service / drex-endpoint-web`
- **上游 / 下游**：TODO(@allen)
- **负责人**：TODO(@allen)
- **最近更新**：2026-05-13

### trex-event
- **业务范围**：TODO(@allen) —— 推测是事件 / 消息总线类服务
- **技术形态**：TODO（master 当前空，内容应在 worktree / 分支中）
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-java/drex-event
- **本地路径建议**：`{your_workspace}/backend-java/trex-event/`
- **stack**：Java（推测）
- **多模块结构**：TODO（master 暂无 pom.xml）
- **负责人**：TODO(@allen)
- **最近更新**：2026-05-13

### trex-admin
- **业务范围**：运营 / admin 面板 BFF
- **技术形态**：GraphQL BFF（M1 时观察到 pom.xml 嵌在 `.worktrees/reborn/`，疑似在重构）
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-java/trex-admin
- **本地路径建议**：`{your_workspace}/backend-java/trex-admin/`
- **stack**：Java + GraphQL（推测）
- **多模块结构**：TODO（master 当前空）
- **负责人**：TODO(@allen)
- **最近更新**：2026-05-12

---

## B. `backend-python/` — Python 微服务

### trex-hexagonal
- **业务范围**：AI agent 平台 —— 统一 API / RAG / 特征存储 / 异步任务编排（生产级）
- **技术形态**：Python FastAPI service + Celery worker + 多组件
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-python/hexagonal
- **本地路径建议**：`{your_workspace}/backend-python/trex-hexagonal/`
- **stack**：Python 3.11 / FastAPI / LangGraph / Celery / Feast / PostgreSQL / Redis / Docker Compose
- **多模块结构**：TODO（master 当前空 —— 本地 clone 有完整内容，可能在 dev 分支）
- **上游 / 下游**：TODO(@allen)
- **负责人**：TODO(@allen)
- **最近更新**：2026-05-13

### trex-persona-feast
- **业务范围**：persona 特征工程 + 特征存储（Feast）
- **技术形态**：Python multi-module
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-python/persona-feast
- **本地路径建议**：`{your_workspace}/backend-python/trex-persona-feast/`
- **stack**：Python / Feast / requirements.txt
- **多模块结构**：`feature_repo / persona-web / technical_design`
- **上游 / 下游**：TODO(@allen)
- **负责人**：TODO(@allen)
- **最近更新**：2026-05-13

### trex-prism-engine
- **业务范围**：TODO(@allen) —— 推测是收益 / yield 计算引擎（URL path 是 `yield-engine`）
- **技术形态**：Python service + web
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-python/yield-engine
- **本地路径建议**：`{your_workspace}/backend-python/trex-prism-engine/`
- **stack**：Python / requirements.txt
- **多模块结构**：`service / web`
- **上游 / 下游**：TODO(@allen)
- **负责人**：TODO(@allen)
- **最近更新**：2026-05-13

`〔Python 后端规约缺失〕` 本 handbook 当前 `backend/` 章主体面向 Java；Python 后端的脚手架、依赖管理、测试、日志、可观测性规约**待补 M3+**。建议立项 `backend-python/` 一级目录或独立 sub-handbook。

---

## C. `anchor/` — anchor 子领域（13 项 混栈）

`〔t-rex 现状〕`：**anchor 是 t-rex 的子领域**（具体业务定位 TODO(@allen)：链上洞察 / 第三方数据接入 / Token NFT 分析？）；自成 13 个仓的独立产品线，含 Java 后端、Node/TS、Foundry 智能合约多栈。

### C.1 anchor Java 后端（8 项）

| 项目 | URL path | 模块结构 | 业务范围（推测） | 最近 |
|---|---|---|---|---|
| **anchor-core** | `anchor/anchor-core` | `anchor-core-api/common/contract/dal/graphql/server` | 核心领域；**含 `-contract` 模块**（智能合约交互） | 2026-04-13 |
| **anchor-endpoint** | `anchor/anchor-endpoint` | `anchor-endpoint-api/common/dal/server` | 端点接入（**容器已停用，能力迁移至 `trex-endpoint`**） | 2026-03-18 |
| **anchor-event** | `anchor/anchor-event` | `anchor-event-server`（单模块） | 事件总线（**容器已停用，能力迁移至 `trex-event`**） | 2026-03-18 |
| **anchor-insight-nft** | `anchor/anchor-insight-nft` | `anchor-insight-nft-api/common/contract/dal/server` | NFT 洞察；**含 `-contract` 模块** | 2026-04-07 |
| **anchor-insight-thirdpart** | `anchor/anchor-insight-thirdpart` | `anchor-insight-thirdpart-api/common/dal/server` | 第三方数据洞察 | 2026-04-07 |
| **anchor-insight-token** | `anchor/anchor-insight-token` | `anchor-insight-token-adapter/api/common/dal/server` | Token 洞察；**含 `-adapter` 模块** | 2026-04-07 |
| **anchor-team** | `anchor/anchor-team` | `anchor-team-api/dal/model/server/web` | 团队 / 用户域 | 2026-04-13 |
| **anchor-web** | `anchor/anchor-web` | `anchor-web-api/common/service`（含 Dockerfile + monitoring） | Gateway / BFF | 2026-05-11 |

TODO(@allen)：每个项目业务范围 / 上下游 / 负责人补全。
TODO(@allen)：`anchor-endpoint`、`anchor-event` 已停用并迁移到 `trex-endpoint`、`trex-event`，后续确认仓库归档策略（保留只读 / 标记 archived / 文档跳转说明）。

### C.2 anchor 前端 / Node 工具（3 项）

| 项目 | URL path | stack | 推测 | 最近 |
|---|---|---|---|---|
| **anchor-admin** | `anchor/anchor-admin` | Node.js + TypeScript（`package.json` + Dockerfile） | 运营 admin 前端 / SPA | 2026-03-12 |
| **anchor-dashboard** | `anchor/anchor-dashboard` | Node.js + TypeScript | 用户 dashboard 前端 / SPA | 2026-03-12 |
| **anchor-sdk** | `anchor/anchor-sdk` | Node.js + TypeScript（含 `examples/` 目录） | SDK / 客户端工具 | 2026-05-11 |

TODO(@allen)：本 handbook `frontend/` 占位是否扩到这 3 个项目？或 anchor 子领域有独立前端规约？

### C.3 anchor 区块链 / 加密（2 项）

| 项目 | URL path | stack | 推测 | 最近 |
|---|---|---|---|---|
| **anchor-labs** | `anchor/anchor-labs` | Foundry / Solidity（`deployments/lib/scripts/src/test`） | 智能合约 lab / 部署 | 2026-05-12 |
| **anchor-insight-zktls** | `anchor/anchor-insight-zktls` | Node.js + TypeScript（含 `mpc / proxy / migrations`） | zkTLS 数据洞察 / 隐私计算 | 2026-05-12 |

TODO(@allen)：智能合约 + zkTLS 类项目在本 handbook 是否独立成章（区块链规约 / 隐私计算规约）？

---

## 全局视图

```text
                        t-rex 后端生态 (22 项)
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   backend-java/        backend-python/         anchor/
    (Java 6)            (Python 3)           (13 项 混栈)
        │                     │                     │
   trex-core           trex-hexagonal          ┌────┴────┐
   trex-passport       trex-persona-feast      │         │
   trex-web            trex-prism-engine     Java     非 Java
   trex-endpoint                              (8 项)   (5 项)
   trex-event                                          │
   trex-admin                                  ┌──────┴──────┐
                                              Node          Foundry
                                              (3 项)        (2 项)
```

## 服务关系图（粗略）

TODO(@allen)：补一张完整上下游关系图（mermaid / ASCII）。当前已知：

- **trex-web** = Gateway，调用 → trex-core / trex-passport / trex-endpoint / trex-event 等 Dubbo 服务
- **trex-core** 主存储 OTS + PG + Redis
- **anchor 子域** 内部应有自己的 Gateway（`anchor-web`）+ 多个领域服务（`anchor-*-server`）+ 智能合约层（`-contract` 模块 / `anchor-labs`）
- **已确认迁移**：`anchor-endpoint` → `trex-endpoint`，`anchor-event` → `trex-event`（anchor 对应容器停用）
- **trex 主域 与 anchor 子域** 之间的接口 / 数据流向 TODO(@allen)

## 新增服务

新建后端服务流程见 `backend/appendix/templates/new-service-checklist.md`，并**回到本章追加条目**。

注意 sub-group 归属：
- Java 后端 → `backend-java/`
- Python 后端 → `backend-python/`
- anchor 相关 → `anchor/`（无论栈类型）

## TODO(@allen) 汇总

- [ ] 22 个项目业务范围 + 上下游 + 负责人逐一补全
- [ ] `trex-admin / trex-event / trex-hexagonal` 的 master 为空 —— 默认分支调整 / 内容补齐 / 或确认在 dev 分支开发
- [ ] **GitLab path rename**：display name 已 `trex-*` / `anchor-*` 但 URL path 仍是 `drex-*` / 等历史名 —— 是否启动批量 rename
- [ ] **anchor 子领域定位**：业务范围 / 与 t-rex 主域边界 / 数据流向
- [ ] Python 后端规约章（M3+ 立项）
- [ ] 智能合约 / zkTLS / SDK 类项目是否独立规约
- [ ] 完整上下游关系图（mermaid）

## 维护

- 新增 / 重命名 / 迁移项目需同步更新本章 + GitLab description
- 服务条目变更（业务范围 / 主理人 / 仓库迁移）需同步本章
- sub-group 调整需同步更新 `common/01-gitlab-and-workspace.md`
