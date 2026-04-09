---
name: superteam:weekly-report
description: Use when a team member asks to generate a weekly report — produces Markdown weekly reports from GitLab commits, MR records, and agent usage data
---

# 智能周报生成

根据 GitLab commit/MR 记录、Agent token 用量、使用频次等数据，自动生成 Markdown 格式周报。

## 定位

team member 通过 hub 主动请求（如"帮我生成本周周报"），系统自动汇总本周工作数据并生成结构化周报。

## 状态

> **占位符** — 功能待设计和实现。当前调用将返回"功能开发中"。

## 输入（待定）

- 时间范围（默认本周）
- GitLab project ID
- 团队成员列表

## 输出（待定）

- Markdown 格式周报，包含：
  - 本周完成事项（基于 commit/MR）
  - Agent 使用统计
  - 下周计划（待人工补充）

## 可用数据源

| 数据源 | 说明 | 状态 |
|--------|------|------|
| 任务数据（tm_tasks + AGE graph） | 迭代进度、成员任务、故事点完成情况 | ✅ 已有（sync-task-data 同步） |
| 知识库文档（kb_trex_team_docs） | 本周新增/更新的文档 | ✅ 已有（capture-docs 同步） |
| GitLab commit/MR | 代码提交、合并请求 | 🚧 待对接 |
| Agent token 用量 | AI 工具使用统计 | 🚧 待对接 |

## 待设计事项

- [ ] GitLab API 对接方案
- [ ] Agent token 用量数据源
- [ ] 周报模板设计（可利用 mv_member_iteration_summary 物化视图）
- [ ] 多成员 vs 单成员模式
- [ ] 历史周报存储与检索
- [ ] 利用 AGE 图查询生成成员贡献分析
