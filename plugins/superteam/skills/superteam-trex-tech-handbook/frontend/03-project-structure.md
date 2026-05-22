# 目录与模块划分

前端有三种已验证的目录形态，按子系统类型选用。

## 三种目录形态

| 形态 | 适用 | 划分维度 |
|---|---|---|
| **页面功能型** | Web App（trex-website / trex-2b / dapp-dashboard）| 按页面 / 功能模块（feature-based）|
| **扩展型** | Chrome Extension（trex-extension）| background / content / popup / options 标准 Extension 分区 |
| **库型** | JS SDK（anchor-sdk / trex-proxy-browser-extension-sdk）| src/（核心）/ dist/（产物）/ examples/ |

---

## 形态一：页面功能型（Web App）

trex-website 实际目录（Next.js App Router monorepo）：

```
trex-website/                      # pnpm monorepo 根
├── apps/
│   └── trex-site/                 # 主应用
│       ├── app/                   # Next.js App Router 路由（按页面/功能划分）
│       │   ├── portal/            # Portal 功能
│       │   ├── passport/          # Passport 功能
│       │   ├── auth/              # 登录认证
│       │   ├── extension/         # 插件相关
│       │   └── layout.tsx         # 根布局
│       ├── components/            # 公共 + 功能组件（按 feature 分子目录）
│       │   ├── common/            # 跨功能通用组件
│       │   ├── homePage/          # 首页组件
│       │   ├── portal/            # Portal 组件
│       │   ├── bugsnag/           # BugSnag 初始化封装
│       │   └── ...
│       ├── hooks/                 # 自定义 Hooks（按 feature 分子目录）
│       │   ├── portal/
│       │   ├── auth/
│       │   └── ...
│       ├── api/                   # codegen 产物：WebApi.ts
│       ├── client/                # codegen 产物：TrexClient.ts
│       ├── passportClient/        # codegen 产物：PassportClient.ts
│       ├── config/                # 全局配置
│       ├── contexts/              # React Context
│       ├── public/
│       ├── tailwind.config.ts
│       ├── vitest.config.ts
│       └── package.json
└── packages/
    ├── api/                       # 共享 API 层（供多个 app 使用）
    │   └── src/
    │       ├── trexApi/           # TrexApi.ts + TrexApiProxy.ts
    │       ├── trexAnchorApi/     # TrexAnchorApi.ts + TrexAnchorApiProxy.ts
    │       └── trexQuestsApi/     # TrexQuestsApi.ts + TrexQuestsApiProxy.ts
    ├── firebase/                  # Firebase 初始化封装
    └── ui/                        # 共享 UI 组件库
```

**trex-2b 目录**（pnpm monorepo，3 个 Next.js app + 7 个共享 package）：

```
trex-2b/
├── apps/
│   ├── trex-site/           # landing
│   ├── 2b-growth-portal/    # onBoarding（端口 3000，build 含 oss-upload）
│   └── 2b-dashboard/        # dashboard（端口 3001）
└── packages/
    ├── api/                 # 共享 API 客户端（swagger-typescript-api 生成）
    ├── eslint-config/       # 共享 ESLint 配置
    ├── tailwind-config/     # 共享 Tailwind 配置
    ├── tsconfig/            # 共享 tsconfig 基线
    ├── hooks/               # 共享 hooks
    ├── lib/                 # 共享业务库
    ├── ui/                  # 共享 UI 组件
    └── utils/               # 共享工具
```

**dapp-dashboard 目录**（npm + Turborepo monorepo）：

```
dapp-dashboard/
├── turbo.json              # Turborepo 配置
├── tools/
│   ├── graphql-codegen.yml # GraphQL codegen 配置
│   └── schema_anchor.graphqls
├── apps/
│   └── dashboard/          # Next.js 14 app
└── packages/
    ├── ui/                 # 共享 UI 组件
    ├── graphql/            # GraphQL 客户端（codegen 产物）
    ├── web3/               # Web3 集成（wagmi + viem + thirdweb）
    ├── middleware/         # Next.js middleware
    ├── server-actions/     # Next.js Server Actions
    ├── api-routes/
    ├── components/
    ├── contexts/
    ├── config/
    └── pages/
```

---

## 形态二：扩展型（Chrome Extension）

trex-extension 实际目录（Vite 6 + `@crxjs/vite-plugin` + 多浏览器多环境）：

