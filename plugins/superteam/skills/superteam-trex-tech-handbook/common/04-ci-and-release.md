# CI / 发布 / 回滚

## CI 委托模式【强制】

t-rex 所有项目的 CI 流水线规则**中心化托管**在外部仓，本仓的 `.gitlab-ci.yml` 仅作入口。

**架构**：

```text
本项目仓 .gitlab-ci.yml
    │
    │  include:
    │    project: 'Keccak256-evg/ops/gitlab-cis'
    │    ref: master
    │    file: 'gwave-dev/<project>.yaml'
    ▼
ops/gitlab-cis 仓 master 分支
└── gwave-dev/                # `〔t-rex 现状〕`：ops 仓内部目录名仍是历史 `gwave-dev/`（未跟 sub-group rename）
    ├── drex-core.yaml        # `〔t-rex 现状〕`：ops 内 yaml 文件名仍是历史 `drex-*`（虽然 GitLab path 已 rename 到 trex-core）
    ├── trex-web.yaml
    └── <project>.yaml
```

**含义**：
- 改本仓 `.gitlab-ci.yml` 多数无效（被 include 覆盖）
- 真规则在 `Keccak256-evg/ops/gitlab-cis` master 分支
- 修改 CI 需要：① 向 ops 仓提 MR ② 触发对应项目的 CI dry-run 验证 ③ ops 仓 lead approve 后 merge

**反例**：
```text
❌ 在本仓 .gitlab-ci.yml 内直接写 stages / jobs / scripts，期望覆盖 ops 仓的配置
✅ 在 ops/gitlab-cis 提 MR，修改 gwave-dev/<project>.yaml，按 ops 仓的流程合并
```

## K8s 环境 ↔ 长期分支【强制】

```text
研发 dev_<date>_<name>  ──提测MR──►  review_<date>_<name>
                                          │
                                  QA 整合（多个→1个）
                                          ▼
                                  beta_<date>_<keyword>  ──auto deploy──►  k8s beta env
                                          │
                                  QA 测试 + sign-off
                                          │
                                  QA 提交发布申请
                                          ▼
                          [发布 CI 自动建 MR]
                                          │
                                          ▼
                               beta_<date>_<keyword> ──发布MR──► master ──ops──► k8s prod env
                                          │
                                          研发负责人最终审核
```

**反例**：
```text
❌ 从 review_<date>_<name> 直接发 prod                    （必须经 QA 整合到 beta_* 才发）
❌ 从 dev 长期分支发 prod                                  （prod 部署仅来自 master）
❌ 临时切 ops/gitlab-cis 的 ref 把别的分支当 prod 源       （CI 仅认 master 触发 prod 流水线）
```

| K8s 环境 | 长期基线分支 | 部署来源 |
|---|---|---|
| **dev** | `dev` | 短期 `dev_<date>_<name>` 各自部署（联调） |
| **beta** | `beta` | QA 整合的 `beta_<date>_<keyword>` 部署（测试） |
| **prod** | `master` | master 部署（真实用户） |

短期分支说明：
- `dev_<date>_<name>` —— 研发个人特性分支；push 触发 k8s **dev env** 自动部署
- `review_<date>_<name>` —— 提测 MR 通过后的代码快照（不部署，仅审核通过的代码记录）
- `beta_<date>_<keyword>` —— QA 整合的版本候选分支（keyword 由 QA 取，如 `campaign`）；触发 k8s **beta env** 自动部署

## 发布流程：`beta_<date>_<keyword>` → `master`【强制】

**"发布"** 特指 `beta_<date>_<keyword>` → `master` 的 MR（prod release），与**提测**（`dev_*` → `review_*`，见 `common/03`）和 **QA 整合**（`review_*` → `beta_*`，见 `common/07`）解耦。

| 项 | 内容 |
|---|---|
| **MR 源** | `beta_<date>_<keyword>` |
| **MR 目标** | `master` |
| **MR 创建方** | **发布 CI 自动创建**（触发条件：QA 提交发布申请） |
| **Reviewer** | **研发负责人**（最终审核） |
| **MR description 自动填充** | 来自发布单 + 本批包含的 Linear issue 列表 |

### 完整发布流程

