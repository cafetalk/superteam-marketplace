# 技术栈与脚手架

前端无统一 parent POM，不同类型子系统可能选用不同框架和构建工具。本章按子系统类型定义基线。

## Web App 基线【强制】

适用：trex-website、trex-2b、dapp-dashboard

**统一约定**：
| 维度 | 选型 |
|---|---|
| 框架 | **Next.js**（统一选型）|
| 样式方案 | **Tailwind CSS** + `tailwind-merge` |
| 状态管理 | **React Query**（服务端状态）+ **Jotai**（客户端状态，新工程）|
| API 客户端生成 | swagger-typescript-api（REST）/ @graphql-codegen/cli（GraphQL）|

**各仓库当前实际版本**（`〔t-rex 现状〕` 历史工程混用，不强制迁移）：

| 仓库 | Next.js | React | 包管理器 | Monorepo 工具 | 测试框架 |
|---|---|---|---|---|---|
| trex-website | 16.1 | 18.2 | pnpm | pnpm workspace | Vitest |
| trex-2b | 16.2 | **19.2** | pnpm | pnpm workspace | `node --test` |
| dapp-dashboard | **14.1** | 18.3 | **npm** 10.9.2 | **Turborepo** ^2.6 | Jest |

**新工程基线**（强烈推荐参考 trex-website 配置）：
- Next.js 最新稳定版（App Router）
- React 18.x（除非有 React 19 迁移计划）
- pnpm >=10 + pnpm workspace
- TypeScript ^5
- Tailwind CSS 3.x（v4 仍为新版本，trex-2b 已在试用）
- Vitest（与 Vite 生态一致；trex-website 模式）

`〔t-rex 现状〕`：dapp-dashboard 使用 npm + Turborepo + Next 14，与其他两个 Web App 差异较大；trex-2b 使用 React 19。这些是历史工程现状，新工程优先 pnpm + Next 16+ + React 18。

## Chrome Extension 基线【强制】

适用：trex-extension

| 维度 | 选型 |
|---|---|
| Manifest 版本 | Manifest V3（强制） |
| 构建工具 | **Vite 6** + `@crxjs/vite-plugin`（Chrome Extension Vite 插件）|
| 包管理器 | **pnpm** |
| TypeScript 版本 | **5.9.x** |
| React 版本 | 18.3.x |
| 样式方案 | Tailwind CSS 3.4 |
| 路由 | react-router 6 |
| 状态管理 | **Redux**（`react-redux` + `redux-thunk`）`〔t-rex 现状〕` — Extension 历史使用 Redux，未迁移至 Jotai。新 Web App 仍按 `frontend/06-state-and-data.md` 使用 Jotai。|
| 入口分区 | background / content / popup / options（多 vite.config.ts 分别打包：`vite.config.chrome.ts` / `tlsn-offscreen` / `tlsn-content` 等）|
| 多浏览器 | chrome / firefox / edge / opera（独立 vite config + manifest）|
| 多环境构建 | `pnpm build:dev` / `build:beta` / `build:pre` / `build:prod`（通过 `APP_ENV` 切换）|
| 开发热重载 | nodemon（`nodemon.<browser>.json`）|

## JS SDK 基线【推荐】

适用：anchor-sdk、passport-sdk

| 维度 | 选型（anchor-sdk 为参考实现）|
|---|---|
| 语言 | 纯 TypeScript ^5 |
| 产物格式 | **ESM**（`"type": "module"`，`dist/index.js`）`〔t-rex 现状〕` — anchor-sdk 目前仅输出 ESM，未提供 CJS 兼容产物；新 SDK 建议 ESM + CJS 双产物 |
| 构建工具 | **Bun**（脚本：`bun run scripts/build.ts`；非 tsup / rollup）|
| 包管理器 | Bun（`bun.lock`）|
| Lint | **Biome**（非 ESLint + Prettier；与 Web App 工具链不同）|
| 测试 | Jest |
| 类型声明 | `dist/index.d.ts` 包含在发布产物中 |
| 多入口 | 支持子路径 exports（如 `./react` 对应 React hooks 子包）|
| 链上合约绑定 | TypeChain（`ethers-v6` target）|
| Node 版本 | `engines.node: ">=16.0.0"` |
| 发布目标 | npm registry（`anchor-sdk @0.1.45`，无 scope；`@keccak256-evg/passport-sdk @1.2.0`）|
| 代码托管 | anchor-sdk 在 **GitHub**（`github.com/keccak256-evg/anchor-sdk`），与 GitLab `Keccak256-evg/t-rex/` 不同。`〔t-rex 现状〕` 历史决定，不迁移。|

## zkTLS Provider 基线

适用：trex-zktls（Proxy Provider）、trex-tlsn-plugin（MPC WASM Provider）

| 子系统 | 工具链 |
|---|---|
| trex-zktls | Node.js / TS；`npm run upload:dev` 发布到 OSS（详见仓库 `README.md`）|
| trex-tlsn-plugin | WASM 工具链 + OSS 上传命令在仓库 `README.md` 中维护 |

## 脚手架

前端目前**无统一模板仓**。新工程推荐参考方式：
- **新 Web App**：fork trex-website 的 `apps/trex-site/` 配置（Next.js 16 + pnpm + Vitest + BugSnag + Tailwind）
- **新 Chrome Extension**：fork trex-extension 的 Vite + `@crxjs/vite-plugin` 多浏览器多环境构建模板
- **新 JS SDK**：fork anchor-sdk 的 Bun + Biome + TypeChain + swagger-typescript-api 模板

未来若引入统一脚手架，将在本节填入仓库地址 + 初始化命令。

## 新工程技术栈核查

新建任何前端子系统时，需对照本章对应类型的基线，并在 `frontend/appendix/templates/new-app-checklist.md` 中完成技术栈初始化项。
