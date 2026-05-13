# 后端架构与基础脚手架

t-rex 后端的"骨架"由两个仓库共同支撑：`kiki-framework`（运行时）+ `evg-scaffold`（脚手架 / 生成器）。新建工程**必须**了解二者关系。

## kiki-framework【强制】

**定位**：所有 t-rex 后端工程的 **parent POM**。提供 Spring Boot 版本管理 + 一组 starter（OTS / Redis / Tracing / etc.）。

**版本**：2.5.0-SNAPSHOT（截至 2026-05；具体以本仓 POM 为准）

**已知 starter 清单**（不完全，按需扩充）：

| Starter | 用途 |
|---|---|
| `kiki-ots-spring-boot-starter` | Aliyun OTS TableStore 客户端封装 |
| `kiki-redis-spring-boot-starter` | Redis 客户端 + 缓存抽象 |
| `kiki-observability-tracing-spring-boot-starter` | Zipkin tracing + MDC 注入（traceId / spanId / module / severity） |
| `kiki-core` | 公共工具 / 异常基类 / 错误码协议 |
| `(其他)` | TODO(@allen)：盘点完整 starter 列表 |

**最小 POM 引用**：

```xml
<parent>
    <groupId>com.kiki</groupId>
    <artifactId>kiki-framework</artifactId>
    <version>2.5.0-SNAPSHOT</version>
</parent>
```

TODO(@allen)：补 kiki-framework 仓库 URL + 版本演进路线。

## evg-scaffold【推荐】

**定位**：t-rex 工程脚手架 / 生成器。

**仓库**：https://gitlab.com/Keccak256-evg/gwave-dev/evg-scaffold

**两种使用方式**：

1. **作为脚手架（新建工程时）**：用 evg-scaffold 生成一个起步工程（目录结构 / 默认依赖 / `application.properties` / `bootstrap.properties` / `.gitlab-ci.yml` 入口等）
2. **作为依赖 jar（老工程按需引入）**：把 evg-scaffold 的某些模块作为 jar 依赖加入 POM，复用通用组件

`〔t-rex 现状〕`：老工程可能没有完全通过 evg-scaffold 生成（早期手写），但新工程**推荐**走脚手架确保基础设施一致。

TODO(@allen)：evg-scaffold 主要模块清单 + 各自 jar 坐标。

## 基础设施总览

```text
                ┌──────────────────────────────────────────┐
                │            t-rex 后端微服务              │
                │  drex-core / drex-passport / trex-web    │
                └────┬──────────────┬──────────────┬───────┘
                     │              │              │
              Dubbo  │     HTTP /   │       MQ     │  (TODO)
              (RPC)  │     GraphQL  │              │
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
2. 用 evg-scaffold 生成工程或继承 `kiki-framework` parent POM
3. 配置 Nacos namespace
4. 引入 `kiki-observability-tracing-spring-boot-starter`
5. 包名 `xyz.trex.<project>.*`（新工程；见 `04-coding-standards.md`）
6. 第一次 commit 用 `init:` 前缀 + 分支 `dev_<YYMMDD>_init`（trex team 新规约）
7. 在 `backend/01-microservices.md` 添加本服务条目
