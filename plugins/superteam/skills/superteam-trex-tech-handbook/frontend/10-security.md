# 安全

## Token / 凭据存储

| 数据类型 | 存储位置 | 禁止 |
|---|---|---|
| JWT / Session Token（高敏感）| httpOnly cookie（后端 Set-Cookie）| ❌ localStorage |
| 临时 UI 状态 / 低敏感偏好 | sessionStorage 或内存 | — |
| 私钥 / 助记词 | 浏览器扩展安全存储 API（仅 trex-extension）| ❌ localStorage / sessionStorage |

**禁止使用 localStorage 存储任何高敏感凭据**（JWT、私钥、session token）。

## XSS 防护

- **禁用 `dangerouslySetInnerHTML`**（除非经过代码审计 + 注释说明内容来源已净化）
- 所有用户输入在渲染前经过 HTML 转义（React 默认处理，注意绕过场景）
- 第三方 HTML 内容必须经 DOMPurify 净化后再渲染

```tsx
// ❌ 不允许
<div dangerouslySetInnerHTML={{ __html: userContent }} />

// ✅ 如必须使用，需净化后并添加注释
import DOMPurify from 'dompurify'
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(userContent) }} />
```

## CSRF

- 使用 SameSite cookie（后端 `trex-web` 配置，前端无需额外处理 cookie 策略）
- 有状态变更的接口（POST / PUT / DELETE）需携带 CSRF token，与后端 `trex-web` 方案对齐
- 前端封装层（`*Proxy.ts`）统一注入 CSRF token，不在组件层单独处理

## CSP（Content Security Policy）【推荐】

trex-website 当前 CSP 配置（`next.config.ts` headers 中）：

```js
{
  key: "Content-Security-Policy",
  value: "frame-ancestors 'self' chrome-extension://*;"
}
// 同时：X-Content-Type-Options: nosniff（防 MIME 嗅探）
```

含义：
- `frame-ancestors 'self' chrome-extension://*` — 限定页面只能被同源页面或 Chrome 扩展嵌入（防 clickjacking）
- 注：当前 CSP 较精简，未限制 `script-src` / `connect-src` 等。

新 Web App 建议基线（在 trex-website 基础上扩展）：
- 禁止 `eval` 和 `inline-script`（需配合 `nonce` 或 `hash`）
- 限制 `connect-src` 到已知域名（trex API + RPC 节点 + BugSnag + GA）
- Chrome Extension 的 CSP 在 `manifest.json` 中配置（Manifest V3 已有默认限制）

## Web3 签名安全

- **签名请求必须展示可读内容**：用户看到的签名内容必须与实际签名数据一致，防盲签
- **trex-extension 私钥不落存储**：私钥 / 助记词仅保存在内存或扩展安全存储中，**禁止** localStorage / sessionStorage
- **EIP-712 结构化签名**：涉及链上操作的签名优先使用 EIP-712，确保用户可读
- drex-passport 前端接入规约：TODO(@elaine)

```
❌ 直接让用户签原始 bytes，不展示语义内容
✅ 展示结构化的签名请求（Action / 金额 / 目标地址），再触发签名
```

## Chrome Extension 权限最小化

- `manifest.json` 中 `permissions` 字段只申请必要权限
- 避免申请 `<all_urls>` 等宽泛 host 权限


## 定期安全检查

- `npm audit` 在 CI 中运行，检查已知漏洞
- Dependabot / GitLab 依赖扫描：TODO(@elaine) 确认当前 CI 配置是否覆盖
