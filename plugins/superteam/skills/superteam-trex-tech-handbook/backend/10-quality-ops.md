# 可观测性与运维

## 可观测性【强制】

**Tracing**：`kiki-observability-tracing-spring-boot-starter` → Zipkin
- 自动注入 `traceId / spanId / module / severity` 到 MDC
- 自动上报 RPC / HTTP / DB 等关键事件的 span
- Zipkin 地址在 `application.properties` 中配置（具体地址按环境）

**Logging**：
- 应用日志 → SLS（具体投递方式由 ops/gitlab-cis 中的部署模板配置）
- 日志格式见 `07-exception-and-logging.md`

**Metrics**：
- TODO(@allen)：是否引入 Micrometer + Prometheus？

## 配置中心【强制】

**Nacos**：`spring-cloud-starter-alibaba-nacos-config`

**本地**：`config-local.properties` + `bootstrap.properties`

**规约**：
- 业务配置走 Nacos（按 namespace 隔离环境：local / dev / test / prod）
- 敏感配置（密钥等）：TODO(@allen) — 走 Nacos 加密 / KMS / 环境变量？
- 本地开发用 `config-local.properties` 覆盖；不 commit 个人敏感配置

**反例**：
```text
❌ 把数据库密码 / API key 硬编码进 application.properties
❌ 测试环境配置写死在代码里
❌ 同一份配置在 Nacos 与 application.properties 各写一份（来源不唯一）
```

## 监控告警

TODO(@allen)：
- 监控平台是哪个（云监控 / Prometheus / 自建）？
- 告警接收人 / on-call 轮值
- 告警规则模板（错误率 / P99 延迟 / 队列堆积）
- 业务级监控（如 Campaign 关键指标）

## 性能与容量

TODO(@allen)：
- 接口性能基线（P99 < ?）
- 容量评估流程（新服务上线前的预估）
- 压测要求

## 密钥与机密管理

TODO(@allen)：
- 哪些密钥走 Nacos 加密
- 哪些走 KMS / 阿里云 RAM
- 私钥不入库的强约束

## 故障应急

TODO(@allen)：
- 故障分级（P0 / P1 / P2）
- 应急流程
- 复盘要求

## 维护

- 监控规则、告警阈值、容量基线变化，更新本章
