# 构建质量与运维

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

## 多环境部署（已知现状）

### Vercel（Web App）

| 子系统 | prod URL | 部署触发 |
|---|---|---|
| trex-website | [www.trex.xyz](https://www.trex.xyz/) | push to master |
| trex-2b | prism.trex.xyz | push to master |
| dapp-dashboard | dapp-dashboard-prod.vercel.app | push to master |

- dev / beta / pre 环境：trex-website 使用 `dev` / `beta` / `trexpre` 分支对应独立 Vercel 部署（见 `01-apps.md` trex-website 条目）；其他 Web App 的分支约定参见 `01-apps.md` 各条目环境表

### Chrome Web Store（Extension）

- prod 发布：提交 Chrome Web Store 审核
- dev / beta：本地打包后手动加载（开发者模式）
- 审核流程：参考仓库 README 及 Chrome Web Store 内部操作记录

### Aliyun OSS（zkTLS Provider）

**trex-zktls（Proxy Provider）**

| 环境 | 分支 | Bucket | Base URL | 发布方式 |
|---|---|---|---|---|
| Dev / Beta | `dev` | `drex-dev-new` | `https://drex-dev-new.oss-ap-southeast-1.aliyuncs.com/drex/static/zktls/proxy/providers/` | `npm run upload:dev` |
| Pre / Prod | `master` | `drex-prod` | `https://drex-prod.oss-ap-southeast-1.aliyuncs.com/drex/static/zktls/proxy/providers/` | 手动上传 OSS 控制台（权限 @elaine）|

**trex-tlsn-plugin（MPC / WASM Provider）**

| 环境 | Base URL |
|---|---|
| Dev | `https://drex-dev-new.oss-ap-southeast-1.aliyuncs.com/drex/static/zktls/notary` |
| Beta | `https://drex-beta.oss-ap-southeast-1.aliyuncs.com/drex/static/zktls/notary` |
| Pre / Prod | `https://drex-prod.oss-ap-southeast-1.aliyuncs.com/drex/static/zktls/notary` |

WASM 构建命令 + OSS 上传命令见各仓库 `README.md`（项目专有，不收录于 handbook）。

> `〔t-rex 现状〕`：trex-tlsn-plugin OSS 无 pre 环境，pre 与 prod 共用 OSS-prod 地址（现状固化，新工程不要复制）。

## 性能基线【推荐】

Core Web Vitals 目标值（TODO(@elaine) 确认并填入实际目标）：

| 指标 | 目标 | 当前状态 |
|---|---|---|
| LCP（最大内容绘制）| TODO | TODO |
| FID / INP（交互响应）| TODO | TODO |
| CLS（布局偏移）| TODO | TODO |

## Lighthouse CI

TODO(@elaine)：是否在 CI 中接入 Lighthouse CI 自动化性能检测？  
如接入，配置文件放 `lighthouserc.json`，在 MR CI pipeline 中运行。

## Bundle Analyzer

- Vite 使用 `vite-bundle-visualizer` / `rollup-plugin-visualizer`
- webpack 使用 `webpack-bundle-analyzer`
- 建议在每次发布前手动运行一次，检查是否有意外的大依赖
