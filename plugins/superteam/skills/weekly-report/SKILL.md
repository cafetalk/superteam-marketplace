---
name: weekly-report
description: Use when a team member asks to generate a weekly report — produces Markdown weekly reports from task data, knowledge base docs, and other sources
---

# 智能周报生成 (Coming Soon)

根据任务数据、知识库文档等多数据源，自动生成 Markdown 格式周报。

## 状态

> **骨架实现** — 任务数据和知识库文档数据源已可用，GitLab / Agent 用量数据源待接入。

## 使用方式

```bash
python3 scripts/generate_report.py --member "张三"
python3 scripts/generate_report.py --member "张三" --week 2026-W12
python3 scripts/generate_report.py --member "张三" --format json
python3 scripts/generate_report.py --dry-run
```

## 输出

Markdown 格式周报，包含：
- ✅ 本周完成事项
- 🔄 进行中任务
- 🐛 Bug 跟踪
- 📄 文档更新
- 💻 代码提交（待接入）
- 📋 下周计划（手动补充）

## 配置

```
KB_TREX_PG_URL=<postgres://...>
```
