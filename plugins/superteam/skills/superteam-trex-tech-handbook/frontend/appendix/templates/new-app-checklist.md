# 新建前端子系统 Checklist

对标 `backend/appendix/templates/new-service-checklist.md`，按子系统类型分三类。

完成后，将新子系统条目追加到 `frontend/01-apps.md` 并同步更新 `frontend/00-overview.md`。

---

## 类型 A：Web App

适用：trex-website 类、trex-2b 类、dapp-dashboard 类

- [ ] **仓库创建**：在 `Keccak256-evg/t-rex/` 下新建仓库，仓库名符合命名规范
- [ ] **Push Rule 配置**：GitLab 仓库设置 branch name regex + commit message regex（见 `common/02-branch-and-commit.md` + `common/appendix/project-prefix.md`）
- [ ] **技术栈初始化**：框架 / 构建工具 / 包管理器对齐 `frontend/02-architecture.md` Web App 基线
- [ ] **TypeScript `strict` 开启**：`tsconfig.json` 中确认 `"strict": true`
- [ ] **ESLint + Prettier 配置**：对齐团队统一 config（见 `frontend/04-coding-standards.md`）
- [ ] **API client 生成配置**：
  - [ ] 消费 REST API → 配置 OpenAPI codegen（见 `frontend/05-api-and-integration.md`）
  - [ ] 消费 GraphQL API → 配置 GraphQL codegen（见 `frontend/05-api-and-integration.md`）
- [ ] **BugSnag 接入**：初始化 BugSnag SDK，配置 API Key（见 `frontend/07-error-and-monitoring.md`）
- [ ] **GA 接入**：初始化 GA，配置 Measurement ID（见 `frontend/07-error-and-monitoring.md`）
- [ ] **安全基线**：
  - [ ] Token 存储策略确认（禁止 localStorage 存高敏感凭据，见 `frontend/10-security.md`）
  - [ ] XSS：禁止无净化的 `dangerouslySetInnerHTML`
  - [ ] CSP：配置 Content Security Policy 响应头（见 `frontend/10-security.md`）
- [ ] **测试框架初始化**：安装测试框架 + 至少一个示例单测能跑通（见 `frontend/09-testing.md`）
- [ ] **Playwright E2E 初始化**：`e2e/` + `playwright.config.ts` + 至少一条 smoke 用例能跑通（见 `frontend/09-testing.md` §E2E）
- [ ] **注册到 `frontend/01-apps.md`**：按条目模板填写完整条目
- [ ] **登记环境 URL**：在 [`frontend/12-environments.md`](../12-environments.md) 追加环境 / 分支 / 访问地址表

---

## 类型 B：Chrome Extension

**在类型 A 所有项目基础上，额外确认：**

- [ ] **Manifest V3**：`manifest.json` 使用 Manifest V3 格式（禁止 V2）
- [ ] **权限最小化审计**：`permissions` 字段只申请必要权限，逐项说明理由（见 `frontend/10-security.md`）
- [ ] **Extension 构建配置**：
  - [ ] background（Service Worker）/ content / popup / options 各入口正确配置
  - [ ] 开发模式热重载验证
  - [ ] 生产打包产物验证（在 Chrome 开发者模式下可加载）
- [ ] **Chrome Store 提审确认**：
  - [ ] 了解 Chrome Store 提审周期【参考】：
    - 〔t-rex 经验〕trex-extension 历次提审约 **3–7 天**；排期按此预留缓冲
  - [ ] 准备好 Store 资产（截图 / 图标 / 说明文案）
  - [ ] 确认隐私政策 URL
- [ ] **安全**：
  - [ ] 私钥 / 敏感材料不存 localStorage / sessionStorage（见 `frontend/10-security.md`）
  - [ ] 签名请求展示可读内容（防盲签）

---

## 类型 C：JS SDK

**在类型 A 所有项目基础上（跳过 GA / BugSnag / CSP 等 Web 特有项），额外确认：**

- [ ] **ESM + CJS 双产物构建配置**：
  - [ ] `package.json` 中 `exports` 字段正确配置（`import` + `require` 入口）
  - [ ] 构建命令验证 ESM 产物（`*.mjs`）和 CJS 产物（`*.cjs`）
  - [ ] TypeScript 类型声明文件（`*.d.ts`）包含在发布产物中
- [ ] **`dist/` 在 `.gitignore` 中**：构建产物不提交 git
- [ ] **API 稳定性约定**：
  - [ ] 定义公开 API 边界（哪些导出是公开的 stable API）
  - [ ] 版本遵循 semver；breaking change 需 major 版本号递增
  - [ ] `CHANGELOG.md` 维护方式确认
- [ ] **发布到 registry**：
  - [ ] npm registry 或 GitLab registry 发布步骤文档化
  - [ ] CI/CD 自动发布流程配置（可选）
  - [ ] 发布前 `npm pack` 验证产物内容
- [ ] **多环境兼容性验证**：
  - [ ] Node.js 环境可运行
  - [ ] Browser 环境可运行（如适用）
  - [ ] 明确最低支持的 Node.js 版本（在 `package.json` `engines` 字段声明）