```text
[1] QA 在 k8s beta env 完成测试 + sign-off  (见 common/07)
        │
[2] QA 提交发布申请
        │
        ▼
[3] 发布 CI 触发 → 自动建 MR
        源: beta_<date>_<keyword>
        目标: master
        reviewer: 研发负责人
        │
        ▼
[4] 研发负责人审核
        │
        ├── 有 comment → QA 在 beta_<date>_<keyword> 整合修复 → 重测 → 重审
        │
        └── approve → merge MR
                │
                ▼
[5] master merge 后触发 prod 部署流程（见 §发布单 + §灰度）
        │
        ▼
[6] 运维执行灰度部署 + 监控
```

**反例**：
```text
❌ 从 review_* 直接 MR 到 master（绕过 QA 整合 + beta 测试）
❌ 从 dev_* 直接 MR 到 master（绕过整个测试链路）
❌ 研发自行建 beta_* → master MR（必须由发布 CI 触发，避免绕过 QA 流程）
❌ 跳过研发负责人审核
❌ 从 <project>_master / aspen-pre 等历史分支发 prod
```

`〔t-rex 现状〕`长期分支白名单中除 `dev` / `beta` / `master` 外的项（`<project>_master` / `aspen-pre` / `beta_aspen_red` 等）是其他团队的历史用途；trex team **只关心 `dev` / `beta` / `master`** 三条线（见 `common/02-branch-and-commit.md`）。

### 发布准入门槛【强制】

发布 CI 自动建 MR 前（即 QA 提交发布申请前），**必须** 全部满足：

- [ ] `beta_<date>_<keyword>` 已在 k8s beta env 部署 + QA 验证通过（见 `common/07`）
- [ ] QA 在 Linear 提测 issue / 提测单上明确 ✅ sign-off（见 `common/07` §sign-off 标准）
- [ ] P0 / P1 bug 全部 close
- [ ] 性能基线满足（如适用）
- [ ] 发布单已起草（见下方 §发布单）

任一未达即不允许 QA 提交发布申请。

## 灰度策略【强制】

t-rex 后端 prod 发布**必须灰度**，不允许全量直发（仅 P0 hotfix 例外，见 §紧急发布）。

灰度维度（按场景选 1–2 个组合）：

| 维度 | 适用场景 | 实现 |
|---|---|---|
| **按比例** | 通用变更 / 性能验证 | 5% → 20% → 50% → 100% |
| **按用户** | 鉴权 / 体验调整 | 内部员工 → beta 用户 → 全量 |
| **按 region** | 跨区域服务 | 一个 region → 多 region |
| **按实例 / 机器** | 配置变更 | 一台 → 一组 → 全集群 |

**每阶段观察时长**：≥ 5 分钟（看错误率 + 业务指标曲线）。
**任一阶段触发回滚条件**（见下方 §回滚 SOP）则立刻停止并回滚。

`〔运维相关，见 ops runbook〕`：灰度切流量工具（Nacos / 网关 / k8s rolling）+ 各服务灰度配置位置（Nacos namespace / key 模板）由 ops 维护；handbook 只保留触发条件 + 流程 SOP。

## 发布窗口【推荐】

| 时间段 | 状态 |
|---|---|
| 周一–周四 10:00–17:00 | ✅ **推荐发布窗口** |
| 周五全天 | ⚠️ **避免**（周末无完整 on-call 覆盖） |
| 周末 / 节假日 | ❌ **禁止常规发布**（hotfix 例外） |
| 业务高峰（午餐 11:30–13:00 / 晚高峰 17:30–20:00） | ❌ **避免** |
| 双 11 / 双 12 / 春节 / 大型促销期 | ❌ **窗口期冻结**，所有发布走特批 |

**紧急发布**（P0 hotfix）：任何时间，但**必须 on-call 在场**（见 §紧急发布）。

## 发布单【强制】

每次 prod 发布**必须填发布单**，模板：`backend/appendix/templates/release-checklist.md`

### 必填字段

| # | 字段 | 说明 |
|---|---|---|
| 1 | **版本号** | `v<x.y.z>`（语义化版本） |
| 2 | **变更类型** | `feature` / `hotfix` / `chore` / `release` |
| 3 | **发布时间** | `YYYY-MM-DD HH:MM`（窗口内） |
| 4 | **值班人** | `@<gitlab-handle>`（发布全程在线） |
| 5 | **回滚负责人** | `@<gitlab-handle>`（可与值班人同人） |
| 6 | **包含 MR** | 列出本批 beta→master MR + 关联 Linear issue（每个原 review_<date>_<name> 对应的 issue）|
| 7 | **风险评估** | DB migration / 配置变更 / 上下游影响 / 不可逆操作 |
| 8 | **灰度策略** | 按上方维度 + 各阶段比例 / 时长 |
| 9 | **回滚条件** | 错误率阈值 / P99 阈值 / 业务指标 |
| 10 | **回滚动作** | 镜像版本 / Nacos 配置 prev 版本 / DB 迁移逆脚本 |
| 11 | **发布前 checklist** | 见模板 |
| 12 | **发布后 checklist** | 见模板 |

