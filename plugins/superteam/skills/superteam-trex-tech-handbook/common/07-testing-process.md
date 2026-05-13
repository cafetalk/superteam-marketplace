# 测试过程 SOP

本章规范 **QA 整合 + k8s beta env 测试** 流程 —— 介于研发提测（见 `common/03`）和最终 prod 发布（见 `common/04`）之间。

- `common/03` 研发提测：`dev_*` → `review_*` MR，team lead 审核通过即提测完成
- `common/07`（本章）QA 整合多个 `review_<date>_<name>` → 一个 `beta_<date>_<keyword>`，部署 k8s beta env 测试
- `common/04` 发布：`beta_<date>_<keyword>` → `master` MR，研发负责人审核

## K8s 环境对应【强制】

| K8s 环境 | 部署源分支 | 用途 |
|---|---|---|
| **dev** | `dev_<date>_<name>`（短期）/ 长期 `dev`（基线） | 研发**联调**；每个 dev_* 各自部署实例 |
| **beta** | `beta_<date>_<keyword>`（短期）/ 长期 `beta`（基线） | **QA 测试**；本章主战场 |
| **prod** | 长期 `master` | 真实用户使用 |

`〔t-rex 现状〕`：k8s 环境跑在**阿里云 K8s** 上。pre / staging 环境**目前不单独使用**；如未来引入再扩 handbook。

## 角色与职责【强制】

| 角色 | 主要责任 |
|---|---|
| **开发者** | 提测 / 自测 k8s dev env / 修 QA 反馈 / 回归确认 / Linear 状态同步 |
| **QA / 测试人员** | 整合 review_* → beta_<date>_<keyword> / 部署 beta env / 用例验证 / 提 bug / 跟踪修复 / sign-off / **提交发布申请** |
| **Team lead** | 卡 review（在 common/03 阶段）/ 仲裁优先级 |
| **PM / 业务** | 验收 happy path / 业务规则确认 |
| **研发负责人** | 审核最终发布 MR（在 common/04 阶段）|
| **Ops** | k8s 集群维护 / 发布执行 / 监控告警 |

## QA 整合流程：多 `review_*` → `beta_<date>_<keyword>`【强制】

```text
[1] QA 收到一批 review_<date>_<nameA>, review_<date>_<nameB>, review_<date>_<nameC>...
        （同一个版本计划要发布的 features）
        │
        │  QA 决定本次版本 keyword（如 "campaign"）
        ▼
[2] QA 建 beta_<date>_<keyword> 分支（基于 master tip）
        │
        ▼
[3] QA 为每个 review_<date>_<nameX> 建 MR
        源:    review_<date>_<nameX>
        目标:  beta_<date>_<keyword>
        │
        ▼
[4] QA 自行 merge 多个 MR
        │
        ▼
[5] beta_<date>_<keyword> 上含所有 features
        │
        │  push 触发 k8s beta env 自动部署
        ▼
[6] k8s beta env 部署完成 → QA 开始测试
```

`〔约定〕`：
- `<keyword>` 由 QA 根据版本主题取（如 `campaign` / `onboarding` / `nft-airdrop`）
- 同一个 keyword 可在不同 date 有不同版本（如 `beta_260513_campaign` vs `beta_260520_campaign`）
- 多个 review_* 之间若有冲突，QA 负责协调对应开发者解决（不应该自行改代码）

## 测试流程【强制】

```text
QA 在 k8s beta env 测试 beta_<date>_<keyword>
        │
        ├── ✅ 通过 → sign-off → 提交发布申请 → 见 common/04
        │
        └── ❌ 不通过 → bug 反馈
                          │
                          ▼
                  Linear comment + GitLab MR comment
                  （指定原 review_<date>_<name> 对应的开发者）
                          │
                          ▼
                  开发者在 dev_<date>_<name> 修复
                  （走 common/03 §bug 回流 SOP）
                          │
                          ▼
                  新提测 MR → team lead approve → merge → review_<date>_<name> 更新
                          │
                          ▼
                  QA 重新 merge 进 beta_<date>_<keyword>（追加 commit）
                          │
                          ▼
                  k8s beta env re-deploy → QA 再测
```

## Bug 分级 + 处理【强制】

| 级别 | 定义 | 处理 SLA |
|---|---|---|
| **P0** | 阻塞测试 / 核心业务不可用 / 数据安全风险 | 立刻拉群 + 暂停测试；revert 或紧急修；2h 内响应 |
| **P1** | 核心功能不可用 / 重大体验缺陷 | 24h 内修；本批**不**上 prod |
| **P2** | 体验缺陷 / 边缘 case | 可累积；视情况决定是否阻塞本批 |
| **P3** | 优化建议 / 非关键 | 排入 backlog；不阻塞 |

