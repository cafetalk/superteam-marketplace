# Backend 分支清理与整理 archival log — 2026-05-13

本文件是 trex team **首次大规模分支治理**的事件记录。一次性动作，做完留档，handbook 后续规则演化与本文无依赖关系。

如果你只想看当前规约，请回到 `common/02-branch-and-commit.md`。

---

## 1. 背景

2026-05-13 trex team 对 GitLab 上的 t-rex 后端 22 个仓做了一次集中分支治理，含两类动作：

1. **清理**：删除已合入 master/`<project>_master` 的过期分支 + 删除 2025 名字明显过期的残留
2. **整理**：把历史 `<project>dev` / `<project>beta` / `<project>_master` 长期分支重命名为 trex team 新规约的 bare `dev` / `beta` / `master`（详见 `common/02-branch-and-commit.md`）

短期分支（带日期 + name 的 `<project>dev_YYYYMMDD_xxx` 形态）**不批量重命名**，按 handbook policy A 自然消化到 2026-06-30。

## 2. 操作规则

### 清理（Phase 1 / Phase 2 / Phase 3）

| 条件 | 处置 |
|---|---|
| branch tip 是 master/`<project>_master` 的 ancestor（严格合入） | **删** |
| 名字 regex 匹配 `_2025\d{4}_` 的非合入分支 | **删** |
| 名字不匹配 2025 但 > 60 天未活动 + 未合入 | 询问 owner（多数也删） |
| 跨项目错放的分支（drex 项目残留在 anchor 仓） | **删**（Phase 3） |
| 60 天内活跃 + 未合入 | **保留** |

### 整理（Phase 4 / Phase 5）

| 老规约长期分支 | 新规约 | 操作 |
|---|---|---|
| `<project>dev` (bare, 无日期 / name) | `dev` | `git push origin <old>:dev` + `git push origin --delete <old>` |
| `<project>beta` (bare) | `beta` | 同上 |
| `<project>_master` | `master` | 多数情形 `git push origin <project>_master:master` fast-forward + 删 `<project>_master`；分叉情形人工 merge 后清 |

短期分支（Phase 6 deferred）：开发者下次接触各自 `<project>dev_<date>_<name>` 时 squash + 重命名到 `dev_<YYMMDD>_<name>`。team policy 6/30 deadline。

## 3. Phase 1 — 首轮严格清理（5 backend-java 仓）

| 仓 | 之前 | 之后 | 删除 |
|---|---|---|---|
| drex-passport | 98 | 7 | 91 |
| drex-core | 93 | 22 | 71 |
| trex-web | 119 | 19 | 100 |
| drex-endpoint | 21 | 9 | 12 |
| drex-event | 17 | 2 | 15 |
| **小计** | **348** | **59** | **289** |

drex-event 用 `drex_master` 作 anchor（master 本仓停滞 10 月），其他仓用 master。

## 4. Phase 2 — 二轮清理（17 仓：trex-admin + 3 backend-python + 13 anchor）

| 仓 | 之前 | 之后 | 删除 |
|---|---|---|---|
| trex-admin | 0 | 0 | 0 |
| trex-hexagonal | 3 | 1 | 2 |
| trex-persona-feast | 14 | 2 | 12 |
| trex-prism-engine | 12 | 1 | 11 |
| anchor-admin | 15 | 8 | 7 |
| anchor-core | 118 | 9 | **109** |
| anchor-dashboard | 11 | 7 | 4 |
| anchor-endpoint | 27 | 2 | 25 |
| anchor-event | 17 | 1 | 16 |
| anchor-insight-nft | 38 | 4 | 34 |
| anchor-insight-thirdpart | 19 | 5 | 14 |
| anchor-insight-token | 27 | 4 | 23 |
| anchor-insight-zktls | 46 | 4 | 42 |
| anchor-labs | 3 | 2 | 1 |
| anchor-sdk | 6 | 3 | 3 |
| anchor-team | 46 | 2 | 44 |
| anchor-web | 71 | 6 | 65 |
| **小计** | **473** | **61** | **412** |

anchor-core 是单项最大清理量（109）。trex-admin 是初始化仓（无内容）。

## 5. Phase 3 — Tier C 跨项目残留清理

`drexdev_20260312_log_alert` + `drexreview_20260312_log_alert` 错推到 anchor 仓里（应该在 drex 项目）：

| 仓 | 删除 |
|---|---|
| anchor-insight-nft | 2 |
| anchor-insight-thirdpart | 2 |
| anchor-insight-token | 2 |
| anchor-web | 2 |
| **小计** | **8** |

