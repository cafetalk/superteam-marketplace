# Push Rule v3.0 Rollout — 2026-05-19

## 背景

2026-05-19 M2-B conformance audit（详见 `docs/audits/2026-05-19-handbook-conformance.md` Check 8）发现 handbook 文档描述的 Push Rule regex（600+ 字符 "org 共享模版"）与 GitLab 真实配置（120 字符 + 项目独立配置）严重不一致。

本 rollout 双向修复：
1. **handbook 改**：v3.0 regex 文档对齐 GitLab 真实状态 + 加入 6 位日期支持（团队约定新建必须用此格式）
2. **GitLab 改**：61 个 t-rex sub-group 项目的 Push Rule 批量 PUT 到 v3.0 standard

## v3.0 Target regex

**Branch Name**：

```regex
(((pre|auto|dev|alpha|beta|feature|hotfix|review)(|_(\d{8}|\d{6}|\d{4})_[\.A-Za-z0-9\-]{2,30}))|^dev$|^beta$|^master$|^main$)
```

**Commit Message**（standard；部分项目用 conventional-commits superset，单独保留）：

```regex
^((init|feat|alter|fix|perf|refactor|docs|style|test|build|revert|ci|chore|release|workflow):|Merge|Reverted|Revert)[\s\S]+
```

## Rollout 范围（61 projects, 2026-05-19 audit）

按当前 Push Rule 状态分 4 类，**逐类决策处理**：

### 🟢 MATCH-CURRENT （23 个）—— **Phase 1 直接迁移**

当前 regex 与 audit 前 "Current regex" 完全一致（120 char），仅缺 `\d{6}`。

- **anchor/**: anchor-admin, anchor-core, anchor-dashboard, anchor-endpoint, anchor-event, anchor-insight-nft, anchor-insight-thirdpart, anchor-insight-token, anchor-insight-zktls, anchor-labs, anchor-sdk, anchor-team, anchor-web（13 个）
- **backend-java/**: trex-admin, trex-core, trex-endpoint, trex-event, trex-passport, trex-web, trex-widget（7 个）
- **backend-python/**: trex-hexagonal, trex-persona-feast, trex-prism-engine（3 个）

**操作**：PUT `branch_name_regex` 到 v3.0 Target；commit_regex 视项目状态（空 / standard / trex-admin 的 conventional-commits 变种）保持不变。**风险评估**：零行为损失，仅新增 6 位日期支持。

### 🟡 CUSTOM Variant A（"21-prefix legacy"，23 个）—— **Phase 2 迁移**

当前 regex 含 21 个项目前缀 + 16 条 `<project>_master` 白名单，比 v3.0 宽得多。

- **root**: trex-docs, trex-passport-contract, trex-test
- **archived-deprecated/**: auth-center, drex-activity, drex-asset, drex-customer, trex-protocol
- **scaffold/**: knotify, kseq, kurl, trex-framework
- **skills/**: code-audit, report-hub, superteam-mcp-server
- **trex-demos/**: persona-notary, universal-bridge-demo
- **trex-tls/**: attestor-core, request-field-tracer-extension, tls, trex-notary, trex-notary-12, trex-notary-websockify, zk-symmetric-crypto
- **web/**: bugsnag-webhook

**操作**：PUT `branch_name_regex` 到 v3.0 Target —— 这一步**真的会收紧**（项目前缀分支不再能新建）。建议先在 1-2 个低活跃仓试点（推荐 `archived-deprecated/auth-center` 等）确认 push rule 生效后再批量推。

### 🟡 CUSTOM Variant B/C（"anchored short"，9 个）—— **Phase 3 迁移**

当前已支持 `\d{6}` 但 regex 形式不同（用 `^...$` 锚定），且不接受 bare `main`。

- **sdk/**: trex-passport-sdk, trex-proxy-browser-extension-sdk
- **trex-tls/**: trex-tlsn-plugin, trex-zktls-providers
- **web/**: dapp-dashboard, nft-metadata-tookit, trex-extension, trex-2b (含 `pre` 冗余), trex-website (含 `pre` 冗余)

**操作**：PUT `branch_name_regex` 到 v3.0 Target，统一格式。功能上几乎等价（这些项目本来就支持 6 位日期，只是不接受 `main` 长期分支）。

### ⚪ EMPTY（4 个）—— **Phase 4 决策**

push rule 存在但 `branch_name_regex == ""`，即无任何限制。

- scaffold/**trex-scaffold**
- trex-demos/**thirdweb-reclaim-demo**
- trex-demos/**trex-marketplace**
- skills/**superteam** ⭐（即本 handbook 仓）

**风险**：现存分支可能不符合 v3.0 regex（因为之前完全自由）。需先检查现存分支再贴 regex。

**操作**：
1. 列出每个仓的现存分支名
2. 不符合 v3.0 的分支：要么先 rename 到合规，要么决定"是否接受 grandfather"
3. 确认 ok 后 PUT v3.0 Target

⚠️ **特别注意 `agentic/superteam`（handbook 自家仓；2026-05-19 由 `skills/` rename）**：handbook 历次 PR 用的都是 `dev_<YYMMDD>_<kebab>` 形式（6 位日期），与 v3.0 兼容 ✅；可以直接 PUT。

## 执行顺序

1. ✅ **PR-9 merge**：handbook regex 文档 v3.0（本 PR）
2. **Phase 1 PUT**：23 个 MATCH-CURRENT 项目 → v3.0（最低风险）
3. **冒烟测试**：在 1 个 Phase 1 项目尝试 `dev_260519_smoke-test` 分支验证
4. **Phase 2 PUT**：23 个 Variant A 项目 → v3.0（收紧，需先公告团队）
5. **Phase 3 PUT**：9 个 Variant B/C 项目 → v3.0（统一格式）
6. **Phase 4 检查**：4 个 EMPTY 项目，检查现存分支后 PUT
7. **配套 audit 复跑**：`/tmp/audit.py` 重跑确认所有 61 个项目都是 v3.0

## 团队公告内容（建议在 Phase 2 之前发）

> [trex team] 2026-05-19 起 Push Rule 收紧：
> 1. 新建分支必须用 `<stage>_<YYMMDD>_<name>` 格式（**6 位日期**）；不接受老式 `drexdev_*` / `kikidev_*` / `<project>_master` 等
> 2. 现存老分支 grandfather 但**不能再 push 新 commit**；需迁移到 bare 形式
> 3. 长期分支统一 `dev` / `beta` / `master` / `main`
> 4. 详见 handbook `common/02-branch-and-commit.md` + `appendix/project-prefix.md`

## 复跑验证

```bash
# 全量复跑 audit Check 8
python3 /tmp/audit_push_rules.py  # 或重新生成

# 期望结果：61 个项目全部 branch_name_regex = v3.0 Target
```

## 变更日志

| 时间 | 动作 | 操作人 |
|---|---|---|
| 2026-05-19 | v3.0 regex 落地 handbook（PR-9 merge） | claude + allen.qin |
| 2026-05-19 | Phase 1 PUT（23 MATCH-CURRENT） | TBD |
| 2026-05-19+ | Phase 2-4 PUT | TBD |
