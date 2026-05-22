# 编码规范

本章与仓库内 **前端通用开发与代码质量规范**（参考实现：`trex-2b/.claude/rules/coding.mdc`）对齐，作为跨子系统的手册摘要；具体项目可在 `.claude/rules` 或 ESLint 包中再做覆盖。

---

## 1. 命名规范

### 1.1 元素与命名风格速查【强制】

| 元素 | 命名规范 | 示例 |
| --- | --- | --- |
| 文件名 | **kebab-case**（全小写、连字符） | `user-profile.tsx`（✅）· `UserProfile.tsx`（❌） |
| 文件夹 | kebab-case | `user-profile/`、`dashboard-settings/` |
| 组件名（代码中） | PascalCase | `function UserProfile() {}` |
| 变量 | camelCase | `userProfileData` |
| 函数 | camelCase，宜动词短语；返回 boolean 可用 `is` / `has` / `should` | `fetchUserData()`、`isValid()` |
| 自定义 Hook | camelCase，且必须以 `use` 开头 | `useAuth()`；非 Hook 勿用 `use` 前缀 |
| 模块级 / 导出的常量 | UPPER_SNAKE_CASE | `API_BASE_URL`、`MAX_RETRY_COUNT` |
| 类型 / 接口 | PascalCase；禁用 `I` 前缀；**无 `Type` 后缀**；**建议 `T` 前缀**（如 `TUserProfile`） | 以业务语义优先 |
| 自定义 CSS 类名 | kebab-case | `.btn-primary`；Tailwind 工具类随框架 |
| 环境变量 | UPPER_SNAKE_CASE | `NEXT_PUBLIC_API_URL`；仅服务端用的变量勿加 `NEXT_PUBLIC_` |
| URL 查询参数名 | **snake_case** | `?page_number=2&sort_by=name` |
| localStorage / sessionStorage / Cookie 名 | 按项目统一前缀；**trex-2b** 约定：`trex2b` 前缀 + 小写 + 连字符 | `trex2b-access-token` |

- **Next.js App Router**：`app/` 下目录名用 kebab-case，与 URL 一致；动态段 `[segment]` 段名小写且宜语义化（如 `[userId]` 优于泛用 `[id]`）。
- 命名须**语义化**：避免 `data`、`option`、`flag` 等泛称；名称应自解释（例：`isLoggedIn` 优于 `flag // 是否登录`）。
- 组件 props 建议加类型注解，优先联合类型或字面量类型。
- **属性命名与取值**：全英文、camelCase、语义化；禁止中文、空格或随意特殊符号。

### 1.2 布尔变量【强制】

用于权限、开关、入口控制的布尔变量须**行为化、目的明确**，例如 `showXxxEntry`、`canXxx`、`isXxxEnabled`。

- **禁止**模糊命名：`whitelist`、`option`、`flag`、`depositFiat`、`withdraw` 等（第三方或历史遗留须在代码中注明原因）。
- 示例：错误 `whitelist` → 正确 `showWhitelistEntry`。

### 1.3 组件语义后缀（可选约定）

在 PascalCase 组件名上可按职能加后缀，便于扫读：

| 后缀 | 含义 |
| --- | --- |
| `*Modal` | 弹窗 |
| `*Card` | 卡片 / 列表项展示 |
| `*Form` | 表单 |
| `*List` | 列表（确为多条渲染时使用） |
| `*Page` | 页面级（对应路由） |
| `*Button` | 操作按钮 |

---

## 2. JSX 规范【强制】

### 2.1 testID / accessibilityLabel / key

- **静态字符串必须字面量**：`testID="okBtn"` ✅ · `testID={"okBtn"}` ❌（须改为字面量）。
- **动态值允许花括号**：`testID={id}`、`testID={\`item_${i}\`}`、`testID={isVip ? "vip" : "guest"}`。
- **key**：须唯一且稳定；优先 `key={item.id}` 或 `key={\`prefix_${index}\`}`；避免 `key={index}`（除非数据无稳定 id）。静态 key 同样禁止 `key={"x"}` 形式，应用 `key="x"`。

适用 React / React Native 等 JSX。

**示例：** `<TouchableOpacity testID="okBtn" />` · 不合规：`<TouchableOpacity testID={"okBtn"} />`。

---

## 3. 代码结构与可读性

- 逻辑完整：if/else 覆盖意图，**避免遗漏 else**；优先早期返回、减少嵌套。
- 勿过早抽象；组件与函数**单一职责**。
- 解构：默认值在解构时处理；**解构层级不宜过深**（建议不超过约两层）；不对无默认值或语义会变的对象滥用解构。
- 复用逻辑优先 hooks 或工具函数；**UI 与业务逻辑分层清晰**。
- 无样式与功能的空 `<div>` / `<View>` 可删或改为 `<>`。

---

## 4. 健壮性与安全性

