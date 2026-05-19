# 后端微服务清单 ⭐

t-rex 后端 GitLab 共 **22 个微服务 + 4 个基础设施**，分 4 个 sub-group：

| Sub-group | 数量 | 类型 | 路径 |
|---|---|---|---|
| **`backend-java/`** | 6 | 微服务 | https://gitlab.com/Keccak256-evg/t-rex/backend-java |
| **`backend-python/`** | 3 | 微服务 | https://gitlab.com/Keccak256-evg/t-rex/backend-python |
| **`anchor/`** | 13 | 微服务（混栈）| https://gitlab.com/Keccak256-evg/t-rex/anchor |
| **`scaffold/`** | 4 | 基础设施 / lib | https://gitlab.com/Keccak256-evg/t-rex/scaffold |

`〔t-rex 现状〕`：本 handbook 当前的 `backend/` 章主体（02–10）针对 **Java 后端**（trex-framework 体系）。Python 后端规约 + anchor 子领域规约**待补**（M3+），先把清单列全。

## 命名约定观察

display name 已统一到 `trex-*` / `anchor-*` 前缀。2026-05-14（TREX-449）把后端 **8 个 URL path 也全部 rename 对齐到 display name**（详见 [`docs/ops/2026-05-14-path-rename-log.md`](../../docs/ops/2026-05-14-path-rename-log.md)）。

**仍未对齐的**：
- `trex-tls/` 下 3 个 path/display 不一致项 —— display 本身可疑，等 owner review 后单独处理

