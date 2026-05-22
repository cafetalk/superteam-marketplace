# 前端术语表

格式：**术语** — 在 t-rex 中的含义 + 详读位置（与 `backend/appendix/glossary.md` 对齐）。

---

## 渲染与架构

**SSR（Server-Side Rendering）** — 服务端渲染，页面 HTML 由服务器生成后返回。trex-website 使用 Next.js 16 App Router，**默认即为 Server Component（SSR）**；约 32% 的组件保持服务端渲染（首屏 HTML 由 Node.js 渲染），其余通过 `"use client"` 切换为客户端组件。

**SSG（Static Site Generation）** — 静态站点生成，构建时预生成 HTML。trex-website **不使用** `generateStaticParams`（无传统 SSG），但用 **ISR**（见下条）替代。

**ISR（Incremental Static Regeneration）** — 增量静态再生，介于 SSG 和 SSR 之间，按 `revalidate` 时间间隔后台再生。trex-website 在 sitemap 路由使用（`export const revalidate = 86400`，24 小时再生一次）。

**CSR（Client-Side Rendering）** — 客户端渲染，浏览器端 JS 渲染内容。trex-website 中通过 `"use client"` 指令显式标注（约 315 个文件，~68%）。

**Hydration** — SSR/SSG 页面加载后，客户端 React 接管 DOM 并绑定事件的过程。

**SPA（Single Page Application）** — 单页应用，路由切换不刷新整页。trex-website / trex-2b / dapp-dashboard 均通过 Next.js / SPA 框架支持客户端路由。

**PWA（Progressive Web App）** — 渐进式 Web 应用，支持离线、推送通知等原生应用能力。**t-rex 不使用 PWA**。

---

## 构建与优化

**Code Splitting** — 代码分割，按路由或动态 import 将 bundle 拆分为多个 chunk，减少首屏加载体积。

**Tree Shaking** — 构建时自动去除未使用的代码。SDK 发布需特别注意确保产物支持 tree shaking（使用 ESM 格式）。

**Bundle Analyzer** — 分析构建产物体积的工具（见 `11-quality-ops.md`）。

**Source Map** — 构建产物到源码的映射文件，用于生产环境报错定位。生产环境不暴露给公网（见 `10-security.md`）。

---

## 状态管理

**React Query** — 服务端状态管理库，处理接口数据的缓存 / 加载 / 错误 / 重试。t-rex 中为**【强制】**服务端状态方案（见 `06-state-and-data.md`）。

**Jotai** — 原子化客户端状态管理库。t-rex 中为**【强制】**客户端状态方案（见 `06-state-and-data.md`）。

---

## 错误与监控

**ErrorBoundary** — React 错误边界，捕获子组件树的渲染错误，防止整页白屏（见 `07-error-and-monitoring.md`）。

**BugSnag** — 前端错误监控 SaaS 平台，t-rex 中**【强制】**接入（见 `07-error-and-monitoring.md`）。

**GA（Google Analytics）** — 用户行为分析与埋点，t-rex 中**【强制】**接入（见 `07-error-and-monitoring.md`）。

---

## API 集成

**OpenAPI Codegen** — 从 OpenAPI spec 自动生成类型安全的 API client（见 `05-api-and-integration.md`）。

**GraphQL Codegen** — 从 GraphQL schema 自动生成类型和查询 hooks（见 `05-api-and-integration.md`）。

**CSP（Content Security Policy）** — HTTP 响应头，限制页面可加载的资源来源，防 XSS（见 `10-security.md`）。

---

## Web3 / 链上

**zkTLS** — 基于 TLS 的零知识证明协议，在不泄露原始内容的前提下证明数据来自特定 HTTPS 源。t-rex 中由 trex-zktls / trex-tlsn-plugin 提供（见 `01-apps.md`）。

**Notary** — zkTLS 证明流程中的公证节点，负责见证 TLS 握手并出具证明。

**WASM Provider** — 以 WebAssembly 形式运行的 zkTLS Provider，trex-tlsn-plugin 为此类型（见 `01-apps.md`）。

**MPC（Multi-Party Computation）** — 多方安全计算，trex-tlsn-plugin 基于 MPC TLS 协议实现 TLS 证明。

**Proxy Provider** — 另一类 zkTLS Provider，通过代理节点参与 TLS 握手，trex-zktls 为此类型（见 `01-apps.md`）。

**anchor-sdk** — t-rex JS SDK，封装 anchor-api 调用和链上 Badge Mint（见 `01-apps.md`）。

**passport-sdk** — t-rex JS SDK，封装 passport 检查和 Mint（见 `01-apps.md`）。

**盲签（Blind Signing）** — 用户在未充分理解签名内容的情况下签名，存在安全风险。t-rex 中**禁止**（见 `10-security.md`）。

**Manifest V3** — Chrome Extension 最新 API 标准，使用 Service Worker 替代 background page，权限更精细。trex-extension 遵循此标准（见 `02-architecture.md`）。

---

## 其他

**ESM（ES Modules）** — JavaScript 标准模块系统（`import` / `export`）。SDK 必须输出 ESM 格式（见 `11-quality-ops.md`）。

**CJS（CommonJS）** — Node.js 传统模块系统（`require` / `module.exports`）。SDK 需同时输出 CJS 兼容格式（见 `11-quality-ops.md`）。
