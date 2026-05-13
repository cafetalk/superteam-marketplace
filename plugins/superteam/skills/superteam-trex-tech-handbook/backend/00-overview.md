# 后端总览

## 后端在 t-rex 中的定位

t-rex 后端是一组 Java 微服务集群，承担：
- 业务领域服务（广告主 / 投放 / 用户身份 / 增长 / 活动）
- 对外网关（项目方 Portal / 用户端 API）
- 数据接入与特征工程对接（与数据栈协同）

后端**不**直接负责前端渲染、智能合约执行、CEX/DEX 原始数据采集 —— 这些由各自的栈承担。

## 技术大盘

| 维度 | 选型 |
|---|---|
| 语言 | Java 17 |
| 应用框架 | Spring Boot（继承 `kiki-framework` parent POM） |
| RPC | Apache Dubbo |
| API | OpenAPI（生成 Controller）+ GraphQL（drex-core 查询层） |
| ORM | MyBatis-Plus 3.5.3 |
| 主存储 | Aliyun OTS TableStore（NoSQL） |
| 辅存储 | PostgreSQL 42.5.4 + Druid 连接池 |
| 缓存 | Redis（`kiki-redis-spring-boot-starter`） |
| 配置中心 | Nacos（`spring-cloud-starter-alibaba-nacos-config`） |
| 可观测性 | Zipkin（`kiki-observability-tracing-spring-boot-starter`）；日志 → SLS |
| 构建 | Maven（含 `mvnw`） |
| CI | 中心化托管在 `ops/gitlab-cis`（见 `common/04-ci-and-release.md`） |

## 关键非显然事实

1. **kiki-framework parent POM 是 t-rex 后端工程的共同祖先**。继承它会自动得到一组 starter（OTS / Redis / 可观测性）+ 统一依赖版本管理。详见 `02-architecture.md`。
2. **evg-scaffold** 是新建工程的脚手架，仓库 https://gitlab.com/Keccak256-evg/gwave-dev/evg-scaffold ，亦可作 jar 依赖按需引入。详见 `02-architecture.md`。
3. **包名前缀双轨**：新工程统一 `xyz.trex.*`；老工程保持 `com.drex.*` 不变。详见 `04-coding-standards.md`。
4. **两种典型形态并存**：Gateway（业务领域分模块）vs Dubbo 领域服务（技术分层分模块）。详见 `03-module-design.md`。
5. **MDC 强制字段**：日志必须带 `traceId / spanId / module / severity`，由观测 starter 注入。详见 `07-exception-and-logging.md`。

## 与 superteam 子项目的边界

`〔t-rex 现状〕` 本 handbook 的 backend 章**不**覆盖 `ai-workspace/superteam/`（Python skills 架构）。superteam 有自己的 `CLAUDE.md` + 一套不同的目录与测试约定。

## 阅读顺序建议

新人或新做 t-rex 后端任务的 AI 助手按此顺序：

1. `00-overview.md`（本文档）
2. `01-microservices.md` — 知道有哪些服务、各管什么
3. `02-architecture.md` — 共同基础设施
4. `03-module-design.md` — 你的新服务应该选哪种形态
5. 按需读 04-10 + appendix
