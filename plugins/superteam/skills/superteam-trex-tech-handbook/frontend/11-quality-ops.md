# 构建与发布

> 各子系统环境 URL / 分支映射见 [`12-environments.md`](12-environments.md)。本章只记录构建质量与发布操作。

## Web App 构建

- **Treeshaking 验证**：构建产物需确认无意外的大依赖（使用 bundle analyzer 检查）
- **Source Map**：
  - 开发 / 测试环境：生成 source map，方便调试
  - 生产环境：**禁止将 source map 暴露给公网**（上传到 BugSnag 后删除，或只在 CI 保留）

## SDK 构建

- **类型声明**：发布时包含 `*.d.ts`
- **产物格式**：
  - 推荐：ESM + CJS 双产物
  - `〔t-rex 现状〕` anchor-sdk 当前仅 ESM（`"type": "module"`，`dist/index.js` + `dist/index.d.ts`）
- **发布流程**：
  - anchor-sdk：`bun run release`（正式版）/ `bun run beta`（beta 版）→ npm 公开发布（`anchor-sdk @0.1.45`，无 scope）
  - passport-sdk：npm 公开发布（`@keccak256-evg/passport-sdk @1.2.0`）
  - 版本遵循 semver；breaking change 需 major 版本号递增

## 发布单【强制】

prod 发布单见 [`appendix/templates/release-checklist.md`](appendix/templates/release-checklist.md)。

## 多环境发布（已知现状）

### Vercel（Web App）

| 子系统         | 部署触发         |
| -------------- | ---------------- |
| trex-website   | push to `master` |
| trex-2b        | push to `master` |
| dapp-dashboard | push to `master` |

- 各 Web App 长期环境分支与 URL 按子系统不同，见 [`12-environments.md`](12-environments.md)（trex-website 含 `pre`；trex-2b / dapp-dashboard 无 `pre`）

### Chrome Web Store（Extension）

- prod 发布：提交 Chrome Web Store 审核
- 〔t-rex 经验〕审核约 **3–7 天** 〔来源：团队经验〕（首次与更新相近；官方无固定 SLA，见 [Review process](https://developer.chrome.com/docs/webstore/review-process)）
- dev / beta：本地打包后手动加载（开发者模式）
- Extension 环境详情见 [`12-environments.md#trex-extension`](12-environments.md#trex-extension)
- 审核流程：参考仓库 README 及 Chrome Web Store 内部操作记录

### Aliyun OSS（zkTLS Provider）

**trex-zktls（Proxy Provider）**

| 环境       | 分支     | 发布方式                            |
| ---------- | -------- | ----------------------------------- |
| Dev / Beta | `dev`    | `npm run upload:dev`                |
| Pre / Prod | `master` | 手动上传 OSS 控制台（权限 @elaine） |

环境 Bucket / Base URL 见 [`12-environments.md#trex-zktls`](12-environments.md#trex-zktls)。

**trex-tlsn-plugin（MPC / WASM Provider）**

WASM 构建命令 + OSS 上传命令见各仓库 `README.md`（项目专有，不收录于 handbook）。

环境 Base URL 见 [`12-environments.md#trex-tlsn-plugin`](12-environments.md#trex-tlsn-plugin)。

## 性能基线【推荐】

Core Web Vitals 目标（适用于 trex-website Portal 与 trex-2b Web App）：

| 指标 | 目标（p75 〔来源：官方 · [Core Web Vitals](https://web.dev/vitals/)〕） | 当前状态 | 测量方式 |
|------|-------------|----------|----------|
| **LCP**（最大内容绘制） | ≤ **2.5 s** 〔来源：官方〕 | Portal **2.8 s**（未达标）/ 2b landing **1.4 s**（达标）〔t-rex 现状〕2026-06-24 Lighthouse desktop | Lighthouse / CrUX |
| **INP**（交互响应，替代 FID） | ≤ **200 ms** 〔来源：官方〕 | TODO | Lighthouse / CrUX |
| **CLS**（布局偏移） | ≤ **0.1** 〔来源：官方〕 | Portal **0** / 2b **0**（均达标）〔t-rex 现状〕2026-06-24 Lighthouse desktop | Lighthouse / CrUX |

`〔t-rex 现状〕` LCP / CLS 来自 2026-06-24 单次 Lighthouse desktop（`www.trex.xyz/portal`、`prism.trex.xyz/landing-page`）；字段 p75 以 CrUX 为准。

发布 prod 前对关键 URL 手动 Lighthouse（Portal 首页、核心转化页、2b onboarding 首屏）；得分低于上表须在发布单记录原因与跟进项。

## Playwright E2E CI【推荐】

工具与目录规范见 [`09-testing.md`](09-testing.md) §E2E。

- **配置文件**：仓库根 `playwright.config.ts`；`baseURL` 指向对应环境（dev / review 预览 URL，见 [`12-environments.md`](12-environments.md)）
- **CI 集成**：GitLab MR pipeline 跑 smoke 子集（`npx playwright test --grep @smoke` 或等价 tag）；全量用例 nightly 或发布前手动触发
- **产物**：失败时上传 `playwright-report/`、`test-results/` 为 CI artifact
- **门禁**：暂不阻塞 merge；提测前开发者须确认关键路径 E2E 通过

`〔t-rex 现状〕`：各 Web App 仓库 Playwright CI 尚未统一接入；trex-website 优先落地。

## Lighthouse CI【推荐】

**策略**（与 Playwright E2E 一致）：**不阻塞 MR merge**；发布前手动 Lighthouse 为主；可选在 MR pipeline 跑 Lighthouse 作回归参考。

**trex-website 优先落地**可选 CI（artifact 上传报告）：

```json
// lighthouserc.json（仓库根）
{
  "ci": {
    "collect": {
      "url": ["https://www.trex.xyz/portal"],
      "numberOfRuns": 1
    },
    "assert": {
      "assertions": {
        "categories:performance": ["warn", { "minScore": 0.8 }],
        "largest-contentful-paint": ["warn", { "maxNumericValue": 2500 }],
        "cumulative-layout-shift": ["warn", { "maxNumericValue": 0.1 }],
        "interaction-to-next-paint": ["warn", { "maxNumericValue": 200 }]
      }
    },
    "upload": { "target": "temporary-public-storage" }
  }
}
```

`lighthouserc.json` 指标来源：`minScore` **0.8** 〔来源：团队经验〕；`numberOfRuns` **1** 〔来源：团队经验〕；`2500` / `0.1` / `200` 〔来源：官方 · 与上表 CWV 一致〕。

- `assert` 级别用 **warn**（不 fail pipeline）；阈值与上表 CWV 对齐
- 2b 可对 onboarding 预览 URL 复制同配置，改 `collect.url`
- `〔t-rex 现状〕` 各仓尚未提交 `lighthouserc.json`；按上模板新增即可

## Bundle Analyzer

- Vite 使用 `vite-bundle-visualizer` / `rollup-plugin-visualizer`
- webpack 使用 `webpack-bundle-analyzer`
- 建议在每次发布前手动运行一次，检查是否有意外的大依赖
