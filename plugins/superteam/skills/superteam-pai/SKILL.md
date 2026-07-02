---
name: superteam-pai
description: PAI (Project Action Intelligence) 调度中枢 — 规则规划器编排 pulse 日链路、周报与洞察（B 方案 V1）
---

# PAI — 调度框架

**Project Action Intelligence** 在 Superteam 中的 **编排层**：类似 `scripts/run_reports.sh`，负责子任务顺序、依赖、回填与失败汇总，供 cron / nanobot / Hub 路由统一调用。

## 架构

```
用户自然语言 / --job → run_pai.py（规则规划器）→ plan JSON → 子进程 worker CLI
                                                      ↓
              superteam-report（sprint/task/member、周报）
              superteam-report-insight（PAI 洞察 snapshot_pai）
```

- **不把用户提示词传给 worker**；子 skill 只收结构化 CLI（`--date`、`--out-dir`、`--upload` 等）。
- **C 方案（后处理 / LLM 写作）暂未实现**。

## 命令

```bash
# 等同 run_reports.sh daily（四类 pulse）
python3 skills/superteam-pai/scripts/run_pai.py --job daily

# 自然语言规划（dry-run 只看 plan）
python3 skills/superteam-pai/scripts/run_pai.py --dry-run --prompt "只要 sprint 和 insight"

# 指定日期回填
python3 skills/superteam-pai/scripts/run_pai.py --date 2026-06-20 --job all

# 团队周报（额外参数透传）
python3 skills/superteam-pai/scripts/run_pai.py --job team-weekly -- --dry-run
```

**Hub 路由**：`/superteam-pai`、`superteam-pai`；或自然语言 **更新看板**、**今日 pulse 全量**、**pulse 入库** 等（见 `superteam/SKILL.md` 关键词表）→ `run_pai.py`（`pass_query=True`）。

洞察单步仍走 **`superteam-report-insight`**（如「生成 pai 日报」），不经本 skill。

## Job 与子 skill

| Job / step | Worker skill | 脚本 |
|------------|--------------|------|
| `pulse-daily` | superteam-report | `snapshot_sprint.py` |
| `pulse-task-daily` | superteam-report | `snapshot_task.py` |
| `pulse-pai-daily` | superteam-report-insight | `snapshot_pai.py` |
| `pulse-member-daily` | superteam-report | `snapshot_member.py` |
| `team-weekly` | superteam-report | `generate_team_weekly_report.py` |
| `personal` | superteam-report | `generate_report.py` |

预定义 job：`all` / `daily`（四类 pulse）、`pulse`、`insight` / `pai`、`sprint`、`task`、`member` 等，与 `run_reports.sh` 子命令对齐。

`pulse-pai-daily` 自动依赖 `pulse-daily`（与 shell 串联一致）。

## 配置

与 `run_reports.sh` 相同：`KB_TREX_PG_URL`、`TREX_PULSE_DIR`、`SUPERTEAM_NODE` 等见 `~/.superteam/config`。

## 定时调度（方案 B）

注册表：`~/.superteam/pai/schedules.json`。**不在进程内 sleep**；由 cron 每分钟唤醒 `run-due`。

```bash
# 注册：每 3 小时跑 daily（四类 pulse）；同 job 再次注册会覆盖（如改为 1h）
python3 skills/superteam-pai/scripts/run_pai.py schedule add --job daily --every 3h

# 列出 / 禁用（daily 固定 id 为 pulse-daily）
python3 skills/superteam-pai/scripts/run_pai.py schedule list
python3 skills/superteam-pai/scripts/run_pai.py schedule disable --id pulse-daily

# cron 唤醒（建议每分钟）
* * * * * cd /path/to/superteam && python3 skills/superteam-pai/scripts/run_pai.py schedule run-due >> ~/.superteam/logs/pai-schedule.log 2>&1
```

自然语言注册（含「每/定时」，非立即执行）：

```bash
python3 skills/superteam-pai/scripts/run_pai.py "每3小时刷新看板" --schedule
python3 skills/superteam-pai/scripts/run_pai.py "每3小时刷新看板" --schedule --run-now
```

「更新看板」仍是一次性执行，不会写入 schedule。

## 与 run_reports.sh 的关系

- **run_reports.sh**：固定 DAG，无规划，适合 cron。
- **run_pai.py**：规则型规划器（B V1），适合自然语言或显式 `--job`；可逐步替代 shell 入口。
