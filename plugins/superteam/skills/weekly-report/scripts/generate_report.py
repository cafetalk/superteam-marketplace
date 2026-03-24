#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""weekly-report generator — 周报生成骨架。

聚合多数据源生成 Markdown 周报。已实现的数据源：任务数据、知识库文档。
待实现：GitLab commits/MR、Agent token 用量。

Usage:
    python generate_report.py --member "张三"
    python generate_report.py --member "张三" --week 2026-W12
    python generate_report.py --member "张三" --format json
    python generate_report.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path

# Load shared modules
_sys_path_shared = str(Path(__file__).resolve().parent.parent.parent / "_shared")
if _sys_path_shared not in sys.path:
    sys.path.insert(0, _sys_path_shared)


# ---------------------------------------------------------------------------
# Week utilities
# ---------------------------------------------------------------------------
def _current_iso_week() -> str:
    """Return current ISO week as '2026-W12'."""
    now = datetime.now()
    return f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"


def _week_date_range(iso_week: str) -> tuple[str, str]:
    """Convert '2026-W12' to (start_date, end_date) strings."""
    year, week = iso_week.split("-W")
    # Monday of that ISO week
    monday = datetime.strptime(f"{year}-W{int(week)}-1", "%G-W%V-%u")
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Data source: task management (tm_* tables)
# ---------------------------------------------------------------------------
def fetch_task_data(member: str, start_date: str, end_date: str) -> dict:
    """Query tm_task_members + tm_tasks for member's work in date range.

    Returns: {"tasks_completed": [...], "tasks_in_progress": [...], "bugs": [...]}
    """
    try:
        from db import get_connection
        conn = get_connection()
    except Exception as exc:
        warnings.warn(f"DB not available, skipping task data: {exc}")
        return {"tasks_completed": [], "tasks_in_progress": [], "bugs": []}

    try:
        cur = conn.cursor()

        # Completed tasks
        cur.execute("""
            SELECT t.title, t.status, t.story_points, tm.role, t.done_date::text
            FROM tm_task_members tm
            JOIN tm_tasks t ON t.id = tm.task_id
            WHERE tm.member_name = %s
              AND t.done_date BETWEEN %s AND %s
            ORDER BY t.done_date
        """, (member, start_date, end_date))
        completed = [
            {"title": r[0], "status": r[1], "sp": float(r[2]) if r[2] else 0,
             "role": r[3], "done_date": r[4]}
            for r in cur.fetchall()
        ]

        # In-progress tasks
        cur.execute("""
            SELECT t.title, t.status, t.story_points, tm.role
            FROM tm_task_members tm
            JOIN tm_tasks t ON t.id = tm.task_id
            WHERE tm.member_name = %s
              AND t.status NOT IN ('已完成', '已发布', 'done', 'closed')
            ORDER BY t.title
        """, (member,))
        in_progress = [
            {"title": r[0], "status": r[1], "sp": float(r[2]) if r[2] else 0,
             "role": r[3]}
            for r in cur.fetchall()
        ]

        # Bugs reported/assigned
        cur.execute("""
            SELECT title, severity, status, found_date::text, resolved_date::text
            FROM tm_bugs
            WHERE (reporter = %s OR assignee = %s)
              AND (found_date BETWEEN %s AND %s
                   OR resolved_date BETWEEN %s AND %s)
            ORDER BY found_date
        """, (member, member, start_date, end_date, start_date, end_date))
        bugs = [
            {"title": r[0], "severity": r[1], "status": r[2],
             "found": r[3], "resolved": r[4]}
            for r in cur.fetchall()
        ]

        cur.close()
        conn.close()
        return {
            "tasks_completed": completed,
            "tasks_in_progress": in_progress,
            "bugs": bugs,
        }
    except Exception as exc:
        conn.close()
        warnings.warn(f"Task data query failed: {exc}")
        return {"tasks_completed": [], "tasks_in_progress": [], "bugs": []}


