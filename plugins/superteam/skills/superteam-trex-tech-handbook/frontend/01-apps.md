# 前端应用 / SDK 清单 ⭐

t-rex 前端共 10 个子系统（Web App / Extension / SDK / Tool / zkTLS Provider）。  
开发任意子系统前，先在本章找到对应条目，了解仓库地址与技术栈；**环境 / 域名见 [`12-environments.md`](12-environments.md)**。

## 一、核心应用系统

### trex-website
- **类型**：Web App（pnpm monorepo）
- **业务范围**：C 端 Portal + 官网，用户身份、Badge 展示、活动入口
- **技术栈**：Next.js 16.1.0（App Router）/ Tailwind CSS / TypeScript ^5 / pnpm workspace / Vitest
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/t-rex/trex-website
- **消费的后端 / 链上 API**：trex-web REST（`swagger-typescript-api` 生成）；anchor-api；passport-api；wagmi + @reown/appkit（Web3 钱包）
- **环境 & 部署**：部署平台为 **kaibinluo 部署系统**（底层 Vercel）；build 含 `oss-upload` + `upload:sourcemap`；环境 / 分支 / 访问地址见 [`12-environments.md#trex-website`](12-environments.md#trex-website)
- **关键模块 / 页面**：`app/portal/`（Portal）/ `app/passport/`（Passport）/ `app/auth/`（登录）/ `packages/api/`（API 客户端层）

---

### trex-extension
- **类型**：Chrome / Firefox / Edge / Opera Extension（Manifest V3）
- **业务范围**：浏览器扩展，用户身份验证 + 钱包操作 + zkTLS / TLSNotary 证明 + 多环境 Header 注入
- **技术栈**：Vite 6 + `@crxjs/vite-plugin` / pnpm / TypeScript 5.9 / React 18.3 / Tailwind CSS 3.4 / Redux（react-redux）/ wagmi + viem / `tlsn-js` + `@extism/extism` + `@trex-tls/proxy-browser-extension-sdk`
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/t-rex/trex-extension
- **消费的后端 / 链上 API**：trex-web REST（`swagger-typescript-api` 生成三套 client：trexApi / trexQuestsApi / trexAnchorApi）；zkTLS notary
- **环境 & 部署**：见 [`12-environments.md#trex-extension`](12-environments.md#trex-extension)
  - 构建命令：`pnpm build:dev` / `build:beta` / `build:pre` / `build:prod`（通过 `APP_ENV` 切换；输出到 `dist_chrome/` 等）
  - 多浏览器构建：`build:chrome` / `build:firefox` / `build:edge` / `build:opera`
  - 开发：`pnpm dev`（nodemon 热重载）
- **关键模块 / 页面**：`src/pages/`（Extension UI）/ `src/newApi/`（REST 客户端）/ `src/tlsn/` + `src/tlsnReducers/` + `src/tlsnUtils/`（TLSNotary 集成）/ `src/teetlsverifyApi/`

---

### trex-2b
- **类型**：Web App（pnpm monorepo：`apps/*` 与 `packages/*`）
- **业务范围**：B 端交互层（项目方 onBoarding 流程入口）
- **技术栈**：Next.js 16.2 / React **19.2** / pnpm workspace / TypeScript ^5 / Tailwind CSS v4（`@tailwindcss/postcss ^4`）/ swagger-typescript-api
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/t-rex/trex-2b
- **消费的后端 / 链上 API**：trex-web REST（`swagger-typescript-api` 生成）；`@keccak256-evg/anchor-sdk @0.1.46`（注意：scoped 包名，与 trex-website 用的 `anchor-sdk` 无 scope 不同）；`@reown/appkit`（钱包）
- **Monorepo 结构**：
  - `apps/2b-growth-portal/` — **onBoarding**（dev 端口 3000；build 含 `oss-upload`）
  - `apps/2b-dashboard/` — dashboard（dev 端口 3001）
  - 共享能力见仓库根目录 `packages/*`（如 `api`、`ui`、`lib` 等，随仓库演进）
- **环境 & 部署**：经 **kaibinluo 部署系统** 发布至 **Vercel**（部署平台同 trex-website）；长期分支 `dev` / `beta` / `master`（无 Pre）；onBoarding / dashboard 地址见 [`12-environments.md#trex-2b`](12-environments.md#trex-2b)
- **关键模块 / 页面**：onBoarding（核心 B 端入口）/ dashboard
- **测试**：
  - **Vitest ^3.2** + `@testing-library/react` + `jsdom`（根目录 `vitest.config.ts` / `vitest.setup.ts`；workspace 分 project：`libs`、`2b-dashboard`、`2b-growth-portal`）
  - **单测文件**：放在源文件同级的 `__tests__/**/*.{test,spec}.{ts,tsx}`（示例：`apps/2b-growth-portal/src/.../__tests__/`、`packages/libs/src/utils/__tests__/`）
  - **仓库级脚本测试**：根目录 `tests/*.mjs`（`node --test`，如 monorepo 结构 / SEO / motion 等约定校验）
  - **常用命令**（仓库根目录）：`pnpm test`（`node --test` + Vitest 全量）/ `pnpm test:unit` / `pnpm test:unit:watch`；按 app 跑：`pnpm exec vitest run --project 2b-growth-portal` 或 `--project 2b-dashboard`
  - **规范**：`.agents/rules/vitest-testing.mdc`；流程与交付见仓库内 `vitest-unit-tests` skill；通用策略见 `frontend/09-testing.md`

---

## 二、管理端

### dapp-dashboard
- **类型**：Web App（npm + Turborepo monorepo）
- **package.json name**：`anchor-dashboard`（与仓库目录名 dapp-dashboard 不一致）
- **业务范围**：内部 DApp 管理面板
- **合约文档**：《T-Rex Dashboard》
- **技术栈**：Next.js **14.1**（注意比 trex-website/trex-2b 的 16.x 旧）/ React 18.3 / **npm 10.9.2**（非 pnpm！）/ **Turborepo ^2.6** / TypeScript ^5.9 / Tailwind CSS 3.3 / Jest
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/aspen-platform/team/elaine-ma/dapp-dashboard
- **消费的后端 / 链上 API**：**drex-core GraphQL**（`@graphql-codegen/cli ^5.0.7` + `@graphql-codegen/typescript` 生成；dev schema URL `http://anchor-dashboard.dev.dipbit.xyz/graphql`）；wagmi + viem + thirdweb（Web3）；axios（部分 REST）
- **Monorepo 结构**：`apps/dashboard/` + 多个 `packages/*`（如 `@dapp-dashboard/ui` / `@dapp-dashboard/graphql` / `@dapp-dashboard/web3` / `@dapp-dashboard/middleware` / `@dapp-dashboard/server-actions` 等）
- **环境 & 部署**（Vercel）：环境地址见 [`12-environments.md#dapp-dashboard`](12-environments.md#dapp-dashboard)
- **关键命令**：`npm run codegen`（GraphQL codegen）/ `npm run download`（拉 dev 环境 schema）
- **关键模块 / 页面**：`apps/dashboard/`（Next.js app）/ `packages/graphql/`（GraphQL 客户端）/ `packages/web3/`（Web3 集成）/ `packages/server-actions/`（Next.js Server Actions）

---

## 三、SDK 及工具类

### anchor-sdk
- **类型**：JS SDK
- **业务范围**：获取 anchor-api；链上 Mint Badge / Payment / ERC1155 Token 管理；被多个项目集成（dt / dojo / deek / trex / slg）
- **技术栈**：TypeScript ^5 / **Bun**（构建：`bun run scripts/build.ts`）/ **Biome**（lint）/ Jest（test）/ ethers v6 + viem / TypeChain（合约类型绑定）
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/zeek/anchor/anchor-sdk（注意：不在 `Keccak256-evg/t-rex/` 下；另有 GitHub 公开镜像 `github.com/keccak256-evg/anchor-sdk`）
- **消费的后端 / 链上 API**：anchor-api（swagger-typescript-api 生成于 `src/generated/`）；链上合约（abi → typechain）
- **环境 & 部署**：npm 公开发布（`anchor-sdk @0.1.45`，无 scope）；`bun run release` 正式发布；`bun run beta` beta 发布
- **NPM exports**：`.`（主入口 `dist/index.js`）+ `./react`（React hooks 子入口 `dist/react/index.js`）
- **关键模块**：`AnchorApiClientV2.ts`（REST client）/ `AnchorERC1155Client.ts`（ERC1155 合约）/ `AnchorPayClient.ts`（支付）/ `src/react/`（React hooks 子包）/ `src/typechain/`（合约 TS 绑定）

---

### passport-sdk
- **类型**：JS SDK
- **业务范围**：与 T-REX Passport 系统交互——检查钱包是否已有 Passport、创建 Passport、多钱包绑定/解绑、升级；供 Web App（如 trex-website）集成
- **技术栈**：TypeScript ^5 / **npm** / **Rollup 4**（`rollup -c` → ESM `dist/`）/ **viem ^2** + **thirdweb ^5**（peerDependencies）/ React Hooks（`react` 为 optional peer）
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/t-rex/sdk/trex-passport-sdk
- **NPM 包名**：[`@keccak256-evg/passport-sdk`](https://www.npmjs.com/package/@keccak256-evg/passport-sdk)
- **消费的后端 / 链上 API**：链上 **PassportRegistry** / **Passport** 合约（ABI 内置于 `src/abi/`）；RPC 按 `Environment`（DEV / BETA / PROD）切换（如 testnet `https://testnetrpc.trex.xyz`、prod `https://rpc.trex.xyz`）；环境配置含 trex-web API Base URL（`dev-api` / `beta-api` / `api.trex.xyz`，见 `src/constants/environment.ts`）
- **环境 & 部署**：npm 公开发布；构建 `npm run build`；发布脚本 `./publish.sh`（需 `npm login`）
- **NPM exports**：`.`（`dist/index.js` + 类型 `dist/index.d.ts`）
- **关键模块**：`PassportSDK.ts`（Thirdweb）/ `ViemPassportSDK.ts`（Viem，推荐）/ `UnifiedPassportSDK.ts`（EIP-1193 统一入口）/ `src/hooks/`（`useUnifiedPassportSDK`、`useWalletPassport` 等）/ `src/abi/`（合约 ABI）/ `src/constants/`（链、地址、环境）

---

### nft-metadata-toolkit
- **类型**：Tool（离线脚本）
- **业务范围**：批量整理 NFT 生成器产出的图片与 JSON 元数据，合并多目录图片编号，输出 **OpenSea 上传** 所需的资源包（`output/images/` + `metadata.csv`）
- **技术栈**：**Node.js 14+**（无 `package.json`，单文件 CommonJS 脚本）/ `fs` + `path` 原生模块
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/t-rex/web/nft-metadata-tookit（仓库目录名拼写为 **`tookit`**，非 `toolkit`）
- **本地路径建议**：`{your_workspace}/tools/nft-metadata-tookit`
- **消费的后端 / 链上 API**：无（离线）；产出 CSV 中的 `external_url` 指向静态图床（默认 `anchor.deek.network`，可在脚本 `CONFIG.baseImageUrl` 修改）
- **环境 & 部署**：仅本地运行，不部署、不发布 npm；运行前将生成器产物放入约定目录后执行 `node opensea-resource-generator.js`
- **目录约定**：`images/`（主系列 PNG）/ `1_1/`（补充系列，接续编号）/ `metadata/metadata.json` + `metadata/collection/*.json`（输入）→ `output/images/` + `output/metadata.csv`（输出）
- **关键模块**：`opensea-resource-generator.js`（主脚本：`CONFIG` 配置、图片合并编号、元数据转 CSV、动态 attributes 列、legend 属性处理）

---

### bugsnag-webhook
- **类型**：配套服务（Webhook 转发）
- **业务范围**：接收 Bugsnag Webhook 错误通知并转发到钉钉
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/t-rex/bugsnag-webhook
- **环境 & 部署**：Vercel；部署地址见 [`12-environments.md#配套服务`](12-environments.md#配套服务)

---

## 四、zkTLS / Tee-TLS 相关

### trex-proxy-browser-extension-sdk
- **类型**：浏览器扩展 SDK（Browser Extension SDK）
- **业务范围**：供浏览器扩展使用的 zkTLS 代理集成 SDK；通过 Offscreen Document + WASM 在 Manifest V3 Extension 中触发 zkTLS 证明流程
- **技术栈**：TypeScript ^4.9.4 / **webpack 5** / npm / React 18.2 + Redux 4 + React Router 6 / Tailwind CSS ^3.3 / `@extism/extism ^1.0.3` / `@trex-tls/attestor-core ^0.2.0` / ethers ^6
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/aspen-platform/team/elaine-ma/trex-proxy-browser-extension-sdk
- **NPM 包名**：`@trex-tls/proxy-browser-extension-sdk @0.3.14`（发布到 GitLab npm registry）
- **消费的后端 / 链上 API**：zkTLS notary / Proxy Provider；`@trex-tls/attestor-core` / `@trex-tls/tls`
- **环境 & 部署**：GitLab npm registry 发布（`publishConfig.registry: https://gitlab.com/api/v4/projects/79771907/packages/npm/`）
- **NPM exports**：`.`（主入口）+ `./background` + `./content` + `./offscreen` + `./interceptor/network` + `./interceptor/injection` + `./download-circuits`
- **关键模块**：`src/background/`（背景页消息路由、Session/Tab 管理）/ `src/content/`（内容脚本 + UI 组件）/ `src/offscreen/`（WASM 证明生成）/ `src/interceptor/`（网络拦截 + 注入脚本）

---

### trex-zktls
- **类型**：zkTLS Proxy Provider（配置数据仓库）
- **业务范围**：Proxy Provider 配置，为 zkTLS 证明提供代理能力；内容为 Provider 规则定义文件，上传至 OSS 后由 Extension 消费
- **技术栈**：Provider 配置文件（JSON/规则定义）；发布脚本 `npm run upload:dev`
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/t-rex/trex-zktls
- **消费的后端 / 链上 API**：无（静态配置，被 trex-extension 通过 OSS URL 消费）
- **环境 & 部署**：Aliyun OSS；环境 / Bucket / Base URL 见 [`12-environments.md#trex-zktls`](12-environments.md#trex-zktls)；发布命令见 [`11-quality-ops.md`](11-quality-ops.md)
- **关键模块**：`proxy-providers/providers/`（Provider 配置文件目录）

---

### trex-tlsn-plugin
- **类型**：WASM Provider（TLSNotary / Extism 插件）
- **业务范围**：为 **trex-extension** 等 TLSNotary 浏览器扩展提供各平台 HTTPS 请求的 MPC 证明插件；`products/` 下按平台维护验证逻辑，产出 `.wasm` 供扩展加载
- **技术栈**：**TypeScript ^5** + **esbuild** + **Extism js-pdk**（`@extism/js-pdk`；构建链：`esbuild` 打包 → `extism-js` 编译为 WASM，需先 `./install.sh` 安装 CLI）/ **npm**；可选 **Rust** + `extism-pdk`（示例 `products/twitter_profile_rs/`，`cargo build`）
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/t-rex/trex-tls/trex-tlsn-plugin
- **本地路径建议**：`{your_workspace}/zktls/trex-tlsn-plugin`
- **消费的后端 / 链上 API**：zkTLS **notary**（本地/远程 Notary Server）；插件内对目标平台 HTTPS API 做 TLSNotary 公证（无独立业务 REST）
- **环境 & 部署**：构建产物上传 **Aliyun OSS**，由 **trex-extension** 按环境拉取；Base URL 见 [`12-environments.md#trex-tlsn-plugin`](12-environments.md#trex-tlsn-plugin)；发布命令见 [`11-quality-ops.md`](11-quality-ops.md)
- **关键命令**：`./install.sh`（安装 `extism-js`）/ `cd products/<平台> && npm run build`（单插件）/ `npm run build:all`（批量构建至 `build/*.wasm`）/ `npm run gen-template`（生成新平台脚手架模板）
- **关键模块**：`products/`（各平台插件，如 `duolingo`、`bilibili`、`github_connect`）/ `scripts/build-all-products.js`（批量构建）/ 各产品 `esbuild.js`（WASM 命名规则 `{api_prefix}_{常量}.wasm`，如 `duolingo_api_users_DUOLINGO_PLUS.wasm`）/ `.cursor/skills/create-platform-verification/`（新平台插件生成技能）

---

## 新增子系统

新建前端子系统时：
1. 完成 `frontend/appendix/templates/new-app-checklist.md` 对应类型的 Checklist
2. 在本章追加条目
3. 同步更新 `00-overview.md` 的子系统分类

## 维护

- 子系统信息变更（仓库迁移 / 技术栈升级）需同步更新本章
- **环境 / 域名变更** → 只更新 [`12-environments.md`](12-environments.md)，不在本章重复维护 URL 表