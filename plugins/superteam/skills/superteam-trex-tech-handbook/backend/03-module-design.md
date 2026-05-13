# 模块划分：两种典型形态

t-rex 后端工程现有**两种**经过验证的模块组织方式。**两种并存**，不是"有一种是错的"。

## 形态对照

| 维度 | Gateway 形态 | Dubbo 领域服务形态 |
|---|---|---|
| **典型项目** | `trex-web` | `drex-core` / `drex-passport` |
| **主要职责** | 对外 API 网关 / BFF，聚合下游 Dubbo 服务 | 领域服务，对内提供 `Remote*Service` Dubbo 接口 |
| **模块划分准则** | 按**业务领域** | 按**技术分层** |
| **典型模块** | `drex-module-customer` / `activity` / `growth` / `core` / `common` + `drex-web-start` 入口 | `core-api` / `core-dal` / `core-service` / `core-web` / `core-graphql` / `core-model` |
| **跨服务调用** | Dubbo client 调下游领域服务 | Dubbo provider 暴露接口；也可 client 调其他领域服务 |
| **Controller 形态** | OpenAPI generator 生成 + `*ApiDelegateImpl` 写业务 | 直接 `@RestController`（领域服务通常没有 REST，仅 Dubbo） |
| **对外暴露** | HTTP REST（含 OpenAPI 生成的 SDK） | Dubbo（生产者）；可选 GraphQL（drex-core 有 `core-graphql`） |
| **典型用户** | 前端 / 项目方 Portal | 兄弟领域服务 + Gateway |

## 新项目选型决策

```text
你的新服务对外吗？
├── 是（直接面向前端 / 第三方）       → Gateway 形态
│   └── 学 trex-web 的模块切法
│
└── 否（仅供其他后端服务调用）        → Dubbo 领域服务形态
    └── 学 drex-core 的分层切法
```

特殊情况：

- 跨多个业务域的聚合服务（少见）—— 偏 Gateway
- 同时对外 + 对内 —— 仍按 Gateway 起，对内接口可走 Dubbo provider 副通道
- 数据中台 / 工具服务 —— 偏 Dubbo 领域服务

## 〔t-rex 现状〕：并存而非冲突

历史上有人质疑"为什么 trex-web 和 drex-core 模块切法完全不一样"。答案是：**两者职能不同，切法应该不同**：

- Gateway 的边界是 **HTTP 端点的业务域**（用户中心 / 增长 / 活动）—— 按业务切便于"加一个新业务领域不动其他模块"
- Dubbo 领域服务的边界是 **技术职责**（接口定义 / 数据访问 / 业务逻辑 / Web 入口）—— 按层切便于"换 ORM 不动接口、换 Dubbo 版本不动业务"

两种切法都符合"高内聚低耦合"原则，只是在不同维度做内聚。

## 共有约束（不论选哪种）

- 包名遵循 `04-coding-standards.md`
- 错误码与异常基类遵循 `07-exception-and-logging.md`
- 共用 `kiki-framework` parent POM
- 共用 Nacos / OTS / Redis / Zipkin
- 测试遵循 `08-testing.md`

## 反例（不要这样做）

```text
❌ Gateway 直接访问数据库（绕过下游 Dubbo 领域服务） → 破坏服务边界，无法复用业务规则、难以审计
❌ 一个对外 Gateway，按技术层切模块 → 新增业务要改 N 个模块，发版风险高
❌ 把 Gateway 的 Controller 业务逻辑直接写在 Controller 里 → 应该写在 ApiDelegateImpl
❌ 把领域服务的接口定义放在 service 模块 → 应该在 api 模块（供消费者依赖）
```

## 维护

模块划分变更必须经技术评审 + 同步本章。新形态出现（如果有）应作为第三列加入对照表。