- **异常**：不应静默吞掉；仅 `console` 不处理、不向上传递视为不规范（业务上 intentional silent catch 须注释说明）。
- **Magic number / magic string**：用具名常量或配置（业务常量可注明）。
- **async**：仅在有真实异步需求时使用。
- 渲染与解析前**判空**，避免 `undefined`/`null` 穿透。
- **`||` 与 `??`**：可能为 `0` / `""` / `false` 时优先 `??`；明确「假值即回退」时用 `||`。
- **console**：禁止将调试用 `console.log` / `warn` / `error` 提交主分支；保留须有理由（埋点、约定日志等）并注释。

---

## 5. 依赖与配置

- 依赖版本与升级策略由仓库约定；避免无理由锁死版本。
- 依赖管理集中，避免重复与冲突。
- 字体与排版顺序按设计 / 项目规范。

---

## 6. 代码风格、注释与导出

- **Lint + Prettier**：代码须通过 lint，并用 Prettier 格式化（见下文团队 Prettier 约定）。
- **注释**：少而精；不写「代码在做什么」的废话；应写**为什么**、边界、已知限制、workaround。注释须与实现一致。
- **样式**：单组件样式优先写在组件 `className`；**禁止**随意使用内联 `style`（除非有明确理由）；避免冗余 class。
- **导出【强制】**
  - 优先**具名导出**，避免默认导出；避免匿名 `export default`。
  - 聚合导出在 `index.ts` 中 `export { X } from "./X"`。
  - **删除死代码**；除对外入口（如包 `index` re-export）外，勿 `export` 未被任何模块引用的声明，保持最小公开 API。

---

## 7. 样式与资源

- 设计 token / 变量命名与设计稿一致；考虑暗色等主题。
- 图片：统一 assets、语义化命名；优先 webp/avif；建议 import 而非散落硬编码路径；按需尺寸，避免大图硬缩。
- **Tailwind**：优先语义化、响应式类；避免无必要的 arbitrary 尺寸（如能用语义类则少写 `translate-x-[360px]`）。

---

## 8. TypeScript

- 新代码**优先全部 TS**；`tsconfig` 建议 `strict: true`（以各仓库为准）。
- **避免裸 `any`**：倾向 `unknown` + 类型守卫；`〔t-rex 现状〕` 部分仓库 ESLint 对 `any` 仍为 `warn`，新代码应主动收紧。
- **`interface` 与 `type`**：`interface` 描述对象形态；`type` 用于联合 / 交叉等。
- 避免不安全 `as`；必须使用时**注释原因**。
- 禁用 `@ts-ignore`；必要时 `@ts-expect-error` + 说明。

```ts
// ❌ 不推荐
const data: any = fetchData();

// ✅ 推荐
const data: unknown = fetchData();
if (isUser(data)) {
  // data is User
}
```

---

## 9. ESLint 与子系统现状【参考】

**trex-website**（Next.js）可作为 Web App 规则集参考，例如：

- `eslint-config-next`（core-web-vitals + typescript）
- `@typescript-eslint/no-explicit-any`：多为 **warn**（目标收紧为 error，存量渐进）
- `tailwindcss/no-contradicting-classname`、`react-hooks/set-state-in-effect` 等

**其他子系统（`〔t-rex 现状〕`，尚未统一）：**

- **trex-2b**：共享包 `@trex-2b/eslint-config`（`packages/eslint-config/`），monorepo 内统一 lint 的参考实现。
- **dapp-dashboard**：ESLint 9 + typescript-eslint + prettier 相关插件。
- **trex-extension**：ESLint 8.x 栈，主版本与其他仓库 ESLint 9 不一致。
- **anchor-sdk**：**Biome**（非 ESLint）。

**收敛方向**：推广 trex-2b 式共享 ESLint 配置包；新应用对齐团队 Prettier 与核心 TS 规则。

---

## 10. Prettier【强制】

以 **trex-website** 根目录 `.prettierrc` 为团队默认（新子系统可直接复用）：

```json
{
  "printWidth": 120,
  "semi": true,
  "singleQuote": false,
  "trailingComma": "none",
  "useTabs": false,
  "tabWidth": 2,
  "endOfLine": "auto"
}
```

要点：双引号、分号、**无尾逗号**、行宽 120。结合各仓库 **lint-staged** / CI 做提交前格式化。

---

## 11. Import 规范

- 绝对路径优先（`tsconfig` paths 或构建 alias）。
- 禁止循环依赖（可配合 `import/no-cycle` 等规则）。
- import 顺序：第三方 → 内部模块（各仓库可细化）。

---

## 维护

- 规范细则以各仓库 `.claude/rules`、`eslint.config` 为准；本文件随 `coding.mdc` 演进同步修订。
- 子系统工具链升级（ESLint 主版本、Prettier）后应更新 **§9** 与 **§10**。
