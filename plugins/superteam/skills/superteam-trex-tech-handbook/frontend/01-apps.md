# 前端应用 / SDK 清单 ⭐

t-rex 前端共 10 个子系统（Web App / Extension / SDK / Tool / zkTLS Provider）。  
开发任意子系统前，先在本章找到对应条目，了解仓库地址、技术栈和环境信息。

## 一、核心应用系统

### trex-website
- **类型**：Web App（pnpm monorepo）
- **业务范围**：C 端 Portal + 官网，用户身份、Badge 展示、活动入口
- **技术栈**：Next.js 16.1.0（App Router）/ Tailwind CSS / TypeScript ^5 / pnpm workspace / Vitest
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/t-rex/trex-website
- **本地路径建议**：`{your_workspace}/frontend/trex-website`
- **消费的后端 / 链上 API**：trex-web REST（`swagger-typescript-api` 生成）；anchor-api；passport-api；wagmi + @reown/appkit（Web3 钱包）
- **环境 & 部署**：部署平台为 **kaibinluo 部署系统**（Vercel）；build 含 `oss-upload` + `upload:sourcemap`
  
  | 环境 | 分支 | 访问地址 |
  |---|---|---|
  | Dev | `dev` | https://trex-webdev.vercel.app/ |
  | Beta | `beta` | https://trex-webbeta.vercel.app/ |
  | Pre | `trexpre` | https://trex-webpre.vercel.app/ |
  | Prod | `master` | [www.trex.xyz](https://www.trex.xyz/) |
  
- **关键模块 / 页面**：`app/portal/`（Portal）/ `app/passport/`（Passport）/ `app/auth/`（登录）/ `packages/api/`（API 客户端层）

---

### trex-extension
- **类型**：Chrome / Firefox / Edge / Opera Extension（Manifest V3）
- **业务范围**：浏览器扩展，用户身份验证 + 钱包操作 + zkTLS / TLSNotary 证明 + 多环境 Header 注入
- **技术栈**：Vite 6 + `@crxjs/vite-plugin` / pnpm / TypeScript 5.9 / React 18.3 / Tailwind CSS 3.4 / Redux（react-redux）/ wagmi + viem / `tlsn-js` + `@extism/extism` + `@trex-tls/proxy-browser-extension-sdk`
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/t-rex/trex-extension
- **本地路径建议**：`{your_workspace}/frontend/trex-extension`
- **消费的后端 / 链上 API**：trex-web REST（`swagger-typescript-api` 生成三套 client：trexApi / trexQuestsApi / trexAnchorApi）；zkTLS notary
- **环境 & 部署**：
  
  | 环境 | 详情 |
  |---|---|
  | Prod | [Chrome Web Store](https://chromewebstore.google.com/detail/t-rex/pijboicnfckimnfokpgofmdobghpmpeg) |
  | Dev / Beta | 本地打包安装（Extension ID：`enamjhlahegmpcpnfbcnkodmlghbmcoh`）|
  
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
- **本地路径建议**：`{your_workspace}/frontend/trex-2b`
- **消费的后端 / 链上 API**：trex-web REST（`swagger-typescript-api` 生成）；`@keccak256-evg/anchor-sdk @0.1.46`（注意：scoped 包名，与 trex-website 用的 `anchor-sdk` 无 scope 不同）；`@reown/appkit`（钱包）
- **Monorepo 结构**：
  - `apps/2b-growth-portal/` — **onBoarding**（dev 端口 3000；build 含 `oss-upload`）
  - `apps/2b-dashboard/` — dashboard（dev 端口 3001）
  - 共享能力见仓库根目录 `packages/*`（如 `api`、`ui`、`lib` 等，随仓库演进）
- **环境 & 部署**：与 **trex-website** 相同，经 **kaibinluo 部署系统** 发布至 **Vercel**；环境 / 分支约定一致（Dev→`dev`、Beta→`beta`、Pre→`trexpre`、Prod→`master`）。**2b-growth-portal** 示例如下（**2b-dashboard** 同套流程，域名以各自 Vercel 项目为准）：
  
  | 环境 | 分支 | 访问地址（2b-growth-portal 示例） |
  |---|---|---|
  | Dev | `dev` | https://trex-2b-dev-onboarding.vercel.app |
  | Beta | `beta` | https://trex-2b-beta-onboarding.vercel.app |
  | Prod | `master` | https://prism.trex.xyz |
- **关键模块 / 页面**：onBoarding（核心 B 端入口）/ dashboard
- **测试**：TODO

---

## 二、管理端

### dapp-dashboard
- **类型**：Web App（npm + Turborepo monorepo）
- **package.json name**：`anchor-dashboard`（与仓库目录名 dapp-dashboard 不一致）
- **业务范围**：内部 DApp 管理面板
- **合约文档**：《T-Rex Dashboard》
- **技术栈**：Next.js **14.1**（注意比 trex-website/trex-2b 的 16.x 旧）/ React 18.3 / **npm 10.9.2**（非 pnpm！）/ **Turborepo ^2.6** / TypeScript ^5.9 / Tailwind CSS 3.3 / Jest
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/aspen-platform/team/elaine-ma/dapp-dashboard
- **本地路径建议**：`{your_workspace}/frontend/dapp-dashboard`
- **消费的后端 / 链上 API**：**drex-core GraphQL**（`@graphql-codegen/cli ^5.0.7` + `@graphql-codegen/typescript` 生成；dev schema URL `http://anchor-dashboard.dev.dipbit.xyz/graphql`）；wagmi + viem + thirdweb（Web3）；axios（部分 REST）
- **Monorepo 结构**：`apps/dashboard/` + 多个 `packages/*`（如 `@dapp-dashboard/ui` / `@dapp-dashboard/graphql` / `@dapp-dashboard/web3` / `@dapp-dashboard/middleware` / `@dapp-dashboard/server-actions` 等）
- **环境 & 部署**（Vercel）：
  
  | 环境 | 访问地址 |
  |---|---|
  | Dev | https://dapp-dashboard-dev.vercel.app |
  | Beta | https://dapp-dashboard-beta.vercel.app/ |
  | Prod | https://dapp-dashboard-prod.vercel.app/ |
- **关键命令**：`npm run codegen`（GraphQL codegen）/ `npm run download`（拉 dev 环境 schema）
- **关键模块 / 页面**：`apps/dashboard/`（Next.js app）/ `packages/graphql/`（GraphQL 客户端）/ `packages/web3/`（Web3 集成）/ `packages/server-actions/`（Next.js Server Actions）

---

## 三、SDK 及工具类

### anchor-sdk
- **类型**：JS SDK
- **业务范围**：获取 anchor-api；链上 Mint Badge / Payment / ERC1155 Token 管理；被多个项目集成（dt / dojo / deek / trex / slg）
- **技术栈**：TypeScript ^5 / **Bun**（构建：`bun run scripts/build.ts`）/ **Biome**（lint）/ Jest（test）/ ethers v6 + viem / TypeChain（合约类型绑定）
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/zeek/anchor/anchor-sdk（注意：不在 `Keccak256-evg/t-rex/` 下；另有 GitHub 公开镜像 `github.com/keccak256-evg/anchor-sdk`）
- **本地路径建议**：`{your_workspace}/sdk/anchor-sdk`
- **消费的后端 / 链上 API**：anchor-api（swagger-typescript-api 生成于 `src/generated/`）；链上合约（abi → typechain）
- **环境 & 部署**：npm 公开发布（`anchor-sdk @0.1.45`，无 scope）；`bun run release` 正式发布；`bun run beta` beta 发布
- **NPM exports**：`.`（主入口 `dist/index.js`）+ `./react`（React hooks 子入口 `dist/react/index.js`）
- **关键模块**：`AnchorApiClientV2.ts`（REST client）/ `AnchorERC1155Client.ts`（ERC1155 合约）/ `AnchorPayClient.ts`（支付）/ `src/react/`（React hooks 子包）/ `src/typechain/`（合约 TS 绑定）

---

### passport-sdk
- **类型**：JS SDK
- **业务范围**：检查钱包是否有 passport；发起 Mint passport
- **技术栈**：TypeScript；TODO(@elaine) 构建 / 包管理
- **GitLab 仓库**：TODO(@elaine)
- **NPM 包名**：`@keccak256-evg/passport-sdk`
- **本地路径建议**：`{your_workspace}/sdk/passport-sdk`
- **消费的后端 / 链上 API**：TODO(@elaine) drex-passport；链上合约
- **环境 & 部署**：npm 公开发布

---

### nft-metadata-toolkit
- **类型**：Tool（工具脚本）
- **业务范围**：生成 NFT 图片和对应的 Metadata 元数据
- **技术栈**：TODO(@elaine) Node.js / 脚本语言
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/aspen-platform/team/elaine-ma/nft-metadata-tookit（注意仓库名有拼写错误 `tookit`）
- **本地路径建议**：`{your_workspace}/tools/nft-metadata-toolkit`
- **消费的后端 / 链上 API**：无（离线工具）
- **环境 & 部署**：本地运行，不部署
- **关键模块**：TODO(@elaine)

---

## 四、zkTLS / Tee-TLS 相关

### trex-proxy-browser-extension-sdk
- **类型**：浏览器扩展 SDK（Browser Extension SDK）
- **业务范围**：供浏览器扩展使用的 zkTLS 代理集成 SDK；通过 Offscreen Document + WASM 在 Manifest V3 Extension 中触发 zkTLS 证明流程
- **技术栈**：TypeScript ^4.9.4 / **webpack 5** / npm / React 18.2 + Redux 4 + React Router 6 / Tailwind CSS ^3.3 / `@extism/extism ^1.0.3` / `@trex-tls/attestor-core ^0.2.0` / ethers ^6
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/aspen-platform/team/elaine-ma/trex-proxy-browser-extension-sdk
- **NPM 包名**：`@trex-tls/proxy-browser-extension-sdk @0.3.14`（发布到 GitLab npm registry）
- **本地路径建议**：`{your_workspace}/zktls/trex-proxy-browser-extension-sdk`
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
- **本地路径建议**：`{your_workspace}/zktls/trex-zktls`
- **消费的后端 / 链上 API**：无（静态配置，被 trex-extension 通过 OSS URL 消费）
- **环境 & 部署**：Aliyun OSS

  | 环境 | 分支 | Bucket | Base URL |
  |---|---|---|---|
  | Dev / Beta | `dev` | `drex-dev-new` | `https://drex-dev-new.oss-ap-southeast-1.aliyuncs.com/drex/static/zktls/proxy/providers/` |
  | Pre / Prod | `master` | `drex-prod` | `https://drex-prod.oss-ap-southeast-1.aliyuncs.com/drex/static/zktls/proxy/providers/` |

  - Dev / Beta 发布：根目录 `npm run upload:dev`
  - Prod 发布：[阿里云 OSS 控制台](https://oss.console.aliyun.com/bucket/oss-ap-southeast-1/drex-prod/object?path=drex%2Fstatic%2Fzktls%2Fproxy%2Fproviders%2F) 手动上传
- **关键模块**：`proxy-providers/providers/`（Provider 配置文件目录）

---

### trex-tlsn-plugin
- **类型**：WASM Provider（MPC Provider）
- **业务范围**：基于 TLSNotary / WASM 的 MPC 证明 Provider
- **技术栈**：WASM；TODO(@elaine) Rust / wasm-pack
- **GitLab 仓库**：https://gitlab.com/Keccak256-evg/t-rex/trex-tlsn-plugin
- **本地路径建议**：`{your_workspace}/zktls/trex-tlsn-plugin`
- **消费的后端 / 链上 API**：zkTLS notary
- **环境 & 部署**：Aliyun OSS

  | 环境 | Base URL |
  |---|---|
  | Dev | `https://drex-dev-new.oss-ap-southeast-1.aliyuncs.com/drex/static/zktls/notary` |
  | Beta | `https://drex-beta.oss-ap-southeast-1.aliyuncs.com/drex/static/zktls/notary` |
  | Pre / Prod | `https://drex-prod.oss-ap-southeast-1.aliyuncs.com/drex/static/zktls/notary` |

  `〔t-rex 现状〕` OSS 无 pre 环境 → pre 与 prod 共用 OSS-prod 地址，**新工程不要复制此模式**。WASM 构建命令 + 上传命令见仓库 `README.md`。
- **关键模块**：WASM 证明插件（示例：`duolingo_api_users_DUOLINGO_PLUS.wasm`）；构建命令 + 上传命令见仓库 `README.md`

---

## 新增子系统

新建前端子系统时：
1. 完成 `frontend/appendix/templates/new-app-checklist.md` 对应类型的 Checklist
2. 在本章追加条目
3. 同步更新 `00-overview.md` 的子系统分类

## 维护

- 子系统信息变更（仓库迁移 / 部署地址 / 技术栈升级）需同步更新本章
- TODO(@elaine) 字段在了解实际情况后及时补全
