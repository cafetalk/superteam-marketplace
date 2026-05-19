# 异常与日志

## 错误码体系【强制】

t-rex 错误码采用**分段编号 + enum** 模式。两种风格并存（按工程形态）：

### Dubbo 领域服务（trex-core 样板）
- 错误码 enum：`<Project>ResponseCode`（trex-core: `CoreResponseCode`）
- 异常基类：`<Project>Exception`（trex-core: `CoreException`，持有 `<Project>ResponseCode`）
- **错误码分段规约**（trex-core 实际样例，2026-05-19 audit 校准）：
  - `0xxx` — 成功（`SUCCESS`）
  - `4xxx` — 通用错误（参数 / 数据 / 限流）+ 部分业务（reward / rexy / reply）—— `〔t-rex 现状〕`段内未严格按域切分，已有 10 codes
  - `5xxx` — **Squad Task 模块**（11 codes；`〔t-rex 现状〕`早期文档描述为 "YouTube" 已 stale，业务变更后实际是 Squad Task）
  - `6xxx` — Campaign 模块（实际仅 1 code，业务大头落在 5xxx）
  - 各服务自管段位（仍【强制】，避免冲突）
- 位置：`<project>-api/.../common/`（trex-core 在 `com.drex.core.api.common.CoreResponseCode` —— 包名 `com.drex.*` 是历史 groupId，不强制迁移）

### Gateway（trex-web 样板）
- 错误码 enum：`ErrorCode`（`com.drex.web.common.ErrorCode`）
  - 形如 `SIGNATURE_INVALID("00001", "...")`
- 异常处理器：`GlobalExceptionHandler`（`@ControllerAdvice`），统一捕获后映射到 `WebResult` 包装
- 返回包装：`WebResult<T>` —— code + message + data 三段

### 新工程选择
- Dubbo 领域服务 → 沿用 trex-core 风格（`<Project>ResponseCode` + `<Project>Exception`）
- Gateway → 沿用 trex-web 风格（`ErrorCode` + `GlobalExceptionHandler` + `WebResult`）

**反例**：
```text
❌ 直接 throw RuntimeException 没有错误码 → 调用方无法分辨
❌ 错误码用字符串拼接 → 必须用 enum
❌ 多个模块共用 4xxx 段 → 必须按段分配，避免冲突
```

**待团队评审**：

- [ ] 跨服务错误码传递约定（Dubbo → Gateway → 前端的映射）
- [ ] 各服务错误码段位分配登记表

## 日志规约【强制】

**日志框架**：SLF4J + Lombok `@Slf4j`（不要直接 `LoggerFactory.getLogger`）

**示例**：
```java
@Slf4j
public class CampaignServiceImpl implements CampaignService {
    public CampaignDetail getCampaign(Long id) {
        log.info("getCampaign request, id={}", id);
        // ...
    }
}
```

### MDC 必填字段【强制】

每条日志必须含以下 MDC 字段（**由 `kiki-observability-tracing-spring-boot-starter` 自动注入**）：

| MDC key | 含义 |
|---|---|
| `traceId` | 全链路追踪 ID |
| `spanId` | 当前 span ID |
| `module` | 业务模块标签（应用启动时配置） |
| `severity` | 严重级别（可选自定义） |

### 日志格式

参考 trex-core `application.properties` 已落地的 pattern：

```properties
logging.pattern.console=[%p][%t][%d{yyyy-MM-dd HH:mm:ss.SSS}][%c][%L][%X{traceId}][%X{spanId}][%X{module}][%X{severity}]%m%n
```

**反例**：
```text
❌ 直接 System.out.println / e.printStackTrace()
❌ 日志中拼字符串：log.info("xxx=" + xxx) → 用占位符
❌ 在循环里 log.debug 不判断 isDebugEnabled() 的高开销代码
❌ 把敏感信息（token / 手机号 / 身份证）打全量日志
```

**待团队评审**：

- [ ] 日志级别使用规约（DEBUG / INFO / WARN / ERROR 边界）
- [ ] 异常日志：`log.error("...", e)` 必须打异常 stack
- [ ] 敏感字段脱敏（与 09-security 敏感字段清单联动）

## 维护

- MDC 字段调整必须同步 kiki-observability 配置 + 各服务的 application.properties pattern
- 错误码段位扩张必须登记
