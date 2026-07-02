# 多环境地址

> **环境 / 域名变更只维护本文档。** 子系统画像见 [`01-apps.md`](01-apps.md)；构建与发布操作见 [`11-quality-ops.md`](11-quality-ops.md)；BugSnag / GA **接入配置**见 [`07-error-and-monitoring.md`](07-error-and-monitoring.md)。特性分支提测流程见 [`08-test-handoff.md`](08-test-handoff.md)（仅 trex-website、trex-2b 使用特性分支预览）。

## trex-website

C 端 Portal + 官网。仓库与技术栈见 [`01-apps.md`](01-apps.md#trex-website)。

**部署平台**：[kaibinluo 部署系统](https://i18n.kaibinluo.com/build/prj_nlGdLjstKE6Zg0ELpLJ7uPW6gjfB) / [Vercel](https://vercel.com/trex-65b2f62e/trex-web)

| 环境 | 分支     | 访问地址                       |
| ---- | -------- | ------------------------------ |
| Dev  | `dev`    | https://trex-webdev.trex.xyz/  |
| Beta | `beta`   | https://trex-webbeta.trex.xyz/ |
| Pre  | `pre`    | https://trex-webpre.trex.xyz/  |
| Prod | `master` | https://www.trex.xyz/          |

### 特性分支预览（多环境测试）

`dev_*` / `review_*` 等工作流见 [`08-test-handoff.md`](08-test-handoff.md)。

- **测试域名**：https://beta.trex.xyz/
- **通过插件打分支 Header 参考**：[《TREX FRONTEND GROUP 多环境系统使用指南》](https://alidocs.dingtalk.com/i/nodes/6LeBq413JAzzgxd3CZ2XG67z8DOnGvpb?doc_type=wiki_doc)

## trex-2b

B 端 onBoarding + dashboard。仓库与技术栈见 [`01-apps.md`](01-apps.md#trex-2b)。**部署平台同 trex-website**。

### onBoarding（2b-growth-portal）

| 环境 | 分支     | 访问地址                                  |
| ---- | -------- | ----------------------------------------- |
| Dev  | `dev`    | https://trex-2b-dev-onboarding.trex.xyz   |
| Beta | `beta`   | https://trex-2b-beta-onboarding.trex.xyz/ |
| Prod | `master` | https://prism.trex.xyz/                   |

无 Pre 环境。

### 特性分支预览（多环境测试）

`dev_*` / `review_*` 等工作流见 [`08-test-handoff.md`](08-test-handoff.md)。

- **测试域名**：https://prism-beta.trex.xyz/
- **ModHeader 示例**：`X-2b-Feature-Branch: review_260527_gitlabDeploy`

### dashboard（2b-dashboard）

**不单独对外暴露域名**——用户经 onBoarding 入口访问，由 **2b-growth-portal 将路由 rewrite 到 dashboard**（同域下的子路径，非独立公网域名）。本地开发：`2b-dashboard` dev 端口 **3001**（onBoarding 为 3000）。

## dapp-dashboard

内部 DApp 管理面板。仓库与技术栈见 [`01-apps.md`](01-apps.md#dapp-dashboard)。

| 环境 | 分支     | 访问地址                             |
| ---- | -------- | ------------------------------------ |
| Dev  | `dev`    | https://dapp-dashboard-dev.trex.xyz  |
| Beta | `beta`   | https://dapp-dashboard-beta.trex.xyz |
| Prod | `master` | https://dapp-dashboard-prod.trex.xyz |

无 Pre 环境；不使用特性分支预览。

**配套链接**：

- **合约文档**：[《T-Rex Dashboard》](https://alidocs.dingtalk.com/i/nodes/qnYMoO1rWxDDXKoLCKOPqk76W47Z3je9?doc_type=wiki_doc)
- **Swagger**：https://anchordev.dipbit.xyz/swagger-ui/index.html#/AnchorV2
- **Figma**：[Trex 开发文档](https://www.figma.com/design/cdLnaGaisTnutAaEikGCi8/Trex-%E5%BC%80%E5%8F%91%E6%96%87%E6%A1%A3?m=dev)

## trex-extension

浏览器扩展。仓库与技术栈见 [`01-apps.md`](01-apps.md#trex-extension)。

| 环境       | 分支 / 说明              | 详情                                                                                                |
| ---------- | ------------------------ | --------------------------------------------------------------------------------------------------- |
| Prod       | `master`（商店提审基线） | [Chrome Web Store](https://chromewebstore.google.com/detail/t-rex/pijboicnfckimnfokpgofmdobghpmpeg) |
| Dev / Beta | 本地打包                 | Extension ID：`enamjhlahegmpcpnfbcnkodmlghbmcoh`                                                    |

- **Chrome Web Store 发布控制台**：https://chrome.google.com/webstore/devconsole/52b79ed9-e6b8-4d46-b182-e0912143120c（需找 chris 要账号）

## 后端 API / RPC 端点

| 服务                                 | 环境    | 地址                                                         |
| ------------------------------------ | ------- | ------------------------------------------------------------ |
| trex-web REST API                    | Dev     | `https://dev-api.trex.xyz`                                   |
| trex-web REST API                    | Beta    | `https://beta-api.trex.xyz`                                  |
| trex-web REST API                    | Prod    | `https://api.trex.xyz`                                       |
| 链 RPC                               | Testnet | `https://testnetrpc.trex.xyz`                                |
| 链 RPC                               | Prod    | `https://rpc.trex.xyz`                                       |
| dapp-dashboard GraphQL schema（dev） | Dev     | `http://anchor-dashboard.dev.dipbit.xyz/graphql`             |
| anchor-api Swagger                   | Dev     | https://anchordev.dipbit.xyz/swagger-ui/index.html#/AnchorV2 |

passport-sdk 环境配置详见仓库 `src/constants/environment.ts`（见 [`01-apps.md`](01-apps.md#passport-sdk)）。

## 观测控制台

接入配置（API Key、Measurement ID、代码示例）见 [`07-error-and-monitoring.md`](07-error-and-monitoring.md)。以下为**控制台入口**：

| 工具             | 链接                                                                                               |
| ---------------- | -------------------------------------------------------------------------------------------------- |
| BugSnag（prod）  | https://app.bugsnag.com/trex-prod/trex-prod                                                        |
| BigQuery（beta） | https://console.cloud.google.com/bigquery?authuser=0&project=t-rex-beta                            |
| GA               | https://analytics.google.com/analytics/web/?hl=zh-cn#/a355077621p489137222/reports/intelligenthome |

## 配套服务

### bugsnag-webhook

接收 Bugsnag Webhook 错误通知并转发到钉钉。

- **GitLab**：https://gitlab.com/Keccak256-evg/t-rex/bugsnag-webhook
- **Vercel 部署地址**：https://t-rex-bugsnag-webhook.vercel.app/webhook

## trex-zktls

zkTLS Proxy Provider（OSS 静态配置）。仓库见 [`01-apps.md`](01-apps.md#trex-zktls)；发布命令见 [`11-quality-ops.md`](11-quality-ops.md)。

| 环境       | 分支     | Bucket         | Base URL                                                                                  |
| ---------- | -------- | -------------- | ----------------------------------------------------------------------------------------- |
| Dev / Beta | `dev`    | `drex-dev-new` | `https://drex-dev-new.oss-ap-southeast-1.aliyuncs.com/drex/static/zktls/proxy/providers/` |
| Pre / Prod | `master` | `drex-prod`    | `https://drex-prod.oss-ap-southeast-1.aliyuncs.com/drex/static/zktls/proxy/providers/`    |

Prod 手动上传：[阿里云 OSS 控制台](https://oss.console.aliyun.com/bucket/oss-ap-southeast-1/drex-prod/object?path=drex%2Fstatic%2Fzktls%2Fproxy%2Fproviders%2F)（权限 @elaine）

## trex-tlsn-plugin

MPC WASM Provider（OSS）。仓库见 [`01-apps.md`](01-apps.md#trex-tlsn-plugin)；发布命令见 [`11-quality-ops.md`](11-quality-ops.md)。

| 环境       | Base URL                                                                        |
| ---------- | ------------------------------------------------------------------------------- |
| Dev        | `https://drex-dev-new.oss-ap-southeast-1.aliyuncs.com/drex/static/zktls/notary` |
| Beta       | `https://drex-beta.oss-ap-southeast-1.aliyuncs.com/drex/static/zktls/notary`    |
| Pre / Prod | `https://drex-prod.oss-ap-southeast-1.aliyuncs.com/drex/static/zktls/notary`    |

**访问示例**：https://drex-prod.oss-ap-southeast-1.aliyuncs.com/drex/static/zktls/notary/duolingo_api_users_DUOLINGO_PLUS.wasm

> `〔t-rex 现状〕`：OSS 无 pre 环境，pre 与 prod 共用 OSS-prod 地址（现状固化，新工程不要复制）。

## 维护

- 环境 / 域名变更 → **只更新本文档**
- 新增有环境 URL 的 Web App → 同步更新 [`01-apps.md`](01-apps.md) + 本文档对应小节
