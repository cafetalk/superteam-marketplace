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
- `〔t-rex 现状〕`：**未引入 Micrometer + Prometheus** —— Tracing (Zipkin) 已覆盖 RPC / HTTP / DB 关键事件 + MDC，Metrics 单独立轨暂不必要；业务级监控由各服务自行打日志 + SLS 聚合。后续若有跨服务 SLO / 容量基线诉求再评估。

## 配置中心【强制】

**Nacos**：`spring-cloud-starter-alibaba-nacos-config`

**本地**：`config-local.properties` + `bootstrap.properties`

**规约**：
- 业务配置走 Nacos（按 namespace 隔离环境：local / dev / test / prod）
- **敏感配置（密钥等）**：`〔t-rex 现状〕`已有方案走 **Nacos 加密 namespace**；KMS / 环境变量是后续细化（具体走哪类的决策见 09-security 章 "密钥管理细则"）
- 本地开发用 `config-local.properties` 覆盖；不 commit 个人敏感配置

**反例**：
```text
❌ 把数据库密码 / API key 硬编码进 application.properties
❌ 测试环境配置写死在代码里
❌ 同一份配置在 Nacos 与 application.properties 各写一份（来源不唯一）
```

## 监控告警

`〔运维相关，见 ops runbook〕`：监控平台 / 告警接收人 / on-call 轮值 / 告警规则模板等由 **ops/gitlab-cis** + ops runbook 维护，不在 handbook 内重述（避免双向漂移）。具体接入位置：服务上线时由 ops 配置；研发只需保证日志 → SLS 与 tracing → Zipkin 已接入。

## 性能与容量

**待性能平台对齐**：

- [ ] 接口性能基线（P99 < ?）—— 平台准备好后回填
- [ ] 容量评估流程（新服务上线前的预估）
- [ ] 压测要求

## 密钥与机密管理

合并到上方 **配置中心 §敏感配置** 段；细则待 09-security 章"密钥管理细则" ADR 完成后回填。

## 故障应急

`〔运维相关，见 ops runbook〕`：故障分级（P0 / P1 / P2）/ 应急流程 / 复盘要求由 ops 团队维护。研发侧职责见 `common/04-ci-and-release.md` 的回滚 SOP + on-call 段。

## 维护

- 监控规则、告警阈值、容量基线变化，更新本章
