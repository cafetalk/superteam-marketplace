# 前端发布 Checklist 模板

> **流程** 见 [`08-test-handoff.md`](../../08-test-handoff.md) §发布、`11-quality-ops.md`（构建与部署操作）。  
> 源自钉钉 [Trex前端发布模板](https://alidocs.dingtalk.com/i/nodes/Obva6QBXJw99kworf2Rby21PWn4qY5Pr)；正文以 git 为准，钉钉作历史参考。  
> **发布分支** = 本批 `review_<YYMMDD>_<keyword>`（与提测分支同名，如 `review_260512_campaign`）。

---

## 一、发布信息

| 项目 | 内容 |
|------|------|
| **发布内容** | `[例如：Campaign 领奖]` |
| **设计文档** | `<链接或附件>` |
| **关联 Linear** | `TREX-<id>`（可多个） |
| **发布日期** | `YYYY-MM-DD` |
| **发布执行人** | 迭代负责人 |
| **QA 负责人** | @QA |
| **发布分支** | `review_<YYMMDD>_<keyword>` |
| **发布类型** | ☐ 产品需求 · ☐ 技术需求 / 日常重构 · ☐ Hotfix |

---

## 二、发布前确认

迭代负责人须在正式启动前全部确认：

- [ ] **需求 / 验收通过** — 产品 / UI / QA 已在测试环境验证
- [ ] **后端 / 合约就绪** — 已部署生产且向前兼容
- [ ] **生产配置** — 环境变量、合约地址等无误
- [ ] **CDN 与域名** — 状态正常

### 跨栈依赖顺序【强制】

必须按依赖顺序依次发布，避免线上故障：

```text
合约 → 后端 → 前端：trex-extension → 前端：trex-website（及依赖 website 的其余前端）
```

涉及 anchor-sdk 时：先 **npm 发布 SDK**，再在 trex-website / trex-2b 中升级依赖版本后发布应用。

---

## 三、第一阶段：生产部署

勾选本次实际涉及的系统；未涉及的可整行跳过。

### trex-website

仓库：[trex-website](https://gitlab.com/Keccak256-evg/t-rex/web/trex-website) · 环境见 [`12-environments.md`](../../12-environments.md#trex-website)

| 执行人 | 发布分支 | 执行内容 | 完成 |
|--------|----------|----------|------|
| 迭代负责人 | `review_<YYMMDD>_<keyword>` | ☐ 合并发布分支至 `pre` · ☐ pre 环境验收通过 · ☐ 合并 `pre` 至 `master` · ☐ 添加 Git Tag · ☐ 部署成功 | ☐ |

### trex-2b

仓库：[trex-2b](https://gitlab.com/Keccak256-evg/t-rex/web/trex-2b/) · 无 Pre 环境

| 执行人 | 发布分支 | 执行内容 | 完成 |
|--------|----------|----------|------|
| 迭代负责人 | `review_<YYMMDD>_<keyword>` | ☐ 合并发布分支至 `master` · ☐ 添加 Git Tag · ☐ 部署成功 | ☐ |

### trex-extension

仓库：[trex-extension](https://gitlab.com/Keccak256-evg/t-rex/web/trex-extension)

| 执行人 | 发布分支 | 执行内容 | 完成 |
|--------|----------|----------|------|
| 迭代负责人 | `review_<YYMMDD>_<keyword>` | ☐ 合并发布分支至 `master` · ☐ 添加 Git Tag · ☐ [Chrome 商店](https://chrome.google.com/webstore/devconsole/52b79ed9-e6b8-4d46-b182-e0912143120c) 提审 · ☐ 审核通过后发布 | ☐ |

### anchor-sdk

仓库：[anchor-sdk](https://gitlab.com/Keccak256-evg/t-rex/anchor/anchor-sdk)

| 执行人 | 发布分支 | 执行内容 | 完成 |
|--------|----------|----------|------|
| 迭代负责人 | `review_<YYMMDD>_<keyword>` | ☐ 合并发布分支至 `master` · ☐ 添加 Git Tag · ☐ npm 发布 anchor-sdk · ☐ 在 trex-website / trex-2b 升级 SDK 版本 | ☐ |

### dapp-dashboard

仓库：[dapp-dashboard](https://gitlab.com/Keccak256-evg/t-rex/web/dapp-dashboard/)

| 执行人 | 发布分支 | 执行内容 | 完成 |
|--------|----------|----------|------|
| 迭代负责人 | `review_<YYMMDD>_<keyword>` | ☐ 合并发布分支至 `master` · ☐ 添加 Git Tag · ☐ 部署成功 | ☐ |

### 其他子系统（按需追加）

passport-sdk、trex-zktls、trex-tlsn-plugin 等见 [`01-apps.md`](../../01-apps.md) 与 [`11-quality-ops.md`](../../11-quality-ops.md)。

---

## 四、第二阶段：线上验证

| 验证内容 | 验证人 | 检查点 | 完成 |
|----------|--------|--------|------|
| **功能验收** | @产品 @QA 迭代负责人 | 使用真实线上账号完成涉及系统的核心业务路径；已配置 Playwright 的仓库可辅以 E2E smoke 回归（见 [`09-testing.md`](../../09-testing.md) §E2E） | ☐ |
| **监控与报错** | 迭代负责人 | BugSnag 无本次发布引入的新增致命异常（见 [`07-error-and-monitoring.md`](../../07-error-and-monitoring.md)） | ☐ |

---

## 五、归档

- [ ] Linear 发布相关 issue 已更新进度并关闭（或留 follow-up）
- [ ] 发布完成通告（团队群 / 频道）
- [ ] 本 checklist 已归档（Linear comment / 钉钉副本 / `trex-releases`，按团队当期约定）

---

`〔填写约定〕`
- **发布分支**必须与提测 `review_*` 一致，不使用短期 `beta_<YYMMDD>_<keyword>` 分支
- trex-website 经长期分支 `pre` 再合 `master`；其余 Web App 一般为 `review_*` → `master`
- 11–12 类 checklist 须逐项实测后勾选，禁止批量打勾
- 后端 k8s 灰度 / Nacos 等字段见 `backend/appendix/templates/release-checklist.md` 与 `common/04-ci-and-release.md`
