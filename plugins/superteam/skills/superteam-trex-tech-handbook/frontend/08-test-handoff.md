# 前端开发提测流程 SOP

提测阶段与 `common/03-test-handoff.md` 一致；**发布阶段前端不走短期 `beta_*` 分支**，见下文「与 common 的差异」。

## 工作流 stage 与短期分支

| 工作流 stage | 分支 | 说明 |
|---|---|---|
| **prod** | `master` | 生产 |
| **dev** | `dev_<YYMMDD>_<keyword>` | 开发、联调；特性分支预览见 [`12-environments.md`](12-environments.md) |
| **review** | `review_<YYMMDD>_<keyword>` | 提测 MR 目标；`keyword` 与对应 `dev_*` 一致；**亦为发布时的代码来源分支** |

`〔t-rex 前端现状〕`：**不创建**短期 `beta_<YYMMDD>_<keyword>` 工作流分支。`12-environments.md` 中的长期分支 `dev` / `beta` / `pre` / `master` 是稳定环境用，与上表短期分支不同。

示例：`dev_260512_campaign` → MR → `review_260512_campaign` → QA 验收 → 发布合并 `review_260512_campaign` → `master`（trex-website 经 `pre`，见发布单）

## 流程速览

```text
[1] dev_<YYMMDD>_<keyword> 开发 + 自测
[2] 提测 MR：dev_* → review_*（team lead 审核 merge）
[3] QA 在 review_* 特性分支预览 / 约定环境测试 + sign-off
[4] 发布：review_* → master（trex-website：review_* → pre → master）
        发布单见 appendix/templates/release-checklist.md
```

## 与 common 的差异

| 环节 | `common/`（后端 / 平台默认） | 前端 `〔现状〕` |
|---|---|---|
| QA 整合 | 多个 `review_*` → 短期 `beta_*` | **无**短期 `beta_*`；QA 直接在 `review_*` 上验收 |
| 发布 MR | `beta_*` → `master` | `review_*` → `master`（website 经 `pre`） |
| 参考 | `common/07-testing-process.md` | 测试入口见 [`12-environments.md`](12-environments.md) 特性分支预览 |

分支命名仍见 `common/02-branch-and-commit.md`、`common/appendix/project-prefix.md`。

## 提测单字段【强制】

每次建提测 MR 时，**必须同步填写提测单**。字段以 `common/03-test-handoff.md` §提测单 **7 项必填**为基础（提测人、关联 Linear、MR 链接、目标分支 `review_*`、变更范围、自测记录、回滚预案）；回滚预案按**前端语境**写发布回滚 / 配置回退 / 依赖版本回退，不默认 beta 整合语境。

**前端补充项**（在 common 7 项之外或细化）：
- **测试环境**：`dev_*` / `review_*` 分支 + 部署 URL（稳定环境 URL 与特性分支预览见 [`12-environments.md`](12-environments.md)）
- **测试账号 / 钱包地址**（如需）
- **E2E 自测**（仓库已配置 Playwright 时）：关键路径用例通过 + 运行环境 URL（见 [`09-testing.md`](09-testing.md)）

**归档**：提测单写入 `trex-releases` 仓（`releases/<release-item>/submissions/<date>_<name>/submission.md`，由 `superteam-trex-delivery` 的 `submit` 生成，详见 `common/08-release-record.md`）。模板字段参考 `backend/appendix/templates/test-handoff.md`。

## 发布

prod 发布执行 checklist 见 [`appendix/templates/release-checklist.md`](appendix/templates/release-checklist.md)；构建与部署操作见 [`11-quality-ops.md`](11-quality-ops.md)。

发布前须确认跨栈依赖顺序（合约 → 后端 → extension → website 等），详见发布单 §二。
