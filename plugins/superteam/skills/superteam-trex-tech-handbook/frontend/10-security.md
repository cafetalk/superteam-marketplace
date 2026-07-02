# 安全

## Token / 凭据存储

| 数据类型 | 存储位置 | 禁止 |
|---|---|---|
| JWT / Session Token（高敏感）| httpOnly cookie（后端 Set-Cookie）| ❌ localStorage |
| 临时 UI 状态 / 低敏感偏好 | sessionStorage 或内存 | — |
| 私钥 / 助记词 | 浏览器扩展安全存储 API（仅 trex-extension）| ❌ localStorage / sessionStorage |

**禁止使用 localStorage 存储任何高敏感凭据**（JWT、私钥、session token）。

## XSS 防护

- **禁用 `dangerouslySetInnerHTML`**（除非经过代码审计 + 注释说明内容来源已净化）
- 所有用户输入在渲染前经过 HTML 转义（React 默认处理，注意绕过场景）
- 第三方 HTML 内容必须经 DOMPurify 净化后再渲染

```tsx
// ❌ 不允许
<div dangerouslySetInnerHTML={{ __html: userContent }} />

// ✅ 如必须使用，需净化后并添加注释
import DOMPurify from 'dompurify'
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(userContent) }} />
```

## CSRF

- 使用 SameSite cookie（后端 `trex-web` 配置，前端无需额外处理 cookie 策略）
- 有状态变更的接口（POST / PUT / DELETE）需携带 CSRF token，与后端 `trex-web` 方案对齐
- 前端封装层（`*Proxy.ts`）统一注入 CSRF token，不在组件层单独处理

## CSP（Content Security Policy）【推荐】

trex-website 当前 CSP 配置（`next.config.ts` headers 中）：

```js
{
  key: "Content-Security-Policy",
  value: "frame-ancestors 'self' chrome-extension://*;"
}
// 同时：X-Content-Type-Options: nosniff（防 MIME 嗅探）
```

含义：
- `frame-ancestors 'self' chrome-extension://*` — 限定页面只能被同源页面或 Chrome 扩展嵌入（防 clickjacking）
- 注：当前 CSP 较精简，未限制 `script-src` / `connect-src` 等。

按环境增减 `connect-src` / `frame-src`（如 beta API 子域）；每次变更须在 dev / beta 全站回归（钱包弹窗、Turnstile、zkTLS iframe）。

Chrome Extension 的 CSP 在 `manifest.json` 中配置（Manifest V3 已有默认限制）。

## Web3 签名安全

- **签名请求必须展示可读内容**：用户看到的签名内容必须与实际签名数据一致，防盲签
- **trex-extension 私钥不落存储**：私钥 / 助记词仅保存在内存或扩展安全存储中，**禁止** localStorage / sessionStorage
- **EIP-712 结构化签名**：涉及链上操作的签名优先使用 EIP-712，确保用户可读
- **Passport 接入**：链上 mint 与 REST 双通路见 [`05-api-and-integration.md`](05-api-and-integration.md) §Passport 双通路集成

```
❌ 直接让用户签原始 bytes，不展示语义内容
✅ 展示结构化的签名请求（Action / 金额 / 目标地址），再触发签名
```

## Chrome Extension 权限最小化

- `manifest.json` 中 `permissions` / `host_permissions` 只申请必要权限
- **新 Extension 默认禁止** `<all_urls>`；trex-extension 因 zkTLS 见下文审计例外

### trex-extension 权限审计（2026-06）【参考】

来源：`trex-extension/manifest.json` + `vite.config.base.ts`（Chrome / Firefox / Edge / Opera 共用 base；Firefox background 为 scripts 非 service worker）。

**`permissions`（prod）**：

| 权限 | 用途推断 |
|------|----------|
| `activeTab` | 当前标签页操作 |
| `scripting` | 注入 content script |
| `notifications` | 推送通知 UI |
| `sidePanel` | 侧边栏 TLSN UI |
| `tabs` | 多标签 / 会话管理 |
| `webRequest` | 网络拦截（zkTLS / Reclaim） |
| `storage` | 扩展本地存储 |
| `offscreen` | WASM / TLS 离屏文档 |
| `cookies` | 部分站点会话读取 |

**`host_permissions`**：`<all_urls>` — zkTLS / Reclaim 需在任意 HTTPS 页注入 content script 并 `webRequest` 拦截；**当前功能依赖，不可删除**。新 Extension 若无同等需求，**禁止**默认复制 `<all_urls>`；按目标站清单申请 `host_permissions`。

**收窄方向**（trex-extension 后续工程）：将 TLSN content script 的 `matches` 改为 Provider 配置中的目标域 + trex 域，保留 `webRequest` 最小 host 集；变更须全量 zkTLS 回归 + Chrome Store 审核。

**`content_scripts`**：2 组，均匹配 `<all_urls>`（OAuth 域名在 `exclude_matches` 排除）；TLSN 脚本 `run_at: document_start`。

**`content_security_policy.extension_pages`**：`script-src 'self' 'wasm-unsafe-eval'; object-src 'self'; worker-src 'self';`

**dev overlay**（`manifest.dev.json`）：去掉 `offscreen` / `cookies`；放宽 `frame-src` 含 localhost。

## 第三方依赖清单（安全相关）【参考】

2026-06 `package.json` 盘点（版本随各仓演进，以仓库为准）：

**trex-website**（`apps/trex-site`）：`@bugsnag/*`、`firebase`、`@reown/appkit`、`thirdweb`、`wagmi`/`viem`、`anchor-sdk`、`@keccak256-evg/passport-sdk`、`@reclaimprotocol/browser-extension-sdk`、`@trex-tls/proxy-browser-extension-sdk`、`@marsidev/react-turnstile`

**trex-2b**：Growth Portal — `@keccak256-evg/anchor-sdk`、`@reown/appkit`、`thirdweb`、`wagmi`/`viem`、`ethers`、`@ai-sdk/react`；Dashboard — 无钱包 SDK

**trex-extension**：`@reclaimprotocol/browser-extension-sdk`、`@trex-tls/proxy-browser-extension-sdk`、`@extism/extism`、`tlsn-js`、`firebase`、`wagmi`/`viem`、`crypto-js`

新引入第三方脚本 / SDK 须：说明用途、是否加载远程脚本、是否访问用户数据，并在 PR 中注明。

## 定期安全检查【推荐】

| 措施 | 要求 |
|------|------|
| **依赖漏洞扫描** | MR pipeline 执行 `pnpm audit --audit-level=high`（或 `npm audit`）；high/critical 须修复或登记例外后方可 merge |
| **新依赖 PR** | 说明用途、是否远程脚本、是否接触用户数据 / 钱包 |
| **生成代码** | swagger / codegen 产物不手改；安全审计关注手写 Proxy 与业务层 |

`〔t-rex 现状〕` trex-website / trex-2b 本地 `.gitlab-ci.yml` 未含 audit 步骤；trex-website 另引用 `Keccak256-evg/mugen/fe/ci-template`（以模板实际 stages 为准）。trex-extension 无 CI 配置。新仓初始化时应将 audit 加入 pipeline。
