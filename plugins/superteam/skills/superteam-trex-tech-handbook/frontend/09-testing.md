# 测试策略

## Web App 单测【强制】

- **新工程推荐框架**：**Vitest ^2.1.0**（与 Vite 生态一致；trex-website 已在用）
- **组件测试**：`@testing-library/react ^16.0.0` + `@testing-library/jest-dom ^6.6.0`
- **环境**：jsdom（`jsdom ^25.0.0`，在 vitest.config.ts 中配置 `environment: 'jsdom'`）
- **覆盖范围**：公共组件 / 自定义 Hook / 工具函数 / API 封装层

`〔t-rex 现状〕` 各仓库测试框架不一致：
- trex-website：**Vitest** + Testing Library + jsdom
- trex-2b：**Node.js 内置 `node --test`**（位于 root `tests/` 目录）
- dapp-dashboard：**Jest** + ts-jest

收敛方向：新工程统一 Vitest；存量工程不强制迁移。

测试文件放置规范：
- 与源文件同目录，命名为 `<filename>.test.ts(x)`
- 或集中在 `__tests__/` 目录（按团队约定统一）

```ts
// Hook 测试示例（占位，待用实际用例补全）
import { renderHook } from '@testing-library/react'
import { useBadgeList } from '../hooks/useBadgeList'

test('should return badge list', () => {
  const { result } = renderHook(() => useBadgeList('user-1'))
  // ...
})
```

## Chrome Extension 测试

适用：trex-extension

- **Popup UI 测试**：React Testing Library（与 Web App 相同）
- **Background Service Worker / Content Script 测试**：`〔t-rex 现状〕` trex-extension 仓库当前 `package.json` 未配置测试框架（无 `test` script），主要靠手动多浏览器加载验证；暂不制定强制策略

## SDK 测试

适用：anchor-sdk、passport-sdk、trex-proxy-browser-extension-sdk

- 单测覆盖全部公开 API（导出函数 / 类）
- 需测试 Node.js + Browser 双环境（或明确仅支持一种环境）

## E2E 测试【推荐】

- **工具**：Playwright
- **覆盖范围**：关键用户路径（Badge Mint / Onboarding 完成 / 钱包连接）
- **运行环境**：随 E2E 工具确定后一并规划 CI 集成方式

## Mock 策略

- API 调用在单测中 mock（React Query 的 query function 层 mock）
- 避免 mock 内部实现；优先 mock 边界（网络请求 / 浏览器 API）
- Chrome Extension API（`chrome.*`）需在测试环境中 mock
