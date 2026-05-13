# 前端规范（占位）

`〔t-rex 现状〕`：**前端规范规划中，下一阶段独立推进**。本目录目前仅作占位，避免 SKILL.md 导航出现 404 链接。

## 适用于前端的通用规范（已生效）

即便前端规范尚未填充，前端工作**仍然适用** `common/` 层：

- `common/01-gitlab-and-workspace.md` — GitLab 组织 + 本地工作区目录
- `common/02-branch-and-commit.md` — 分支命名（`dev_*` / `review_*` 等 trex team 新规约）+ commit msg 前缀
- `common/03-test-handoff.md` — 提测流程 SOP
- `common/04-ci-and-release.md` — CI 委托 + 发布 + 回滚

## 前端规范将覆盖的内容（拟）

- 技术栈基线（框架 / 构建 / 包管理 / TypeScript）
- 目录与模块划分准则
- 组件库 / 设计系统对接
- 状态管理与数据获取
- 测试策略（unit / e2e）
- 与后端契约（OpenAPI client 生成 / GraphQL codegen）
- 性能与可观测性
- 安全（CSP / token 存储 / XSS / CSRF）

## TODO

- TODO(@allen)：前端规范主笔人 / kickoff 时间
- TODO(@allen)：现有前端仓库清单 + 各自技术栈现状
- TODO(@allen)：前端 GitLab sub-group 路径

## 维护

- 本 README 在前端规范启动后会被 `frontend/SKILL.md`（或 `00-overview.md`）替代
