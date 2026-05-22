# 前端工具链

## 必装工具

| 工具 | 版本 | 说明 |
|---|---|---|
| Node.js | **>=20.0.0**【强制】 | 所有前端工程的运行时基础（来自 trex-website `engines` 字段）|
| 包管理器 | **pnpm >=10.0.0**【强制】 | monorepo 统一使用 pnpm；禁止混用 npm / yarn |
| Git | latest | 版本控制，见 `common/02-branch-and-commit.md` |

**Node.js 版本管理**：使用 `nvm` 或 `fnm`，项目根目录放 `.nvmrc` 锁定版本，执行 `nvm use` 自动切换。  
建议：`.nvmrc` 内容写 `20`（与 `engines: node >=20.0.0` 对齐）。

## 推荐工具

| 工具 | 说明 |
|---|---|
| VS Code / Cursor | 主力 IDE |
| ESLint 插件 | 编辑器内实时 lint 提示 |
| Prettier 插件 | 保存时自动格式化 |
| TypeScript 插件 | 类型检查（VS Code 内置）|
| GitLens | git blame / history 可视化 |
| Chrome DevTools | 调试 Web App + Extension |
| React DevTools | 组件树 + Hook 状态检查 |
| React Query Devtools | `@tanstack/react-query-devtools`（trex-website 已集成）|

## 通用命令速查

以下为约定命令名（具体实现在各子系统 `package.json` 中）：

```bash
# 安装依赖
npm install / pnpm install / yarn

# 启动开发服务器
npm run dev

# 构建生产产物
npm run build

# 运行单测
npm run test
npm run test:watch     # 监听模式

# Lint 检查
npm run lint
npm run lint:fix       # 自动修复

# TypeScript 类型检查
npm run type-check

# 生成 API client（如配置了 codegen）
npm run generate:api
npm run generate:graphql
```

## Chrome Extension 专项命令

```bash
# 打包 Extension（dev 模式，hot reload）
npm run dev

# 打包 Extension（生产产物，用于 Chrome Store 提审）
npm run build

# 加载未打包扩展（开发者模式）
# 1. 打开 chrome://extensions/
# 2. 开启"开发者模式"
# 3. 点击"加载已解压的扩展程序" → 选择 dist/ 目录
```

## zkTLS Provider 专项命令

```bash
# trex-zktls — 上传到 OSS dev/beta 环境
npm run upload:dev

# trex-zktls — prod 环境
# 手动上传 Aliyun OSS 控制台（权限 @elaine）
```

> trex-tlsn-plugin 的 WASM 构建 + OSS 上传命令在仓库 `README.md` 中维护（项目专有命令不收录于本 handbook）。

## 调试工具

| 场景 | 工具 |
|---|---|
| Web App 性能分析 | Chrome DevTools Performance / Lighthouse |
| Bundle 体积分析 | vite-bundle-visualizer / rollup-plugin-visualizer |
| Extension 调试 | Chrome DevTools（background: chrome://extensions → inspect）|
| WASM 调试 | 见 trex-tlsn-plugin 仓库 `README.md` |
| 网络请求调试 | Chrome DevTools Network |