存量旧 path 通过 GitLab redirect 短期仍可 fetch，但 CI / 本地 clones / 文档应该用新 path。

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
- **最近更新**：YYYY-MM-DD
```

`〔t-rex 现状〕` **不收录 owner / 负责人字段** —— AI 编码时代，AI agent 读完整 handbook + 代码即可 onboard，代码所有权的人工权重下降。具体业务问题走 Linear / 群求助，不依赖文档"找人"。

---

## A. `backend-java/` — Java 微服务（trex-framework 体系）

### trex-core
- **业务范围**：广告主 / Campaign / Onboarding 等核心领域服务（含 GraphQL 查询层）
- **技术形态**：**Dubbo 领域服务**（按技术分层）
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-java/trex-core
- **本地路径建议**：`{your_workspace}/backend-java/trex-core/`
- **stack**：Java 17 / Spring Boot / Dubbo / MyBatis-Plus / OTS / PostgreSQL / GraphQL（`spring-boot-starter-graphql` + `graphql-java-extended-scalars 22.0`）
- **多模块结构**：`core-api / core-dal / core-graphql / core-model / core-service / core-web`
- **上游**：trex-web（BFF）；其他领域服务的 Dubbo client
- **下游**：trex-passport；OTS（主）；PostgreSQL（辅）；Redis；Nacos
- **最近更新**：2026-05-13

### trex-passport
- **业务范围**：用户身份 / 社交平台集成 / 登录 / 签名验证 / Session
- **技术形态**：**Dubbo 领域服务**
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-java/trex-passport
- **本地路径建议**：`{your_workspace}/backend-java/trex-passport/`
- **stack**：Java 17 / Spring Boot / trex-framework / MyBatis-Plus
- **多模块结构**：`drex-passport-api / drex-passport-dal / drex-passport-model / drex-passport-service / drex-passport-web`（**模块名仍 `drex-passport-*`**；2026-05-14 GitLab path rename 到 `trex-passport` 时未跟改模块名 —— 2026-05-19 audit 校准。POM 内部还引用了历史 `kcustomer-api` 模块作为依赖）
- **上游**：trex-web；其他需鉴权 / 用户信息的领域服务
- **下游**：OTS / PostgreSQL / Redis / Nacos（与 trex-core 同套基础设施）
- **最近更新**：2026-05-13
- `〔note〕` `trex-passport`（Java backend）与历史 Rust/Foundry `trex-passport`、`anchor-labs`、`anchor-insight-zktls` 容易混淆 —— 当前 `backend-java/trex-passport` 是 Java 版本（path 已在 2026-05-14 由 `drex-passport` rename 到 `trex-passport`，见 `docs/ops/2026-05-14-path-rename-log.md`）

### trex-web
- **业务范围**：对外 API / BFF —— 聚合下游 Dubbo 领域服务，给前端 / 项目方 Portal 用
- **技术形态**：**Gateway**（按业务领域分模块）
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-java/trex-web
- **本地路径建议**：`{your_workspace}/backend-java/trex-web/`
- **stack**：Java 17 / Spring Boot / trex-framework / OpenAPI 2.0.2 / Aliyun OSS SDK 3.18.1
- **多模块结构**：`drex-module-activity / drex-module-common / drex-module-core / drex-module-customer / drex-module-onboarding / drex-web-start`（2026-05-19 audit 校准；M1 时见过的 `drex-module-growth` 在 master 已不在，可能合并 / 重命名）
- **上游**：前端 / 项目方 Portal（HTTP REST）
- **下游**：trex-core, trex-passport, trex-endpoint, trex-event 等 Dubbo 服务；Nacos；Zipkin
- **最近更新**：2026-05-13

### trex-endpoint
- **业务范围**：`〔t-rex 现状〕`GitLab description 为空；从模块名（`drex-endpoint-*`）推测为对外端点 / 接入服务（已接管 `anchor-endpoint` 的能力）—— 待 owner 在 GitLab description 补充权威定义
- **技术形态**：**Dubbo 领域服务**（按技术分层）
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-java/trex-endpoint
- **本地路径建议**：`{your_workspace}/backend-java/trex-endpoint/`
- **stack**：Java 17 / Spring Boot / trex-framework
- **多模块结构**：`drex-endpoint-api / drex-endpoint-dal / drex-endpoint-service / drex-endpoint-web`
- **最近更新**：2026-05-13

### trex-event
- **业务范围**：事件 / 消息总线服务（含 anchor-event 能力迁移过来）
- **技术形态**：**Dubbo 领域服务**
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-java/trex-event
- **本地路径建议**：`{your_workspace}/backend-java/trex-event/`
- **stack**：Java / Spring Boot / trex-framework
- **多模块结构**：`drex-event-server`（单模块；master 有完整 pom.xml + 代码）
- **最近更新**：2026-05-15

### trex-admin
- **业务范围**：运营 / admin 面板 BFF
- **技术形态**：GraphQL BFF
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-java/trex-admin
- **本地路径建议**：`{your_workspace}/backend-java/trex-admin/`
- **stack**：Java / Spring Boot / GraphQL / trex-framework
- **多模块结构**：`trex-admin-common / trex-admin-dal / trex-admin-graphql / trex-admin-security / trex-admin-start`
- **最近更新**：2026-05-15（重构 reborn 已合主干，master 已 populated 含 5 模块 + `technical_design/`）
- `〔reborn 期内未完成项〕`（2026-05-19 audit 发现）：
  - **`kiki-observability-tracing-spring-boot-starter` 未接入** —— 其他 backend-java 仓全部接入，trex-admin 是唯一例外
  - **`ops/gitlab-cis/gwave-dev/` 内无对应 CI yaml** —— 其他 5 个 backend 服务都有 `drex-*.yaml`

---

## B. `backend-python/` — Python 微服务

### trex-hexagonal
- **业务范围**：AI agent 平台 —— 统一 API / RAG / 特征存储 / 异步任务编排（生产级）
- **技术形态**：Python FastAPI service + Celery worker + Streamlit UI + 多组件
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-python/trex-hexagonal
- **本地路径建议**：`{your_workspace}/backend-python/trex-hexagonal/`
- **stack**：Python / FastAPI / LangGraph / Celery / Feast / PostgreSQL / Redis / Streamlit / Docker Compose
- **多模块结构**：`app/` / `ui/` / `feature_store/` / `tests/` / `scripts/` / `data/` / `docs/` + `docker-compose.yml` + `Dockerfile`（master 27 entries 完整 populated）
- **最近更新**：2026-05-15（master 已初始化完成）

### trex-persona-feast
- **业务范围**：persona 特征工程 + 特征存储（Feast）
- **技术形态**：Python multi-module
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-python/trex-persona-feast
- **本地路径建议**：`{your_workspace}/backend-python/trex-persona-feast/`
- **stack**：Python / Feast / requirements.txt
- **多模块结构**：`feature_repo / persona-web / technical_design`
- **最近更新**：2026-05-13

### trex-prism-engine
- **业务范围**：`〔t-rex 现状〕`URL path 历史曾为 `yield-engine`，2026-05-14 已 rename 到 `trex-prism-engine`；从历史命名推测为收益 / yield 计算引擎，待 owner 补充权威定义
- **技术形态**：Python service + web
- **GitLab URL**：https://gitlab.com/Keccak256-evg/t-rex/backend-python/trex-prism-engine
- **本地路径建议**：`{your_workspace}/backend-python/trex-prism-engine/`
- **stack**：Python / requirements.txt
- **多模块结构**：`service / web`
- **最近更新**：2026-05-13

`〔Python 后端规约缺失〕` 本 handbook 当前 `backend/` 章主体面向 Java；Python 后端的脚手架、依赖管理、测试、日志、可观测性规约**待补 M3+**。建议立项 `backend-python/` 一级目录或独立 sub-handbook。

---

## C. `anchor/` — anchor 子领域（13 项 混栈）

`〔t-rex 现状〕`：**anchor 是 t-rex 的子领域** —— 自成 13 个仓的独立产品线，含 Java 后端、Node/TS、Foundry 智能合约多栈。从仓名/模块名推断业务覆盖链上洞察（`anchor-insight-*`）、NFT、Token、第三方数据、zkTLS、智能合约（`anchor-labs`）；anchor 子域的精确业务边界 / 与 trex 主域接口由 anchor team owner 维护，本 handbook 仅从工程视角列清单。

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

`〔t-rex 现状〕`：anchor 各项目的业务范围 / 上下游由 anchor team owner 在 GitLab description 维护，本 handbook 不在此重述。

`〔已停用容器 archive 策略待立〕`：`anchor-endpoint` / `anchor-event` 已停用并迁移到 `trex-endpoint` / `trex-event`；仓库保留只读 / 标记 archived / 文档跳转的选择 —— 待 ops 主理人 + anchor team 共同定。

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

## D. `scaffold/` — 基础设施 / lib（4 项）

`〔t-rex 现状〕`：2026-05-19 新建的 sub-group，把历史散在 `gwave-dev/` 下的工程脚手架 + 公共 lib 集中归到 `t-rex/scaffold/`。**不是微服务**，是 t-rex 后端工程的共同支撑。

| 项目 | URL path | 类型 | 来源 / 关系 | 最近 |
|---|---|---|---|---|
| **trex-framework** | `scaffold/trex-framework` | parent POM + runtime starters | **替代** `gwave-dev/kiki-framework`（已 fork 过来）—— 新工程统一继承本仓 | 2026-05-19 |
| **trex-scaffold** | `scaffold/trex-scaffold` | 新建工程生成器 | **替代** `gwave-dev/evg-scaffold`（已 transfer + rename） | 2026-05-19 |
| **knotify** | `scaffold/knotify` | 通知 lib | fork from `gwave-dev/knotify`；⚠️ 即将下沉到 `backend-java/trex-widget` | 2026-05-19 |
| **kseq** | `scaffold/kseq` | 序列 lib | fork from `gwave-dev/kseq`；⚠️ 即将下沉到 `backend-java/trex-widget` | 2026-05-19 |

### 关键约定【强制】

- **新工程必须继承 `trex-framework` parent POM**（取代 `kiki-framework`，详见 `02-architecture.md`）
- **新工程推荐用 `trex-scaffold` 生成**（取代 `evg-scaffold`）
- **`knotify` / `kseq` 处于过渡期**：现存依赖可继续用；新代码不要新引入 —— 团队规划把这两个 + `kurl` 合并下沉到一个新的 `trex-widget` 服务（落 `backend-java/`，未来追加）

### 与 `gwave-dev/` 老仓的关系

- `gwave-dev/kiki-framework`、`gwave-dev/knotify`、`gwave-dev/kseq` 物理仍存在但**视为 deprecated**，禁止新工程引用
- `gwave-dev/evg-scaffold` 已 transfer 到 `t-rex/scaffold/trex-scaffold`，旧 URL GitLab redirect

---

## 全局视图

```text
                  t-rex 后端生态 (22 微服务 + 4 基础设施)
                              │
        ┌──────────────┬──────┴───────┬────────────────┐
        │              │              │                │
   backend-java/  backend-python/  anchor/         scaffold/
    (Java 6)      (Python 3)    (13 混栈)       (基础设施 4)
        │              │              │                │
   trex-core      trex-hexagonal   ┌──┴──┐        trex-framework
   trex-passport  trex-persona-     Java 非 Java   trex-scaffold
   trex-web        feast            (8)  (5)       knotify ⚠️
   trex-endpoint  trex-prism-                      kseq ⚠️
   trex-event      engine                          ↘ 计划合入
   trex-admin                                       backend-java/
                                                    trex-widget
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

- [ ] 22 个项目业务范围 + 上下游逐一补全
- [x] ~~`trex-admin / trex-event / trex-hexagonal` master 为空~~ ✅ 2026-05-15 全部解决：
  - `trex-admin`: 重构 reborn 已合主干，master 5 模块齐全
  - `trex-event`: master 一直有 `drex-event-server` 模块（之前误报）
  - `trex-hexagonal`: master 27 entries 已 populated（含 app/ ui/ feature_store/ + docker-compose）
- [x] ~~**GitLab path rename**~~ ✅ 已完成 (TREX-449, 2026-05-14)：display name 已 `trex-*` / `anchor-*`，URL path 也对齐到 display
- [ ] **anchor 子领域定位**：业务范围 / 与 t-rex 主域边界 / 数据流向
- [ ] Python 后端规约章（M3+ 立项）
- [ ] 智能合约 / zkTLS / SDK 类项目是否独立规约
- [ ] 完整上下游关系图（mermaid）

## 维护

- 新增 / 重命名 / 迁移项目需同步更新本章 + GitLab description
- 服务条目变更（业务范围 / 仓库迁移）需同步本章
- sub-group 调整需同步更新 `common/01-gitlab-and-workspace.md`
