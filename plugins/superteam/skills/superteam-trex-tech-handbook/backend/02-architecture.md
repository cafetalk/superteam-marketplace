# 后端架构与基础脚手架

t-rex 后端的"骨架"由两个仓库共同支撑：`trex-framework`（运行时 parent POM + starter）+ `trex-scaffold`（脚手架 / 生成器）。新建工程**必须**了解二者关系。

## trex-framework【强制】

**定位**：所有 t-rex Java 后端工程的 **parent POM**。提供 Spring Boot 3.0.2 版本管理 + 一组 starter（OTS / Redis / Tracing / Dubbo / Cache / KMS / Ignite / etc.）。

**仓库**：https://gitlab.com/Keccak256-evg/t-rex/scaffold/trex-framework

**版本**：`2.5.0-SNAPSHOT`（截至 2026-05；以本仓 `pom.xml` 为准）

`〔t-rex 现状〕`：**repo path 已 rename 到 `trex-framework`**（2026-05-19 sub-group 迁移），但 **Maven 坐标仍是历史 `com.kikitrade:kiki-framework`** —— groupId / artifactId 改名是后续动作，新工程目前仍按下面坐标继承。

**最小 POM 引用**：

```xml
<parent>
    <groupId>com.kikitrade</groupId>
    <artifactId>kiki-framework</artifactId>
    <version>2.5.0-SNAPSHOT</version>
</parent>
```

**已知 starter 清单**（来自仓库根目录扫描；按用途分组）：

| 分组 | Starter | 用途 |
|---|---|---|
| 存储 | `kiki-ots-spring-boot-starter` / `kiki-ots` / `kiki-ots-mongodb` | Aliyun OTS TableStore 客户端封装 |
| 存储 | `kiki-mybatis` | MyBatis 集成 |
| 存储 | `kiki-shardingdb-spring-boot-starter` | Sharding-JDBC 分库分表 |
| 缓存 | `kiki-redis-spring-boot-starter` | Redis 客户端 + 缓存抽象 |
| 缓存 | `kiki-cache-spring-boot-starter` | 通用缓存接口 |
| 缓存 | `kiki-ignite-spring-boot-starter` + `kiki-ignite-prometheus` + `kiki-ignite-cache-names-*-extension` | Apache Ignite 分布式缓存 |
| 配置 | `kiki-config-spring-boot-starter` | Nacos config 协作 |
| 配置 | `kiki-kms-spring-boot-starter` | 密钥管理（KMS） |
| RPC | `kiki-dubbo-deployment-tag-aware-spring-boot-starter` | Dubbo 部署 tag 路由 |
| RPC | `kiki-dubbo-mock-spring-boot-starter` | Dubbo mock 调试 |
| 可观测 | `kiki-observability-tracing-spring-boot-starter` / `-brave-*` | Zipkin tracing + MDC 注入（traceId / spanId / module / severity） |
| 可观测 | `kiki-observability-metrics-spring-boot-starter` | 指标采集 |
| 消息 | `kiki-ons-spring-boot-starter` | Aliyun ONS / RocketMQ |
| 消息 | `kiki-kafka-connect-consumer` | Kafka Connect consumer |
| 数据 | `kiki-dts-new-spring-boot-starter` / `kiki-dts-unified` | DTS 数据传输 |
| 数据 | `kiki-odps-spring-boot-starter` | MaxCompute (ODPS) |
| 调度 | `kiki-elasticjob-spring-boot-starter` | ElasticJob 分布式调度 |
| 状态机 | `kiki-state-machine-spring-boot-starter` | 状态机 DSL |
| 集成 | `kiki-hookclient-spring-boot-starter` | hook client |
| 基础 | `kiki-core` | 公共工具 / 异常基类 / 错误码协议 |
| 测试 | `kiki-bdd-testing` / `kiki-bdd-testing-common` / `kiki-boot-test` / `kiki-framework-test` | BDD + Spring Boot 测试辅助 |

starter 不是全部强制引入 —— 按业务需要挑选；详细 API 见各 starter README。

## trex-scaffold【推荐】

**定位**：t-rex 工程脚手架 / 生成器。

**仓库**：https://gitlab.com/Keccak256-evg/t-rex/scaffold/trex-scaffold

`〔t-rex 现状〕`：repo path 已 rename 到 `trex-scaffold`（2026-05-19），但 **内部模块名仍是历史 `evg-scaffold-*` 前缀**（artifact rename 后续动作）。

**两种使用方式**：

1. **作为脚手架（新建工程时）**：用 trex-scaffold 生成起步工程（目录结构 / 默认依赖 / `application.properties` / `bootstrap.properties` / `.gitlab-ci.yml` 入口等）
2. **作为依赖 jar（老工程按需引入）**：把下表的某个模块作为 jar 依赖加入 POM，复用通用组件

**模块清单**：

| 模块 | 用途 |
|---|---|
| `evg-scaffold-common` | 通用工具 / 基类 / 配置 |
| `evg-scaffold-endpoint` / `-endpoint-client` | 对外端点 server 端 + client 端封装 |
| `evg-scaffold-event` / `-event-client` | 事件 / 消息 server + client |
| `evg-scaffold-inner-event` | 进程内事件总线 |
| `evg-scaffold-feast-client` | Feast 特征存储 client |
| `evg-scaffold-telegram` | Telegram 集成 |
| `evg-scaffold-vampire-attack` | （专项业务集成；详见模块 README） |

`〔t-rex 现状〕`：老工程多数没有完全通过 trex-scaffold 生成（早期手写），但新工程**推荐**走脚手架确保基础设施一致。

## 基础设施总览

```text
                ┌──────────────────────────────────────────┐
                │            t-rex 后端微服务              │
                │  trex-core / trex-passport / trex-web    │
                └────┬──────────────┬──────────────┬───────┘
                     │              │              │
              Dubbo  │     HTTP /   │   RocketMQ   │
              (RPC)  │     GraphQL  │   (ONS)      │
                     ▼              ▼              ▼
              ┌────────────┐ ┌────────────┐ ┌────────────┐
              │   Nacos    │ │  前端 /    │ │     ?      │
              │ 注册+配置  │ │  Portal    │ │            │
              └─────┬──────┘ └────────────┘ └────────────┘
                    │
                    ▼
   ┌────────────────────────────────────────────────────────┐
   │              基础设施层 (Aliyun + 自建)                │
   │  ┌────────┐  ┌────────────┐  ┌────────┐  ┌──────────┐ │
   │  │  OTS   │  │ PostgreSQL │  │ Redis  │  │  Zipkin  │ │
   │  │TableSt.│  │  + Druid   │  │        │  │ SLS 日志 │ │
   │  └────────┘  └────────────┘  └────────┘  └──────────┘ │
   └────────────────────────────────────────────────────────┘
```

## 新工程脚手架步骤（简）

详尽 checklist 见 `backend/appendix/templates/new-service-checklist.md`。最小步骤：

1. 在 `gitlab.com/Keccak256-evg/t-rex/backend-java/` 下新建仓
2. 用 trex-scaffold 生成工程或继承 `trex-framework` parent POM
3. 配置 Nacos namespace
4. 引入 `kiki-observability-tracing-spring-boot-starter`
5. 包名 `xyz.trex.<project>.*`（新工程；见 `04-coding-standards.md`）
6. 第一次 commit 用 `init:` 前缀 + 分支 `dev_<YYMMDD>_init`（trex team 新规约）
7. 在 `backend/01-microservices.md` 添加本服务条目
