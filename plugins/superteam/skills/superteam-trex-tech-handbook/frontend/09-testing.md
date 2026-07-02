# 测试策略

## Web App 单测【强制】

- **新工程推荐框架**：**Vitest ^2.1.0**（与 Vite 生态一致；trex-website 已在用）
- **组件测试**：`@testing-library/react ^16.0.0` + `@testing-library/jest-dom ^6.6.0`
- **环境**：jsdom（`jsdom ^25.0.0`，在 vitest.config.ts 中配置 `environment: 'jsdom'`）
- **覆盖范围**：公共组件 / 自定义 Hook / 工具函数 / API 封装层

`〔t-rex 现状〕` 各仓库测试框架不一致：
- trex-website：**Vitest** + Testing Library + jsdom
- trex-2b：**Vitest ^3.2**（workspace projects：`libs` / `2b-dashboard` / `2b-growth-portal`）+ 根目录 `tests/*.mjs`（**`node --test`**，monorepo 结构 / SEO 等约定校验）
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

适用：Web App（trex-website、trex-2b、dapp-dashboard）

- **工具**：Playwright（`@playwright/test ^1.49.0`）
- **覆盖范围**：关键用户路径（Badge Mint / Onboarding 完成 / 钱包连接）
- **目录规范**：仓库根目录 `e2e/`，用例 `*.spec.ts`；配置 `playwright.config.ts`
- **运行**：本地 `npx playwright test`；对标环境 URL 见 [`12-environments.md`](12-environments.md)
- **CI**【推荐】：MR pipeline 跑 smoke 子集；全量用例可在 nightly 或发布前触发；**暂不阻塞 merge**
- **提测门禁**：仓库已配置 Playwright 时，提测前关键路径 E2E 须本地 / CI 通过（见 [`08-test-handoff.md`](08-test-handoff.md)）

`〔t-rex 现状〕`：各 Web App 仓库尚未统一接入 Playwright；**优先在 trex-website 落地**，其余仓库随需求跟进。

Chrome Extension（trex-extension）E2E 暂不强制，继续依赖手动多浏览器验证；后续可选用 Playwright 加载 unpacked extension。

JS SDK（anchor-sdk 等）不做浏览器 E2E，用单测覆盖。

## 覆盖率【推荐】

### 目标

| 范围 | lines 目标 | 说明 |
|------|------------|------|
| 新写的工具函数 / hooks / API 封装 | **≥ 80%** 〔来源：团队经验〕 | PR 应含对应 `*.test.ts(x)` |
| 新写的 UI 组件（含交互） | **≥ 60%** 〔来源：团队经验〕 | 关键路径须覆盖，非追求全分支 |
| 存量仓整体 | 不设 CI 阻塞阈值 | 与 E2E 策略一致，渐进补测 |

### 各仓配置

| 子系统 | 框架 | Coverage 配置 | CI 门禁 |
|--------|------|---------------|---------|
| trex-website | Vitest | `vitest.config.ts`：`v8`，reporter `text/json/html` | 无阻塞阈值 |
| trex-2b | Vitest ^3.2 + `node --test` | 根 `vitest.config.ts` 无 coverage 块；建议与 website 对齐加 `coverage` | 无 |
| dapp-dashboard | Jest | 按仓内配置 | 无 |
| trex-extension | 无 | — | — |
| passport-sdk | 无 | 公开 API 须有单测后再设阈值 | — |

**运行示例**（trex-website）：

```bash
pnpm exec vitest run --coverage
```

覆盖率报告仅作 MR review 参考，**不阻塞 merge**（与 Playwright E2E 门禁一致）。新 monorepo 初始化时复制 trex-website 的 `vitest.config.ts` `coverage` 块。

## Mock 策略

- API 调用在单测中 mock（React Query 的 query function 层 mock）
- 避免 mock 内部实现；优先 mock 边界（网络请求 / 浏览器 API）
- Chrome Extension API（`chrome.*`）需在测试环境中 mock
