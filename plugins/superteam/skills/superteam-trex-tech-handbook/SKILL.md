---
name: superteam-trex-tech-handbook
description: Use when starting any t-rex ecosystem work that is NOT inside the superteam sub-project — loads architecture, microservice catalog, coding standards, branch/commit rules, test handoff SOP for t-rex backend (and placeholder frontend) development.
version: 1.2.0
last_reviewed: 2026-05-15
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
- [`frontend/README.md`](frontend/README.md) — placeholder (separate iteration)

## Conventions

Every chapter uses 阿里巴巴 Java 开发手册 style:
- **【强制】** — mandatory, blocking
- **【推荐】** — strongly recommended
- **【参考】** — informational
- **`〔t-rex 现状〕`** — deviation from industry standard, locked by current practice

## Status

M1.5 (in progress): framework + 22-project current-state catalog + sub-group restructure (incl. `scaffold/`).
Roadmap and open items: `docs/skills-design/2026-05-11-trex-tech-handbook.md`.
