# 前端规范（占位）

`〔t-rex 现状〕`：**前端规范规划中**，由 [TREX-405](https://linear.app/t-rex-v1/issue/TREX-405/) 独立推进。本目录目前仅作占位，避免 SKILL.md 导航 404。

## ⚠️ AI agent 读到此页时

**DO**：
- 遵守 `common/*` 通用规范（分支 / commit / 提测 / Linear 等都适用）
- 参考具体前端仓的 `README.md` + `package.json` + 现有代码模式
- 把"已知前端仓"段（下方）里列出的仓作为**模式 fallback** —— 同类项目用同套技术栈倾向

**DO NOT**：
- 把"占位"理解为"前端无任何规范" —— 缺的是 **handbook 化的明文规范**，不是规范本身
- 自创全新技术栈 / 工程结构 —— 先看现有前端仓怎么做的再决定

## 适用于前端的通用规范（已生效）

即便前端规范尚未填充，前端工作**仍然适用** `common/` 层：

- `common/01-gitlab-and-workspace.md` — GitLab 组织 + 本地工作区目录
- `common/02-branch-and-commit.md` — 分支命名（`dev_*` / `review_*` 等 trex team 新规约）+ commit msg 前缀
- `common/03-test-handoff.md` — 提测流程 SOP
- `common/04-ci-and-release.md` — CI 委托 + 发布 + 回滚

## 已知前端仓（fallback 参考）

GitLab 路径前缀：`gitlab.com/Keccak256-evg/t-rex/`

| Sub-group | 仓 | 形态（粗略） |
|---|---|---|
| `web/` | `trex-website` | 营销 / 落地页 |
| `web/` | `trex-extension` | 浏览器 extension |
| `web/` | `dapp-dashboard` | Web3 dashboard |
| `web/` | `trex-2b` | B2B portal |
| `web/` | `nft-metadata-tookit` | NFT 工具 UI |
| `anchor/` | `anchor-admin` | Node/TS admin SPA |
| `anchor/` | `anchor-dashboard` | Node/TS 用户 dashboard |
| `anchor/` | `anchor-sdk` | Node/TS 客户端 SDK |

栈细节看各仓 `README.md` + `package.json`。AI agent 起新前端工作时**优先参考其中同形态的仓**。

## 前端规范将覆盖的内容（拟，由 TREX-405 推进）

- 技术栈基线（框架 / 构建 / 包管理 / TypeScript）
- 目录与模块划分准则
- 组件库 / 设计系统对接
- 状态管理与数据获取
- 测试策略（unit / e2e）
- 与后端契约（OpenAPI client 生成 / GraphQL codegen）
- 性能与可观测性
- 安全（CSP / token 存储 / XSS / CSRF）

## 维护

- 本 README 在前端规范启动后会被 `frontend/SKILL.md`（或 `00-overview.md`）替代
- 现有前端仓清单变化时同步上方表格
