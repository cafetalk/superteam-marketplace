# trex-tech-handbook

`superteam:trex-tech-handbook` — t-rex 生态开发上下文 skill。把架构、命名约定、分支 / commit 规约、提测流程 SOP 等"潜规则"打包给 AI 编码工具和新成员按需加载。

不覆盖 `superteam` 子项目（它有自己的 CLAUDE.md）。

## 快速导航

- 入口 + 完整目录：[`SKILL.md`](SKILL.md)
- 三层结构：
  - [`common/`](common/) — 跨前后端通用规范（GitLab / 分支 / commit / 提测 / CI）
  - [`backend/`](backend/) — Java 后端规范（架构 / 微服务 / 编码 / RPC / 存储 / 日志 / 测试 / 安全 / 可观测性）
  - [`frontend/`](frontend/) — 占位，下一阶段独立推进

## 状态

M1（首发）：框架骨架 + 已知现状占位 + `TODO(@allen)` 待补条目。详见 `docs/skills-design/2026-05-11-trex-tech-handbook.md`。

## 维护

- 设计文档：`docs/skills-design/2026-05-11-trex-tech-handbook.md`
- 实现计划：`docs/skills-design/2026-05-12-trex-tech-handbook-plan.md`
- Linear 跟踪：[TREX-395](https://linear.app/t-rex-v1/issue/TREX-395)
