# 状态与数据

## 服务端状态：React Query

适用：所有需要与后端接口交互的异步数据（列表 / 详情 / 分页 / 轮询）。

- 接口数据缓存、加载状态（`isLoading` / `isFetching`）、错误状态、自动重试均通过 React Query 管理
- **禁止**在 `useEffect` 里手写 loading state + fetch 逻辑

```ts
// ✅ 推荐
const { data, isLoading, error } = useQuery({
  queryKey: ['badges', userId],
  queryFn: () => badgeApi.listBadges(userId),
})

// ❌ 不允许
const [data, setData] = useState()
const [loading, setLoading] = useState(false)
useEffect(() => {
  setLoading(true)
  fetch(url).then(r => r.json()).then(setData).finally(() => setLoading(false))
}, [])
```

- Mutation（写操作）使用 `useMutation`，成功后按需 `invalidateQueries` 触发相关查询刷新
- QueryKey 规范：参考各自项目现有实现（如 `['badges', userId]` 分层风格）

## 客户端状态：Jotai

适用：Web App 类子系统（trex-website / trex-2b / dapp-dashboard 等）。纯 UI 状态（弹窗开关 / 当前选中项）和跨组件共享的全局状态（用户偏好 / 主题 / 钱包连接状态）。

- Atom 定义放在 `src/store/` 目录（或各 feature 目录下，按影响范围决定）
- 命名规范：`xxxAtom`（如 `walletConnectionAtom`、`sidebarOpenAtom`）
- 避免将服务端数据存入 Jotai atom（应由 React Query 持有）

```ts
// ✅ 客户端 UI 状态
const sidebarOpenAtom = atom(false)

// ❌ 不要把接口数据放进 atom（应用 React Query）
const badgesAtom = atom<Badge[]>([])
```

`〔t-rex 现状〕`：**trex-extension 使用 Redux**（`react-redux` + `redux-thunk` + `redux-logger`，主要因 TLSNotary 流程有大量异步状态机），未迁移至 Jotai。这是历史选型固化的现状，新工程不要复制；新 Web App 仍按本节使用 Jotai。

## Token / Session 管理

| 场景 | 存储方式 |
|---|---|
| 高敏感凭据（JWT / 私钥衍生 token）| httpOnly cookie（后端 Set-Cookie）|
| 低敏感偏好 / 临时状态 | sessionStorage（页面级）或内存（组件生命周期）|
| **禁止** | localStorage 存储高敏感凭据 |


## Web3 钱包状态

trex-website 当前钱包集成方案（作为 Web App 基准）：

- **`wagmi @2.15.2` + `viem @2.38.6`**：EVM 链交互核心库；`wagmi` 提供 React hooks（`useAccount` / `useConnect` / `useSignMessage` 等）；`viem` 处理底层 RPC
- **`@reown/appkit @1.7.3`**（WalletConnect 的继任 SDK）：钱包连接 UI + 多链支持；配合 `@reown/appkit-adapter-wagmi`（EVM）+ `@reown/appkit-adapter-solana` 使用
- **`thirdweb @5.105.29`**：辅助链上操作

钱包连接状态通过 wagmi 的 `useAccount` hook 读取，无需手动存入 Jotai atom。

trex-extension 的钱包状态管理方案：TODO(@elaine) 确认（Extension 场景与 Web App 不同，需查仓库）

安全要求：
- 私钥 / 敏感签名材料：**禁止**存入 localStorage / sessionStorage（仅内存 + 扩展安全存储 API）
- 签名请求必须展示可读内容（防盲签，详见 `10-security.md`）