发布单贴 Linear 发布 issue comment（或与本批 dev 上的 issue 关联），全程更新进度。

## 回滚 SOP【强制】

### 触发条件

**任一**满足立刻回滚：

- **错误率** > 阈值（具体阈值见 ops 监控配置；参考起点：5xx > 0.5%）
- **P99 延迟** > 阈值（参考起点：环比 +30%）
- **业务指标** 异常下降（订单 / 注册 / 用户活跃 —— 具体指标定义见 ops runbook / 业务监控配置）
- **大量用户反馈**（客服 / 内部使用方告知）
- **on-call 主观判断**

### 回滚动作

```text
[1] 监控告警 / 用户反馈触发
        │
        ▼
[2] On-call 群内 @值班人 + @回滚负责人  [2 分钟内响应]
        │
        ▼
[3] 评估回滚范围
        │
        ├── 局部异常（单实例 / 单 region）
        │      ▼
        │   Nacos / 网关切流量（剔除问题实例）
        │      ▼
        │   持续监控；若恢复，按 §复盘处理
        │   若不恢复，升级到全量回滚
        │
        └── 全量异常（多实例 / 跨 region）
               ▼
[4]    镜像回退：触发 ops/gitlab-cis 中的 rollback 流水线
               ▼
[5]    配置回滚（如本次发布含配置变更）：Nacos key 回到 prev 版本
               ▼
[6]    DB 迁移回退（如有 schema 变更）：执行预案逆脚本
               ▼
[7]    验证 prod 恢复（监控曲线 + 用户反馈 + 业务指标）
               ▼
[8]    复盘（事后 24h 内 RCA 文档 + Linear comment）
```

`〔运维相关，见 ops runbook〕`：具体可执行命令 / Nacos 切流量手册由 ops 维护。

### 回滚反例【强制规避】

```text
❌ 看到告警先 debug 再决定 → 应该先回滚保业务，再 debug
❌ 回滚后不复盘                → 必须 RCA 24h 内出
❌ DB 已迁移就不能回滚         → 提前准备逆脚本是发布单【强制】字段
❌ 私自跳过灰度，全量发布       → 仅 P0 hotfix 例外，且 on-call 在场
```

## 值班 / On-call【推荐】

- **轮值**：周轮换（`〔运维相关〕`具体排班表见 ops / 团队文档）
- **响应 SLA**：P0 事件 **5 分钟**内响应；P1 事件 30 分钟内
- **on-call 工具**：`〔运维相关〕`选型由 ops 决定（候选：云监控告警推送 / 钉钉机器人 / 电话 / PagerDuty）
- **跨团队 on-call**：发布期间多团队联合值守（开发 + ops + QA）
- **on-call 笔记**：每次 on-call 完成后在团队文档登记（异常 / 处理 / 改进项）

## 紧急发布（Hotfix）

prod P0 故障时的快速通道：

```text
P0 故障 → 立即 on-call 集合 → 评估 hotfix vs 立即回滚
                                  │
                                  ├── 立即回滚先恢复 → 再走正常 hotfix 流程
                                  │
                                  └── 直接 hotfix（极少数情形）：
                                         - 跳过常规灰度（5%→20%→...）可改为 50%→100% 快速灰度
                                         - 必须 team lead + ops + 值班人同时在线
                                         - 24h 内补完整发布单 + RCA 复盘
                                         - 不允许跳过 review（hotfix 分支仍走 hotfix_<date>_<name> → review_<date>_<name> → beta_<date>_<keyword> → master）
```

`〔t-rex 现状〕`：紧急发布是异常路径；近 30 天 < 1 次为健康。频次升高 → 团队 retro 找根因。

## 维护

- CI 委托关系在新增项目时必须同步配置（见 `backend/appendix/templates/new-service-checklist.md`）
- 灰度阈值 / 发布窗口 / 回滚 SLA 调整需团队 + ops 共识，更新本章
- 发布单字段变化时同步 `backend/appendix/templates/release-checklist.md`
- on-call 排班 / 工具链 调整需同步更新本章 §值班