## 6. Phase 4 — Tier A 长期 dev 分支重命名（12 仓）

| 仓 | 老 | 新 | 备注 |
|---|---|---|---|
| drex-passport | drexdev | dev | |
| drex-core | drexdev | dev | |
| trex-web | drexdev | dev | |
| trex-persona-feast | drexdev | dev | |
| anchor-core | anchordev | dev | |
| anchor-endpoint | anchordev | dev | |
| anchor-insight-nft | anchordev | dev | |
| anchor-insight-thirdpart | anchordev | dev | |
| anchor-insight-token | anchordev | dev | ⚠️ 第一次 push 静默失败，第二次补救成功 |
| anchor-insight-zktls | anchordev | dev | ⚠️ 同上 |
| anchor-team | anchordev | dev | |
| anchor-web | anchordev | dev | ⚠️ 远端有旧 `dev` 指向 master tip 与 anchordev 分叉；force-update `dev` 到 anchordev 内容（保留 5 个独有 commits：log_alert / notary / mbti） |

## 7. Phase 5 — Tier B 长期 master 整合（3 backend-java 仓）

用户手动执行（自动化路径被 `Bash(git push *:master)` deny rule 拦下）：

| 仓 | drex_master 状态 | 操作 |
|---|---|---|
| drex-endpoint | 比 master 多 16 commits | `git push origin drex_master:master` fast-forward + 删 drex_master |
| drex-event | 比 master 多 48 commits（master 停滞 10 月）| 同上 |
| trex-web | master(+1) vs drex_master(+22) 分叉 | 人工 merge 后 push + 删 drex_master |

drex-core 的 drex_master 在 Phase 1 已清，无 Phase 5 操作。

## 8. Phase 6 — Tier D 短期分支批量重命名（DEFERRED）

约 50 个短期分支保留旧形态 `<project><stage>_<YYYYMMDD>_<name>`。按 handbook policy A：

- 不批量动；避免破坏 in-flight 工作
- 开发者下次接触自己分支时 squash + 重命名到 `<stage>_<YYMMDD>_<name>` 新规约
- team policy: **2026-06-30** deadline 前全部消化
- 6/30 之后审查残留，必要时强制重命名

## 9. 累计数据

| 维度 | 数量 |
|---|---|
| 覆盖仓数 | 22 |
| Phase 1+2+3 删除分支 | 289 + 412 + 8 = **709** |
| Phase 4 重命名（含 1 个 force-update） | 12 |
| Phase 5 master 整合 | 3 |
| 起始分支总数（含 master）| 821 |
| 终态分支总数 | ~108（含 master + dev + 短期 in-flight）|
| **净减少** | ~86% |

## 10. 关联的 handbook 改动

本次治理同步在 handbook 中落地：

- `common/02-branch-and-commit.md` 加入 `<project>dev/beta/<project>_master → dev/beta/master` 迁移映射表 + rename SOP
- `common/appendix/project-prefix.md` Push Rule regex 末尾追加 trex team 新规约 alternation（org 共享模版兼容性纯添加）
- `common/01-gitlab-and-workspace.md` 升级到 4 个 sub-group 描述（backend-java / backend-python / anchor / skills），含归属规约表
- `backend/01-microservices.md` 全量重写为 22-repo 完整 catalog（GitLab API 实时校验）

## 11. trex team 治理后长期分支对齐表（backend-java 6 仓）

| 仓 | master | dev | beta | 历史长期 |
|---|---|---|---|---|
| drex-passport | ✅ | ✅ | — | — |
| drex-core | ✅ | ✅ | — | — |
| trex-web | ✅ | ✅ | — | — |
| drex-endpoint | ✅ | — | — | — |
| drex-event | ✅ | — | — | — |
| trex-admin | ✅ | — | — | — |

不所有仓都强制有 `dev`，只有 trex-team 长期使用集成分支的项目才创建（其他项目可直接 review→master）。

## 12. 未来如何参考

- **新仓 setup**：按 `common/01-gitlab-and-workspace.md` 子组归属 + `backend/appendix/templates/new-service-checklist.md` 初始化
- **历史分支询问 owner**：本文件 Phase 1 的"询问 owner 列表"（已在 git history 中归档，可恢复）
- **下次类似治理**：参考本文操作规则（Section 2）

## 维护

- 本文件是**事件归档**，不会更新；未来类似治理另起 `branch-cleanup-<date>.md`
- handbook 规则演化以 `common/02-branch-and-commit.md` 为准
- 若发现本治理遗漏的过期分支，按本文 Section 2 规则评估后单独处理
