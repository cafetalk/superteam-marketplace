# 前端开发提测流程 SOP

与 `common/03-test-handoff.md`（提测）、`common/07-testing-process.md`（QA 整合）、`common/04-ci-and-release.md`（发布）**同一套流程**；前端无 `trexbeta_*` 等单独前缀。

## 分支与环境

| 环境 | 分支 | 说明 |
|---|---|---|
| **prod** | `master` | 生产 |
| **dev** | `dev_<YYMMDD>_<keyword>` | 开发、联调（push 触发 dev 部署） |
| **review** | `review_<YYMMDD>_<keyword>` | 提测 MR 目标；`keyword` 与对应 `dev_*` 一致 |
| **beta** | `beta_<YYMMDD>_<keyword>` | QA 整合候选；beta 环境测试 |

示例：`dev_260512_campaign` → MR → `review_260512_campaign` → QA测试 → MR → `master` → 自动发布

## 流程速览

```text
[1] dev_<YYMMDD>_<keyword> 开发 + 自测
[2] 提测 MR：dev_* → review_*（team lead 审核 merge）
[3] QA 整合多个 review_* → beta_<YYMMDD>_<keyword>
[4] beta 环境测试 + sign-off
[5] 发布：beta_* → master；发布单见 appendix/templates/release-checklist.md
```

## 提测单字段

建议至少包含：
- **功能描述**、**关联 Linear**（`TREX-xxx`）
- **测试环境**：`dev_*` / `review_*` 分支 + 部署 URL
- **测试账号 / 钱包地址**（如需）
- **自测 checklist**、**已知问题**

模板见 `backend/appendix/templates/test-handoff.md`。

## 分支命名

见 `common/02-branch-and-commit.md`、`common/appendix/project-prefix.md`。
