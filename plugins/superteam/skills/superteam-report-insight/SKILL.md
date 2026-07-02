---
name: superteam-report-insight
description: Use when generating PAI (Project Action Intelligence) daily briefings — Linear sprint → Project Lead 项目简报，按 by_leader 聚合风险与行动建议（report 洞察派生层）
---

# Report Insight — PAI v2 Project Lead 简报

由同日 **sprint 日快照**（`type=sprint`）派生，**不重复拉 Linear**。面向 Project Lead：按负责人聚合项目简报、风险与建议动作。

> **命名说明**：本 skill 负责 **数据二次加工（洞察 worker）**；**调度编排** 预留 skill **`superteam-pai`**（见 `skills/superteam-pai/SKILL.md`）。

## 命令入口

```bash
python3 skills/superteam-report-insight/scripts/snapshot_pai.py --upload
python3 skills/superteam-report-insight/scripts/snapshot_pai.py --date 2026-06-24 --viewer 王冲
```

**路由关键词（`superteam/scripts/route.py`）**：`PAI`、`pai 日报`、`pai 快照`、`pulse pai`、`project lead 简报` 等 → `snapshot_pai.py`。

定时入口（仓库根目录，经 `run_reports.sh` 编排）：

```bash
bash scripts/run_reports.sh pulse-pai-daily
```

**前置**：必须先有同日 sprint 快照（`bash scripts/run_reports.sh pulse-daily`）。

## 输出

- **本地**：`~/.superteam/pulse/<YYYY-MM-DD>/trex-pai-daily.json`
- **入库**：`sp_trex_pulse`，`type=pai`，`period=daily`，`team=trex`

### Payload 结构（v2）

| 字段 | 说明 |
|------|------|
| `version` | `"2"` |
| `by_leader` | 按 Project Lead 姓名索引；**顶层无** `projects[]` |
| `by_leader.<name>.linear_profile_url` | `https://linear.app/<workspace>/profiles/<slug>` |
| `by_leader.<name>.risks_aggregate` | 风险计数聚合 |
| `by_leader.<name>.problems[]` | 需关注问题列表 |
| `by_leader.<name>.projects[]` | 各项目 `briefing` / `moves` / `risks` |
| `summary` | 一行摘要 |

`--viewer <姓名>` 时仅输出该 Lead，`team` 变为 `trex-<slug>`。

## 与 superteam-report / superteam-pai 的关系

| Skill | 职责 |
|-------|------|
| **superteam-report** | sprint / task / member 快照采集、个人/团队周报 |
| **superteam-report-insight**（本 skill） | PAI v2 洞察派生（sprint → `type=pai`） |
| **superteam-pai** | 调度框架（开发中）；cron 暂用 `scripts/run_reports.sh` |

默认 cron `run_reports.sh all` 顺序：`pulse-daily` → `pulse-task-daily` → **`pulse-pai-daily`** → `pulse-member-daily`。

## 配置

与 pulse 快照相同：`KB_TREX_PG_URL`（入库）、`~/.superteam/pulse`（本地落盘，可用 `TREX_PULSE_DIR` 覆盖）。