```
trex-extension/
├── manifest.json                # 默认 manifest（V3）
├── manifest.dev.json            # 开发环境 manifest
├── vite.config.base.ts          # 共享构建配置
├── vite.config.chrome.ts        # Chrome 入口（主构建）
├── vite.config.firefox.ts       # Firefox 构建
├── vite.config.edge.ts          # Edge 构建
├── vite.config.opera.ts         # Opera 构建
├── vite.config.tlsn-content.ts  # TLSNotary content script 单独构建
├── vite.config.tlsn-offscreen.ts# TLSNotary offscreen document 单独构建
├── vite.config.tlsn-popup.ts    # TLSNotary popup 单独构建
├── nodemon.<browser>.json       # 各浏览器开发热重载配置
├── custom-vite-plugins.ts
├── tailwind.config.ts
├── postcss.config.ts
├── public/                      # 静态资源（图标、HTML 模板等）
├── scripts/                     # 构建脚本（如 patch-reclaim-sdk.js）
├── dist_chrome/                 # 构建产物（不入 git）
├── docs/
└── src/
    ├── api/                     # 旧版 REST 客户端（generate:api）
    ├── newApi/                  # 新版 codegen 产物
    │   ├── trexApi/             # TrexApi.ts
    │   ├── trexQuestsApi/       # TrexQuestsApi.ts
    │   └── trexAnchorApi/       # TrexAnchorApi.ts
    ├── teetlsverifyApi/         # Tee-TLS 验证 API
    ├── pages/                   # Extension UI 页面（popup/options 等）
    ├── components/              # 公共 + 业务组件
    ├── hooks/                   # 自定义 Hooks
    ├── config/                  # 全局配置
    ├── firebase/                # Firebase 接入
    ├── tlsn/                    # TLSNotary 核心逻辑
    ├── tlsnReducers/            # TLSNotary Redux reducers
    ├── tlsnUtils/               # TLSNotary 工具函数
    ├── locales/                 # i18n 文案
    ├── utils/                   # 通用工具
    ├── types/                   # 类型定义
    ├── assets/
    ├── global.d.ts
    └── vite-env.d.ts
```

关键特点：
- 多浏览器 × 多环境矩阵构建（每个浏览器独立 vite config + manifest）
- TLSNotary 相关入口（content / offscreen / popup）拆为独立 vite 构建
- 状态管理用 Redux（见 `tlsnReducers/`）— `〔t-rex 现状〕` 历史选型，未迁移 Jotai

---

## 形态三：库型（JS SDK）

anchor-sdk 实际目录：

```
anchor-sdk/
├── README.md
├── CHANGELOG.md
├── LICENSE
├── biome.json                 # Biome lint 配置
├── bun.lock                   # Bun lock 文件
├── package.json
├── tsconfig.json
├── tsconfig.build.json        # 构建专用 tsconfig
├── docs/
├── examples/                  # 使用示例
├── scripts/                   # 构建 / 发布脚本
│   ├── build.ts               # bun run 入口
│   ├── publish.ts             # release / beta 发布
│   └── update-api-docs.sh
└── src/
    ├── index.ts               # 公开 API 主入口
    ├── AnchorApiClientV2.ts   # REST API 客户端
    ├── AnchorERC1155Client.ts # ERC1155 合约客户端
    ├── AnchorPayClient.ts     # 支付客户端
    ├── constants.ts
    ├── types.ts
    ├── react/                 # React hooks 子入口（exports "./react"）
    ├── abi/                   # 智能合约 ABI（JSON）
    ├── typechain/             # TypeChain 生成的合约 TS 绑定
    ├── generated/             # swagger-typescript-api 生成的 REST 客户端
    └── swagger/               # OpenAPI / Swagger spec
```

关键特点：
- 多入口 exports：主入口 + `./react` 子入口（React hooks 独立分包）
- 合约 TS 绑定：通过 TypeChain 从 ABI 生成（`pnpm typechain`）
- REST 客户端：swagger-typescript-api 生成到 `src/generated/`
- 构建：Bun 脚本（非 tsup/rollup）；产物到 `dist/`（不入 git）
- Lint：Biome（与 Web App 的 ESLint + Prettier 不同）

---

## 正反例

```
❌ Web App 所有组件平铺在 /components，页面组件与纯 UI 组件混在一起
❌ SDK 把构建产物 dist/ 提交进 git（dist/ 应在 .gitignore 中）
❌ Chrome Extension 在 content script 里直接读写 localStorage（应通过 background 中转）
✅ 每个 feature 模块自包含：components / hooks / api / types 全在该目录下
✅ 公共 UI 组件无业务逻辑依赖，可跨 feature 复用
```

---

## 新工程目录初始化

按对应形态建立目录骨架，并在 `frontend/appendix/templates/new-app-checklist.md` 中确认目录结构项完成。