**强制约定**：
- 每个 bug 必须 link 回原 Linear issue（comment 或 sub-issue），并标注对应的 review_<date>_<name>
- P0 / P1 不允许 sign-off
- P2 / P3 必须有明确处置（修 / 延期到下一批 / Won't fix），不允许悬空

## 回归边界【推荐】

| 回归类型 | 谁负责 |
|---|---|
| **变更影响面内** 的功能 | 开发者自测（k8s dev env）+ QA 复核（k8s beta env） |
| **变更影响面外** 的功能 | QA 评估 + 执行（基于变更范围 + 经验） |
| **跨服务** 的链路回归 | 跨团队协作；建 cross-team Linear issue |
| **性能 / 压测回归** | TODO(@allen) — 需要性能平台 |

回归用例选择优先级：
1. 受影响业务的 happy path
2. 受影响业务的关键边界 / 异常 case
3. 跨服务接口契约（消费方调用）
4. 历史 P0 / P1 bug 的重现路径

## Test Sign-off 标准【强制】

QA 提交发布申请前（即触发 `common/04` §发布 CI 自动建 MR），**必须**全部满足，由 QA 在 Linear 提测 issue 上明确 ✅：

- [ ] **功能 case 100% 通过**（提测单列出的功能 + QA 补充用例）
- [ ] **变更影响面内回归 100% 通过**
- [ ] **变更影响面外回归通过**（QA 判定的关键回归）
- [ ] **P0 / P1 bug 全部 close**
- [ ] **P2 / P3 bug 有明确处置**（修复 ✓ 或延期单独 issue 跟踪）
- [ ] **性能基线满足**（如有性能要求）
- [ ] **跨服务对接验证通过**（如涉及）
- [ ] **QA 在 Linear 提测 issue / 提测单上明确签字** ✅

未 sign-off 不允许 QA 提交发布申请 —— 强 gate。

## 自动化测试覆盖【推荐】

TODO(@allen) 整章 —— 当前自动化能力 TBD：

- 单元测试：见 `backend/08-testing.md`（JUnit 5 + Mockito）
- 接口自动化：是否引入 Postman / Karate / RestAssured？覆盖率目标？
- 端到端（E2E）：跨服务场景的自动化方案？
- 性能压测：平台 / 工具 / 触发时机？
- 自动化失败回流机制：CI 失败 → ?

## QA 协作工具

TODO(@allen)：
- QA 提测通知机制（接收 review_*_merged 的渠道：钉钉机器人 / Linear 自动通知 / 人工 trigger？）
- Bug 跟踪工具（Linear sub-issue / 独立 bug tracker？）
- 测试用例管理（独立工具 / 仓内文档 / Linear？）
- 测试结果汇总（dashboard？）
- **发布申请提交流程** —— QA 怎么触发 `common/04` 的发布 CI（GitLab Pipeline 手动 trigger / 钉钉机器人 / Linear webhook？）

## 反例【强制规避】

```text
❌ 没经过 k8s beta env 测试直接上 prod          → 绕过 QA 关键卡口
❌ P0 bug 找到后还继续推进发布                   → 必须立刻暂停 + 修 / revert
❌ bug 未 sign-off 就提交发布申请                → 违反 sign-off 强 gate
❌ QA 反馈用钉钉私聊 / 群消息记录                → 断追溯；必须 comment 留痕
❌ 把 P2 bug 标 P3 来满足 sign-off                → 违反分级诚信
❌ 跨服务链路回归甩给单一团队                    → 应该跨团队协作，建 cross-team issue
❌ QA 自行修代码绕过原开发者                     → review_* 是审核通过快照；QA 不直接编辑
```

## TODO(@allen)

- **pre / staging 环境**：是否引入？定义 / 部署源分支 / 申请流程
- **QA 提测接收机制**：自动通知 vs 人工 trigger
- **自动化测试基础设施**：接口自动化 / E2E / 性能压测
- **测试用例管理工具**：选型 / 用例归属 / 维护周期
- **bug 跟踪粒度**：Linear sub-issue 还是独立 tracker
- **跨团队回归责任划分**：跨服务变更时的 RACI
- **beta_<date>_<keyword> base 选择**：基于 master tip / 长期 beta tip / 长期 dev tip？影响合并冲突频率
- **发布 CI 触发方式**：GitLab Pipeline 手动 trigger / 钉钉机器人 / Linear webhook？

## 维护

- 环境分层（dev / beta / prod）变化时同步本章 + `common/04` 长期分支对应
- QA 角色 / 责任边界变化时同步责任表
- Bug 分级 SLA 调整需团队共识
- Sign-off checklist 增项时同步本章 + `common/03` §自检
