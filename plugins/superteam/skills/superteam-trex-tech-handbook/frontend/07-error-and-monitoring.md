# 错误处理与监控

各环境前端访问地址见 [`12-environments.md`](12-environments.md)。本章记录 BugSnag / GA **接入配置**；观测控制台入口见 [`12-environments.md#观测控制台`](12-environments.md#观测控制台)。

## 错误边界（Error Boundary）【强制】

React ErrorBoundary 必须封装关键页面 / 模块入口，防止子树崩溃导致白屏。

- 每个页面级路由入口（`*Page` 组件）用 ErrorBoundary 包裹
- ErrorBoundary 的 **fallback UI** 必须展示友好提示（禁止空白或裸堆栈）
- ErrorBoundary 捕获的错误须上报 BugSnag（`Bugsnag.notify`）

**fallback UI 最低要求**：

- 标题 + 简短说明（非技术错误码）
- 至少两种恢复操作 〔来源：团队经验〕：**重试**（重置 boundary state）、**回首页** 或 **刷新页面**
- 使用项目统一 Button / 卡片样式（设计参考：trex-website 仓 `ai-implementation/2025-11-19_refactor_bugsnag-error-boundary-ui.md`）

```tsx
// trex-2b：packages/ui BugsnagErrorBoundary 传入 fallback
<BugsnagErrorBoundary fallback={<ErrorFallback onRetry={...} />}>
  <SomePage />
</BugsnagErrorBoundary>
```

`〔t-rex 现状〕` trex-website `BugsnagErrorBoundary` 仅上报、无 fallback；trex-2b `packages/ui` 支持 `fallback` prop 但各 app 未传入。新代码与存量改造须补齐 fallback。

## BugSnag 集成【强制】

- 前端错误监控工具：BugSnag
- 依赖包：`@bugsnag/js` + `@bugsnag/plugin-react`（React ErrorBoundary 集成）+ `@bugsnag/browser-performance`（性能监控）
- Source map 上传：build 阶段通过 `@bugsnag/source-maps` + `@bugsnag/cli` 自动上传

**API Key 管理**：

| 环境变量 | 用途 |
|---|---|
| `NEXT_PUBLIC_BUGSNAG_API_KEY` | BugSnag API Key（单一 key，所有环境共用）|
| `NEXT_PUBLIC_CLIENT_ENV` | 区分 `prod` / `beta` / `dev`，写入 BugSnag metadata |

**接入参考实现**（trex-website `apps/trex-site/utils/bugsnag.ts`）：

```ts
// 环境推导：基于 window.location.hostname（www.trex.xyz → prod；其他部署 → dev/beta）
// 本地开发（NODE_ENV=development）不上报
Bugsnag.start({
  apiKey: process.env.NEXT_PUBLIC_BUGSNAG_API_KEY,
  plugins: [new BugsnagPluginReact()],
  enabledReleaseStages: environment === "dev" ? ["dev"] : ["prod", "beta"],
  releaseStage: environment,
  onError: (event) => {
    // 过滤已知噪音错误（如 "Minified React error"）
    // 附加 metadata: clientEnv / nodeEnv
  }
})
BugsnagPerformance.start({ apiKey })  // 性能监控独立启动
```

**使用规范**：
- `Bugsnag.notify(error)` — 手动上报已捕获的错误
- `Bugsnag.leaveBreadcrumb(message)` — 关键操作前留下调试痕迹
- 上报时附带必要的 metadata（userId / 当前路由 / 关键业务参数）
- **不在 BugSnag 上报中包含敏感信息**（token / 私钥 / 钱包助记词）
- 通过项目自定义的 `sendError(error, context?)` 辅助函数统一上报入口
- 维护 `IGNORE_BUGSNAG_ERROR` 列表过滤已知噪音错误（如 SSR/CSR hydration 不一致）

**trex-2b 结构化上报**（`packages/libs/src/utils/bugsnag-report.ts`）：

- Growth Portal：`reportGrowthPortalError(error, { flow, stage, ... })`，`flow` 取自 `ONBOARDING_FLOWS`
- Dashboard：`reportDashboardError(error, { flow, stage, ... })`，`flow` 取自 `DASHBOARD_FLOWS`
- 用户拒签钱包（`isUserRejectedWalletError()`）：**不上报**

## GA（Google Analytics）集成

- 埋点工具：Google Analytics

**Measurement ID 多环境管理**【强制】：

每个环境使用**不同的 GA Measurement ID**，对应不同 Firebase 项目，避免数据污染。

| 环境 | Firebase 项目 | Measurement ID（默认值，可被 env 覆盖）|
|---|---|---|
| Prod / Pre | `t-rex-website` | `G-0VDCQ2XJHC` |
| Beta | `t-rex-beta` | `G-R7N22SCT8E` |
| Dev | `t-rex-dev-1e541` | `G-XJEPCQ3RSH` |

环境切换由 `NEXT_PUBLIC_CLIENT_ENV` 决定（`prod` / `pre` / `beta` / `dev`）：

```ts
// packages/firebase/src/config.ts
function resolveFirebaseConfig() {
  const env = (process.env.NEXT_PUBLIC_CLIENT_ENV || '').toLowerCase()
  if (env === 'prod' || env === 'pre') return productionConfig  // pre 复用 prod 配置
  if (env === 'beta') return betaConfig
  if (env === 'dev') return devConfig
  // fallback: NODE_ENV=development → dev；否则 → prod
}
```

**Env 覆盖变量**（不修改源码即可指定）：
- `NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID`
- `NEXT_PUBLIC_FIREBASE_API_KEY` / `NEXT_PUBLIC_FIREBASE_PROJECT_ID` / `NEXT_PUBLIC_FIREBASE_APP_ID` 等

### 事件命名规范【强制】

按产品线固定两套规范；**新埋点不得自创第三套**。

#### trex-website（C 端 Portal / 官网）

| 事件名 | 用途 | `trigger` / 参数 |
|--------|------|------------------|
| `portal_business` | 业务动作信封事件 | `trigger`：与存量埋点一致（**snake_case** 如 `badge_claim`、`view_campaign_detail`；存量 **camelCase** 如 `mintPassport`、`setHandleName` 保留不改） |
| `click` | DOM / 按钮点击 | `trigger` + `buildTrackerProps` 展开字段；源：`data-event-tracker` |
| `login` / `sign_up` | GA4 标准认证事件 | `method` 等 GA4 推荐参数 |
| `portal_api_request` | REST 遥测 | 经 `createInstrumentedFetch` 自动附加 |

- `trigger` 命名：**新埋点优先 snake_case**（`动词_名词`）；存量 camelCase 不批量重命名，避免 GA 断档
- 失败类业务：在 `trigger` 或独立参数中标明结果（如 `badge_zktls_verify_result` + `status`）
- **参数上限** 〔来源：代码 · `trex-website/packages/firebase/src/client.ts`〕：事件名 ≤ **40** 字符；单事件参数 ≤ **25** 个；参数值 ≤ **100** 字符（超出截断）
- 详读：`trex-website/docs/persona-funnel-tracking-audit.md`

#### trex-2b（Growth Portal / Dashboard）

| 规则 | 说明 | 示例 |
|------|------|------|
| 事件名 | **snake_case 离散事件**，不用信封 | `cta_click`、`login_success`、`deposit_fail` |
| 成对结果 | 流程结束用 `*_success` / `*_fail` | `analysis_success`、`sign_out_fail` |
| 自动参数 | 每次 `logGAEvent` 附带 | `current_route`、`source_platform`（`onboarding` / `dashboard`） |
| CTA | `cta_click` + `cta_id`、`cta_text`、`target_route` | Landing hero |

- 详读：trex-2b 仓内 `docs/ga-funnel-events-growth-portal.md`、`docs/dashboard-tracking-report.md`
- **不手动补 `page_view`**（依赖 GA4 自动 page_view）

#### 共用 DOM 埋点

`data-event-tracker` JSON → `buildTrackerProps` → `useDomEventDataTracker` → `logGAEvent("click", { trigger, ... })`（website 与 2b 共用模式）。

**触发时机**【强制】：
- 页面浏览：依赖 GA4 自动 `page_view`（或路由级等价机制）
- 用户行为：关键按钮、表单提交、流程节点完成时手动埋点
- **禁止**在循环、`useEffect` 无依赖刷新、轮询 tick 中重复触发同一 GA 事件

## 用户侧展示规范【强制】

无第三方 toast 库；Web App 使用自定义 `Toast.show({ message, type?: "success" | "error", duration?: 3000 })` 〔来源：代码 · `trex-website/apps/trex-site/components/toast/index.tsx`〕（trex-website `components/toast`；trex-2b `packages/ui/src/toast`，Growth Portal 已挂载 `<ToastViewport />`；`〔t-rex 现状〕` 2b-dashboard **未**挂载 ToastViewport）。

### 分层规则

| 场景 | 用户可见 | BugSnag | GA |
|------|----------|---------|-----|
| 可重试的操作失败（API / 表单） | Toast `type: "error"` | `sendError` / `report*Error` + `stage` | 2b：`{action}_fail`；website：业务 `trigger` 或 `portal_business` |
| 操作成功 | Toast `type: "success"` 或 inline 状态 | 不上报 | 2b：`{action}_success` |
| 用户取消 / 拒签钱包 | 无 toast | **不上报**（2b `isUserRejectedWalletError`；website badge verify 过滤表） |
| 后台轮询 / hydration 失败 | 无 toast | `sendError`（附 `stage`） | 不上报 |
| 阻塞流程（错链、需跳转外链） | **Dialog** 模态 | 视情况 `sendError` | 视情况 |
| React 子树崩溃 | **ErrorBoundary fallback** | 自动 notify | 不上报 |
| 未知 `WebResult.code` | 通用文案「操作失败，请重试」 | `sendError` | 建议 fail 事件 |

### 文案

- 用户可见文案：**英文或产品既定语言**，禁止直接暴露 `error.message` / 堆栈
- 优先使用后端 `msg` / `msgKey` 映射；无映射时用通用兜底句

### Chrome Extension

- 局部 toast hook（`useVerifyFailedToast` 等）或 SidePanel inline 错误
- 系统级通知走 `notifications` API（`NotificationUI`）
- `〔t-rex 现状〕` extension 无 BugSnag——新错误处理仍按上表「用户可见」列，监控待接入 BugSnag 后对齐 Web App

## 后端错误码对接

后端 `WebResult.code` → 前端错误处理：

- 已知错误码按具体业务场景处理（无统一映射表，各 feature 自行处理）
- 未知错误码展示通用兜底文案（"操作失败，请重试"）+ 上报 BugSnag
