# 新建后端服务 Checklist

> 新建一个 t-rex 后端 Java 微服务时按本 checklist 逐项确认。完成后请回到 `backend/01-microservices.md` 追加服务条目。

---

## 创建仓库

- [ ] 仓库路径在 GitLab sub-group `Keccak256-evg/t-rex/backend-java/<service-name>` 之下（见 `common/01-gitlab-and-workspace.md`）
- [ ] 仓库 visibility 设置为 internal（按需 private）
- [ ] 初始 README.md（即便最小）
- [ ] LICENSE 与同 sub-group 其他仓一致

## 配置 Push Rule

- [ ] Branch Name regex 同 `common/appendix/project-prefix.md`
- [ ] Commit Message regex 同 `common/appendix/project-prefix.md`
- [ ] Protected branches: `master` / `<project>_master` / 视项目需要

## 工程脚手架

- [ ] 用 `trex-scaffold` 生成工程（推荐） 或 手写 POM 继承 `trex-framework` parent
- [ ] groupId = `xyz.trex.<project>`（新工程）；老工程延伸模块例外
- [ ] 包名 = `xyz.trex.<project>.*`（新工程）；老工程沿用 `com.drex.*`

## 必装 starter

- [ ] `kiki-observability-tracing-spring-boot-starter`（MDC 注入）
- [ ] `kiki-ots-spring-boot-starter`（如使用 OTS）
- [ ] `kiki-redis-spring-boot-starter`（如使用 Redis）
- [ ] `spring-cloud-starter-alibaba-nacos-config`
- [ ] 数据库依赖（如使用 PG）：MyBatis-Plus + PostgreSQL Driver + Druid

## 配置中心

- [ ] 申请 Nacos namespace（local / dev / test / prod）
- [ ] `bootstrap.properties` 配置 Nacos 地址 + namespace + group
- [ ] `application-local.properties` 本地开发覆盖
- [ ] `config-local.properties` 个人敏感配置（**不入 git**）

## 日志

- [ ] 日志 pattern 包含 MDC 4 字段（见 `backend/07-exception-and-logging.md`）
- [ ] 日志输出到文件 / SLS（按 ops 团队规范）

## CI

- [ ] 本仓 `.gitlab-ci.yml` 入口 `include` 到 `Keccak256-evg/ops/gitlab-cis` master 的 `gwave-dev/<service-name>.yaml`（向 ops 仓提 MR 创建对应 yaml）。`〔t-rex 现状〕`：ops/gitlab-cis 内部的 `gwave-dev/` 是历史命名（ops repo 尚未跟随 sub-group 重组 rename），所有后端 Java 服务的 CI 入口都落在该目录
- [ ] 验证 CI 跑通

## 错误码 + 异常基类

- [ ] Dubbo 领域服务 → 创建 `<Project>ResponseCode` enum + `<Project>Exception` 基类
- [ ] Gateway → 沿用 `ErrorCode` + `GlobalExceptionHandler` + `WebResult` 模式

## 测试

- [ ] JUnit 5 + Mockito（不要用 JUnit 4 / JUnit 3.8.1）
- [ ] `src/test/java/<package-prefix>/...` 目录
- [ ] 至少跑通 1 个示例单测

## 注册到 handbook

- [ ] 在 `backend/01-microservices.md` 追加本服务条目（按模板填全字段）
- [ ] 标注业务范围、技术形态（Gateway / Dubbo 领域服务）、上下游
- [ ] **不填负责人**（`01-microservices.md` 已说明：不收录 owner 字段）

## 首次 commit

- [ ] 分支名 `dev_<YYMMDD>_init`（trex team 新规约，见 `common/02-branch-and-commit.md`）
- [ ] commit msg 用 `init:` 前缀（如 `init: scaffold campaign-service from trex-scaffold`）
- [ ] 走完整 `common/03-test-handoff.md` SOP（`dev_*` → `review_*` 提测 MR）才能合入 `review_*`；后续 `beta_*` / `master` 由 QA / 发布流程推进

---

`〔t-rex 现状〕`：
- **命名 + 端口 + Nacos namespace 分配**：暂无中央注册表，新仓在群里 sync 一下即可
- **trex-scaffold 具体生成命令**：以 trex-scaffold 仓库 README 为准（仍在完善中）
