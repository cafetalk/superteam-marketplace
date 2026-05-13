# 术语表

按字母排序的 t-rex 后端术语简释。新人 / AI 助手如读不懂某词，先查这里。

## 主条目

### com.drex / xyz.trex (包名前缀)
- `com.drex.*` — 老工程 groupId / 包前缀（drex-core / drex-passport / trex-web 等）。**不强制迁移**
- `xyz.trex.*` — 新工程统一前缀（2026-05 起新建）
- 详见 `backend/04-coding-standards.md`

### Dubbo
Apache Dubbo — t-rex 后端**服务间**通信协议。接口写在 `<project>-api` 模块，命名 `Remote<Domain>Service`。

### drex-core
t-rex 广告主 / 投放计划领域服务的样板。按技术分层切模块 (`core-api` / `core-dal` / `core-service` / `core-web` / `core-graphql` / `core-model`)。groupId `com.drex`。

### drex-passport
t-rex 用户身份 / 登录 / 签名验证 / Session 管理服务。

### evg-scaffold
t-rex 工程脚手架 / 生成器。仓库 https://gitlab.com/Keccak256-evg/gwave-dev/evg-scaffold 。也可作 jar 依赖按需引入。详见 `backend/02-architecture.md`。

### Gateway 形态
t-rex 后端两种工程形态之一。代表项目 trex-web。按业务领域分模块，对外提供 REST API。详见 `backend/03-module-design.md`。

### GraphQL
drex-core 的 `core-graphql` 模块提供 GraphQL 查询入口，适用于多字段复杂查询。技术栈 `spring-boot-starter-graphql` + `graphql-java-extended-scalars` 22.0。

### kiki-framework
t-rex 后端所有工程的 **parent POM**。提供 Spring Boot 版本管理 + 一组 starter（OTS / Redis / Tracing 等）。详见 `backend/02-architecture.md`。

### Mapper (MyBatis-Plus)
MyBatis-Plus 的数据访问 Mapper 接口。类名 `*Mapper`。**注意与 MapperStruct 区分**。

### MapperStruct (MapStruct)
MapStruct 的对象转换接口。类名 `*MapperStruct`。注意与 MyBatis 的 `*Mapper` 区分。`@Mapper(componentModel = "spring")` 注解。

### MDC (Mapped Diagnostic Context)
SLF4J 提供的线程级上下文，t-rex 强制必填字段 `traceId / spanId / module / severity`，由 `kiki-observability-tracing-spring-boot-starter` 自动注入。

### Nacos
Spring Cloud Alibaba 配置中心 + 注册中心。t-rex 所有服务的业务配置都在 Nacos，按 namespace 隔离环境。

### OpenAPI Delegate 模式
trex-web 风格的 Controller 写法：用 OpenAPI generator 生成 `*ApiController` + `*ApiDelegate`；业务实现写在自己的 `*ApiDelegateImpl`。

### ops/gitlab-cis
集中托管的 CI 规则仓库（`Keccak256-evg/ops/gitlab-cis`）。t-rex 所有项目的 `.gitlab-ci.yml` 都通过 `include` 引用此仓的规则。

### OTS (TableStore)
Aliyun OTS TableStore，NoSQL 主存储。通过 `kiki-ots-spring-boot-starter` 访问。详见 `backend/06-data-and-storage.md`。

### p3c
Alibaba Java Coding Guidelines 的 PMD 实现 + IDE 插件。仓库 https://github.com/alibaba/p3c 。推荐在 IDE 中安装以自动检查阿里规约。

### Push Rule (GitLab)
GitLab 项目设置 → Repository → Push Rules。t-rex 后端仓库配置了：
- Branch Name regex — 限制分支命名
- Commit Message regex — 限制 commit msg 前缀
- 违反任一 → push 被拒。详见 `common/02-branch-and-commit.md` 与 `common/appendix/project-prefix.md`。

### Push Rule 'review' 分支
`review_*`（trex team 新规约）/ `trexreview_*`（老规约，其他团队仍在用）分支命名 stage。代码评审必经；team lead 通过 MR review 后 merge 进 `dev`。

### SLS
Aliyun Log Service，t-rex 后端日志的最终归宿。

### t-rex / trex 前缀
- 业务生态名称：t-rex
- GitLab group：`Keccak256-evg/t-rex/`
- 新工程包名 / 分支前缀：`trex`（不带连字符）

### trex-web
t-rex Gateway / BFF 样板，对外提供 REST API 聚合下游 Dubbo 服务。按业务领域分模块。

### worktree (git)
git 的隔离工作区机制。t-rex 推荐对每个新分支创建独立 worktree，避免主 checkout 切分支带来的工程污染。详见 `common/02-branch-and-commit.md`。

### Zipkin
分布式追踪平台。t-rex 后端通过 `kiki-observability-tracing-spring-boot-starter` 上报 span 到 Zipkin。

## 维护

- 新增技术栈 / 概念 / 缩写时同步更新本表
- 条目尽量包含"在 t-rex 是什么 + 在哪里详读"两部分
- TODO(@allen): 建立一个机制（pre-commit hook 或 CI 检查）确保新引入的中间件 / 框架在 PR 合入前补充术语表条目
