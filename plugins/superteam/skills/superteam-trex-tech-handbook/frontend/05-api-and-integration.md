# API 契约消费与集成

后端契约定义在后端侧（`trex-web` OpenAPI yaml + `drex-core` GraphQL schema）。  
前端职责是**正确消费**——生成类型安全客户端，不手写重复类型。

## REST 客户端生成【推荐】

- **契约源**：后端 OpenAPI / Swagger JSON spec（`*.json`，放在各 `*Api/` 目录下，如 `trex_anchor_api.json`）
- **生成工具**：**`swagger-typescript-api` ^13.1.1**（非 orval / openapi-typescript-codegen）
- **生成产物不手改原则**：与后端 OpenAPI Delegate 模式对称——后端不改生成的 Controller，前端不改生成的 client
- **消费方**：trex-website（5 套 client：trexApi / trexAnchorApi / trexQuestsApi / passportClient / webApi）；trex-2b（共享 `packages/api/`）；trex-extension（3 套 client：trexApi / trexQuestsApi / trexAnchorApi 在 `src/newApi/`）；anchor-sdk（`src/generated/`）

**trex-website 已有的生成脚本**（参考模板）：

```bash
# 根 monorepo 级别（packages/api/）
pnpm generate:portal_anchor_api   # packages/api/src/trexAnchorApi/TrexAnchorApi.ts
pnpm generate:portal_quests_api   # packages/api/src/trexQuestsApi/TrexQuestsApi.ts

# apps/trex-site 应用级别
pnpm generate:api          # client/TrexClient.ts（主 REST API）
pnpm generate:passportApi  # passportClient/PassportClient.ts（passport API）
pnpm generate:webApi       # api/WebApi.ts（Web API）
```

**Proxy 包装模式**【强制】：每个生成的 `*Api.ts` 对应一个手写的 `*Proxy.ts`，负责：
- 注入鉴权 Headers（`jwt_token` / `chain_id` / `client_id`）
- Token 刷新逻辑
- 实例化和配置 base URL

```
生成产物（不手改）     手写包装层（可修改）
TrexAnchorApi.ts  →  TrexAnchorApiProxy.ts
TrexQuestsApi.ts  →  TrexQuestsApiProxy.ts
TrexApi.ts        →  TrexApiProxy.ts
```

典型工作流：

```
后端更新 OpenAPI spec JSON → 替换本地 *.json → 运行 pnpm generate:* → 产物更新 → PR review
```

## GraphQL Codegen【推荐】

- **契约源**：`drex-core` `core-graphql` GraphQL schema
- **生成工具**：**`@graphql-codegen/cli ^5.0.7`** + `@graphql-codegen/typescript` + `@graphql-codegen/typescript-resolvers`
- **消费方**：**dapp-dashboard**（已确认在用，配置在 `tools/graphql-codegen.yml`）
- **dev 环境 schema URL**：`http://anchor-dashboard.dev.dipbit.xyz/graphql`

典型工作流（dapp-dashboard）：

```bash
npm run download   # get-graphql-schema http://anchor-dashboard.dev.dipbit.xyz/graphql > tools/schema_anchor.graphqls
npm run codegen    # graphql-codegen --config tools/graphql-codegen.yml
```

生成的 TypeScript 客户端放在 `packages/graphql/`，被 `apps/dashboard/` 消费。

## 链上 / zkTLS API 集成

适用子系统：trex-website / trex-extension / anchor-sdk / trex-proxy-browser-extension-sdk

**anchor-sdk 集成**（已在 trex-website 使用）：
- npm 包：`anchor-sdk @0.1.45`（无 scope 前缀）
- 调用：通过 `TrexAnchorApiProxy` 包装后消费 anchor REST API；链上 Mint 由 anchor-sdk 封装
- 与其他 API client 的关系：`TrexAnchorApi` 生成自 `trex_anchor_api.json`，`TrexAnchorApiProxy` 注入 chain_id 等链相关 headers

**Web3 钱包集成**（trex-website 使用）：
- `wagmi @2.15.2` + `viem @2.38.6` — EVM 链交互
- `@reown/appkit @1.7.3`（WalletConnect v3 的继任者）— 多链钱包连接 UI
- `@reown/appkit-adapter-wagmi` + `@reown/appkit-adapter-solana` — 多链适配器
- `thirdweb @5.105.29` — 辅助链上操作

**zkTLS / proxy-sdk 集成**（trex-website 使用）：
- npm 包：`@trex-tls/proxy-browser-extension-sdk @0.3.14`（即 trex-proxy-browser-extension-sdk 的发布形态）

**trex-tlsn-plugin WASM 加载**（trex-website MPC TEE TLS 验证）：

WASM 产物由 `trex-tlsn-plugin` 构建后上传至 Aliyun OSS；前端**按 URL 加载 OSS 上的 `.wasm` 文件**，不经 npm 打包进 bundle。

