# 错误处理与监控

## 错误边界（Error Boundary）【强制】

React ErrorBoundary 必须封装关键页面 / 模块入口，防止子树崩溃导致白屏。

- 每个页面级路由入口（`*Page` 组件）用 ErrorBoundary 包裹
- ErrorBoundary 的 fallback UI 显示友好的错误提示，而非空白或技术堆栈
- ErrorBoundary 捕获的错误需上报 BugSnag（`Bugsnag.notify`）

```tsx
<ErrorBoundary FallbackComponent={ErrorFallback} onError={reportToBugsnag}>
  <SomePage />
</ErrorBoundary>
```

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

**事件命名规范**：参考各自项目现有埋点实现

**触发时机**：
- 页面浏览：路由切换时自动触发 `pageview`
- 用户行为：关键按钮点击、表单提交、流程完成等手动埋点
- 禁止在循环中触发 GA 事件

## 后端错误码对接

后端 `WebResult.code` → 前端错误处理：

- 已知错误码按具体业务场景处理（无统一映射表，各 feature 自行处理）
- 未知错误码展示通用兜底文案（"操作失败，请重试"）+ 上报 BugSnag
