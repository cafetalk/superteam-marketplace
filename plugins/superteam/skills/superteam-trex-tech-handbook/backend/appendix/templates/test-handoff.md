# 提测单模板

> **流程 SOP** 见 `common/03-test-handoff.md`。本文件是单子模板，复制填写后贴 Linear issue comment（推荐）或 MR description。

---

## 提测单 — `<service-name>` `<YYYY-MM-DD>`

### 1. 提测人
@`<gitlab-handle>`

### 2. 关联 Linear
`TREX-<id>`（与 MR description 首段一致）

### 3. MR 链接
`<完整 GitLab MR URL>`

### 4. 目标环境
- [ ] `test` (dev) — 默认
- [ ] `pre`
- [ ] `staging`

### 5. 变更范围

**功能列表**：
- [ ] 功能 1：...
- [ ] 功能 2：...

**影响面**：
- **接口契约**（OpenAPI / GraphQL / Dubbo `Remote*Service`）：...
- **数据库表 / OTS 表**：...
- **Nacos 配置变更**：...
- **上下游服务**：...
- **跨团队联系人**：...

### 6. 自测记录

**已通过 case**：
- 本地启动 + 核心 case：...
- 单测：`./mvnw test` 结果 (覆盖率 if 有)
- 接口联调（与下游 / 上游）：...
- 边界 case：...

**已知问题 / 风险**：
- ...

### 7. 回滚预案

若 merge 后发现问题，回退路径：
- **镜像回滚**：到 `<prev-version>`
- **配置回滚**（Nacos）：哪些 key 需要回退
- **DB 迁移回退**（如有）：可执行脚本路径 / 手动步骤
- **接口契约回退**（如有）：消费方需要做什么

---

### 可选字段

**单测覆盖率**：`<%>` (target ≥ `<%>`)
**性能基线**：QPS / P99 ms（如对性能有影响）
**第三方依赖**：新增 / 升级的 jar / 服务
**附件**：
- PRD：...
- 设计文档 / RFC：...
- Demo / 截图：...

---

`〔填写约定〕`
- 1–7 是【强制】字段（缺一律不接收）
- 可选字段按场景填
- 各字段单凭 "TBD" 或空白 → 提测单不通过
- 提测单先贴 Linear issue comment（不会丢、Linear 自动通知）；如团队约定也贴 MR description，二者一致即可
