# 前端开发提测流程 SOP

## 五步 SOP

```
[1] 从 master 切 review 保护分支：review_<YYYYMMDD>_<name>
[2] 基于 review_* 切开发分支：trexbeta_<YYYYMMDD>_<name>_<developer>
[3] 少量多次创建 MR：trexbeta_* → review_*（多轮迭代）
[4] 全部功能自测完成后，提交 review_* 给测试
[5] 验收通过后：review_* → master
```

## 步骤详解

| Step | 动作 | 关键产物 | 注意事项 |
|---|---|---|---|
| 1 | 从 master 切保护分支 | `review_<YYYYMMDD>_<name>` | `name` 为功能简称，如 `badge-mint` |
| 2 | 基于 review 分支切开发分支 | `trexbeta_<YYYYMMDD>_<name>_<developer>` | 每位开发者独立开发分支 |
| 3 | 少量多次提 MR | MR（多次，每次小批量）| target 为 `review_*` 分支，不直接 push master |
| 4 | 自测完成，提交 review 分支给测试 | 提测单 | 见下方"提测单字段"；测试在 `review_*` 对应环境验收 |
| 5 | 验收通过合主干 | `review_*` → master | 合并后删除 `review_*` 和对应的 `trexbeta_*` 分支 |

## 前端提测单字段

建议至少包含：
- **功能描述**：本次提测的功能列表
- **关联 Linear**：TREX-xxx 链接
- **测试环境**：对应的 `review_*` 分支 + 部署 URL
- **测试账号 / 钱包地址**（如需）
- **自测 checklist**（开发者已验证的路径）
- **已知问题 / 暂不修复事项**

## 分支命名 regex（Push Rule）

见 `common/02-branch-and-commit.md` 和 `common/appendix/project-prefix.md`。