- **OSS Base URL**：按环境取 [`12-environments.md` §trex-tlsn-plugin](12-environments.md#trex-tlsn-plugin) 表中 `Base URL`（由 `NEXT_PUBLIC_CLIENT_ENV` 映射 dev / beta / pre / prod）
- **插件 URL 规则**：`${ossUrl}/${targetId}_${targetName}.wasm`（`targetId`、`targetName` 来自 badge condition）
- **调用方式**：经浏览器 TLSNotary 客户端 `tlsn.connect()` → `client.runPlugin(pluginUrl)`

```ts
const pluginUrl = `${ossUrl}/${targetId}_${targetName}.wasm`;
const client = await (window as any).tlsn.connect();
const pluginResult = await client.runPlugin(pluginUrl);
```

参考实现：`trex-website` `apps/trex-site/hooks/portal/badges/verify/useMpcTeeTlsVerification.tsx`。

## Passport 双通路集成【强制】

`drex-passport`（后端 Java 服务，OpenAPI 标签 Passport / Auth）与链上 Passport 合约是**两条独立通路**，trex-website 同时使用：

| 通路 | 用途 | 技术 | trex-website 落点 |
|------|------|------|-------------------|
| **链上** | Mint / 查链上 Passport 状态 | npm `@keccak256-evg/passport-sdk`（`PassportSDK`） | `hooks/useMintPassport.tsx`、`components/portal/main/portalLogin/MintPassPort.tsx` |
| **REST** | 登录、会话、`/v1/passport/me` 等业务身份 | `swagger-typescript-api` → `passportClient/PassportClient.ts` + `*Proxy.ts`；Portal 主路径亦经 `client/TrexClient.ts` | `passportClient/`、`hooks/portal/usePortalPassport.ts` |

**链上 SDK 接入要点**：

```ts
// 动态 import，避免 SSR 打包问题
const { PassportSDK } = await import("@keccak256-evg/passport-sdk");
const sdk = new PassportSDK({
  chain: thirdweb_trexChain,
  registryAddress: process.env.NEXT_PUBLIC_PASSPORT_CONTRACT_ADDRESS,
  client: thirdweb_client,
  account: activeAccount,
});
await sdk.checkWalletHasPassport(address);
await sdk.createPassport(); // 用户确认后
```

- 合约地址：`NEXT_PUBLIC_PASSPORT_CONTRACT_ADDRESS`（默认 Registry `0x1B326360Ec9E3cEF6129173D35b86a6803e5751F`，链 ID 1962，见 passport-sdk `src/constants/addresses.ts`）
- SDK 还导出 `ViemPassportSDK`、`UnifiedPassportSDK` 与 React hooks（`useUnifiedPassportSDK` 等）；新集成优先评估 `UnifiedPassportSDK`

**REST 接入要点**：

```bash
pnpm generate:passportApi   # → passportClient/PassportClient.ts（不手改）
```

- Base URL：`apps/trex-site/config/serverUrl.ts`（prod `api.trex.xyz`，dev `api.trex.dev.dipbit.xyz`，beta `api.trex.beta.dipbit.xyz`）
- OpenAPI 源：`apps/trex-site/passportClient/api.json`
- Proxy 层注入鉴权 Header，与 TrexApi 模式一致（见上文 Proxy 包装模式）

**签名安全**（与 `10-security.md` Web3 章节对齐）：链上 `createPassport` 前须展示可读操作说明；禁止盲签原始 bytes。

`〔t-rex 现状〕` **已知偏差**：`passportClient/RegistrationProvider.tsx` 将 `passport_token` 写入 `localStorage`，与本章 token 存储【强制】冲突——应迁移至 httpOnly cookie（或后端会话方案），不得长期保留现状。trex-2b 当前未集成 passport-sdk。

## 手写调用兜底规约

无代码生成时（如内部临时接口 / 第三方 API）：

- 统一封装 `fetch` / `axios`，不在组件内直接散落调用
- 封装层放在 `src/api/` 或对应 feature 的 `api/` 目录下
- 请求 / 响应类型手动定义在 `*.types.ts` 中，并添加注释说明此为手工定义、契约来源

## 错误处理对接

后端统一返回 `WebResult<T>` 格式：

```ts
interface WebResult<T> {
  code: string   // 错误码（"0" 或 "0000" 为成功，其余为失败）
  msg: string
  data: T | null
}
```

前端处理规则：
- `code` 非成功值时，按具体业务场景处理（无统一映射表，各 feature 自行处理）
- 网络错误 / 超时需与业务错误码分开处理

## 反例

```
❌ 手写与 OpenAPI spec 重复的 TypeScript 类型
❌ 在 React 组件的 useEffect 里直接 fetch，没有封装
❌ 修改 codegen 生成的产物（每次 generate 会覆盖）
❌ catch 块吞掉所有错误而不上报 BugSnag
```
