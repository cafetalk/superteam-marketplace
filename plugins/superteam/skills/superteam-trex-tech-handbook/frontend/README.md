# 前端层（frontend/）

t-rex 前端开发上下文包，涵盖 10 个前端子系统的技术规范（[TREX-405](https://linear.app/t-rex-v1/issue/TREX-405/) 落地）。

**适用范围**：所有 t-rex 前端项目（web/ + anchor 子域前端 + quest manage-web + agentic/superteam-web + sdk/ + trex-tls/ 内 Node-based 子项目）。

**与 common/ 关系**：本目录是 **frontend-specific** 规范；分支 / commit / 提测 / Linear / CI / 发布等流程规范仍在 `common/` 章，前端项目 **同样适用**。

## 章节索引

| 章节 | 核心问题 |
|---|---|
| [`00-overview.md`](00-overview.md) | 前端在 t-rex 中的定位；四类子系统概述 |
| [`01-apps.md`](01-apps.md) ⭐ | 前端应用 / SDK / 工具清单（10 个子系统条目）|
| [`02-architecture.md`](02-architecture.md) | 各类子系统技术栈基线（Web App / Extension / SDK / zkTLS Provider）|
| [`03-project-structure.md`](03-project-structure.md) | 三种目录形态（页面功能型 / 扩展型 / 库型）|
| [`04-coding-standards.md`](04-coding-standards.md) | 文件 / 组件 / 类型命名；ESLint / Prettier |
| [`05-api-and-integration.md`](05-api-and-integration.md) | REST codegen / GraphQL codegen / 链上 API 集成 |
| [`06-state-and-data.md`](06-state-and-data.md) | React Query（服务端状态）+ Jotai（客户端状态）|
| [`07-error-and-monitoring.md`](07-error-and-monitoring.md) | 错误边界；BugSnag；GA；用户侧错误展示 |
| [`08-test-handoff.md`](08-test-handoff.md) ⭐ | **前端提测 / 发布分支**（`dev_*` → `review_*` → `master`；无短期 `beta_*`）|
| [`09-testing.md`](09-testing.md) | Web App / Extension / SDK 各自测试策略 |
| [`10-security.md`](10-security.md) | token 存储；XSS / CSRF；Web3 签名安全；Extension 权限 |
| [`11-quality-ops.md`](11-quality-ops.md) | 构建产物；发布操作（Vercel / OSS / Chrome Store）|
| [`12-environments.md`](12-environments.md) ⭐ | **各子系统多环境域名 / 分支 / 测试入口** |
| [`appendix/glossary.md`](appendix/glossary.md) | 前端 + Web3 / zkTLS 术语表 |
| [`appendix/toolchain.md`](appendix/toolchain.md) | Node / 包管理器 / IDE / 命令速查 |
| [`appendix/templates/new-app-checklist.md`](appendix/templates/new-app-checklist.md) | 新建前端子系统 Checklist（A/B/C 三类）|
| [`appendix/templates/release-checklist.md`](appendix/templates/release-checklist.md) | 前端 prod 发布单 |

## 通用规范交叉引用

- `common/01-gitlab-and-workspace.md` — GitLab 组织 + 本地工作区目录
- `common/02-branch-and-commit.md` — 分支命名（`dev_<YYMMDD>_<name>` 等 trex team 新规约，v3.0 6-位日期）+ commit msg 前缀
- `common/03-test-handoff.md` — 提测流程 SOP
- `common/04-ci-and-release.md` — CI 委托 + 发布 + 回滚

## 设计文档

本层设计与实现计划（**设计归档，分支 / 提测以正文为准**）：
[`docs/skills-design/2026-05-12-trex-tech-handbook-frontend.md`](../../../docs/skills-design/2026-05-12-trex-tech-handbook-frontend.md)

现行分支命名：`common/02-branch-and-commit.md`；前端提测 SOP：`frontend/08-test-handoff.md`。

## 阅读顺序

开发前端任务时，先读 `common/`（通用规范），再按需读 `frontend/`：

1. `frontend/00-overview.md` — 前端定位
2. `frontend/01-apps.md` — 找到目标子系统
3. `frontend/02-architecture.md` — 技术栈确认
4. 按需读后续章节

## 维护

- 新增前端子系统时同步更新 `01-apps.md` + `appendix/templates/new-app-checklist.md`；有环境 URL 时同步 `12-environments.md`
- 环境 / 域名变更 → 只更新 `12-environments.md`
- 发布流程 / 构建命令变更 → `11-quality-ops.md`
- 跨 common/ 与 frontend/ 的规约冲突：分支 / commit / 提测 MR 以 **common/** 为准；**前端 QA 整合与发布 MR 源分支**以 `frontend/08-test-handoff.md` + `appendix/templates/release-checklist.md` 为准
