# 前端总览

## 前端在 t-rex 中的职责

t-rex 前端是面向用户（C 端）、项目方（B 端）与内部运营的 Web 交互层，同时也是链上交互（钱包签名 / NFT Mint / zkTLS 验证）的入口。

前端**不**直接处理业务领域逻辑、合约部署、数据存储 —— 这些由后端微服务、链上合约和数据栈承担。

## 四类子系统

### 一、核心应用系统

面向终端用户和项目方的主要交互入口：

- **trex-website**（Portal + 官网，C 端 Web App）
- **trex-extension**（浏览器扩展，用户身份 + 钱包操作）
- **trex-2b**（B 端 Web App：onboarding / dashboard）

### 二、管理端

内部运营和 DApp 管理工具：

- **dapp-dashboard**（DApp 管理面板，Web App）

### 三、SDK 及工具类

供内部前端工程和外部集成方使用的 JavaScript 库和工具脚本：

- **anchor-sdk**（JS SDK：获取 anchor-api；链上 Mint Badge）
- **passport-sdk**（JS SDK：检查 / Mint passport）
- **nft-metadata-toolkit**（工具脚本：生成 NFT 图片和 Metadata）

### 四、zkTLS / Tee-TLS 相关

浏览器端 TLS 证明基础设施：

- **trex-proxy-browser-extension-sdk**（浏览器扩展 SDK）
- **trex-zktls**（Proxy Provider，Aliyun OSS 部署）
- **trex-tlsn-plugin**（MPC WASM Provider，Aliyun OSS 部署）

各子系统详细条目（仓库 / 技术栈 / 部署地址 / 负责人）见 `01-apps.md`。

## 阅读顺序建议

开发任意前端子系统时，按以下顺序加载上下文：

1. `common/00-overview.md` — t-rex 生态整体背景
2. `common/02-branch-and-commit.md` — 分支 / commit 规范（前端完全复用）
3. `common/03-test-handoff.md` — 通用提测流程（前端有差异，见 `frontend/08-test-handoff.md`）
4. **本文档**（`frontend/00-overview.md`）— 前端定位与分类
5. `frontend/01-apps.md` — 找到你要开发的子系统
6. `frontend/02-architecture.md` — 技术栈基线
7. 按需读 `frontend/03-11` + `frontend/appendix/`

## 与 common 层的关系

`common/` 章节（分支命名 / commit 规范 / 提测 / CI / Linear）前端**完全复用**，无需重复。

前端提测 / 发布与 `common/03`、`common/07`、`common/04` 一致；分支速查见 `frontend/08-test-handoff.md`。

## GitLab Sub-group

全部前端仓库统一在 `Keccak256-evg/t-rex/` 下。
