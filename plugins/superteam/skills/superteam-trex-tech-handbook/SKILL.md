---
name: superteam-trex-tech-handbook
description: Use when starting any t-rex ecosystem work that is NOT inside the superteam sub-project — loads architecture, microservice catalog, coding standards, branch/commit rules, test handoff SOP for t-rex backend and frontend development.
version: 1.2.0
last_reviewed: 2026-05-21
status: ready
---

# t-rex Tech Handbook

Development context pack for the **t-rex ecosystem** (excluding the `superteam` sub-project, which has its own CLAUDE.md). Structured in three layers — `common/`, `backend/`, `frontend/` — and loaded on demand.

## When to use

- Starting / planning a new task (when to create a Linear issue + how to describe it)
- Scaffolding a new t-rex service
- Naming decisions (package / class / branch / commit)
- Before code review
- Before commit (to verify Push Rule compliance)
- Before test handoff / release
- Onboarding to t-rex backend / frontend

## Navigation

### Common (cross-stack)
- [`common/00-overview.md`](common/00-overview.md) — t-rex ecosystem overview
- [`common/01-gitlab-and-workspace.md`](common/01-gitlab-and-workspace.md) — GitLab group/sub-group + local workspace
- [`common/02-branch-and-commit.md`](common/02-branch-and-commit.md) — branch naming + commit message + Push Rule regex + git worktree convention
- [`common/03-test-handoff.md`](common/03-test-handoff.md) — **提测 SOP**（`dev_*` → `review_*` MR，team lead 审）
- [`common/04-ci-and-release.md`](common/04-ci-and-release.md) — CI delegation + **发布 SOP (`beta_*` → `master`，发布 CI 自动建，研发负责人审)** + 灰度 + 回滚
- [`common/05-task-tracking.md`](common/05-task-tracking.md) — **Linear issue 生命周期 + 粒度 + 串联代码**
- [`common/06-development-flow.md`](common/06-development-flow.md) — **研发过程 端到端 SOP + Code review 自检 checklist**
- [`common/07-testing-process.md`](common/07-testing-process.md) — **测试过程 SOP（QA 整合 `review_*` → `beta_<date>_<keyword>` + k8s beta env 测试 + sign-off）**
- [`common/08-release-record.md`](common/08-release-record.md) — 提测/发布记录落 git（superteam-trex-delivery）
- [`common/appendix/project-prefix.md`](common/appendix/project-prefix.md) — full Push Rule regex + project prefix history

### Backend (Java)
- [`backend/00-overview.md`](backend/00-overview.md)
- [`backend/01-microservices.md`](backend/01-microservices.md) — ~10 microservice catalog
- [`backend/02-architecture.md`](backend/02-architecture.md) — trex-framework + trex-scaffold
- [`backend/03-module-design.md`](backend/03-module-design.md) — Gateway vs Dubbo domain service
- [`backend/04-coding-standards.md`](backend/04-coding-standards.md) — package naming (xyz.trex / com.drex) + class suffixes
- [`backend/05-rpc-and-api.md`](backend/05-rpc-and-api.md)
- [`backend/06-data-and-storage.md`](backend/06-data-and-storage.md)
- [`backend/07-exception-and-logging.md`](backend/07-exception-and-logging.md)
- [`backend/08-testing.md`](backend/08-testing.md)
- [`backend/09-security.md`](backend/09-security.md)
- [`backend/10-quality-ops.md`](backend/10-quality-ops.md)
- [`backend/appendix/`](backend/appendix/) — glossary, toolchain, templates

### Frontend
- [`frontend/00-overview.md`](frontend/00-overview.md) — 前端定位；四类子系统概述
- [`frontend/01-apps.md`](frontend/01-apps.md) — 10 个前端子系统清单（Web App / Extension / SDK / zkTLS Provider）
- [`frontend/02-architecture.md`](frontend/02-architecture.md) — 技术栈基线（Web App / Extension / SDK / WASM Provider）
- [`frontend/03-project-structure.md`](frontend/03-project-structure.md) — 三种目录形态（页面功能型 / 扩展型 / 库型）
- [`frontend/04-coding-standards.md`](frontend/04-coding-standards.md) — 文件 / 组件 / TypeScript 命名规范
- [`frontend/05-api-and-integration.md`](frontend/05-api-and-integration.md) — REST codegen / GraphQL codegen / 链上 API 集成
- [`frontend/06-state-and-data.md`](frontend/06-state-and-data.md) — React Query（服务端状态）+ Jotai（客户端状态）
- [`frontend/07-error-and-monitoring.md`](frontend/07-error-and-monitoring.md) — ErrorBoundary；BugSnag；GA
- [`frontend/08-test-handoff.md`](frontend/08-test-handoff.md) — 前端提测 / 发布分支（`dev_*` → `review_*` → `beta_*` → `master`）
- [`frontend/09-testing.md`](frontend/09-testing.md) — Web App / Extension / SDK 测试策略
- [`frontend/10-security.md`](frontend/10-security.md) — token 存储；XSS；Web3 签名安全；Extension 权限
- [`frontend/11-quality-ops.md`](frontend/11-quality-ops.md) — 多环境部署（Vercel / OSS / Chrome Store）
- [`frontend/appendix/`](frontend/appendix/) — glossary, toolchain, new-app-checklist

## Conventions

Every chapter uses 阿里巴巴 Java 开发手册 style:
- **【强制】** — mandatory, blocking
- **【推荐】** — strongly recommended
- **【参考】** — informational
- **`〔t-rex 现状〕`** — deviation from industry standard, locked by current practice

## Status

- **Backend + Common (M1.5, 2026-05-21)**: 30 微服务 + 6 基础设施 + 5 agentic catalog；Push Rule v3.0；Owner 字段恢复；服务关系图 3 张 mermaid 落地。详见 `backend/01-microservices.md` 全局视图 + 服务关系图段。
- **Frontend (M3, in progress, by @elaine)**: 11 章 + appendix 已 scaffolded；`01-apps.md` 含 10 子系统条目；C5–C7 仍有 TODO(@elaine) 待 field research。
- Roadmap 与 open items: `docs/skills-design/2026-05-11-trex-tech-handbook.md`。