# ---------------------------------------------------------------------------
# Data source: knowledge base docs
# ---------------------------------------------------------------------------
def fetch_kb_docs(member: str, start_date: str, end_date: str) -> list[dict]:
    """Query kb_trex_team_docs for docs updated in date range."""
    try:
        from db import get_connection
        conn = get_connection()
    except Exception:
        return []

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT file_name, doc_type, created_at::text
            FROM kb_trex_team_docs
            WHERE created_at BETWEEN %s AND %s
            ORDER BY created_at DESC
            LIMIT 50
        """, (start_date, end_date))
        docs = [{"file_name": r[0], "doc_type": r[1], "date": r[2]} for r in cur.fetchall()]
        cur.close()
        conn.close()
        return docs
    except Exception:
        conn.close()
        return []


# ---------------------------------------------------------------------------
# Data source: GitLab commits/MR (stub)
# ---------------------------------------------------------------------------
def fetch_gitlab_data(member: str, start_date: str, end_date: str) -> dict:
    """Stub: GitLab API integration — 待实现。"""
    warnings.warn("GitLab data source not yet implemented, returning empty data")
    return {"commits": [], "merge_requests": []}


# ---------------------------------------------------------------------------
# Data source: Agent token usage (stub)
# ---------------------------------------------------------------------------
def fetch_agent_usage(member: str, start_date: str, end_date: str) -> dict:
    """Stub: Agent token usage stats — 待实现。"""
    warnings.warn("Agent usage data source not yet implemented, returning empty data")
    return {"total_tokens": 0, "sessions": []}


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def generate_markdown(
    member: str,
    iso_week: str,
    task_data: dict,
    kb_docs: list[dict],
    gitlab_data: dict,
    agent_usage: dict,
) -> str:
    """Render Markdown weekly report."""
    start, end = _week_date_range(iso_week)
    lines: list[str] = []

    lines.append(f"# 周报 — {member} ({iso_week})")
    lines.append(f"\n> 周期: {start} ~ {end}")
    lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # --- 本周完成 ---
    lines.append("\n## ✅ 本周完成")
    completed = task_data.get("tasks_completed", [])
    if completed:
        total_sp = sum(t.get("sp", 0) for t in completed)
        lines.append(f"\n共完成 **{len(completed)}** 项任务，合计 **{total_sp}** Story Points。\n")
        for t in completed:
            sp_str = f" ({t['sp']} SP)" if t.get("sp") else ""
            lines.append(f"- [{t['role']}] {t['title']}{sp_str}")
    else:
        lines.append("\n_暂无已完成任务数据_")

    # --- 进行中 ---
    lines.append("\n## 🔄 进行中")
    in_progress = task_data.get("tasks_in_progress", [])
    if in_progress:
        for t in in_progress:
            lines.append(f"- [{t['role']}] {t['title']} — {t['status']}")
    else:
        lines.append("\n_暂无进行中任务数据_")

    # --- Bug ---
    lines.append("\n## 🐛 Bug 跟踪")
    bugs = task_data.get("bugs", [])
    if bugs:
        for b in bugs:
            status_icon = "✅" if b.get("resolved") else "🔴"
            lines.append(f"- {status_icon} [{b['severity']}] {b['title']} — {b['status']}")
    else:
        lines.append("\n_本周无相关 Bug_")

    # --- 文档更新 ---
    lines.append("\n## 📄 文档更新")
    if kb_docs:
        lines.append(f"\n本周知识库新增/更新 **{len(kb_docs)}** 篇文档。\n")
        for d in kb_docs[:10]:
            lines.append(f"- [{d['doc_type']}] {d['file_name']}")
        if len(kb_docs) > 10:
            lines.append(f"- _... 及其他 {len(kb_docs) - 10} 篇_")
    else:
        lines.append("\n_本周无文档更新_")

    # --- GitLab (stub) ---
    if gitlab_data.get("commits") or gitlab_data.get("merge_requests"):
        lines.append("\n## 💻 代码提交")
        for c in gitlab_data.get("commits", []):
            lines.append(f"- {c}")
        for mr in gitlab_data.get("merge_requests", []):
            lines.append(f"- MR: {mr}")
    else:
        lines.append("\n## 💻 代码提交")
        lines.append("\n_GitLab 数据源待接入_")

    # --- 下周计划 ---
    lines.append("\n## 📋 下周计划")
    lines.append("\n_请手动补充_\n")
    lines.append("- [ ] ")

    # --- 统计 ---
    lines.append("\n---")
    lines.append(f"_Generated by superteam:weekly-report_")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="weekly-report generator — aggregate data sources into Markdown report"
    )
    parser.add_argument(
        "--member", "-m", required=True,
        help="Member name (e.g. '张三')"
    )
    parser.add_argument(
        "--week", "-w", default=None,
        help="ISO week (e.g. '2026-W12'), defaults to current week"
    )
    parser.add_argument(
        "--format", "-f", choices=["markdown", "json"], default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what data sources would be queried without executing"
    )
    args = parser.parse_args()

    iso_week = args.week or _current_iso_week()
    start_date, end_date = _week_date_range(iso_week)

    if args.dry_run:
        print(json.dumps({
            "member": args.member,
            "week": iso_week,
            "date_range": [start_date, end_date],
            "data_sources": [
                {"name": "task_data", "status": "available", "table": "tm_*"},
                {"name": "kb_docs", "status": "available", "table": "kb_trex_team_docs"},
                {"name": "gitlab", "status": "stub", "note": "待实现"},
                {"name": "agent_usage", "status": "stub", "note": "待实现"},
            ],
        }, ensure_ascii=False, indent=2))
        return

    # Fetch all data sources
    task_data = fetch_task_data(args.member, start_date, end_date)
    kb_docs = fetch_kb_docs(args.member, start_date, end_date)
    gitlab_data = fetch_gitlab_data(args.member, start_date, end_date)
    agent_usage = fetch_agent_usage(args.member, start_date, end_date)

    if args.format == "json":
        print(json.dumps({
            "member": args.member,
            "week": iso_week,
            "task_data": task_data,
            "kb_docs": kb_docs,
            "gitlab_data": gitlab_data,
            "agent_usage": agent_usage,
        }, ensure_ascii=False, indent=2))
    else:
        report = generate_markdown(
            args.member, iso_week,
            task_data, kb_docs, gitlab_data, agent_usage,
        )
        print(report)


if __name__ == "__main__":
    main()
