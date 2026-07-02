#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""superteam-report generator — 基于 Linear Cycle 为 workspace 全部 Team 生成周报。

只读：通过本机 Linear MCP（`mcp-remote https://mcp.linear.app/mcp`）的 stdio JSON-RPC
调用 tools/list / tools/call 拉取 Team / Cycle / Issue 数据，生成 Markdown。

**项目相关逻辑的数据边界（禁止按具体 Project 名/id 分支）**：
纳入清单、项目阶段、风险等**仅**依据 Linear 返回的 ``issue`` / ``project`` 字段；
**项目一览纳入条件**：Linear Project 状态**仅** **Planned**、**In Progress**
（``status.type`` 为 ``planned`` / ``started``；排除 Backlog / Completed / Canceled）；不按时间窗过滤；
``issue`` 的数量与状态（含 ``statusType`` / ``state.type`` 回退）、以及经
``_iter_report_members()`` 过滤后的 ``list_members()``（与 superteam-member
``list_members.py`` 同源：排除 deleted/merged/无 role；**仅** backend / frontend / architect
与测试职能成员进入周报名单）解析出的
backend / frontend / architect 研发名单；**不得**为某个 workspace 项目写死名称或 id。允许的固定字面量仅限
与「具体哪一个 Linear 项目」无关的占位或集成常量（如「未关联项目」、钉钉目录名）。

Usage:
  python generate_team_weekly_report.py
  # 默认：上周（本地自然周对应的 ISO 周），无需传 --week
  python generate_team_weekly_report.py --week 2026-W15
  python generate_team_weekly_report.py --output reports/team-weekly/2026-W15.md
  python generate_team_weekly_report.py --dry-run
  # 进行中项目截至昨日变化（仅 JSON，默认目录 reports/project-daily/）：
  python generate_team_weekly_report.py --in-progress-snapshot
  # 配置了钉钉 MCP（DINGTALK_MCP_URL 或 ~/.cursor/mcp.json）时自动上传；可用 --no-publish-dingtalk 关闭
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any


# Load shared config helper (keeps architecture: skill script imports _shared/config.py only)
_sys_path_shared = str(Path(__file__).resolve().parent.parent.parent / "_shared")
if _sys_path_shared not in sys.path:
    sys.path.insert(0, _sys_path_shared)

from config import dingtalk_mcp_url, env  # noqa: E402
from daily_report_snapshots import load_weekly_member_code_stats_lookup  # noqa: E402
from db import list_members  # noqa: E402  # type: ignore[reportMissingImports]

# 与 skills/weekly-report/scripts/generate_report.py 一致：团队周报发布到同一钉钉文档目录。
REPORT_FOLDER_URL = (
    "https://alidocs.dingtalk.com/i/nodes/AR4GpnMqJzMM2vo3fqv3bQ7bVKe0xjE3?utm_scene=team_space"
)
REPORT_FOLDER_ID = "AR4GpnMqJzMM2vo3fqv3bQ7bVKe0xjE3"

# 状态分布 / 工作类型等「占比条」：固定字符总长 = 100% 满格（与百分比列一致，不按「数量/最多的一类」缩放）
DISTRIBUTION_PCT_BAR_WIDTH = 20

class _LocalMcpError(Exception):
    pass


class _StdioMcpClient:
    """Minimal MCP stdio JSON-RPC client for `mcp-remote`."""

    def __init__(self, cmd: list[str]):
        self._cmd = cmd
        self._proc: subprocess.Popen[str] | None = None
        self._next_id = 1

    def __enter__(self):
        self._proc = subprocess.Popen(
            self._cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,  # inherit to show OAuth prompts/URLs
            text=True,
            bufsize=1,
        )
        self._call(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "superteam-report", "version": "0.1.0"},
            },
        )
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def _call(self, method: str, params: dict) -> dict:
        if not self._proc or not self._proc.stdin or not self._proc.stdout:
            raise _LocalMcpError("local mcp process not started")
        req_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        self._proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise _LocalMcpError("local mcp closed stdout unexpectedly")
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") != req_id:
                continue
            if "error" in msg:
                err = msg["error"] or {}
                code = err.get("code", "unknown")
                message = err.get("message", "")
                raise _LocalMcpError(f"{code}: {message}")
            return msg.get("result", {}) or {}

    def list_tools(self) -> set[str]:
        res = self._call("tools/list", {})
        tools = res.get("tools", [])
        names: set[str] = set()
        if isinstance(tools, list):
            for t in tools:
                if isinstance(t, dict) and isinstance(t.get("name"), str):
                    names.add(t["name"])
        return names

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        res = self._call("tools/call", {"name": name, "arguments": arguments})
        structured = (res.get("structuredContent") or {}).get("result")
        if structured is not None:
            return structured
        content = res.get("content", [])
        if content and isinstance(content, list) and isinstance(content[0], dict):
            if content[0].get("type") == "text":
                text = content[0].get("text", "")
                try:
                    return json.loads(text)
                except Exception:
                    return text
        return res


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _current_iso_week(now: datetime | None = None) -> str:
    now = now or datetime.now()
    return f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"


def _iso_week_for_date(d: date) -> str:
    """给定自然日所在 ISO 周（周一至周日）。"""
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _last_iso_week(now: datetime | None = None) -> str:
    """上一自然周（周一至周日）对应的 ISO 周，用于周报标题与落盘文件名。"""
    now = now or datetime.now()
    d = now.date()
    days_since_mon = d.weekday()  # Mon=0
    mon_this_week = d - timedelta(days=days_since_mon)
    mon_last_week = mon_this_week - timedelta(days=7)
    y, w, _ = mon_last_week.isocalendar()
    return f"{y}-W{w:02d}"


# 进行中项目快照：项目阶段仍属推进中（与 _project_table_progress_kind 口径一致）
# 未到提测日时，「联调中」仅当报告日距提测里程碑不超过该天数（含当天算 0 天）
_INTEGRATION_STATUS_MAX_DAYS_BEFORE_TEST = 3

_IN_PROGRESS_PROJECT_STATUS_LABELS = frozenset({
    "开发中",
    "联调中",
    "设计中",
    "延期开发中",
    "启动中",
    "测试中",
    "待发布",
    "延期上线",
})

# Linear Project 状态（UI：Backlog / Planned / In Progress / Completed / Canceled）
# 周报与 sprint 项目清单仅纳入 Planned、In Progress。
_LINEAR_PROJECT_STATUS_TYPES_IN_SCOPE = frozenset({"planned", "started"})
_LINEAR_PROJECT_STATUS_NAMES_IN_SCOPE = frozenset({"planned", "in progress"})
# product_created_pending（设计中的需求）额外纳入 Backlog 项目。
_LINEAR_PROJECT_STATUS_TYPES_PRODUCT_PENDING = frozenset({"planned", "started", "backlog"})
_LINEAR_PROJECT_STATUS_NAMES_PRODUCT_PENDING = frozenset({"planned", "in progress", "backlog"})


def _local_tzinfo():
    return datetime.now().astimezone().tzinfo


def _snapshot_yesterday_end(now: datetime | None = None) -> datetime:
    """本地时区「昨日」23:59:59，作为进行中快照的统计截止时刻。"""
    now = now or datetime.now()
    yday = now.date() - timedelta(days=1)
    tz = _local_tzinfo()
    return datetime(yday.year, yday.month, yday.day, 23, 59, 59, tzinfo=tz)


def _snapshot_change_window_start(now: datetime | None = None) -> datetime:
    """变化统计窗口起点：昨日 00:00:00（本地）。"""
    now = now or datetime.now()
    yday = now.date() - timedelta(days=1)
    tz = _local_tzinfo()
    return datetime(yday.year, yday.month, yday.day, 0, 0, 0, tzinfo=tz)


def _ensure_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _issue_activity_in_window(
    it: dict[str, Any],
    win_start: datetime,
    win_end: datetime,
) -> bool:
    """Issue 在窗口内有 created / updated / completed 任一活动即视为「有变化」。"""
    ws = _ensure_aware_utc(win_start)
    we = _ensure_aware_utc(win_end)
    for field in ("updatedAt", "completedAt", "createdAt"):
        dt = _parse_dt(it.get(field))
        if not dt:
            continue
        t = _ensure_aware_utc(dt)
        if ws <= t <= we:
            return True
    return False


def _report_week_datetime_bounds(iso_week: str) -> tuple[datetime, datetime]:
    """报告自然周 [周一 00:00, 周日 23:59:59]（本地时区）。"""
    start_s, end_s = _week_date_range(iso_week)
    tz = _local_tzinfo()
    win_start = datetime.combine(date.fromisoformat(start_s), time.min, tzinfo=tz)
    win_end = datetime.combine(date.fromisoformat(end_s), time(23, 59, 59), tzinfo=tz)
    return win_start, win_end


def _dt_in_window(dt: datetime | None, win_start: datetime, win_end: datetime) -> bool:
    if not dt:
        return False
    t = _ensure_aware_utc(dt)
    ws = _ensure_aware_utc(win_start)
    we = _ensure_aware_utc(win_end)
    return ws <= t <= we


def _is_in_review_status_name(it: dict[str, Any]) -> bool:
    return "review" in str(it.get("status") or "").lower()


def _issue_week_status_transitions(
    it: dict[str, Any],
    iso_week: str,
    status_type_map: dict[str, str],
) -> list[str]:
    """报告周内进入的目标状态（可多选）：in_progress / done / in_review。"""
    if _state_bucket_for_issue(it, status_type_map) == "canceled":
        return []
    win_start, win_end = _report_week_datetime_bounds(iso_week)
    labels: list[str] = []

    completed = _parse_dt(it.get("completedAt"))
    if _dt_in_window(completed, win_start, win_end):
        labels.append("done")

    started = _parse_dt(it.get("startedAt"))
    if _dt_in_window(started, win_start, win_end):
        labels.append("in_progress")
    elif _state_bucket_for_issue(it, status_type_map) == "in_progress":
        updated = _parse_dt(it.get("updatedAt"))
        if _dt_in_window(updated, win_start, win_end):
            labels.append("in_progress")

    if _is_in_review_status_name(it):
        updated = _parse_dt(it.get("updatedAt"))
        if _dt_in_window(updated, win_start, win_end):
            labels.append("in_review")

    # 去重且保持顺序：已完成 > 进行中 > In Review
    order = ("done", "in_progress", "in_review")
    return [k for k in order if k in labels]


def _issue_in_member_week_activity_scope(
    it: dict[str, Any],
    iso_week: str,
    status_type_map: dict[str, str],
) -> bool:
    return bool(_issue_week_status_transitions(it, iso_week, status_type_map))


def _issue_completed_in_iso_week(
    it: dict[str, Any],
    iso_week: str,
    status_type_map: dict[str, str],
) -> bool:
    """``completedAt`` 落在报告自然周内（与 member ``done_this_week`` 一致）。"""
    if _state_bucket_for_issue(it, status_type_map) != "done":
        if _linear_issue_status_type_lower(it, status_type_map) != "completed":
            return False
    completed = _parse_dt(it.get("completedAt"))
    if not completed:
        return False
    win_start, win_end = _report_week_datetime_bounds(iso_week)
    return _dt_in_window(completed, win_start, win_end)


def _issue_due_in_iso_week(it: dict[str, Any], iso_week: str) -> bool:
    """``dueDate`` / ``targetDate`` / ``endDate`` 日历日落入报告自然周。"""
    due = _issue_due_date(it)
    if due is None:
        return False
    start_s, end_s = _week_date_range(iso_week)
    week_start = date.fromisoformat(start_s)
    week_end = date.fromisoformat(end_s)
    return week_start <= due <= week_end


def _issue_in_member_week_workload_scope(
    it: dict[str, Any],
    iso_week: str,
    status_type_map: dict[str, str],
) -> bool:
    """计入当周成员负载：本周完成、当前进行中（含 In Review / 受阻）、或 Todo 且截止日在本周。"""
    b = _state_bucket_for_issue(it, status_type_map)
    if b == "canceled":
        return False
    if b == "done":
        return _issue_completed_in_iso_week(it, iso_week, status_type_map)
    if b == "in_progress":
        return True
    if _is_in_review_status_name(it) or _is_blocked_status(it.get("status")):
        return True
    if b in ("todo", "backlog"):
        return _issue_due_in_iso_week(it, iso_week)
    return False


def _is_in_progress_project_status(status_label: str) -> bool:
    return status_label in _IN_PROGRESS_PROJECT_STATUS_LABELS


def _filter_cycle_issues_for_snapshot(
    cycle_issues: list[dict[str, Any]],
    *,
    win_start: datetime,
    win_end: datetime,
    in_progress_project_names: set[str],
) -> list[dict[str, Any]]:
    """保留：所属项目在推进中 且 昨日窗口内有活动的当前 Cycle issue。"""
    out: list[dict[str, Any]] = []
    for it in cycle_issues:
        pname = _issue_project_name(it)
        if pname not in in_progress_project_names:
            continue
        if _issue_activity_in_window(it, win_start, win_end):
            out.append(it)
    return out


def _in_progress_project_names_from_stats(proj_stats: list[dict[str, Any]]) -> set[str]:
    return {
        str(s["name"])
        for s in proj_stats
        if _is_in_progress_project_status(str(s.get("status_label") or ""))
    }


def _week_date_range(iso_week: str) -> tuple[str, str]:
    year, week = iso_week.split("-W")
    monday = datetime.strptime(f"{year}-W{int(week)}-1", "%G-W%V-%u")
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def _report_week_start_date(iso_week: str) -> date:
    """本报告所覆盖的 ISO 自然周（周一至周日）的周一日期。"""
    start_s, _ = _week_date_range(iso_week)
    return datetime.strptime(start_s, "%Y-%m-%d").date()


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    # Linear uses ISO-8601. Python 3.9 can't parse trailing Z with fromisoformat.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


class LinearMcpClient:
    def __init__(self):
        self._cmd = ["npx", "-y", "mcp-remote", "https://mcp.linear.app/mcp"]

    def _pick(self, names: set[str], primary: str, fallback: str) -> str:
        if primary in names:
            return primary
        if fallback in names:
            return fallback
        raise _LocalMcpError(f"找不到需要的工具：{primary}（或 {fallback}）")

    def list_teams(self, client: _StdioMcpClient, tool_names: set[str] | None = None, limit: int = 250) -> list[dict[str, Any]]:
        tool_names = tool_names or client.list_tools()
        tool = self._pick(tool_names, "list_teams", "linear_list_teams")
        data = client.call_tool(tool, {"limit": limit})
        if isinstance(data, dict) and isinstance(data.get("teams"), list):
            return data["teams"]
        if isinstance(data, list):
            return data
        return []

    def list_cycles_current(self, client: _StdioMcpClient, tool_names: set[str] | None, team_id: str) -> list[dict[str, Any]]:
        tool_names = tool_names or client.list_tools()
        tool = self._pick(tool_names, "list_cycles", "linear_list_cycles")
        data = client.call_tool(tool, {"teamId": team_id, "type": "current"})
        return data if isinstance(data, list) else []

    def list_cycles_for_team(
        self,
        client: _StdioMcpClient,
        tool_names: set[str] | None,
        team_id: str,
    ) -> list[dict[str, Any]]:
        """按 team 拉取 current/previous/next cycles 并去重，用于按时间窗口匹配目标周。"""
        tool_names = tool_names or client.list_tools()
        tool = self._pick(tool_names, "list_cycles", "linear_list_cycles")
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for cycle_type in ("current", "previous", "next"):
            data = client.call_tool(tool, {"teamId": team_id, "type": cycle_type})
            if not isinstance(data, list):
                continue
            for row in data:
                if not isinstance(row, dict):
                    continue
                cid = str(row.get("id") or row.get("cycleId") or "").strip()
                if cid and cid in seen:
                    continue
                if cid:
                    seen.add(cid)
                merged.append(row)
        return merged

    def list_issue_statuses(self, client: _StdioMcpClient, tool_names: set[str] | None, team_id: str) -> list[dict[str, Any]]:
        tool_names = tool_names or client.list_tools()
        tool = self._pick(tool_names, "list_issue_statuses", "linear_list_issue_statuses")
        data = client.call_tool(tool, {"team": team_id})
        return data if isinstance(data, list) else []

    def get_project(
        self,
        client: _StdioMcpClient,
        tool_names: set[str] | None,
        query: str,
    ) -> dict[str, Any]:
        """按名称或 ID 拉取单个 Project（字段可能比 list 更全，含自定义日期）。"""
        tool_names = tool_names or client.list_tools()
        tool = self._pick(tool_names, "get_project", "linear_get_project")
        data = client.call_tool(tool, {"query": query})
        return data if isinstance(data, dict) else {}

    def list_projects(
        self,
        client: _StdioMcpClient,
        tool_names: set[str] | None,
        *,
        limit: int = 50,
        max_pages: int = 20,
    ) -> list[dict[str, Any]]:
        """拉取 workspace 内 Project 元数据（创建时间、Linear 状态、结束时间等）。"""
        # Linear MCP 在 limit 过大（如 250）时可能返回校验错误字符串，故分页用较小 page size。
        projects: list[dict[str, Any]] = []
        cursor: str | None = None
        tool_names = tool_names or client.list_tools()
        tool = self._pick(tool_names, "list_projects", "linear_list_projects")
        for _ in range(max_pages):
            args: dict[str, Any] = {"limit": limit}
            if cursor:
                args["cursor"] = cursor
            data = client.call_tool(tool, args)
            if not isinstance(data, dict):
                break
            batch = data.get("projects") or []
            if not isinstance(batch, list):
                break
            projects.extend(batch)
            if not data.get("hasNextPage"):
                break
            cursor = data.get("cursor") or data.get("nextCursor")
            if not cursor:
                break
        return projects

    def list_milestones_for_project(
        self,
        client: _StdioMcpClient,
        tool_names: set[str] | None,
        project_id: str,
    ) -> list[dict[str, Any]]:
        """拉取 Project 下 Milestone 列表（含提测/发布里程碑与 targetDate）。"""
        if not project_id:
            return []
        tool_names = tool_names or client.list_tools()
        tool = self._pick(tool_names, "list_milestones", "linear_list_milestones")
        data = client.call_tool(tool, {"project": project_id})
        if isinstance(data, dict) and isinstance(data.get("milestones"), list):
            return [m for m in data["milestones"] if isinstance(m, dict)]
        return []

    def list_issues_in_cycle(
        self,
        client: _StdioMcpClient,
        tool_names: set[str] | None,
        team_id: str,
        cycle_id: str,
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """按 Cycle 拉取 issue（服务端过滤，字段完整）。全量 ``list_issues(team=…)`` 常不带 cycle，不能替代本接口。"""
        issues: list[dict[str, Any]] = []
        cursor: str | None = None
        tool_names = tool_names or client.list_tools()
        tool = self._pick(tool_names, "list_issues", "linear_list_issues")
        while True:
            args: dict[str, Any] = {"team": team_id, "cycle": cycle_id, "limit": limit}
            if cursor:
                args["cursor"] = cursor
            data = client.call_tool(tool, args)
            if not isinstance(data, dict):
                break
            issues.extend(data.get("issues") or [])
            if not data.get("hasNextPage"):
                break
            cursor = data.get("cursor") or data.get("nextCursor")
            if not cursor:
                break
        return issues

    def list_issues_for_team(
        self,
        client: _StdioMcpClient,
        tool_names: set[str] | None,
        team_id: str,
        *,
        include_archived: bool = False,
        page_limit: int = 250,
        max_pages: int = 25,
    ) -> list[dict[str, Any]]:
        """分页拉取某 Team 下 issues（不按 Cycle 过滤），供筛选「未划入迭代」等。"""
        issues: list[dict[str, Any]] = []
        cursor: str | None = None
        tool_names = tool_names or client.list_tools()
        tool = self._pick(tool_names, "list_issues", "linear_list_issues")
        for _ in range(max_pages):
            args: dict[str, Any] = {
                "team": team_id,
                "limit": page_limit,
                "orderBy": "updatedAt",
                "includeArchived": include_archived,
            }
            if cursor:
                args["cursor"] = cursor
            data = client.call_tool(tool, args)
            if not isinstance(data, dict):
                break
            batch = data.get("issues") or []
            issues.extend(batch)
            if not data.get("hasNextPage"):
                break
            cursor = data.get("cursor") or data.get("nextCursor")
            if not cursor:
                break
        return issues

    def list_comments(
        self,
        client: _StdioMcpClient,
        tool_names: set[str] | None,
        issue_id: str,
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        tool_names = tool_names or client.list_tools()
        tool = self._pick(tool_names, "list_comments", "linear_list_comments")
        data = client.call_tool(tool, {"issueId": issue_id, "limit": limit, "orderBy": "updatedAt"})
        if isinstance(data, dict) and isinstance(data.get("comments"), list):
            return [c for c in data["comments"] if isinstance(c, dict)]
        if isinstance(data, list):
            return [c for c in data if isinstance(c, dict)]
        return []


@dataclass
class GroupedIssues:
    done: list[dict[str, Any]]
    in_progress: list[dict[str, Any]]
    todo: list[dict[str, Any]]
    backlog: list[dict[str, Any]]


def _state_group_from_type(status_type: str | None) -> str:
    t = (status_type or "").lower().strip()
    if t == "completed":
        return "done"
    if t == "started":
        return "in_progress"
    if t == "unstarted":
        return "todo"
    if t in ("backlog", "triage"):
        return "backlog"
    if t == "canceled":
        return "done"
    return "todo"


def group_issues(issues: list[dict[str, Any]], status_type_map: dict[str, str]) -> GroupedIssues:
    buckets = {"done": [], "in_progress": [], "todo": [], "backlog": []}
    for it in issues:
        status_type = _linear_issue_status_type_lower(it, status_type_map)
        g = _state_group_from_type(status_type if status_type else None)
        buckets[g].append(it)

    def _priority_sort_value(p: Any) -> int:
        # Linear convention: 1=Urgent,2=High,3=Normal/Medium,4=Low,0/None=no priority
        if isinstance(p, dict):
            v = p.get("value")
            if isinstance(v, (int, float)):
                return int(v)
            name = (p.get("name") or "").lower()
            return {"urgent": 1, "high": 2, "medium": 3, "normal": 3, "low": 4}.get(name, 999)
        if isinstance(p, (int, float)):
            return int(p)
        return 999

    # Stable sort for readability
    for k in buckets:
        buckets[k].sort(
            key=lambda x: (_priority_sort_value(x.get("priority")), x.get("updatedAt") or ""),
            reverse=False,
        )

    return GroupedIssues(
        done=buckets["done"],
        in_progress=buckets["in_progress"],
        todo=buckets["todo"],
        backlog=buckets["backlog"],
    )


def _assignee_name(issue: dict[str, Any]) -> str:
    # plugin-linear-linear returns assignee as string
    a = issue.get("assignee")
    if isinstance(a, str):
        return a
    if isinstance(a, dict):
        return a.get("displayName") or a.get("name") or ""
    an = issue.get("assigneeName")
    if isinstance(an, str) and an.strip():
        return an.strip()
    return ""

def _issue_key(issue: dict[str, Any]) -> str:
    return str(issue.get("identifier") or issue.get("id") or "").strip() or "UNKNOWN"


def _issue_label_tokens(it: dict[str, Any]) -> set[str]:
    """Issue 上 labels 归一化为小写 token（匹配 name / slug / id 字符串）。"""
    raw = it.get("labels")
    if not raw:
        return set()
    out: set[str] = set()
    if not isinstance(raw, list):
        return out
    for x in raw:
        if isinstance(x, str) and x.strip():
            out.add(x.strip().lower())
        elif isinstance(x, dict):
            for key in ("name", "slug", "id"):
                v = x.get(key)
                if isinstance(v, str) and v.strip():
                    out.add(v.strip().lower())
    return out


def count_cycle_issues_by_work_labels(issues: list[dict[str, Any]]) -> tuple[int, int, int]:
    """当前迭代内 issue 按标签分类计数：demand→需求、task→任务、bug→Bug（可重叠）。"""
    n_demand = n_task = n_bug = 0
    for it in issues:
        labs = _issue_label_tokens(it)
        if "demand" in labs:
            n_demand += 1
        if "task" in labs:
            n_task += 1
        if "bug" in labs:
            n_bug += 1
    return n_demand, n_task, n_bug


def _is_bug_like_issue(it: dict[str, Any]) -> bool:
    """用于「测试中」补充展示：标签含 bug / 标题形似 Bug 单。"""
    if "bug" in _issue_label_tokens(it):
        return True
    title = str(it.get("title") or "").strip()
    if re.match(r"(?i)^bug[\s:：]", title):
        return True
    if "缺陷" in title:
        return True
    return False


def _bug_cycle_stats(
    items: list[dict[str, Any]],
    status_type_map: dict[str, str],
) -> tuple[int, int]:
    """本 Cycle 内 Bug 口径条数：(总数, 未关闭数)；未关闭 = 非 done 且非 canceled。"""
    bugs = [it for it in items if _is_bug_like_issue(it)]
    n = len(bugs)
    open_n = sum(
        1
        for it in bugs
        if _state_bucket_for_issue(it, status_type_map) not in ("done", "canceled")
    )
    return n, open_n


def _issues_assigned_to_any(
    items: list[dict[str, Any]],
    names: set[str],
) -> list[dict[str, Any]]:
    if not names:
        return []
    return [
        it for it in items
        if (_assignee_name(it) or "").strip() in names
    ]


def _count_cycle_issue_buckets(
    items: list[dict[str, Any]],
    status_type_map: dict[str, str],
) -> tuple[int, int, int, int, int, int, int, float]:
    """返回 n_done, n_ip, n_todo, n_bl, n_other, n_canceled, n_active, done_pct（分母不含 canceled）。"""
    n_done = n_ip = n_todo = n_bl = n_canceled = n_other = 0
    for it in items:
        b = _state_bucket_for_issue(it, status_type_map)
        if b == "done":
            n_done += 1
        elif b == "in_progress":
            n_ip += 1
        elif b == "todo":
            n_todo += 1
        elif b == "backlog":
            n_bl += 1
        elif b == "canceled":
            n_canceled += 1
        else:
            n_other += 1
    n_active = n_done + n_ip + n_todo + n_bl + n_other
    pct = (n_done / n_active * 100.0) if n_active else 0.0
    return n_done, n_ip, n_todo, n_bl, n_other, n_canceled, n_active, pct


def _project_table_progress_kind(status_label: str) -> str:
    """项目一览表「阶段进度」口径：研发子集 / 测试子集 / 全量。"""
    if status_label in ("开发中", "联调中", "设计中", "延期开发中", "启动中"):
        return "dev"
    if status_label in ("测试中", "待发布", "已上线", "延期上线"):
        return "test"
    return "all"


def _issue_estimate_points(it: dict[str, Any]) -> int | None:
    """从 issue 取出故事点整数；Linear 常见为数字或 ``{value: n}``。"""
    e = it.get("estimate")
    if e is None:
        return None
    if isinstance(e, bool):
        return None
    if isinstance(e, (int, float)):
        return int(round(e))
    if isinstance(e, dict):
        v = e.get("value")
        if isinstance(v, (int, float)):
            return int(round(v))
    return None


# Linear 默认刻度：1/2/3/5 对应点值与体量名（与产品约定一致）
_ESTIMATE_BUCKET_META: tuple[tuple[int, str], ...] = (
    (1, "简单（Extra Small）"),
    (2, "中下（Small）"),
    (3, "中等（Medium）"),
    (5, "困难（Large）"),
)

# Linear 估点 → 工时（小时）：与迭代进度看板、产品约定一致
_ESTIMATE_POINT_TO_HOURS: dict[int, float] = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}

# 成员负载：合计工时 ÷ 周基准工时（40h）= 负载比例
_MEMBER_WEEKLY_CAPACITY_HOURS = 40.0


def _issue_estimate_hours(it: dict[str, Any]) -> float | None:
    """将 issue 估点换算为工时（h）；未填估点或不在刻度表上则返回 None。"""
    pts = _issue_estimate_points(it)
    if pts is None:
        return None
    if int(pts) not in _ESTIMATE_POINT_TO_HOURS:
        return None
    return _ESTIMATE_POINT_TO_HOURS[int(pts)]


def _format_hours(h: float) -> str:
    if h <= 0:
        return "0h"
    if abs(h - round(h)) < 0.05:
        return f"{int(round(h))}h"
    return f"{h:.1f}h"


def _member_load_percent(hours_total: float) -> float:
    """负载（%）= 合计工时 / 周基准 40h × 100。"""
    return (hours_total / _MEMBER_WEEKLY_CAPACITY_HOURS) * 100.0


def _format_member_load_cell(hours_total: float, hours_filled: int) -> str:
    if hours_filled <= 0 or hours_total <= 0:
        return "—"
    pct = _member_load_percent(hours_total)
    bar = _pct_share_bar(min(pct, 100.0))
    pct_s = f"{pct:.0f}%" if abs(pct - round(pct)) < 0.05 else f"{pct:.1f}%"
    return f"`{bar}` {pct_s}"


@dataclass
class CycleEstimateSummary:
    bucket_counts: dict[int, int]  # 1,2,3,5 -> 条数
    other_count: int
    other_points_sum: int  # 非 1/2/3/5 的点数之和
    none_count: int

    @property
    def total_points(self) -> int:
        t = sum(pts * self.bucket_counts.get(pts, 0) for pts, _ in _ESTIMATE_BUCKET_META)
        return t + self.other_points_sum

    @property
    def filled_count(self) -> int:
        return sum(self.bucket_counts.values()) + self.other_count


def summarize_cycle_estimates(issues: list[dict[str, Any]]) -> CycleEstimateSummary:
    bucket_counts: dict[int, int] = {1: 0, 2: 0, 3: 0, 5: 0}
    other_count = 0
    other_points_sum = 0
    none_count = 0
    for it in issues:
        pts = _issue_estimate_points(it)
        if pts is None:
            none_count += 1
            continue
        if pts in bucket_counts:
            bucket_counts[pts] += 1
        else:
            other_count += 1
            other_points_sum += pts
    return CycleEstimateSummary(
        bucket_counts=bucket_counts,
        other_count=other_count,
        other_points_sum=other_points_sum,
        none_count=none_count,
    )


def format_cycle_estimate_lines(est: CycleEstimateSummary) -> list[str]:
    """估点小节内的列表行（由上层加组标题与分割线）。"""
    lines: list[str] = []
    for pts, label in _ESTIMATE_BUCKET_META:
        cnt = est.bucket_counts.get(pts, 0)
        sub = cnt * pts
        lines.append(f"- **{pts} 点** · {label}：**{cnt}** 项 → 小计 **{sub}**")
    if est.other_count:
        lines.append(
            f"- **其他点数**（非 1/2/3/5）：**{est.other_count}** 项 → 小计 **{est.other_points_sum}**"
        )
    lines.append(
        f"- **估点合计**：**{est.total_points}**（已填 **{est.filled_count}** 项，未填 **{est.none_count}** 项）"
    )
    return lines


# 点完成率（估点）与时间进度（日历）比较的容差，|Δ| 小于此值视为「正常」
_CYCLE_PACE_MARGIN = 0.12


def sum_estimate_done_and_total_pts(
    cycle_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
) -> tuple[int, int, float | None]:
    """已完成状态 issue 的估点之和、当前 Cycle 内全部 issue 估点之和、点完成率。"""
    total_pts = 0
    done_pts = 0
    for it in cycle_issues:
        pts = _issue_estimate_points(it)
        p = pts if pts is not None else 0
        total_pts += p
        st_name = (it.get("status") or "").strip()
        st_type = (status_type_map.get(st_name) or "").lower()
        if st_type == "completed":
            done_pts += p
    ratio = (done_pts / total_pts) if total_pts > 0 else None
    return done_pts, total_pts, ratio


def cycle_elapsed_fraction(cycle: dict[str, Any], now: datetime) -> float | None:
    """Cycle 时间线上已过去比例 0~1。"""
    s_raw = cycle.get("startsAt")
    e_raw = cycle.get("endsAt")
    s = _parse_dt(s_raw) if s_raw else None
    e = _parse_dt(e_raw) if e_raw else None
    if not s or not e:
        return None
    if now.tzinfo is None:
        now = now.replace(tzinfo=s.tzinfo or timezone.utc)
    if s.tzinfo is not None and e.tzinfo is None:
        e = e.replace(tzinfo=s.tzinfo)
    if s.tzinfo is None and e.tzinfo is not None:
        s = s.replace(tzinfo=e.tzinfo)
    span_sec = (e - s).total_seconds()
    if span_sec <= 0:
        return None
    elapsed = (now - s).total_seconds()
    return max(0.0, min(1.0, elapsed / span_sec))


def format_cycle_pace_lines(
    cycle: dict[str, Any],
    cycle_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    now: datetime,
) -> list[str]:
    """估点完成率 + 时间进度 + 缓慢/正常/赶超。"""
    done_pts, total_pts, ratio_pts = sum_estimate_done_and_total_pts(cycle_issues, status_type_map)
    time_frac = cycle_elapsed_fraction(cycle, now)
    lines: list[str] = []

    if total_pts <= 0:
        lines.append("- 估点完成率（已完成点 / 全部点）：**—**（当前 Cycle 内估点合计为 0，无法计算）")
        lines.append("- 当前时间进度（Cycle 已进行）：**—**")
        lines.append("- **节奏**：**—**（需有估点）")
        return lines

    assert ratio_pts is not None
    lines.append(
        f"- 估点完成率（已完成点 / 全部点）：**{100.0 * ratio_pts:.1f}%**（**{done_pts}** / **{total_pts}**）"
    )

    if time_frac is None:
        lines.append("- 当前时间进度（Cycle 已进行）：**—**（无法解析起止时间）")
        if ratio_pts < 1.0 / 3:
            lab, hint = "缓慢", "点完成率偏低（未结合日历）"
        elif ratio_pts > 2.0 / 3:
            lab, hint = "赶超", "点完成率偏高（未结合日历）"
        else:
            lab, hint = "正常", "点完成率居中（未结合日历）"
        lines.append(f"- **节奏**：**{lab}**（_{hint}_）")
        return lines

    lines.append(f"- 当前时间进度（Cycle 已进行约）：**{100.0 * time_frac:.1f}%**")
    delta = ratio_pts - time_frac
    if delta < -_CYCLE_PACE_MARGIN:
        lab, hint = "缓慢", f"点完成率低于时间进度约 **{abs(delta) * 100:.0f}** 个百分点"
    elif delta > _CYCLE_PACE_MARGIN:
        lab, hint = "赶超", f"点完成率高于时间进度约 **{delta * 100:.0f}** 个百分点"
    else:
        lab, hint = "正常", f"点完成率与时间进度接近（容差 ±{int(_CYCLE_PACE_MARGIN * 100)}%）"
    lines.append(f"- **节奏**：**{lab}**（_{hint}_）")
    return lines


def _issue_title_line(it: dict[str, Any]) -> str:
    return f"{_issue_key(it)} {it.get('title', '')}".strip()


def _group_by_assignee(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_owner: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        by_owner.setdefault(_assignee_name(it) or "未分配", []).append(it)
    return by_owner


def _title_theme(title: str) -> str:
    """从标题抽一层「主题」用于归纳（首段/分隔符前）。"""
    t = (title or "").strip()
    if not t:
        return "（无标题）"
    m = re.match(r"^\[([^\]]+)\]", t)
    if m:
        # 像 [Campaign Reward] 这类前缀视作同一主题，避免被后缀模块名拆散。
        return f"[{m.group(1).strip()}]"
    for sep in ("｜", "|", "：", ":"):
        if sep in t:
            head = t.split(sep, 1)[0].strip()
            if head:
                t = head
            break
    return t[:48] + ("…" if len(t) > 48 else "")


_TASK_NUM_THEME = re.compile(r"^Task\s*\d+\s*$", re.I)


def summarize_titles_by_theme(items: list[dict[str, Any]], max_themes: int = 12) -> list[str]:
    """总览用：按标题主题聚合 issue key；Task1/Task2 等编号类标题不参与总览（仅出现在明细）。"""
    if not items:
        return []
    theme_keys: dict[str, list[str]] = defaultdict(list)
    for it in items:
        theme = _title_theme(str(it.get("title") or ""))
        if _TASK_NUM_THEME.match(theme):
            continue
        theme_keys[theme].append(_issue_key(it))

    out: list[str] = []
    ordered = sorted(theme_keys.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for theme, keys in ordered[:max_themes]:
        uniq = list(dict.fromkeys(keys))
        if len(uniq) == 1:
            out.append(f"- **{theme}**：{uniq[0]}")
            continue
        shown = uniq[:8]
        if len(uniq) > len(shown):
            out.append(f"- **{theme}**：{'、'.join(shown)} 等共 **{len(uniq)}** 项")
        else:
            out.append(f"- **{theme}**：{'、'.join(shown)}")

    return out


def summarize_progress_by_theme(
    done_items: list[dict[str, Any]],
    in_progress_items: list[dict[str, Any]],
    all_cycle_items: list[dict[str, Any]],
    status_type_map: dict[str, str],
    max_themes: int = 12,
) -> list[str]:
    """按主题聚合本周进展，并输出每个主题的完成进度。

    规则：
    - 普通任务：按自身状态计 1 项（completed=1，否则=0）。
    - 父任务（存在子任务）：该任务的进度按子任务汇总，不再按父任务自身状态计数。
    """
    if not done_items and not in_progress_items:
        return []

    def _is_done(it: dict[str, Any]) -> bool:
        st_name = (it.get("status") or "").strip()
        return (status_type_map.get(st_name) or "").lower() == "completed"

    by_key: dict[str, dict[str, Any]] = {}
    for it in all_cycle_items:
        by_key[_issue_key(it)] = it
    children_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in all_cycle_items:
        parent = str(it.get("parentId") or "").strip()
        if parent:
            children_by_parent[parent].append(it)

    theme_done_keys: dict[str, list[str]] = defaultdict(list)
    theme_all_keys: dict[str, list[str]] = defaultdict(list)

    for it in done_items:
        theme = _title_theme(str(it.get("title") or ""))
        if _TASK_NUM_THEME.match(theme):
            continue
        key = _issue_key(it)
        theme_done_keys[theme].append(key)
        theme_all_keys[theme].append(key)
    for it in in_progress_items:
        theme = _title_theme(str(it.get("title") or ""))
        if _TASK_NUM_THEME.match(theme):
            continue
        theme_all_keys[theme].append(_issue_key(it))

    ordered = sorted(theme_all_keys.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    out: list[str] = []
    for theme, all_keys in ordered[:max_themes]:
        uniq_all = list(dict.fromkeys(all_keys))
        done_key_set = set(dict.fromkeys(theme_done_keys.get(theme, [])))
        total = 0
        done_n = 0
        for k in uniq_all:
            child_items = children_by_parent.get(k) or []
            if child_items:
                total += len(child_items)
                done_n += sum(1 for c in child_items if _is_done(c))
                continue
            total += 1
            if k in done_key_set:
                done_n += 1
        progress = (done_n / total * 100.0) if total else 0.0
        if total > 0 and done_n == total:
            prefix = "✅ "
        elif done_n > 0:
            prefix = "🟡 "
        else:
            prefix = "⚪ "
        if len(uniq_all) == 1:
            key_text = uniq_all[0]
        else:
            shown = uniq_all[:8]
            key_text = "、".join(shown)
            if len(uniq_all) > len(shown):
                key_text = f"{key_text} 等共 **{len(uniq_all)}** 项"
        out.append(
            f"- {prefix}**{theme}**：{key_text}（进度 **{progress:.0f}%**，**{done_n}/{total}**）"
        )
    return out


def _member_weekly_report_url_map() -> dict[str, str]:
    """成员名 -> 个人周报钉钉文档 URL。

    通过环境变量/配置读取 JSON：
    TEAM_MEMBER_WEEKLY_REPORT_URLS_JSON='{"李嘉琳":"https://...","王冲":"https://..."}'
    """
    raw = env("TEAM_MEMBER_WEEKLY_REPORT_URLS_JSON") or ""
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in data.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        kk = k.strip()
        vv = v.strip()
        if kk and vv:
            out[kk] = vv
    return out


def _personal_report_week_tokens(iso_week: str) -> list[str]:
    """个人周报文件名/目录常用周标记，用于同目录多周文档时优先匹配当前周。"""
    year_s, week_s = iso_week.split("-W", 1)
    wk = int(week_s)
    yy = int(year_s) % 100
    return [
        f"W{wk}-",
        f"W{wk:02d}-",
        f"{iso_week}",
        f"{yy:02d}W{wk:02d}",
        f"W{wk}",
        f"W{wk:02d}",
    ]


def _score_personal_report_doc(doc_name: str, owner: str, iso_week: str) -> int:
    """分数越高越优先；0 表示不应匹配。"""
    if not doc_name or owner not in doc_name:
        return 0
    if "团队周报" in doc_name:
        return 0
    score = 10
    for i, tok in enumerate(_personal_report_week_tokens(iso_week)):
        if tok in doc_name:
            # 越靠前的 token 越具体（如 W20- 优于裸 W20）
            score += 100 - i * 5
    if doc_name.startswith(f"W{int(iso_week.split('-W')[1])}-"):
        score += 50
    if doc_name.startswith(f"W{int(iso_week.split('-W')[1]):02d}-"):
        score += 50
    return score


def _dingtalk_node_url(node: dict[str, Any]) -> str | None:
    for k in ("url", "documentUrl", "webUrl", "docUrl", "link"):
        v = node.get(k)
        if isinstance(v, str) and v.startswith("http"):
            return v
    return None


def _dingtalk_personal_report_url_map(
    owner_names: list[str],
    folder_id: str,
    iso_week: str,
) -> dict[str, str]:
    """从当周钉钉目录文档中自动匹配成员个人周报链接。

    约定：目录内为个人/团队周报；同名多周时按 iso_week 对应标记（W20 / 2026-W20 / 26W20）优先。
    """
    owner_set = {n.strip() for n in owner_names if n and n.strip() and n.strip() != "未分配"}
    if not owner_set:
        return {}
    nodes = _dingtalk_list_all_nodes_under(folder_id)
    docs: list[tuple[str, str]] = []
    for n in nodes:
        name = _dingtalk_node_display_name(n)
        if not name:
            continue
        if "团队周报" in name:
            continue
        u = _dingtalk_node_url(n)
        if not u:
            continue
        docs.append((name, u))

    out: dict[str, str] = {}
    for owner in owner_set:
        best: tuple[int, str] | None = None
        for name, u in docs:
            sc = _score_personal_report_doc(name, owner, iso_week)
            if sc <= 0:
                continue
            if best is None or sc > best[0]:
                best = (sc, u)
        if best:
            out[owner] = best[1]
    return out


def summarize_owner_progress(
    owner: str,
    done_items: list[dict[str, Any]],
    in_progress_items: list[dict[str, Any]],
    all_cycle_items: list[dict[str, Any]],
    status_type_map: dict[str, str],
    *,
    max_sentences: int = 5,
) -> list[str]:
    """每人不超过 5 句话摘要。"""
    total = len(done_items) + len(in_progress_items)
    done_n = len(done_items)
    inprog_n = len(in_progress_items)
    pct = (done_n / total * 100.0) if total else 0.0

    lines: list[str] = []
    lines.append(f"本周共推进 **{total}** 项，其中已完成 **{done_n}** 项、计划中 **{inprog_n}** 项（完成率 **{pct:.0f}%**）。")

    # 负责人明细中的父任务进度，也按子任务真实完成情况计算（使用全量 cycle + 状态类型映射）。
    themes = summarize_progress_by_theme(
        done_items,
        in_progress_items,
        all_cycle_items,
        status_type_map,
    )
    if themes:
        # 主题摘要最多补充 3 句，控制总句数 <= max_sentences（另有地址句占 1）
        remain = max(0, max_sentences - 2)
        for t in themes[:remain]:
            lines.append(t.lstrip("- ").strip())
    return lines[: max(0, max_sentences - 1)]


def summarize_owner_plan(
    owner: str,
    plan_items: list[dict[str, Any]],
    *,
    max_sentences: int = 5,
) -> list[str]:
    """下周计划的每人摘要（不超过 5 句）。"""
    total = len(plan_items)

    lines: list[str] = []
    lines.append(f"本周计划共 **{total}** 项。")
    themes = summarize_titles_by_theme(plan_items, max_themes=max(1, max_sentences - 2))
    for t in themes[: max(0, max_sentences - 2)]:
        lines.append(t.lstrip("- ").strip())
    return lines[: max(0, max_sentences - 1)]


def _theme_labels_from_items(
    items: list[dict[str, Any]],
    *,
    max_themes: int = 3,
) -> list[str]:
    """从任务标题提取主题标签（去 Task 编号类），按条数降序。"""
    if not items:
        return []
    theme_counts: dict[str, int] = defaultdict(int)
    for it in items:
        theme = _title_theme(str(it.get("title") or ""))
        if _TASK_NUM_THEME.match(theme):
            continue
        theme_counts[theme] += 1
    ordered = sorted(theme_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [t for t, _ in ordered[:max_themes]]


def _sentence_join_themes(themes: list[str]) -> str:
    if not themes:
        return ""
    if len(themes) == 1:
        return f"「{themes[0]}」"
    return "、".join(f"「{t}」" for t in themes[:-1]) + f"及「{themes[-1]}」"


def _filter_issues_by_assignee(
    items: list[dict[str, Any]],
    owner: str,
) -> list[dict[str, Any]]:
    want = owner.strip() or "未分配"
    return [it for it in items if (_assignee_name(it) or "未分配") == want]


def _owner_last_week_summary_one_sentence(
    done_items: list[dict[str, Any]],
    in_progress_items: list[dict[str, Any]],
) -> str:
    """报告周上周工作总结（单句，由已完成 + 进行中任务归纳）。"""
    done_n = len(done_items)
    inprog_n = len(in_progress_items)
    if done_n == 0 and inprog_n == 0:
        return "上周本迭代无已完成或进行中的任务。"

    themes: list[str] = []
    for pool in (done_items, in_progress_items):
        for t in _theme_labels_from_items(pool, max_themes=2):
            if t not in themes:
                themes.append(t)
            if len(themes) >= 3:
                break
        if len(themes) >= 3:
            break
    theme_part = _sentence_join_themes(themes) if themes else "多项任务"

    if done_n and inprog_n:
        return (
            f"上周完成 {done_n} 项、进行中 {inprog_n} 项，"
            f"重点围绕 {theme_part}。"
        )
    if done_n:
        return f"上周完成 {done_n} 项，主要交付 {theme_part}。"
    return f"上周进行中 {inprog_n} 项，持续推进 {theme_part}。"


def _owner_next_week_plan_one_sentence(
    plan_items: list[dict[str, Any]],
    status_type_map: dict[str, str],
) -> str:
    """下周计划（单句）：本迭代内未完成（进行中 / 待开始 / Backlog）任务归纳。"""
    if not plan_items:
        return "下周暂无待办或进行中的排期任务。"

    themes = _theme_labels_from_items(plan_items, max_themes=3)
    theme_part = _sentence_join_themes(themes) if themes else "多项工作"
    n_ip = n_todo = n_bl = 0
    for it in plan_items:
        b = _state_bucket_for_issue(it, status_type_map)
        if b == "in_progress":
            n_ip += 1
        elif b == "todo":
            n_todo += 1
        elif b == "backlog":
            n_bl += 1
    parts: list[str] = []
    if n_ip:
        parts.append(f"进行中 {n_ip}")
    if n_todo:
        parts.append(f"待开始 {n_todo}")
    if n_bl:
        parts.append(f"Backlog {n_bl}")
    stat = "、".join(parts) if parts else f"共 {len(plan_items)}"
    return f"下周计划推进 {len(plan_items)} 项（{stat}），重点 {theme_part}。"


def _owner_yesterday_summary_one_sentence(
    done_items: list[dict[str, Any]],
    in_progress_items: list[dict[str, Any]],
) -> str:
    """进行中快照：昨日有活动的任务归纳（单句）。"""
    done_n = len(done_items)
    inprog_n = len(in_progress_items)
    if done_n == 0 and inprog_n == 0:
        return "昨日无已完成或进行中的相关任务活动。"

    themes: list[str] = []
    for pool in (done_items, in_progress_items):
        for t in _theme_labels_from_items(pool, max_themes=2):
            if t not in themes:
                themes.append(t)
            if len(themes) >= 3:
                break
        if len(themes) >= 3:
            break
    theme_part = _sentence_join_themes(themes) if themes else "多项任务"

    if done_n and inprog_n:
        return (
            f"昨日完成 {done_n} 项、进行中 {inprog_n} 项，"
            f"重点围绕 {theme_part}。"
        )
    if done_n:
        return f"昨日完成 {done_n} 项，主要交付 {theme_part}。"
    return f"昨日进行中 {inprog_n} 项，持续推进 {theme_part}。"


def _owner_carry_forward_plan_one_sentence(
    plan_items: list[dict[str, Any]],
    status_type_map: dict[str, str],
) -> str:
    """进行中快照：截至昨日仍开放的后续排期（单句）。"""
    if not plan_items:
        return "截至昨日无待办或进行中的后续排期。"

    themes = _theme_labels_from_items(plan_items, max_themes=3)
    theme_part = _sentence_join_themes(themes) if themes else "多项工作"
    n_ip = n_todo = n_bl = 0
    for it in plan_items:
        b = _state_bucket_for_issue(it, status_type_map)
        if b == "in_progress":
            n_ip += 1
        elif b == "todo":
            n_todo += 1
        elif b == "backlog":
            n_bl += 1
    parts: list[str] = []
    if n_ip:
        parts.append(f"进行中 {n_ip}")
    if n_todo:
        parts.append(f"待开始 {n_todo}")
    if n_bl:
        parts.append(f"Backlog {n_bl}")
    stat = "、".join(parts) if parts else f"共 {len(plan_items)}"
    return f"后续待推进 {len(plan_items)} 项（{stat}），重点 {theme_part}。"


def _issue_cycle_membership(it: dict[str, Any]) -> bool | None:
    """是否关联到某个 Cycle。

    - ``True``：明确在某个 Cycle 内（有非空 ``cycleId`` 或嵌套 ``cycle.id``）。
    - ``False``：明确未关联 Cycle（API 显式给出空值）。
    - ``None``：**无法判断**——常见于仅按 Team 分页 ``list_issues`` 时不返回 ``cycle`` / ``cycleId``；
      若把 ``None`` 当成「未划入」会严重高估（与 Linear 页面不一致）。
    """
    if "cycleId" in it:
        v = it.get("cycleId")
        if v is not None and str(v).strip():
            return True
        return False

    c = it.get("cycle")
    if "cycle" in it:
        if c is None:
            return False
        if isinstance(c, dict):
            sub = c.get("id") or c.get("cycleId")
            if sub is not None and str(sub).strip():
                return True
            return False
        if isinstance(c, str) and c.strip():
            return True
        return None

    if isinstance(c, dict):
        sub = c.get("id") or c.get("cycleId")
        if sub is not None and str(sub).strip():
            return True
        return False

    return None


def _is_blocked_status(status: str | None) -> bool:
    raw = (status or "").strip()
    s = raw.lower()
    if "阻塞" in raw:
        return True
    if "unblock" in s:
        return False
    return "block" in s


def _risk_line_with_owner(it: dict[str, Any]) -> str:
    who = _assignee_name(it) or "未分配"
    proj = _issue_project_name(it)
    return f"  - **{proj}** · {_issue_title_line(it)} · 持有人：**{who}**"


def _comment_body(c: dict[str, Any]) -> str:
    return str(c.get("body") or c.get("content") or c.get("text") or c.get("message") or "")


def _comment_suggests_discussion(text: str) -> bool:
    t = text.strip()
    if len(t) < 10:
        return False
    tl = t.lower()
    cn = (
        "待讨论", "待确认", "待定", "需要讨论", "需要确认", "需评审", "需对齐",
        "是否", "阻塞", "争议", "分歧", "怎么定", "未定", "未决",
    )
    for x in cn:
        if x in t:
            return True
    en = (
        "blocked", "open question", "need discussion", "need confirm", "tbd",
        "todo:", "question:", "wdyt", "thoughts?",
    )
    for x in en:
        if x in tl:
            return True
    if "？" in t and len(t) > 25:
        return True
    if re.search(r"\?\s*$", t) and len(t) > 25:
        return True
    return False


def _excerpt_discussion_hint(body: str, max_len: int = 160) -> str:
    for line in body.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if len(line) < 10:
            continue
        if _comment_suggests_discussion(line):
            return line if len(line) <= max_len else line[: max_len - 1] + "…"
    one = " ".join(body.split())
    if not one:
        return ""
    return one if len(one) <= max_len else one[: max_len - 1] + "…"


def fetch_discussion_hints_from_comments(
    mcp: LinearMcpClient,
    client: _StdioMcpClient,
    tool_names: set[str],
    in_progress: list[dict[str, Any]],
    max_issues: int = 22,
) -> str:
    """拉取进行中任务的评论，启发式标记可能待讨论的内容。"""
    if not in_progress:
        return ""
    names = tool_names
    if "list_comments" not in names and "linear_list_comments" not in names:
        return ""

    blocks: list[str] = []
    for it in in_progress[:max_issues]:
        iid = str(it.get("identifier") or it.get("id") or "").strip()
        if not iid:
            continue
        try:
            comments = mcp.list_comments(client, names, iid, limit=50)
        except _LocalMcpError:
            continue
        hints: list[str] = []
        seen: set[str] = set()
        for c in comments:
            body = _comment_body(c)
            if not _comment_suggests_discussion(body):
                continue
            ex = _excerpt_discussion_hint(body)
            if ex and ex not in seen:
                seen.add(ex)
                hints.append(ex)
            if len(hints) >= 3:
                break
        if not hints:
            continue
        who = _assignee_name(it) or "未分配"
        st = (it.get("status") or "").strip()
        blocks.append(f"- **{_issue_key(it)}** {it.get('title', '')}")
        blocks.append(f"  - 持有人：**{who}**" + (f" · 状态：{st}" if st else ""))
        for h in hints:
            blocks.append(f"  - 线索：{h}")

    if not blocks:
        return ""
    return "\n".join(
        [
            "\n### 💬 进行中任务 · 评论待讨论线索",
            "_以下为评论正文命中「待讨论/待确认/阻塞/问号」等启发式规则，需人工复核。_",
            *blocks,
        ]
    )


def _priority_label(p: Any) -> str:
    # plugin returns {"value": 3, "name":"Medium"} or may be missing
    if isinstance(p, dict):
        name = (p.get("name") or "").lower()
        if name in ("urgent",):
            return "紧急"
        if name in ("high",):
            return "高"
        if name in ("medium", "normal"):
            return "中"
        if name in ("low",):
            return "低"
    if isinstance(p, (int, float)):
        return {1: "紧急", 2: "高", 3: "中", 4: "低", 0: "无"}.get(int(p), "无")
    return "无"


def _normalize_member_group(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in ("frontend", "front", "fe", "前端"):
        return "frontend"
    if raw in ("backend", "back", "be", "后端"):
        return "backend"
    return "all"


def _member_display_names(m: dict[str, Any]) -> list[str]:
    """用于与 Linear assignee 字符串匹配的姓名集合（含 ``aliases``、邮箱 @ 前本地段）。"""
    seen: set[str] = set()
    out: list[str] = []

    def _add(s: str) -> None:
        t = s.strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)

    for key in ("real_name", "realName", "username", "real_name_en", "realNameEn", "email"):
        v = m.get(key)
        if isinstance(v, str):
            _add(v)
            if key == "email" and "@" in v:
                _add(v.split("@", 1)[0])
    raw_aliases = m.get("aliases")
    if isinstance(raw_aliases, str) and raw_aliases.strip():
        try:
            parsed = json.loads(raw_aliases)
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            for a in parsed:
                if isinstance(a, str):
                    _add(a)
    elif isinstance(raw_aliases, list):
        for a in raw_aliases:
            if isinstance(a, str):
                _add(a)
    return out


def _member_row_excluded(m: dict[str, Any]) -> bool:
    """排除无 role、已删除/已合并等不应参与周报成员解析的记录（与 list_members 同源）。"""
    if not isinstance(m, dict):
        return True
    role = str(m.get("role") or "").strip()
    if not role:
        return True
    st = str(
        m.get("status")
        or m.get("member_status")
        or m.get("record_status")
        or "",
    ).strip().lower()
    if st in ("deleted", "merged", "removed", "inactive", "superseded"):
        return True
    if m.get("deleted") is True or m.get("merged") is True:
        return True
    for k in ("isDeleted", "isMerged"):
        if m.get(k) is True:
            return True
    for k in ("deleted", "merged", "isDeleted", "isMerged"):
        sv = str(m.get(k) or "").strip().lower()
        if sv in ("1", "true", "yes"):
            return True
    return False


def _iter_report_members() -> list[dict[str, Any]]:
    """``list_members()`` 结果过滤：去掉 deleted/merged/无 role；**仅保留**工程三角色
    （backend / frontend / architect）与 **测试** 职能成员（产品/设计等不进入周报成员名单）。
    """
    try:
        raw = list_members()
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for m in raw:
        if not isinstance(m, dict) or _member_row_excluded(m):
            continue
        role = str(m.get("role") or "")
        if _role_bucket_for_weekly(role) is not None or _role_string_indicates_qa(role):
            out.append(m)
    return out


def _role_bucket_for_weekly(role_raw: str) -> str | None:
    """将成员 role 归为 backend / frontend / architect 之一；不属于工程三角色则 ``None``。"""
    role = role_raw or ""
    r = role.strip().lower()
    if ("架构" in role) or ("architect" in r):
        return "architect"
    if ("前端" in role) or ("frontend" in r) or ("front-end" in r) or (r == "fe"):
        return "frontend"
    if ("后端" in role) or ("backend" in r) or ("back-end" in r) or (r == "be"):
        return "backend"
    return None


def _role_string_indicates_qa(role_raw: str) -> bool:
    """是否为测试 / QA 职能（**不得**用 ``\"test\" in role.lower()`` 单独判断：会误伤 ``architect``）。"""
    role = str(role_raw or "")
    r = role.strip().lower()
    if not r:
        return False
    if "测试" in role:
        return True
    if "architect" in r:
        return False
    if "qa" in r:
        return True
    if "test" in r and "latest" not in r:
        return True
    return False


def _is_rd_member_role(role: str) -> bool:
    """研发侧（项目阶段 / 研发指派）：成员表 role 归为 backend、frontend、architect。

    数据来自 ``list_members()``（与 superteam-member/scripts/list_members.py 同源），
    且应先经 ``_iter_report_members`` 过滤 deleted/merged/无 role。
    """
    if _member_role_excluded_for_rd_pipeline(str(role or "")):
        return False
    return _role_bucket_for_weekly(role) is not None


def _member_role_excluded_for_rd_pipeline(role: str) -> bool:
    """测试 / 产品 / 设计等不参与「研发指派」口径。"""
    r = (role or "").strip().lower()
    if not r:
        return True
    if _role_string_indicates_qa(role):
        return True
    if ("产品" in role) or ("设计" in role) or (r in ("pm", "po")):
        return True
    return False


def _rd_member_names() -> set[str]:
    """superteam 成员表中研发人员姓名/别名集合，用于匹配 issue assignee。"""
    names: set[str] = set()
    for m in _iter_report_members():
        if not _is_rd_member_role(str(m.get("role") or "")):
            continue
        names.update(_member_display_names(m))
    return names


def _test_member_names() -> set[str]:
    """成员表中测试职能姓名/别名（与分工「测试」块同源口径）。"""
    names: set[str] = set()
    for m in _iter_report_members():
        role = str(m.get("role") or "")
        if _role_string_indicates_qa(role):
            names.update(_member_display_names(m))
    return names


def _assignee_work_division_role_map() -> dict[str, str]:
    """assignee 显示名 → 周报「分工」分块：``backend`` / ``frontend`` / ``test`` / ``other``。

    后端含 **architect**（与 ``_role_bucket_for_weekly`` 一致）；测试用 ``_role_string_indicates_qa``；
    未命中成员表或产品/设计等归入 ``other``。
    """
    out: dict[str, str] = {}
    for m in _iter_report_members():
        role = str(m.get("role") or "")
        if _role_string_indicates_qa(role):
            bucket = "test"
        elif _role_bucket_for_weekly(role) == "frontend":
            bucket = "frontend"
        elif _role_bucket_for_weekly(role) in ("backend", "architect"):
            bucket = "backend"
        else:
            bucket = "other"
        for nm in _member_display_names(m):
            s = nm.strip()
            if s:
                out[s] = bucket
    return out


# §3 按成员：小节顺序（后端含 architect → 前端 → 测试）
_MEMBER_SECTION_ROLE_ORDER = {"backend": 0, "frontend": 1, "test": 2, "other": 99}


def _report_member_assignee_names() -> set[str]:
    """成员表内可用于匹配 Linear assignee 的姓名/别名集合（``_iter_report_members`` 口径）。"""
    names: set[str] = set()
    for m in _iter_report_members():
        names.update(_member_display_names(m))
    return {n.strip() for n in names if n and n.strip()}


def _member_owner_section_sort_key(owner: str) -> tuple[int, str]:
    bucket = _assignee_work_division_role_map().get(owner.strip(), "other")
    return (_MEMBER_SECTION_ROLE_ORDER.get(bucket, 99), owner)


def _issue_is_open_for_project_status(
    it: dict[str, Any],
    status_type_map: dict[str, str],
) -> bool:
    b = _state_bucket_for_issue(it, status_type_map)
    return b not in ("done", "canceled")


def _project_task_completion_flags(
    project_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    rd_names: set[str],
) -> tuple[bool, bool]:
    """返回 (研发任务是否全部完成, 项目下全部任务是否全部完成)。"""
    active = [
        it
        for it in project_issues
        if _state_bucket_for_issue(it, status_type_map) != "canceled"
    ]
    if not active:
        return True, True
    all_done = all(not _issue_is_open_for_project_status(it, status_type_map) for it in active)
    rd_issues = [
        it
        for it in active
        if (_assignee_name(it) or "").strip() in rd_names
    ]
    if not rd_issues:
        rd_done = True
    else:
        rd_done = all(not _issue_is_open_for_project_status(it, status_type_map) for it in rd_issues)
    return rd_done, all_done


def _merge_issues_into_project_index(
    by_name: dict[str, list[dict[str, Any]]],
    issues: list[dict[str, Any]],
) -> None:
    """把 issue 并入按项目索引（按 _issue_key 去重）。补全 list_issues(team) 分页遗漏的 Cycle 内任务。"""
    seen: dict[str, set[str]] = defaultdict(set)
    for pname, items in by_name.items():
        seen[pname] = {_issue_key(it) for it in items if _issue_key(it)}
    for it in issues:
        pname = _issue_project_name(it)
        if pname == "未关联项目":
            continue
        k = _issue_key(it)
        if not k or k in seen[pname]:
            continue
        seen[pname].add(k)
        by_name[pname].append(it)


def _count_rd_project_issues(
    project_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    rd_names: set[str],
) -> int:
    """项目下由研发人员（backend / frontend / architect，成员表口径）负责的未取消任务数。"""
    n = 0
    for it in project_issues:
        if _state_bucket_for_issue(it, status_type_map) == "canceled":
            continue
        if (_assignee_name(it) or "").strip() in rd_names:
            n += 1
    return n


def _derive_project_lifecycle_status(
    *,
    ref: date,
    test_date: date | None,
    release_date: date | None,
    rd_tasks_done: bool,
    all_tasks_done: bool,
    project_issue_count: int = 0,
    rd_issue_count: int = 0,
) -> str:
    """按里程碑日期 + 任务完成情况推导「项目阶段」展示文案。

    与 Linear Project 面板上的「状态」字段无关；与「本 Cycle 是否清空」无直接关系。

    **未到提测日**（``ref < test_date``）时：

    - ``rd_tasks_done``：项目下**未取消**任务里，凡 assignee 落在成员表「研发」名单中的条目，
      在 ``_state_bucket_for_issue`` 下是否均已 ``done``（含对 ``statusType`` / ``state.type`` 的回退解析）。
      若没有任何此类指派单，视为研发已完成（``True``）。
    - ``rd_tasks_done`` 为真且报告日距 **提测** 里程碑 ≤ 3 天 → **联调中**；
      否则（含研发已完成但距提测仍较远）→ **开发中**。

    **已到提测、未到发布**等分支见代码内条件；``all_tasks_done`` 为项目下全部未取消任务是否均完成。
    """
    if test_date is None or release_date is None:
        if project_issue_count <= 0:
            return "设计中"
        return "未配置里程碑"
    # 未到提测：尚无研发任务（含全空或仅有测试/非研发任务）→ 设计中
    if ref < test_date and (project_issue_count <= 0 or rd_issue_count <= 0):
        return "设计中"
    if ref >= release_date:
        return "已上线" if all_tasks_done else "延期上线"
    if ref >= test_date:
        if all_tasks_done:
            return "待发布"
        if rd_tasks_done:
            return "测试中"
        return "延期开发中"
    days_to_test = (test_date - ref).days
    if (
        rd_tasks_done
        and days_to_test <= _INTEGRATION_STATUS_MAX_DAYS_BEFORE_TEST
    ):
        return "联调中"
    return "开发中"


def _member_names_by_group(group: str) -> set[str]:
    """从成员表读取职能分组，返回可用于匹配 assignee 的名字集合。

    - ``all``：不过滤 assignee（返回空集，由调用方保留全量任务）。
    - ``backend``：**后端周报** —— 包含 role 为 **backend、frontend、architect** 的成员。
    - ``frontend``：**前端周报** —— 仅 **frontend**。

    成员均来自 ``_iter_report_members()``（``list_members`` 且排除 deleted/merged/无 role）。
    """
    if group == "all":
        return set()
    members = _iter_report_members()
    names: set[str] = set()
    for m in members:
        role = str(m.get("role") or "")
        bucket = _role_bucket_for_weekly(role)
        if group == "frontend":
            if bucket != "frontend":
                continue
        elif group == "backend":
            if bucket not in ("backend", "frontend", "architect"):
                continue
        else:
            continue
        names.update(_member_display_names(m))
    return names


def _filter_issues_by_member_group(items: list[dict[str, Any]], member_names: set[str]) -> list[dict[str, Any]]:
    def _is_excluded_issue(it: dict[str, Any]) -> bool:
        # 全局口径：
        # 1) 忽略 canceledAt / deletedAt
        # 2) archivedAt 仅在 statusType=completed 时保留，其他归档状态剔除
        if it.get("deletedAt") or it.get("canceledAt"):
            return True
        status = str(it.get("status") or "").strip().lower()
        status_type = str(it.get("statusType") or "").strip().lower()
        if it.get("archivedAt") and status_type != "completed":
            return True
        if status_type in ("canceled", "cancelled"):
            return True
        if ("取消" in status_type) or ("删除" in status_type):
            return True
        if status in ("canceled", "cancelled", "deleted", "removed"):
            return True
        if ("取消" in status) or ("删除" in status):
            return True
        return False

    visible = [it for it in items if isinstance(it, dict) and not _is_excluded_issue(it)]
    if not member_names:
        return visible
    out: list[dict[str, Any]] = []
    for it in visible:
        assignee = str(it.get("assignee") or it.get("assigneeName") or "").strip()
        if assignee and assignee in member_names:
            out.append(it)
    return out


def _to_local_date(dt: datetime) -> date:
    if dt.tzinfo is not None:
        return dt.astimezone().date()
    return dt.date()


def _pick_cycle_for_week(cycles: list[dict[str, Any]], iso_week: str) -> dict[str, Any] | None:
    """按目标自然周时间命中 Cycle（不依赖 Cycle 当前状态）。"""
    start_s, end_s = _week_date_range(iso_week)
    week_start = datetime.strptime(start_s, "%Y-%m-%d").date()
    week_end = datetime.strptime(end_s, "%Y-%m-%d").date()
    hit: list[tuple[date, dict[str, Any]]] = []
    for c in cycles:
        if not isinstance(c, dict):
            continue
        starts_at = _parse_dt(str(c.get("startsAt") or ""))
        ends_at = _parse_dt(str(c.get("endsAt") or ""))
        if not starts_at or not ends_at:
            continue
        cycle_start = _to_local_date(starts_at)
        cycle_end = _to_local_date(ends_at)
        if cycle_start <= week_end and cycle_end >= week_start:
            hit.append((cycle_start, c))
    if not hit:
        return None
    hit.sort(key=lambda x: x[0], reverse=True)
    return hit[0][1]


def _pick_cycles_for_week(cycles: list[dict[str, Any]], iso_week: str) -> list[dict[str, Any]]:
    """返回目标自然周覆盖到的全部 Cycle，按 startsAt 倒序。"""
    start_s, end_s = _week_date_range(iso_week)
    week_start = datetime.strptime(start_s, "%Y-%m-%d").date()
    week_end = datetime.strptime(end_s, "%Y-%m-%d").date()
    hit: list[tuple[date, dict[str, Any]]] = []
    for c in cycles:
        if not isinstance(c, dict):
            continue
        starts_at = _parse_dt(str(c.get("startsAt") or ""))
        ends_at = _parse_dt(str(c.get("endsAt") or ""))
        if not starts_at or not ends_at:
            continue
        cycle_start = _to_local_date(starts_at)
        cycle_end = _to_local_date(ends_at)
        if cycle_start <= week_end and cycle_end >= week_start:
            hit.append((cycle_start, c))
    hit.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in hit]


def _is_dt_in_iso_week(dt: datetime | None, iso_week: str) -> bool:
    if not dt:
        return False
    start_s, end_s = _week_date_range(iso_week)
    week_start = datetime.strptime(start_s, "%Y-%m-%d").date()
    week_end = datetime.strptime(end_s, "%Y-%m-%d").date()
    d = _to_local_date(dt)
    return week_start <= d <= week_end


def detect_risks(
    in_progress: list[dict[str, Any]],
    cycle_issues: list[dict[str, Any]],
    now: datetime,
    stale_days: int = 3,
) -> tuple[list[dict[str, Any]], list[str]]:
    """返回 (受阻任务列表, 其他风险提示的 Markdown 行)。Blocked 单独供上层小节展示。"""
    blocked = [it for it in cycle_issues if _is_blocked_status(it.get("status"))]
    lines: list[str] = []
    if not in_progress and not cycle_issues:
        return blocked, lines

    stale: list[dict[str, Any]] = []
    no_desc: list[dict[str, Any]] = []
    no_owner: list[dict[str, Any]] = []
    urgent_open: list[dict[str, Any]] = []

    for it in in_progress:
        upd = _parse_dt(it.get("updatedAt"))
        if upd and (now - upd).days >= stale_days:
            stale.append(it)
        desc = (it.get("description") or "").strip()
        if len(desc) < 30:
            no_desc.append(it)
        if not _assignee_name(it):
            no_owner.append(it)
        pr = it.get("priority")
        if isinstance(pr, dict) and pr.get("name") in ("Urgent", "High"):
            urgent_open.append(it)

    def _append_block(title: str, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        lines.append(f"- **{title}**（{len(items)} 项）")
        for it in items[:30]:
            lines.append(_risk_line_with_owner(it))
        if len(items) > 30:
            lines.append(f"  - _… 另有 {len(items) - 30} 项未列出_")

    _append_block(f"超过 {stale_days} 天未更新", stale)
    _append_block("未分配负责人", no_owner)
    _append_block("描述过短/缺失（范围不清）", no_desc)
    if len(urgent_open) >= 5:
        lines.append(f"- **高优任务堆积**（紧急/高共 {len(urgent_open)} 项，需确认资源与范围）")
        for it in urgent_open[:30]:
            lines.append(_risk_line_with_owner(it))
        if len(urgent_open) > 30:
            lines.append(f"  - _… 另有 {len(urgent_open) - 30} 项未列出_")

    return blocked, lines


def _issue_project_name(it: dict[str, Any]) -> str:
    """Linear issue 上的项目名（兼容 string / dict / 顶层字段）。"""
    p = it.get("project")
    if isinstance(p, str) and p.strip():
        return p.strip()
    if isinstance(p, dict):
        for k in ("name", "title", "slug"):
            v = p.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    for k in ("projectName", "projectTitle"):
        v = it.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return "未关联项目"


def _build_project_meta_by_name(projects: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """按项目名索引 Linear Project（同名后者覆盖，通常 workspace 内唯一）。"""
    by_name: dict[str, dict[str, Any]] = {}
    for p in projects:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()
        if name:
            by_name[name] = p
    return by_name


def _parse_project_date_field(val: Any) -> date | None:
    if val is None or val == "":
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    s = str(val).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _project_lead_name(pm: dict[str, Any]) -> str:
    lead = pm.get("lead")
    if isinstance(lead, dict):
        return str(lead.get("name") or lead.get("id") or "").strip()
    return ""


def _project_has_lead(pm: dict[str, Any]) -> bool:
    return bool(_project_lead_name(pm))


def _milestone_end_date(ms: dict[str, Any]) -> date | None:
    """Milestone 结束时间（Linear 一般为 targetDate）。"""
    for key in ("targetDate", "endDate", "completedAt", "dueDate"):
        d = _parse_project_date_field(ms.get(key))
        if d is not None:
            return d
    return None


def _scan_object_for_labeled_dates(
    obj: dict[str, Any],
    *,
    want_test: bool,
    want_release: bool,
) -> tuple[date | None, date | None]:
    """从 dict / content / customFields 中扫描「提测时间」「发布时间」类字段。"""
    test_d: date | None = None
    release_d: date | None = None

    def _take_test(val: Any) -> None:
        nonlocal test_d
        if test_d is None:
            test_d = _parse_project_date_field(val)

    def _take_release(val: Any) -> None:
        nonlocal release_d
        if release_d is None:
            release_d = _parse_project_date_field(val)

    for key, val in obj.items():
        if key in ("content", "customFields", "fields", "_milestones", "milestones"):
            continue
        kl = str(key).strip().lower()
        if want_test and ("提测" in str(key) or kl in ("testsubmitdate", "test_submit_date", "qadate", "qa_date")):
            _take_test(val)
        if want_release and (
            "发布" in str(key) or kl in ("releasedate", "release_date", "launchdate", "launch_date", "golivedate")
        ):
            _take_release(val)

    for block in (obj.get("content"), obj.get("customFields"), obj.get("fields")):
        if not isinstance(block, list):
            continue
        for item in block:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or item.get("name") or item.get("title") or "")
            val = item.get("value") if "value" in item else item.get("date")
            if want_test and "提测" in label:
                _take_test(val)
            if want_release and "发布" in label:
                _take_release(val)

    return test_d, release_d


def _find_milestone_by_name(milestones: list[dict[str, Any]], *name_parts: str) -> dict[str, Any] | None:
    for ms in milestones:
        name = str(ms.get("name") or "").strip()
        if not name:
            continue
        for part in name_parts:
            if part and part in name:
                return ms
    return None


def _linear_project_milestones(pm: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pm.get("_milestones")
    if not isinstance(raw, list):
        return []
    return [m for m in raw if isinstance(m, dict)]


def _milestone_identity(ms: dict[str, Any]) -> tuple[str, str]:
    return (
        str(ms.get("id") or "").strip(),
        str(ms.get("name") or "").strip(),
    )


def _issue_matches_project_milestone(it: dict[str, Any], ms: dict[str, Any]) -> bool:
    """任务是否挂在指定 Linear Project Milestone 上。"""
    mid, mname = _milestone_identity(ms)
    if not mid and not mname:
        return False
    for key in ("projectMilestone", "milestone"):
        raw = it.get(key)
        if isinstance(raw, dict):
            rid = str(raw.get("id") or "").strip()
            rname = str(raw.get("name") or raw.get("title") or "").strip()
            if mid and rid == mid:
                return True
            if mname and rname == mname:
                return True
        if isinstance(raw, str) and raw.strip():
            if mname and raw.strip() == mname:
                return True
            if mid and raw.strip() == mid:
                return True
    for key in ("projectMilestoneId", "milestoneId"):
        v = str(it.get(key) or "").strip()
        if v and mid and v == mid:
            return True
    return False


def _milestone_is_project_start(ms: dict[str, Any]) -> bool:
    """下个里程碑是否为「项目启动」（名称含该字样即视为）。"""
    return "项目启动" in str(ms.get("name") or "").strip()


def _linear_project_start_milestones(pm: dict[str, Any]) -> list[dict[str, Any]]:
    return [ms for ms in _linear_project_milestones(pm) if _milestone_is_project_start(ms)]


def _project_start_milestone_has_open_tasks(
    issues: list[dict[str, Any]],
    pm: dict[str, Any],
    status_type_map: dict[str, str],
) -> bool:
    """存在「项目启动」里程碑，且其下仍有未完成（非取消）任务。"""
    for ms in _linear_project_start_milestones(pm):
        for it in issues:
            if _state_bucket_for_issue(it, status_type_map) in ("canceled", "done"):
                continue
            if _issue_matches_project_milestone(it, ms):
                return True
    return False


def _assignees_under_project_milestone(
    issues: list[dict[str, Any]],
    ms: dict[str, Any],
    status_type_map: dict[str, str],
    *,
    open_only: bool = False,
) -> list[str]:
    """该里程碑下（全项目任务、非取消）负责人去重列表。"""
    owners: set[str] = set()
    for it in issues:
        b = _state_bucket_for_issue(it, status_type_map)
        if b == "canceled":
            continue
        if open_only and b == "done":
            continue
        if not _issue_matches_project_milestone(it, ms):
            continue
        owners.add((_assignee_name(it) or "").strip() or "未分配")
    return sorted(owners, key=lambda x: (x == "未分配", x))


def _format_assignee_list(names: list[str], *, max_show: int = 6) -> str:
    if not names:
        return "（无关联任务）"
    if len(names) <= max_show:
        return "、".join(names)
    return "、".join(names[:max_show]) + f" 等 **{len(names)}** 人"


def _next_linear_project_milestone(
    pm: dict[str, Any],
    ref_day: date,
) -> tuple[dict[str, Any] | None, date | None]:
    """未到期（``>= ref_day``）的最近一个 Linear Project Milestone（按 targetDate 等排序）。"""
    dated: list[tuple[date, dict[str, Any]]] = []
    undated: list[dict[str, Any]] = []
    for ms in _linear_project_milestones(pm):
        d = _milestone_end_date(ms)
        if d is not None:
            dated.append((d, ms))
        else:
            undated.append(ms)
    dated.sort(key=lambda x: (x[0], str(x[1].get("name") or "")))
    for d, ms in dated:
        if d >= ref_day:
            return ms, d
    return (undated[0], None) if undated else (None, None)


def _project_next_milestone_table_fields(
    pm: dict[str, Any],
    project_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    ref_day: date,
    *,
    test_d: date | None,
    rel_d: date | None,
) -> tuple[str, str, str]:
    """项目一览表：下个里程碑名、剩余天数文案、当前处理人（仅「项目启动」节点展示）。"""
    ms, ms_d = _next_linear_project_milestone(pm, ref_day)
    if ms is not None:
        name = str(ms.get("name") or "").strip() or "（未命名）"
        if ms_d is not None:
            days = (ms_d - ref_day).days
            days_cell = f"**{days}**" if days >= 0 else f"已过 **{abs(days)}**"
            name_cell = f"{name}（{ms_d.isoformat()}）"
        else:
            days_cell = "—"
            name_cell = name
        handlers_cell = "—"
        if _milestone_is_project_start(ms):
            owners = _assignees_under_project_milestone(
                project_issues, ms, status_type_map, open_only=True,
            )
            handlers_cell = _format_assignee_list(owners)
        return name_cell, days_cell, handlers_cell

    next_d, next_lbl = _next_project_milestone_after(ref_day, test_d, rel_d)
    if next_d is not None and next_lbl:
        days = (next_d - ref_day).days
        return (
            f"{next_lbl}（{next_d.isoformat()}）",
            f"**{days}**",
            "—",
        )
    return "—", "—", "—"


def _milestone_schedule_date(ms: dict[str, Any], *, for_release: bool) -> date | None:
    """单个 Milestone：优先自定义提测/发布时间，未设置则用该 Milestone 结束时间。"""
    want_test = not for_release
    want_release = for_release
    custom_test, custom_release = _scan_object_for_labeled_dates(
        ms, want_test=want_test, want_release=want_release,
    )
    end_d = _milestone_end_date(ms)
    if for_release:
        return custom_release or end_d
    return custom_test or end_d


def _extract_project_milestone_dates(
    pm: dict[str, Any],
) -> tuple[date | None, date | None]:
    """从 Project Milestone（提测/发布）解析日程；未设提测/发布时间则用各 Milestone 结束时间。"""
    milestones = pm.get("_milestones")
    if not isinstance(milestones, list):
        milestones = []

    test_d: date | None = None
    release_d: date | None = None

    ms_test = _find_milestone_by_name(milestones, "提测")
    ms_release = _find_milestone_by_name(milestones, "发布")
    if ms_test:
        test_d = _milestone_schedule_date(ms_test, for_release=False)
    if ms_release:
        release_d = _milestone_schedule_date(ms_release, for_release=True)

    if test_d is None or release_d is None:
        proj_test, proj_release = _scan_object_for_labeled_dates(
            pm, want_test=(test_d is None), want_release=(release_d is None),
        )
        if test_d is None:
            test_d = proj_test
        if release_d is None:
            release_d = proj_release

    desc = str(pm.get("description") or "")
    if desc:
        if test_d is None:
            m_test = re.search(r"提测时间\s*[:：]\s*(\d{4}-\d{2}-\d{2})", desc)
            if m_test:
                test_d = _parse_project_date_field(m_test.group(1))
        if release_d is None:
            m_rel = re.search(r"发布时间\s*[:：]\s*(\d{4}-\d{2}-\d{2})", desc)
            if m_rel:
                release_d = _parse_project_date_field(m_rel.group(1))

    # 仍无日程时，用 Project 结束时间（targetDate）同时作为提测、发布
    project_end = _parse_project_date_field(pm.get("targetDate"))
    if test_d is None:
        test_d = project_end
    if release_d is None:
        release_d = project_end

    return test_d, release_d


def _enrich_linear_projects(
    mcp: LinearMcpClient,
    client: _StdioMcpClient,
    tool_names: set[str],
    projects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """对候选项目逐个 get_project，合并自定义里程碑字段。"""
    enriched: list[dict[str, Any]] = []
    for p in projects:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()
        full = mcp.get_project(client, tool_names, name) if name else {}
        merged = {**p, **(full if isinstance(full, dict) else {})}
        pid = str(merged.get("id") or "").strip()
        if pid:
            merged["_milestones"] = mcp.list_milestones_for_project(
                client, tool_names, pid,
            )
        enriched.append(merged)
    return enriched


def _project_linear_status_type(pm: dict[str, Any]) -> str:
    st = pm.get("status")
    if isinstance(st, dict):
        return str(st.get("type") or "").strip().lower()
    return ""


def _project_linear_status_in_scope(pm: dict[str, Any]) -> bool:
    """Linear Project 仅纳入 Planned / In Progress（排除 Backlog、Completed、Canceled）。"""
    st = pm.get("status")
    if not isinstance(st, dict):
        return False
    status_type = str(st.get("type") or "").strip().lower()
    if status_type in _LINEAR_PROJECT_STATUS_TYPES_IN_SCOPE:
        return True
    name = str(st.get("name") or "").strip().lower()
    return name in _LINEAR_PROJECT_STATUS_NAMES_IN_SCOPE


def _project_linear_status_in_product_pending_scope(pm: dict[str, Any]) -> bool:
    """product_created_pending 用：纳入 Planned / In Progress / Backlog。"""
    st = pm.get("status")
    if not isinstance(st, dict):
        return False
    status_type = str(st.get("type") or "").strip().lower()
    if status_type in _LINEAR_PROJECT_STATUS_TYPES_PRODUCT_PENDING:
        return True
    name = str(st.get("name") or "").strip().lower()
    return name in _LINEAR_PROJECT_STATUS_NAMES_PRODUCT_PENDING


def _project_start_date_field(pm: dict[str, Any]) -> date | None:
    return _parse_project_date_field(pm.get("startDate"))


def _project_end_date_field(pm: dict[str, Any]) -> date | None:
    return _parse_project_date_field(pm.get("targetDate"))


def _linear_project_scope_reason(
    pm: dict[str, Any],
    *,
    ref: date,
    report_week_start: date,
) -> str | None:
    """纳入项目清单：仅 Linear Project 状态为 Planned / In Progress。

    返回 ``None`` 表示纳入；否则为排除原因。``ref`` / ``report_week_start`` 保留以兼容调用方。
    """
    _ = ref
    _ = report_week_start
    name = str(pm.get("name") or "").strip() or "（未命名）"
    if _project_linear_status_in_scope(pm):
        return None
    label = _project_linear_status_name(pm) or _project_linear_status_type(pm) or "未知"
    return f"{name}：状态为 {label}（仅纳入 Planned / In Progress，排除 Backlog / Completed / Canceled）"

def _filter_linear_projects_for_report(
    projects: list[dict[str, Any]],
    *,
    report_week_start: date,
    ref: date | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """筛选纳入周报的项目（对齐 workspace Projects 视图），按创建时间倒序。"""
    ref_day = ref or date.today()
    active: list[dict[str, Any]] = []
    excluded_notes: list[str] = []
    for p in projects:
        if not isinstance(p, dict):
            continue
        reason = _linear_project_scope_reason(
            p, ref=ref_day, report_week_start=report_week_start,
        )
        if reason is None:
            active.append(p)
        else:
            excluded_notes.append(reason)
    active.sort(
        key=lambda p: str(p.get("createdAt") or ""),
        reverse=True,
    )
    return active, excluded_notes


def _project_is_ended(pm: dict[str, Any]) -> bool:
    if pm.get("completedAt") or pm.get("canceledAt"):
        return True
    st = pm.get("status")
    if isinstance(st, dict):
        return (st.get("type") or "").lower() in ("completed", "canceled")
    return False


def _project_is_canceled(pm: dict[str, Any]) -> bool:
    if pm.get("canceledAt"):
        return True
    st = pm.get("status")
    if isinstance(st, dict):
        return (st.get("type") or "").lower() == "canceled"
    return False


def _project_linear_status_name(pm: dict[str, Any]) -> str:
    st = pm.get("status")
    if isinstance(st, dict):
        return str(st.get("name") or "").strip()
    return ""


def _issue_identifier(it: dict[str, Any]) -> str:
    return str(it.get("identifier") or it.get("id") or "").strip()


def _issue_identifier_title(it: dict[str, Any]) -> str:
    ident = _issue_identifier(it)
    title = str(it.get("title") or "").strip()
    if ident and title:
        return f"{ident} {title}"
    return title or ident or "（无标题）"


_ISSUE_KEY_PREFIX_RE = re.compile(r"^\s*[A-Za-z][A-Za-z0-9]*-\d+\s*[:：\-–.]?\s*")


def _issue_title_without_identifier(it: dict[str, Any]) -> str:
    """任务标题去掉行首 identifier（周报分工摘要中不展示任务号）。"""
    t = str(it.get("title") or "").strip()
    t = _ISSUE_KEY_PREFIX_RE.sub("", t).strip()
    return t or "（无标题）"


def _text_strip_issue_ids(text: str) -> str:
    """去掉正文中类似 ``TREX-123`` 的任务号片段（避免摘要里重复出现 id）。"""
    t = re.sub(r"\b[A-Za-z][A-Za-z0-9]*-\d+\b", "", text or "")
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def _next_project_milestone_after(
    ref_day: date,
    test_d: date | None,
    rel_d: date | None,
) -> tuple[date | None, str]:
    """严格晚于 ``ref_day`` 的最近一个项目里程碑（提测 / 发布）。"""
    raw: list[tuple[date, str]] = []
    if isinstance(test_d, date) and test_d > ref_day:
        raw.append((test_d, "提测"))
    if isinstance(rel_d, date) and rel_d > ref_day:
        raw.append((rel_d, "发布"))
    if not raw:
        return None, ""
    raw.sort(key=lambda x: (x[0], 0 if x[1] == "提测" else 1))
    d0, lb0 = raw[0]
    labels = [lb0]
    for d, lb in raw[1:]:
        if d == d0 and lb not in labels:
            labels.append(lb)
        elif d > d0:
            break
    label = "·".join(labels) if len(labels) > 1 else labels[0]
    return d0, label


# 距离「下一里程碑」的日历天 ≥ 此值视为时间充足（不标紧急）
_MILESTONE_TIME_COMFORT_DAYS = 7


def _schedule_urgent_flag(
    ref_day: date,
    s: dict[str, Any],
) -> tuple[bool, str]:
    """是否紧急进度：仅看「当前日期 → 项目下一里程碑」剩余时间是否充足（+ 有未完成才紧张）。"""
    n_open = int(s.get("n_open") or 0)
    test_d = s.get("test_date")
    rel_d = s.get("release_date")
    next_d, next_lbl = _next_project_milestone_after(ref_day, test_d, rel_d)

    if next_d is None:
        return (
            False,
            "无尚未到来的提测/发布日（均在当前日期或之前）",
        )

    days = (next_d - ref_day).days
    buf = _MILESTONE_TIME_COMFORT_DAYS

    if n_open == 0:
        return (
            False,
            f"下一节点为 **{next_lbl} {next_d.isoformat()}**（剩 **{days}** 天），本 Cycle 无未完成任务",
        )

    if days >= buf:
        return (
            False,
            f"下一节点为 **{next_lbl} {next_d.isoformat()}**（剩 **{days}** 天）≥ **{buf}** 天缓冲，时间充足",
        )

    return (
        True,
        f"下一节点为 **{next_lbl} {next_d.isoformat()}**（剩 **{days}** 天）< **{buf}** 天缓冲且仍有未完成，时间偏紧",
    )


def _digest_description_blurb(raw: str, *, max_len: int = 72) -> str:
    """分工用短描述：优先首句，再截断，避免一大段 Markdown 贴进周报。"""
    t = (raw or "").strip()
    if not t:
        return ""
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", t)
    t = re.sub(r"\[[^\]]+\]\([^)]+\)", "", t).strip()
    for sep in ("。", ". ", ".\n", "\n"):
        if sep in t:
            head = t.split(sep, 1)[0].strip()
            if len(head) >= 12:
                t = head + ("…" if sep == "。" else "")
                break
    t = _text_strip_issue_ids(t)
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


# 每人分工有序列表：控制「条数」与「单条长度」的平衡
_DIGEST_MAX_ISSUE_LINES = 4
# 原始描述（strip 后）超过该字符数则不附描述摘录，仅「状态 + 标题」（防单条任务描述过长）
_DIGEST_DESC_RAW_MAX = 200
_DIGEST_DESC_MAX_LEN = 72
# 超出逐条上限后，按父单/标题主题聚类汇总，最多占用的汇总行数（含「其余合并」行）
_DIGEST_TAIL_MAX_CLUSTER_LINES = 5


def _issue_linear_id(it: dict[str, Any]) -> str:
    return str(it.get("id") or it.get("issueId") or "").strip()


def _digest_counter_zh_parts(c: Counter) -> str:
    """状态计数 → 周报分工用中文片段（与逐条溢出旧口径一致）。"""
    parts: list[str] = []
    if c["done"]:
        parts.append(f"已完成 **{c['done']}**")
    if c["in_progress"]:
        parts.append(f"进行中 **{c['in_progress']}**")
    if c["todo"]:
        parts.append(f"待开始 **{c['todo']}**")
    if c["backlog"]:
        parts.append(f"Backlog **{c['backlog']}**")
    if c["canceled"]:
        parts.append(f"已取消 **{c['canceled']}**")
    if c["other"]:
        parts.append(f"其他 **{c['other']}**")
    return "、".join(parts) if parts else "—"


def _digest_overflow_cluster_lines(
    tail: list[dict[str, Any]],
    owner_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    *,
    max_lines: int = _DIGEST_TAIL_MAX_CLUSTER_LINES,
) -> list[str]:
    """将未逐条展开的任务按「同父单 / 同标题主题」聚类，输出若干条可读汇总（尽量不超过 ``max_lines`` 行）。"""
    if not tail:
        return []
    id_to_issue: dict[str, dict[str, Any]] = {}
    for it in owner_issues:
        iid = _issue_linear_id(it)
        if iid:
            id_to_issue[iid] = it
    parent_ids_with_children: set[str] = set()
    for x in owner_issues:
        pid = str(x.get("parentId") or "").strip()
        if pid:
            parent_ids_with_children.add(pid)
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    labels: dict[str, str] = {}
    for it in tail:
        pid = str(it.get("parentId") or "").strip()
        self_id = _issue_linear_id(it)
        if pid and pid in id_to_issue:
            gk = f"p:{pid}"
            if gk not in labels:
                labels[gk] = _issue_title_without_identifier(id_to_issue[pid])
        elif self_id and self_id in parent_ids_with_children:
            gk = f"p:{self_id}"
            if gk not in labels:
                labels[gk] = _issue_title_without_identifier(it)
        else:
            th = _title_theme(str(it.get("title") or ""))
            gk = f"t:{th}"
            if gk not in labels:
                labels[gk] = th
        clusters[gk].append(it)

    def _sort_key(gk: str) -> tuple[int, int, str]:
        citems = clusters[gk]
        c = Counter(_state_bucket_for_issue(x, status_type_map) for x in citems)
        hip = 0 if c["in_progress"] else 1
        return (hip, -len(citems), labels.get(gk, gk))

    ordered = sorted(clusters.keys(), key=_sort_key)
    out: list[str] = []
    if len(ordered) <= max_lines:
        for gk in ordered:
            citems = clusters[gk]
            c = Counter(_state_bucket_for_issue(x, status_type_map) for x in citems)
            stat = _digest_counter_zh_parts(c)
            lbl = labels.get(gk, "（无主题）")
            out.append(f"{stat} · 「{lbl}」等 **{len(citems)}** 项")
        return out

    kept = ordered[: max_lines - 1]
    merged_gks = ordered[max_lines - 1 :]
    for gk in kept:
        citems = clusters[gk]
        c = Counter(_state_bucket_for_issue(x, status_type_map) for x in citems)
        stat = _digest_counter_zh_parts(c)
        lbl = labels.get(gk, "（无主题）")
        out.append(f"{stat} · 「{lbl}」等 **{len(citems)}** 项")
    rest_items = [it for gk in merged_gks for it in clusters[gk]]
    c = Counter(_state_bucket_for_issue(x, status_type_map) for x in rest_items)
    stat = _digest_counter_zh_parts(c)
    out.append(
        f"{stat} · 其余 **{len(rest_items)}** 项（**{len(merged_gks)}** 个主题/父单分支，详见 Linear 该项目下筛选）"
    )
    return out


def _owner_cycle_tasks_digest_lines(
    owner_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
) -> list[str]:
    """单负责人在本 Cycle、本项目下各任务一行摘要（无任务号），供有序列表渲染。

    规则：最多展开 ``_DIGEST_MAX_ISSUE_LINES`` 条任务明细；每条若原始描述（strip）长度
    **不超过** ``_DIGEST_DESC_RAW_MAX`` 则附短描述（经 ``_digest_description_blurb``，上限
    ``_DIGEST_DESC_MAX_LEN``），否则仅「状态 + 标题」；超出部分按父单/标题主题聚类汇总
    （最多 ``_DIGEST_TAIL_MAX_CLUSTER_LINES`` 行，主题过多时末行合并）。
    """
    if not owner_issues:
        return ["（本 Cycle 无任务）"]

    def _state_zh(it: dict[str, Any]) -> str:
        b = _state_bucket_for_issue(it, status_type_map)
        return {
            "done": "已完成",
            "in_progress": "进行中",
            "todo": "待开始",
            "backlog": "Backlog",
            "canceled": "已取消",
            "other": "其他",
        }.get(b, "其他")

    def _sort_key(it: dict[str, Any]) -> tuple[int, str]:
        b = _state_bucket_for_issue(it, status_type_map)
        pri = 0 if b == "in_progress" else 1
        return (pri, str(it.get("title") or ""))

    sorted_items = sorted(owner_issues, key=_sort_key)
    n = len(sorted_items)
    cap = _DIGEST_MAX_ISSUE_LINES
    show = min(n, cap)
    rest = n - show

    out: list[str] = []
    for idx, it in enumerate(sorted_items[:show]):
        title = _issue_title_without_identifier(it)
        st_zh = _state_zh(it)
        line = f"{st_zh}「{title}」"
        raw = str(it.get("description") or "").strip()
        if raw and len(raw) <= _DIGEST_DESC_RAW_MAX:
            blurb = _digest_description_blurb(raw, max_len=_DIGEST_DESC_MAX_LEN)
            if blurb:
                line += f"：{blurb}"
        out.append(line)

    if rest > 0:
        tail = sorted_items[show:]
        out.extend(_digest_overflow_cluster_lines(tail, owner_issues, status_type_map))

    return out


def _description_excerpt(desc: str | None, max_len: int = 280) -> str:
    t = (desc or "").strip()
    if not t:
        return "（无描述）"
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", t)
    t = re.sub(r"\[[^\]]+\]\([^)]+\)", "", t)
    t = t.strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _linear_issue_status_type_lower(
    it: dict[str, Any],
    status_type_map: dict[str, str],
) -> str:
    """解析 Linear issue 的状态类型（小写）。

    优先用当前 Team 的「状态显示名 → 类型」表；表未命中时回退 ``statusType``、
    ``state.type``（MCP / GraphQL 常见字段），避免旧工作流别名导致误判为未完成。
    """
    name = (it.get("status") or "").strip()
    t = (status_type_map.get(name) or "").strip().lower()
    if t:
        return t
    t = str(it.get("statusType") or "").strip().lower()
    if t:
        return t
    st = it.get("state")
    if isinstance(st, dict):
        t = str(st.get("type") or "").strip().lower()
        if t:
            return t
    return ""


def _state_bucket_for_issue(it: dict[str, Any], status_type_map: dict[str, str]) -> str:
    """与 group_issues 一致的状态桶，另单独识别已取消。"""
    st_type = _linear_issue_status_type_lower(it, status_type_map)
    if st_type == "canceled":
        return "canceled"
    if st_type == "completed":
        return "done"
    if st_type == "started":
        return "in_progress"
    if st_type == "unstarted":
        return "todo"
    if st_type in ("backlog", "triage"):
        return "backlog"
    return "other"


def _state_bucket_zh(it: dict[str, Any], status_type_map: dict[str, str]) -> str:
    b = _state_bucket_for_issue(it, status_type_map)
    return {
        "done": "已完成",
        "in_progress": "进行中",
        "todo": "待开始",
        "backlog": "Backlog",
        "canceled": "已取消",
        "other": "其他",
    }.get(b, "其他")


def _md_table_escape_cell(text: str) -> str:
    """Markdown 表格单元格：压平换行并避免 ``|`` 破坏列。"""
    t = re.sub(r"\s+", " ", (text or "").strip())
    return t.replace("|", "｜")


def _issue_member_table_status_cell(
    it: dict[str, Any],
    status_type_map: dict[str, str],
) -> str:
    """§3 成员表「状态」列：优先 Linear 状态显示名，否则回退状态桶中文。"""
    label = str(it.get("status") or "").strip()
    return label or _state_bucket_zh(it, status_type_map)


def _issue_member_table_task_cell(it: dict[str, Any]) -> str:
    """§3 成员表「任务」列：仅标题（无任务号、无描述）。"""
    return _issue_title_without_identifier(it)


def _issue_work_done_summary(
    it: dict[str, Any],
    status_type_map: dict[str, str],
    *,
    desc_max_len: int = 160,
) -> str:
    """状态 + 标题拼接（兼容旧调用；§3 表格请用分列函数）。"""
    _ = desc_max_len
    st = _issue_member_table_status_cell(it, status_type_map)
    return f"{st}「{_issue_member_table_task_cell(it)}」"


def _issue_due_date(it: dict[str, Any]) -> date | None:
    """任务截止/目标日（Linear 常见 dueDate / targetDate）。"""
    for key in ("dueDate", "targetDate", "endDate"):
        d = _parse_project_date_field(it.get(key))
        if d is not None:
            return d
    return None


def _issue_days_remaining_cell(
    it: dict[str, Any],
    status_type_map: dict[str, str],
    ref_day: date,
) -> str:
    if _state_bucket_for_issue(it, status_type_map) == "done":
        return "—"
    due = _issue_due_date(it)
    if due is None:
        return "—"
    days = (due - ref_day).days
    if days < 0:
        return f"逾期 {abs(days)}"
    if days == 0:
        return "0（今日）"
    return str(days)


def _issue_risk_reasons(
    it: dict[str, Any],
    status_type_map: dict[str, str],
    now: datetime,
    *,
    stale_days: int = 3,
) -> list[str]:
    """单条未完成任务的风险信号（与 detect_risks 口径一致）。"""
    if _state_bucket_for_issue(it, status_type_map) == "done":
        return []
    reasons: list[str] = []
    if _is_blocked_status(it.get("status")):
        reasons.append("受阻")
    bucket = _state_bucket_for_issue(it, status_type_map)
    if bucket == "in_progress":
        upd = _parse_dt(it.get("updatedAt"))
        if upd and (now - upd).days >= stale_days:
            reasons.append("久未更新")
        if not _assignee_name(it):
            reasons.append("未分配")
        if len((it.get("description") or "").strip()) < 30:
            reasons.append("描述过短")
    pr = it.get("priority")
    if isinstance(pr, dict) and pr.get("name") in ("Urgent", "High"):
        reasons.append("高优")
    return reasons


def _issue_risk_cell(
    it: dict[str, Any],
    status_type_map: dict[str, str],
    now: datetime,
) -> str:
    reasons = _issue_risk_reasons(it, status_type_map, now)
    if not reasons:
        return "否"
    return "是（" + "、".join(reasons) + "）"


def _html_kv_table(rows: list[tuple[str, str]], *, value_allows_html: bool = False) -> str:
    """HTML 两列表格：维度 | 内容（表头用 th）。"""
    if not rows:
        return ""
    parts = ["<table>", "<tbody>"]
    for label, value in rows:
        cell = value if value_allows_html else html.escape(value)
        parts.append(
            f"<tr><th>{html.escape(label)}</th><td>{cell}</td></tr>",
        )
    parts.append("</tbody></table>")
    return "\n".join(parts)


def _html_table_with_rowspan_col0(
    headers: list[str],
    rows: list[tuple[str, ...]],
) -> str:
    """HTML 表格：第 0 列相同连续行合并 rowspan。"""
    if not rows:
        return ""
    parts = [
        "<table>",
        "<thead><tr>"
        + "".join(f"<th>{html.escape(h)}</th>" for h in headers)
        + "</tr></thead>",
        "<tbody>",
    ]
    i = 0
    ncols = len(headers)
    while i < len(rows):
        row0 = rows[i][0]
        j = i + 1
        while j < len(rows) and rows[j][0] == row0:
            j += 1
        span = j - i
        for k in range(i, j):
            cells = list(rows[k])
            if len(cells) != ncols:
                raise ValueError(f"row width {len(cells)} != {ncols}")
            parts.append("<tr>")
            if k == i:
                parts.append(
                    f'<td rowspan="{span}">{html.escape(cells[0])}</td>',
                )
            for c in cells[1:]:
                parts.append(f"<td>{html.escape(c)}</td>")
            parts.append("</tr>")
        i = j
    parts.append("</tbody></table>")
    return "\n".join(parts)


def _html_table_role_owner_tasks(rows: list[tuple[str, str, str]]) -> str:
    """HTML 表格：角色、负责人列按连续相同值合并 rowspan。"""
    if not rows:
        return ""
    parts = [
        "<table>",
        "<thead><tr>"
        + "".join(
            f"<th>{html.escape(h)}</th>"
            for h in ("角色", "负责人", "任务")
        )
        + "</tr></thead>",
        "<tbody>",
    ]
    i = 0
    while i < len(rows):
        role = rows[i][0]
        role_end = i
        while role_end < len(rows) and rows[role_end][0] == role:
            role_end += 1
        role_span = role_end - i
        k = i
        while k < role_end:
            owner = rows[k][1]
            owner_end = k
            while owner_end < role_end and rows[owner_end][1] == owner:
                owner_end += 1
            owner_span = owner_end - k
            for t in range(k, owner_end):
                parts.append("<tr>")
                if t == i:
                    parts.append(
                        f'<td rowspan="{role_span}">{html.escape(role)}</td>',
                    )
                if t == k:
                    parts.append(
                        f'<td rowspan="{owner_span}">{html.escape(owner)}</td>',
                    )
                parts.append(f"<td>{html.escape(rows[t][2])}</td>")
                parts.append("</tr>")
            k = owner_end
        i = role_end
    parts.append("</tbody></table>")
    return "\n".join(parts)


def _project_division_table_rows(
    items: list[dict[str, Any]],
    status_type_map: dict[str, str],
) -> list[tuple[str, str, str]]:
    """按项目分工表行：(角色, 负责人, 任务摘要)。"""
    by_o: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in items:
        by_o[_assignee_name(it) or "未分配"].append(it)
    div_role_map = _assignee_work_division_role_map()
    role_blocks: list[tuple[str, str, defaultdict[str, list[dict[str, Any]]]]] = [
        ("backend", "后端", defaultdict(list)),
        ("frontend", "前端", defaultdict(list)),
        ("test", "测试", defaultdict(list)),
        ("other", "其他", defaultdict(list)),
    ]
    for owner, o_issues in by_o.items():
        rb = div_role_map.get(owner.strip(), "other") if owner != "未分配" else "other"
        for key, _lbl, acc in role_blocks:
            if key == rb:
                acc[owner].extend(o_issues)
                break
    out: list[tuple[str, str, str]] = []
    for _rb_key, rb_label, owners_map in role_blocks:
        if not owners_map:
            continue
        for owner in sorted(owners_map.keys(), key=lambda x: (x == "未分配", x)):
            for line in _owner_cycle_tasks_digest_lines(
                owners_map[owner], status_type_map,
            ):
                out.append((rb_label, owner, line))
    return out


def _render_project_detail_meta_kv_table(
    s: dict[str, Any],
    *,
    lead: str,
    ref_day: date,
) -> str:
    """单项目概况：Leader / 里程碑 / 进度 / 参与人 / 风险（键值表）。"""
    if s.get("test_date") or s.get("release_date"):
        td = s["test_date"].isoformat() if s.get("test_date") else "—"
        rd = s["release_date"].isoformat() if s.get("release_date") else "—"
        urgent, urgent_note = _schedule_urgent_flag(ref_day, s)
        urg_txt = "是" if urgent else "否"
        note_plain = re.sub(r"\*\*([^*]+)\*\*", r"\1", urgent_note) if urgent_note else ""
        note = f"（{note_plain}）" if note_plain else ""
        milestone = (
            f"提测 {td} · 发布 {rd} · 项目阶段 {s['status_label']} · "
            f"是否紧急进度 {urg_txt}{note}"
        )
    else:
        milestone = (
            f"提测 — · 发布 — · 项目阶段 {s['status_label']} · "
            "是否紧急进度 —（无提测/发布日）"
        )
    progress = (
        f"完成 {s['n_done']} / 进行中 {s['n_ip']} / 待开始 {s['n_todo']} / "
        f"Backlog·Triage {s['n_bl']}"
        + (f" / 其他 {s['n_other']}" if s["n_other"] else "")
        + (f"；已取消 {s['n_canceled']}（不计入分母）" if s["n_canceled"] else "")
        + f"；{s.get('progress_label_zh', '本周期')} {s['done_pct']:.1f}%"
        + (
            f"；本 Cycle Bug {s.get('n_bugs_cycle', 0)}"
            f"（未关闭 {s.get('n_bugs_open', 0)}）"
            if s["status_label"] == "测试中"
            else ""
        )
    )
    owners = sorted({(_assignee_name(it) or "未分配") for it in s["items"]})
    participants = "、".join(owners) if owners else "（无）"

    if s["risk_parts"]:
        risk_lines = [html.escape(p) for p in s["risk_parts"]]
        for it in s.get("proj_blocked") or []:
            risk_lines.append(html.escape(_risk_line_with_owner(it).strip()))
        if len(s.get("proj_blocked") or []) > 10:
            risk_lines.append(
                html.escape(
                    f"… 另有 {len(s['proj_blocked']) - 10} 项 Blocked 未列出",
                ),
            )
        risk_cell = "<br/>".join(risk_lines)
    else:
        risk_cell = html.escape("未发现明显信号")

    kv_rows = [
        ("Leader", html.escape(lead or "—")),
        ("里程碑", html.escape(milestone)),
        ("进度", html.escape(f"（{s.get('progress_label_zh', '本周期')}口径）{progress}")),
        ("参与人", html.escape(participants)),
        ("风险", risk_cell),
    ]
    return _html_kv_table(kv_rows, value_allows_html=True)


def _member_issue_table_sort_key(
    it: dict[str, Any],
    status_type_map: dict[str, str],
) -> tuple:
    bucket = _state_bucket_for_issue(it, status_type_map)
    open_first = 0 if bucket != "done" else 1
    return (open_first, _issue_project_name(it), _issue_key(it))


def _format_member_week_code_line(stats: dict[str, int] | None) -> str | None:
    """§3 每人上周 Git 代码行数（来自 daily_report_snapshots）。"""
    if not stats:
        return None
    ins = int(stats.get("insertions") or 0)
    dels = int(stats.get("deletions") or 0)
    if ins == 0 and dels == 0:
        return None
    net = ins - dels
    days = int(stats.get("active_days") or 0)
    day_part = f"，活跃 **{days}** 天" if days else ""
    return f"- **上周代码变更**：`+{ins}` / `-{dels}`（净 `{net:+d}`{day_part}）"


def _member_week_code_stats_lookup(iso_week: str) -> dict[str, dict[str, int]] | None:
    return load_weekly_member_code_stats_lookup(
        iso_week,
        member_rows=_iter_report_members(),
    )


def _render_member_cycle_issues_table(
    member_cycle_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    now: datetime,
    iso_week: str,
    grouped: GroupedIssues | None = None,
    member_code_lookup: dict[str, dict[str, int]] | None = None,
) -> list[str]:
    """§3 按成员：每人一句上周总结与下周计划 + 独立表格（任务表按报告周状态变化过滤）。"""
    week_start, week_end = _week_date_range(iso_week)
    lines: list[str] = []
    lines.append("\n#### 3. 按成员：本迭代内全部任务")
    if not member_cycle_issues:
        lines.append("\n_（本 Cycle 无任务）_")
        return lines

    ref_day = _to_local_date(now)
    known_members = _report_member_assignee_names()
    by_owner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in member_cycle_issues:
        if _state_bucket_for_issue(it, status_type_map) == "canceled":
            continue
        owner = (_assignee_name(it) or "").strip()
        if not owner or owner not in known_members:
            continue
        by_owner[owner].append(it)

    if not by_owner:
        lines.append(
            "\n_（本 Cycle 无成员表内负责人的任务；未分配或非成员表 assignee 不计入。）_",
        )
        return lines

    headers = ["项目", "任务ID", "状态", "任务", "剩余(天)", "风险"]
    owners = sorted(by_owner.keys(), key=_member_owner_section_sort_key)

    for owner in owners:
        table_items = sorted(
            [
                it for it in by_owner[owner]
                if _issue_in_member_week_activity_scope(it, iso_week, status_type_map)
            ],
            key=lambda it: _member_issue_table_sort_key(it, status_type_map),
        )
        table_rows: list[tuple[str, ...]] = []
        for it in table_items:
            table_rows.append((
                _issue_project_name(it),
                _issue_key(it),
                _issue_member_table_status_cell(it, status_type_map),
                _issue_member_table_task_cell(it),
                _issue_days_remaining_cell(it, status_type_map, ref_day),
                _issue_risk_cell(it, status_type_map, now),
            ))
        lines.append(f"\n##### {owner}")
        if grouped is not None:
            done_o = _filter_issues_by_assignee(grouped.done, owner)
            inprog_o = _filter_issues_by_assignee(grouped.in_progress, owner)
            plan_o = _filter_issues_by_assignee(
                grouped.in_progress + grouped.todo + grouped.backlog,
                owner,
            )
            summary = _owner_last_week_summary_one_sentence(done_o, inprog_o)
            plan = _owner_next_week_plan_one_sentence(plan_o, status_type_map)
            lines.append(f"\n- **上周工作总结**：{summary}")
            lines.append(f"\n- **下周计划**：{plan}")
        if member_code_lookup is not None:
            code_line = _format_member_week_code_line(member_code_lookup.get(owner))
            if code_line:
                lines.append(f"\n{code_line}")
        if table_rows:
            lines.append("\n" + _html_table_with_rowspan_col0(headers, table_rows))
        else:
            lines.append(
                f"\n_（{week_start} ~ {week_end} 内无进入进行中 / 已完成 / In Review 的任务行；"
                "已取消除外，且**不按** §1 项目阶段或发布状态过滤。）_",
            )

    lines.append(
        "\n> **口径**：每人先给 **上周工作总结**、**下周计划** 各一句（由本 Cycle 任务归纳："
        "上周 = 已完成 + 进行中；下周 = 进行中 + 待开始 + Backlog）；再附任务表。"
        "按成员分表；**项目**列相同连续行合并单元格。"
        f"任务表仅列报告周（{week_start} ~ {week_end}）内进入 **进行中**（``startedAt`` 在周内，"
        "或无 ``startedAt`` 时当前仍为进行中且 ``updatedAt`` 在周内）、**已完成**（``completedAt`` 在周内）、"
        "**In Review**（状态名含 review 且 ``updatedAt`` 在周内）的 Cycle 任务（已取消除外），"
        "**不按** §1 项目阶段或发布状态过滤；**仅统计** superteam 成员表内 assignee（后端→前端→测试顺序）。"
        "**状态** = Linear 当前状态显示名（无则回退状态桶）；**任务** = 标题（无任务号、无描述摘录）。"
        "**上周代码变更** = ``daily_report_snapshots``（``source=git``）区间内按人汇总 "
        "``payload.files[kind=user].user.stats.insertions/deletions``（人名与成员表别名匹配）。"
        "**剩余(天)** = 报告日至 ``dueDate``（或 ``targetDate``）日历差，已完成填 **—**；"
        "无截止日记 **—**。**风险**仅对未完成任务判定（受阻 / 进行中久未更新 / 未分配 / 描述过短 / 高优），"
        "无信号为 **否**，有信号为 **是（…）**；已完成填 **否**。"
        "表内按项目、未完成优先、任务 ID 排序。"
    )
    return lines


# 与 snapshot_member.workload 同源：issue 集合不做成员组/过期项目过滤
_MEMBER_WORKLOAD_SCOPE_NOTE = (
    "报告周内 completedAt 完成、当前进行中/In Review/受阻、"
    "Todo/Backlog 且 due 在本周；更早完成不计"
)


def _member_workload_rows(
    cycle_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    iso_week: str,
) -> list[dict[str, Any]]:
    """按负责人汇总当周负载（本周完成 + 当前进行中；上周及更早完成不计）。"""
    by_member: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in cycle_issues:
        if not _issue_in_member_week_workload_scope(it, iso_week, status_type_map):
            continue
        by_member[_assignee_name(it) or "未分配"].append(it)

    rows: list[dict[str, Any]] = []
    for owner, items in by_member.items():
        n_done = n_ip = n_todo = n_bl = n_canceled = n_other = 0
        hours_total = hours_done = hours_open = 0.0
        hours_filled = 0
        for it in items:
            b = _state_bucket_for_issue(it, status_type_map)
            if b == "canceled":
                n_canceled += 1
                continue
            h = _issue_estimate_hours(it)
            if h is not None:
                hours_total += h
                hours_filled += 1
            if b == "done":
                n_done += 1
                if h is not None:
                    hours_done += h
            elif b == "in_progress":
                n_ip += 1
                if h is not None:
                    hours_open += h
            elif b == "todo":
                n_todo += 1
                if h is not None:
                    hours_open += h
            elif b == "backlog":
                n_bl += 1
                if h is not None:
                    hours_open += h
            else:
                n_other += 1
                if h is not None:
                    hours_open += h
        n_open = n_ip + n_todo + n_bl + n_other
        n_active = n_done + n_open
        rows.append({
            "owner": owner,
            "total": len(items),
            "active": n_active,
            "done": n_done,
            "in_progress": n_ip,
            "todo": n_todo,
            "backlog": n_bl,
            "other": n_other,
            "canceled": n_canceled,
            "open": n_open,
            "hours_total": hours_total,
            "hours_done": hours_done,
            "hours_open": hours_open,
            "hours_filled": hours_filled,
            "done_pct": (n_done / n_active * 100.0) if n_active else 0.0,
        })
    rows.sort(key=lambda r: (-r["hours_total"], -r["open"], r["owner"]))
    return rows


def _member_aligned_workload_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """与 snapshot_member 展示一致：成员表姓名顺序；未分配单独置后（若有）。"""
    by_owner = {str(r.get("owner") or ""): r for r in rows}
    out: list[dict[str, Any]] = []
    for owner in sorted(_report_member_assignee_names(), key=_member_owner_section_sort_key):
        r = by_owner.get(owner)
        if r is not None:
            out.append(r)
    unassigned = by_owner.get("未分配")
    if unassigned and int(unassigned.get("total") or 0) > 0:
        out.append(unassigned)
    return out


def _summarize_project_cycle_stats(
    pname: str,
    items: list[dict[str, Any]],
    status_type_map: dict[str, str],
    now: datetime,
    project_meta: dict[str, Any] | None = None,
    project_issues: list[dict[str, Any]] | None = None,
    rd_names: set[str] | None = None,
    qa_names: set[str] | None = None,
) -> dict[str, Any]:
    """单项目 Cycle 统计：进度计数、里程碑状态、风险信号（与 §3 口径一致）。"""
    pm = project_meta or {}
    project_created_at = _parse_dt(pm.get("createdAt")) if pm else None
    project_ended = _project_is_ended(pm) if pm else False
    project_canceled = _project_is_canceled(pm) if pm else False
    linear_status = _project_linear_status_name(pm) if pm else ""
    test_date, release_date = _extract_project_milestone_dates(pm) if pm else (None, None)
    ref_day = _to_local_date(now)
    all_proj_issues = project_issues if project_issues is not None else items
    rd_set = _rd_member_names() if rd_names is None else rd_names
    qa_set = _test_member_names() if qa_names is None else qa_names
    proj_issue_count = len(all_proj_issues)
    rd_issue_count = _count_rd_project_issues(all_proj_issues, status_type_map, rd_set)
    if proj_issue_count > 0:
        rd_done, all_done = _project_task_completion_flags(
            all_proj_issues,
            status_type_map,
            rd_set,
        )
    else:
        rd_done, all_done = True, True
    lifecycle_status = _derive_project_lifecycle_status(
        ref=ref_day,
        test_date=test_date,
        release_date=release_date,
        rd_tasks_done=rd_done,
        all_tasks_done=all_done,
        project_issue_count=proj_issue_count,
        rd_issue_count=rd_issue_count,
    )
    if (
        pm
        and not project_canceled
        and _project_start_milestone_has_open_tasks(all_proj_issues, pm, status_type_map)
    ):
        lifecycle_status = "启动中"
    (
        full_n_done,
        full_n_ip,
        full_n_todo,
        full_n_bl,
        full_n_other,
        full_n_canceled,
        full_n_active,
        _full_pct,
    ) = _count_cycle_issue_buckets(items, status_type_map)
    full_n_open = full_n_ip + full_n_todo + full_n_bl + full_n_other

    proj_blocked = [it for it in items if _is_blocked_status(it.get("status"))]
    stale_n = 0
    in_prog = [it for it in items if _state_bucket_for_issue(it, status_type_map) == "in_progress"]
    for it in in_prog:
        upd = _parse_dt(it.get("updatedAt"))
        if upd and (now - upd).days >= 3:
            stale_n += 1
    no_owner_n = sum(1 for it in in_prog if not _assignee_name(it))
    short_desc_n = sum(
        1 for it in in_prog if len((it.get("description") or "").strip()) < 30
    )

    risk_parts: list[str] = []
    if proj_blocked:
        risk_parts.append(f"Blocked **{len(proj_blocked)}** 项")
    if stale_n:
        risk_parts.append(f"进行中超过 3 天未更新 **{stale_n}** 项")
    if no_owner_n:
        risk_parts.append(f"进行中未分配 **{no_owner_n}** 项")
    if short_desc_n:
        risk_parts.append(f"进行中描述过短 **{short_desc_n}** 项")
    if project_ended and full_n_open > 0:
        risk_parts.append(f"项目已结束仍有未完成 **{full_n_open}** 项")

    risk_short: list[str] = []
    if proj_blocked:
        risk_short.append(f"Blocked×{len(proj_blocked)}")
    if stale_n:
        risk_short.append(f"久未更新×{stale_n}")
    if no_owner_n:
        risk_short.append(f"未分配×{no_owner_n}")
    if short_desc_n:
        risk_short.append(f"描述过短×{short_desc_n}")
    if project_ended and full_n_open > 0:
        risk_short.append(f"已结束未清×{full_n_open}")

    status_label = lifecycle_status
    if project_canceled:
        status_label = "已取消"
    elif project_ended and lifecycle_status not in ("已上线", "延期上线"):
        status_label = "已结束"

    progress_kind = _project_table_progress_kind(status_label)
    progress_label_zh = "本周期"
    sub: list[dict[str, Any]] = items
    if progress_kind == "dev":
        progress_label_zh = "开发进度"
        sub = _issues_assigned_to_any(items, rd_set)
        if not sub:
            sub = items
            progress_label_zh = "本周期"
    elif progress_kind == "test":
        progress_label_zh = "测试进度"
        sub = _issues_assigned_to_any(items, qa_set)
        if not sub:
            sub = [it for it in items if _is_bug_like_issue(it)]
            progress_label_zh = "测试进度（Bug）"
        if not sub:
            sub = items
            progress_label_zh = "本周期"

    n_done, n_ip, n_todo, n_bl, n_other, n_canceled, n_active, pct = _count_cycle_issue_buckets(
        sub, status_type_map,
    )
    n_open = n_ip + n_todo + n_bl + n_other

    n_bugs_cycle, n_bugs_open = (0, 0)
    if status_label == "测试中":
        n_bugs_cycle, n_bugs_open = _bug_cycle_stats(items, status_type_map)

    next_ms_name, next_ms_days, next_ms_owners = _project_next_milestone_table_fields(
        pm,
        all_proj_issues,
        status_type_map,
        ref_day,
        test_d=test_date,
        rel_d=release_date,
    )

    return {
        "name": pname,
        "items": items,
        "total": len(items),
        "n_done": n_done,
        "n_ip": n_ip,
        "n_todo": n_todo,
        "n_bl": n_bl,
        "n_canceled": n_canceled,
        "n_other": n_other,
        "n_active": n_active,
        "n_open": n_open,
        "done_pct": pct,
        "progress_kind": progress_kind,
        "progress_label_zh": progress_label_zh,
        "n_open_full_cycle": full_n_open,
        "n_active_full_cycle": full_n_active,
        "n_bugs_cycle": n_bugs_cycle,
        "n_bugs_open": n_bugs_open,
        "status_label": status_label,
        "risk_parts": risk_parts,
        "risk_short": "；".join(risk_short) if risk_short else "",
        "proj_blocked": proj_blocked,
        "in_prog": in_prog,
        "project_created_at": project_created_at,
        "project_ended": project_ended,
        "linear_status": linear_status,
        "test_date": test_date,
        "release_date": release_date,
        "detail_anchor": _report_project_detail_anchor(pname),
        "next_ms_name": next_ms_name,
        "next_ms_days": next_ms_days,
        "next_ms_owners": next_ms_owners,
    }


def _project_overview_sort_key(stats: dict[str, Any]) -> tuple:
    """按 Linear 项目创建时间倒序（与 _filter_linear_projects_for_report 预排序一致，作稳定次序）。"""
    created = stats.get("project_created_at")
    ts = created.timestamp() if created else 0.0
    return (-ts, stats["name"])


def _render_project_overview_lines(
    proj_stats: list[dict[str, Any]],
) -> list[str]:
    """§1 项目一览：表格展示进度、状态、风险，便于扫读。"""
    if not proj_stats:
        return []

    lines: list[str] = []
    lines.append("\n#### 1. 本迭代涉及的项目")
    lines.append(
        "\n| 项目 | 任务 | 下个里程碑 | 剩(天) | 当前处理人 | 阶段进度 | "
        "进度（完成/进行中/待办+Backlog） | 项目阶段 | 风险 |"
    )
    lines.append("| --- | ---: | --- | ---: | --- | ---: | --- | --- | --- |")
    for s in proj_stats:
        anchor = str(s.get("detail_anchor") or _report_project_detail_anchor(str(s.get("name") or "")))
        name_cell = f'<a href="#{anchor}">{html.escape(str(s.get("name") or ""))}</a>'
        bar = _pct_share_bar(s["done_pct"])
        prog = f"{s['n_done']}/{s['n_ip']}/{s['n_todo'] + s['n_bl']}"
        risk_cell = f"⚠️ {s['risk_short']}" if s["risk_short"] else "✅ 无"
        status_cell = s["status_label"]
        if s["status_label"] == "测试中":
            status_cell = (
                f"{status_cell} · Bug **{s.get('n_bugs_cycle', 0)}**"
                f"（未关闭 **{s.get('n_bugs_open', 0)}**）"
            )
        elif (
            s["status_label"] == "开发中"
            and s.get("n_open_full_cycle", s["n_open"]) == 0
            and s.get("n_active_full_cycle", s["n_active"]) > 0
        ):
            status_cell = f"{s['status_label']}·本Cycle已清"
        plab = s.get("progress_label_zh") or "本周期"
        pct_cell = f"`{bar}` **{s['done_pct']:.0f}%** · _{plab}_"
        lines.append(
            f"| {name_cell} | {s['total']} | {s.get('next_ms_name', '—')} | "
            f"{s.get('next_ms_days', '—')} | {s.get('next_ms_owners', '—')} | {pct_cell} | "
            f"{prog} | {status_cell} | {risk_cell} |"
        )
    lines.append(
        "\n> **口径**：**阶段进度**与「进度」三数按**项目阶段**切换子集：**启动中 / 开发中 / 联调中 / 设计中 / 延期开发中**"
        " 仅统计 assignee 落在成员表 **backend / frontend / architect** 的本 Cycle 任务（若该子集为空则退化为全量）；"
        "**项目阶段**为 **启动中** 时：Linear 存在名称含 **项目启动** 的 Project Milestone，且其下仍有**未完成**任务（与下个里程碑「当前处理人」同一匹配口径）。"
        "**测试中 / 待发布 / 已上线 / 延期上线** 优先统计 **测试**职能指派，若无则退化为带 **bug** 标签（或标题形似 Bug）"
        " 的任务子集，再空则全量。**项目阶段**仍按**整个项目**研发任务 + 提测/发布日推导；"
        f"**联调中**仅在未到提测且研发任务均已关闭、且距提测 ≤ {_INTEGRATION_STATUS_MAX_DAYS_BEFORE_TEST} 天时出现。"
        "「进行中」= Linear 状态类型 Started。**测试中**行在「项目阶段」列追加本 Cycle **Bug 总数与未关闭数**（标签 bug 或标题规则）。"
        "风险信号仍按**全 Cycle** 任务扫描。**项目**列可点击跳转至下文「按项目」对应小节。"
        "**下个里程碑**取 Linear Project 里程碑列表中**最近一个未到期**节点（按 targetDate 等，``>=`` 报告日）；"
        "**当前处理人**仅当下个里程碑为 **项目启动** 时展示：该项目下、挂该 Milestone 且**未完成**任务的 assignee；"
        "其余里程碑为 **—**。若无未到期 Milestone 则回退下一 **提测/发布** 日。**剩(天)** 为报告日至该节点日历日之差。"
    )

    return lines


def _render_member_workload_lines(
    cycle_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    iso_week: str,
    workload_rows: list[dict[str, Any]] | None = None,
) -> list[str]:
    """成员负载：放在「当前迭代」区块末尾（项目一览 → 按项目 → 按成员明细之后）。"""
    rows = (
        workload_rows
        if workload_rows is not None
        else _member_workload_rows(cycle_issues, status_type_map, iso_week)
    )
    if not rows:
        return []

    lines: list[str] = []
    lines.append("\n#### 4. 成员负载")
    pt_h = "、".join(f"{p}点→{int(h)}h" for p, h in sorted(_ESTIMATE_POINT_TO_HOURS.items()))
    lines.append(
        f"\n> **负载** = **合计工时(估) ÷ {_MEMBER_WEEKLY_CAPACITY_HOURS:.0f}h**（周基准），以百分比展示；"
        f"条长按 **合计工时** 降序。"
        f"工时由 Linear **estimate** 按刻度换算：**{pt_h}**（与 §1 迭代进度看板一致；"
        "非 1/2/3/4/5 或未填估点不计入工时列，负载为 **—**）。"
        f"**统计范围**（与 **snapshot_member** 一致）：报告周 **{iso_week}**，"
        f"{_MEMBER_WORKLOAD_SCOPE_NOTE}。"
        "负载条满格 = **100%**（40h），可超过 100%。"
    )

    total_open = sum(r["open"] for r in rows)
    total_hours_open = sum(r["hours_open"] for r in rows)
    total_hours = sum(r["hours_total"] for r in rows)

    lines.append(
        f"\n- **团队概览**：共 **{len(rows)}** 人参与；未完成任务 **{total_open}** 条"
        + (f"；未完成工时（估）合计 **{_format_hours(total_hours_open)}**" if total_hours_open else "")
        + (f"；当周可换算工时合计 **{_format_hours(total_hours)}**" if total_hours else "")
    )
    hot = [
        r["owner"] for r in rows
        if r["owner"] != "未分配"
        and r["hours_filled"] > 0
        and _member_load_percent(r["hours_total"]) >= 100.0
    ]
    if hot:
        lines.append(
            f"- **负载偏高**：{'、'.join(hot)}（合计工时 ÷ 40h **≥ 100%**）",
        )

    lines.append(
        "\n| 成员 | 任务 | 合计工时(估) | 已完成(h) | 未完成(h) | 完成 | 进行中 | 待开始 | Backlog | 负载 |",
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for r in rows:
        hot_mark = (
            " 🔥"
            if r["hours_filled"] > 0 and _member_load_percent(r["hours_total"]) >= 100.0
            else ""
        )
        total_h = _format_hours(r["hours_total"]) if r["hours_filled"] else "—"
        done_h = _format_hours(r["hours_done"]) if r["hours_done"] > 0 else "—"
        open_h = _format_hours(r["hours_open"]) if r["hours_open"] > 0 else "—"
        load_cell = _format_member_load_cell(r["hours_total"], r["hours_filled"])
        lines.append(
            f"| {r['owner']}{hot_mark} | {r['total']} | {total_h} | {done_h} | {open_h} | "
            f"{r['done']} | {r['in_progress']} | {r['todo']} | {r['backlog']} | {load_cell} |",
        )

    unassigned = next((r for r in rows if r["owner"] == "未分配"), None)
    if unassigned and unassigned["total"] > 0:
        lines.append(
            f"\n- **未分配**：**{unassigned['total']}** 条任务仍无负责人，其中未完成 **{unassigned['open']}** 条，需排期前补齐 assignee。"
        )

    return lines


_TEAM_RISK_CRITERIA_LINES = [
    "数据范围：本报告周 **Cycle 内**任务（与 §1–§4 一致），**已取消**不计入。",
    "**受阻**：状态显示名含「阻塞」且不含 unblock（与成员表「风险」列一致）。",
    "**久未更新**：状态类型为进行中，且 ``updatedAt`` 距今 **≥ 3 天**。",
    "**未分配负责人**：进行中任务无 assignee。",
    "**描述过短**：进行中任务描述（strip 后）**< 30 字符**，范围易不清。",
    "**高优堆积**：进行中且优先级为 Urgent/High 的条目 **≥ 5**。",
    "**逾期未完成**：未完成且 ``dueDate``/``targetDate`` **早于**报告日。",
    "**负载偏高**：成员 **合计工时(估) ÷ 40h ≥ 100%**（与 §4 负载公式一致）。",
    "**里程碑偏紧**：项目下一提测/发布节点距报告日 **< 7 天** 且 Cycle 内仍有未完成（``_schedule_urgent_flag``）。",
    "**项目扫描信号**：§1 项目一览「风险」列已标出的 Blocked / 久未更新 / 未分配等（按项目汇总）。",
    "**明细格式**：任务类风险每条明细前缀 **项目** 名；项目级/成员负载类明细已按项目或成员列出。",
]


def _collect_team_risk_findings(
    cycle_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    now: datetime,
    grouped: GroupedIssues,
    proj_stats: list[dict[str, Any]],
    workload_rows: list[dict[str, Any]],
    *,
    stale_days: int = 3,
) -> list[dict[str, Any]]:
    """汇总团队级风险条目，供 §5 渲染；每项含 title / basis / detail_lines。"""
    ref_day = _to_local_date(now)
    in_progress = grouped.in_progress
    open_issues = [
        it for it in cycle_issues
        if _state_bucket_for_issue(it, status_type_map) not in ("done", "canceled")
    ]

    findings: list[dict[str, Any]] = []

    blocked = [it for it in cycle_issues if _is_blocked_status(it.get("status"))]
    if blocked:
        findings.append({
            "title": "任务受阻 (Blocked)",
            "basis": "状态显示名含「阻塞」且非 unblock",
            "detail_lines": [_risk_line_with_owner(it) for it in blocked[:20]],
            "extra": len(blocked) - 20 if len(blocked) > 20 else 0,
        })

    stale: list[dict[str, Any]] = []
    no_owner_ip: list[dict[str, Any]] = []
    no_desc: list[dict[str, Any]] = []
    urgent_open: list[dict[str, Any]] = []
    for it in in_progress:
        upd = _parse_dt(it.get("updatedAt"))
        if upd and (now - upd).days >= stale_days:
            stale.append(it)
        if not _assignee_name(it):
            no_owner_ip.append(it)
        if len((it.get("description") or "").strip()) < 30:
            no_desc.append(it)
        pr = it.get("priority")
        if isinstance(pr, dict) and pr.get("name") in ("Urgent", "High"):
            urgent_open.append(it)

    if stale:
        findings.append({
            "title": f"进行中超过 {stale_days} 天未更新",
            "basis": f"进行中且 updatedAt 距今 ≥ {stale_days} 天",
            "detail_lines": [_risk_line_with_owner(it) for it in stale[:20]],
            "extra": max(0, len(stale) - 20),
        })
    if no_owner_ip:
        findings.append({
            "title": "进行中未分配负责人",
            "basis": "进行中任务 assignee 为空",
            "detail_lines": [_risk_line_with_owner(it) for it in no_owner_ip[:20]],
            "extra": max(0, len(no_owner_ip) - 20),
        })
    if no_desc:
        findings.append({
            "title": "进行中描述过短/缺失",
            "basis": "进行中任务描述 strip 后 < 30 字符",
            "detail_lines": [_risk_line_with_owner(it) for it in no_desc[:15]],
            "extra": max(0, len(no_desc) - 15),
        })
    if len(urgent_open) >= 5:
        findings.append({
            "title": "高优任务堆积",
            "basis": "进行中 Urgent/High 优先级 ≥ 5 项",
            "detail_lines": [_risk_line_with_owner(it) for it in urgent_open[:15]],
            "extra": max(0, len(urgent_open) - 15),
        })

    overdue: list[dict[str, Any]] = []
    for it in open_issues:
        due = _issue_due_date(it)
        if due is not None and due < ref_day:
            overdue.append(it)
    if overdue:
        findings.append({
            "title": "逾期未完成",
            "basis": "未完成且 dueDate/targetDate 早于报告日",
            "detail_lines": [_risk_line_with_owner(it) for it in overdue[:20]],
            "extra": max(0, len(overdue) - 20),
        })

    unassigned_open = [
        it for it in open_issues if not _assignee_name(it)
    ]
    if unassigned_open:
        findings.append({
            "title": "未完成任务无负责人",
            "basis": "未完成（含待开始/Backlog/进行中）且 assignee 为空",
            "detail_lines": [_risk_line_with_owner(it) for it in unassigned_open[:15]],
            "extra": max(0, len(unassigned_open) - 15),
        })

    hot = [
        r for r in workload_rows
        if r["owner"] != "未分配"
        and r["hours_filled"] > 0
        and _member_load_percent(r["hours_total"]) >= 100.0
    ]
    if hot:
        hot.sort(key=lambda r: -r["hours_total"])
        findings.append({
            "title": "成员负载偏高",
            "basis": f"合计工时(估) ÷ {_MEMBER_WEEKLY_CAPACITY_HOURS:.0f}h ≥ 100%（见 §4）",
            "detail_lines": [
                f"  - **{r['owner']}**：{_format_hours(r['hours_total'])}"
                f"（负载 **{_member_load_percent(r['hours_total']):.0f}%**）"
                for r in hot[:8]
            ],
            "extra": 0,
        })

    urgent_projects: list[str] = []
    for s in proj_stats:
        urgent, note = _schedule_urgent_flag(ref_day, s)
        if urgent:
            note_plain = re.sub(r"\*\*([^*]+)\*\*", r"\1", note) if note else ""
            urgent_projects.append(
                f"  - **{s['name']}**：{note_plain or '下一节点时间偏紧且仍有未完成'}",
            )
    if urgent_projects:
        findings.append({
            "title": "项目里程碑时间偏紧",
            "basis": (
                f"下一提测/发布距报告日 < {_MILESTONE_TIME_COMFORT_DAYS} 天"
                "且 Cycle 内仍有未完成"
            ),
            "detail_lines": urgent_projects,
            "extra": 0,
        })

    project_scan: list[str] = []
    for s in proj_stats:
        if not s.get("risk_short"):
            continue
        project_scan.append(
            f"  - **{s['name']}**：{s['risk_short']}",
        )
    if project_scan:
        findings.append({
            "title": "项目一览已标记风险",
            "basis": "§1 按全 Cycle 扫描：Blocked / 久未更新 / 未分配 / 描述过短等",
            "detail_lines": project_scan,
            "extra": 0,
        })

    startup_projects: list[str] = []
    for s in proj_stats:
        if s.get("status_label") != "启动中":
            continue
        pm = s.get("project_meta")  # may not exist in s
        startup_projects.append(
            f"  - **{s['name']}**：项目阶段为启动中（项目启动里程碑下仍有未完成）",
        )
    # status_label 启动中 already implies startup milestone open - use name only
    if startup_projects:
        findings.append({
            "title": "项目处于启动中",
            "basis": "存在「项目启动」里程碑且其下仍有未完成任务（§1 项目阶段规则）",
            "detail_lines": startup_projects,
            "extra": 0,
        })

    return findings


def _render_team_risk_lines(
    cycle_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    now: datetime,
    grouped: GroupedIssues,
    proj_stats: list[dict[str, Any]],
    workload_rows: list[dict[str, Any]],
) -> list[str]:
    """§5 团队风险：成员负载之后，附判断依据与明细。"""
    lines: list[str] = []
    lines.append("\n#### 5. 团队风险")
    lines.append("\n> **判断依据**")
    for crit in _TEAM_RISK_CRITERIA_LINES:
        lines.append(f"> - {crit}")

    findings = _collect_team_risk_findings(
        cycle_issues,
        status_type_map,
        now,
        grouped,
        proj_stats,
        workload_rows,
    )
    if not findings:
        lines.append("\n- ✅ **结论**：未发现需团队集中处理的显性风险信号（以上规则均未触发）。")
        return lines

    lines.append(f"\n- **结论**：共识别 **{len(findings)}** 类风险信号，需关注：")
    for i, f in enumerate(findings, start=1):
        lines.append(f"\n**{i}. {f['title']}**")
        lines.append(f"- 判断依据：{f['basis']}")
        extra = int(f.get("extra") or 0)
        n_show = len(f.get("detail_lines") or [])
        total_hint = f"（展示 {n_show} 条" + (f"，另有 {extra} 条未列出" if extra else "") + "）"
        lines.append(f"- 明细{total_hint}：")
        for dl in f.get("detail_lines") or []:
            lines.append(dl if dl.startswith("  -") else f"  - {dl}")
        if extra > 0 and not any("另有" in dl for dl in f.get("detail_lines") or []):
            lines.append(f"  - _… 另有 {extra} 条未列出_")

    return lines


def _report_project_detail_anchor(pname: str) -> str:
    """项目详情小节锚点 id（ASCII，避免各渲染器对中文 fragment 差异）。"""
    key = (pname or "").strip().encode("utf-8")
    return "proj-detail-" + hashlib.sha256(key).hexdigest()[:16]


def _active_report_project_names(
    active_linear_projects: list[dict[str, Any]] | None,
) -> set[str]:
    """周报「本迭代涉及的项目」清单的项目名集合。"""
    if not active_linear_projects:
        return set()
    return {
        str(p.get("name") or "").strip()
        for p in active_linear_projects
        if str(p.get("name") or "").strip()
    }


def _excluded_report_project_names(
    all_linear_projects: list[dict[str, Any]],
    *,
    ref: date,
    report_week_start: date,
) -> set[str]:
    """未纳入周报清单的 Linear 项目名（状态非 Planned / In Progress）。"""
    excluded: set[str] = set()
    for p in all_linear_projects:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()
        if not name:
            continue
        if _linear_project_scope_reason(p, ref=ref, report_week_start=report_week_start) is not None:
            excluded.add(name)
    return excluded


def _excluded_report_project_names_for_product_pending(
    all_linear_projects: list[dict[str, Any]],
    *,
    ref: date,
    report_week_start: date,
) -> set[str]:
    """product_created_pending 用：排除 Completed / Canceled 等项目，保留 Backlog。"""
    _ = report_week_start
    excluded: set[str] = set()
    for p in all_linear_projects:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()
        if not name:
            continue
        if _project_linear_status_in_product_pending_scope(p):
            continue
        excluded.add(name)
    return excluded


def _filter_issues_excluding_projects(
    issues: list[dict[str, Any]],
    excluded_project_names: set[str],
) -> list[dict[str, Any]]:
    """从 Cycle / 进展列表中剔除已结束等未纳入清单的项目任务。"""
    if not excluded_project_names:
        return issues
    return [
        it for it in issues
        if _issue_project_name(it) not in excluded_project_names
    ]


def _json_date(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _json_report_meta(
    *,
    iso_week: str,
    now: datetime,
    member_group: str,
    cycle_notes: list[str] | None = None,
    report_mode: str = "weekly",
    cutoff_date: str | None = None,
    change_window: dict[str, str] | None = None,
) -> dict[str, Any]:
    start, end = _week_date_range(iso_week)
    meta: dict[str, Any] = {
        "iso_week": iso_week,
        "week_start": start,
        "week_end": end,
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "member_group": member_group,
        "cycle_notes": cycle_notes or [],
        "report_mode": report_mode,
    }
    if cutoff_date:
        meta["cutoff_date"] = cutoff_date
    if change_window:
        meta["change_window"] = change_window
    if report_mode == "in_progress_snapshot":
        meta["data_scope"] = {
            "projects": (
                "Linear 项目阶段为进行中（开发中/联调/设计/测试/待发布/启动中等，"
                "不含已上线、已结束、已取消）"
            ),
            "tasks": (
                "当前 Cycle 内、所属上述项目、且在 change_window（昨日 00:00–23:59）"
                "内有 createdAt/updatedAt/completedAt 活动的 issue；"
                "任务字段为 Linear 当前值（非历史快照）"
            ),
            "cycle": iso_week,
        }
    return meta


def _build_proj_stats_list(
    cycle_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    now: datetime,
    active_linear_projects: list[dict[str, Any]],
    project_meta_by_name: dict[str, dict[str, Any]],
    project_issues_by_name: dict[str, list[dict[str, Any]]],
    rd_member_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    active_names = _active_report_project_names(active_linear_projects)
    by_project: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in cycle_issues:
        pname = _issue_project_name(it)
        if pname in active_names:
            by_project[pname].append(it)
    rd_names = rd_member_names if rd_member_names is not None else _rd_member_names()
    qa_names = _test_member_names()
    proj_stats = [
        _summarize_project_cycle_stats(
            str(p.get("name") or "").strip(),
            by_project.get(str(p.get("name") or "").strip(), []),
            status_type_map,
            now,
            project_meta=p,
            project_issues=project_issues_by_name.get(str(p.get("name") or "").strip(), []),
            rd_names=rd_names,
            qa_names=qa_names,
        )
        for p in active_linear_projects
        if str(p.get("name") or "").strip()
    ]
    proj_stats.sort(key=_project_overview_sort_key)
    return proj_stats


def _serialize_issue_task_row(
    it: dict[str, Any],
    status_type_map: dict[str, str],
    now: datetime,
) -> dict[str, Any]:
    ref_day = _to_local_date(now)
    pts = _issue_estimate_points(it)
    hrs = _issue_estimate_hours(it)
    return {
        "task_id": _issue_key(it),
        "project": _issue_project_name(it),
        "assignee": _assignee_name(it) or "未分配",
        "status": str(it.get("status") or ""),
        "status_bucket": _state_bucket_zh(it, status_type_map),
        "title": _issue_title_without_identifier(it),
        "estimate_points": pts,
        "estimate_hours": hrs,
        "due_date": _json_date(_issue_due_date(it)),
        "days_remaining": _issue_days_remaining_cell(it, status_type_map, ref_day),
        "risk": _issue_risk_cell(it, status_type_map, now),
    }


def _proj_stats_to_overview_json(s: dict[str, Any]) -> dict[str, Any]:
    status_label = s["status_label"]
    if (
        status_label == "开发中"
        and s.get("n_open_full_cycle", s["n_open"]) == 0
        and s.get("n_active_full_cycle", s["n_active"]) > 0
    ):
        status_label = f"{status_label}·本Cycle已清"
    return {
        "name": s["name"],
        "detail_anchor": s.get("detail_anchor") or _report_project_detail_anchor(s["name"]),
        "cycle_task_count": s["total"],
        "next_milestone": s.get("next_ms_name", "—"),
        "days_to_milestone": re.sub(
            r"\*\*([^*]+)\*\*",
            r"\1",
            str(s.get("next_ms_days", "—")),
        ),
        "current_handlers": s.get("next_ms_owners", "—"),
        "progress_kind": s.get("progress_kind"),
        "progress_label": s.get("progress_label_zh", "本周期"),
        "progress_done_pct": round(s["done_pct"], 1),
        "progress_counts": {
            "done": s["n_done"],
            "in_progress": s["n_ip"],
            "todo": s["n_todo"],
            "backlog": s["n_bl"],
            "other": s.get("n_other", 0),
        },
        "status_label": status_label,
        "bugs_cycle": s.get("n_bugs_cycle", 0) if s["status_label"] == "测试中" else 0,
        "bugs_open": s.get("n_bugs_open", 0) if s["status_label"] == "测试中" else 0,
        "risk_short": s.get("risk_short") or "",
        "risk_signals": list(s.get("risk_parts") or []),
        "test_date": _json_date(s.get("test_date")),
        "release_date": _json_date(s.get("release_date")),
    }


def _proj_stats_to_detail_json(
    s: dict[str, Any],
    *,
    lead: str,
    ref_day: date,
    division_rows: list[tuple[str, str, str]],
) -> dict[str, Any]:
    urgent, urgent_note = _schedule_urgent_flag(ref_day, s)
    note_plain = re.sub(r"\*\*([^*]+)\*\*", r"\1", urgent_note) if urgent_note else ""
    owners = sorted({(_assignee_name(it) or "未分配") for it in s["items"]})
    return {
        "name": s["name"],
        "detail_anchor": s.get("detail_anchor") or _report_project_detail_anchor(s["name"]),
        "leader": lead or "—",
        "milestone": {
            "test_date": _json_date(s.get("test_date")),
            "release_date": _json_date(s.get("release_date")),
            "status_label": s["status_label"],
            "schedule_urgent": urgent,
            "schedule_note": note_plain,
        },
        "progress": {
            "label": s.get("progress_label_zh", "本周期"),
            "done_pct": round(s["done_pct"], 1),
            "done": s["n_done"],
            "in_progress": s["n_ip"],
            "todo": s["n_todo"],
            "backlog": s["n_bl"],
            "other": s.get("n_other", 0),
            "canceled": s.get("n_canceled", 0),
            "bugs_cycle": s.get("n_bugs_cycle", 0),
            "bugs_open": s.get("n_bugs_open", 0),
        },
        "participants": owners,
        "risk_signals": list(s.get("risk_parts") or []),
        "blocked_count": len(s.get("proj_blocked") or []),
        "division": [
            {"role": role, "owner": owner, "task": task}
            for role, owner, task in division_rows
        ],
    }


def _workload_row_to_json(r: dict[str, Any]) -> dict[str, Any]:
    load_pct: float | None = None
    if r.get("hours_filled", 0) > 0 and r.get("hours_total", 0) > 0:
        load_pct = round(_member_load_percent(r["hours_total"]), 1)
    return {
        "owner": r["owner"],
        "task_count": r["total"],
        "hours_total": r.get("hours_total", 0.0),
        "hours_done": r.get("hours_done", 0.0),
        "hours_open": r.get("hours_open", 0.0),
        "hours_filled_tasks": r.get("hours_filled", 0),
        "load_percent": load_pct,
        "load_high": bool(load_pct is not None and load_pct >= 100.0),
        "done": r["done"],
        "in_progress": r["in_progress"],
        "todo": r["todo"],
        "backlog": r["backlog"],
        "open_count": r["open"],
    }


def build_team_weekly_json_bundle(
    *,
    iso_week: str,
    now: datetime,
    member_group: str,
    cycle_issues: list[dict[str, Any]],
    workload_cycle_issues: list[dict[str, Any]] | None = None,
    status_type_map: dict[str, str],
    grouped: GroupedIssues,
    project_meta_by_name: dict[str, dict[str, Any]],
    active_linear_projects: list[dict[str, Any]],
    project_issues_by_name: dict[str, list[dict[str, Any]]],
    rd_member_names: set[str] | None,
    cycle_notes: list[str] | None,
    report_mode: str = "weekly",
    cutoff_date: str | None = None,
    change_window: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """四类 JSON：项目一览 / 按项目 / 按成员 / 成员负载与团队风险。"""
    meta = _json_report_meta(
        iso_week=iso_week,
        now=now,
        member_group=member_group,
        cycle_notes=cycle_notes,
        report_mode=report_mode,
        cutoff_date=cutoff_date,
        change_window=change_window,
    )
    ref_day = _to_local_date(now)
    proj_stats = _build_proj_stats_list(
        cycle_issues,
        status_type_map,
        now,
        active_linear_projects,
        project_meta_by_name,
        project_issues_by_name,
        rd_member_names=rd_member_names,
    )
    meta_by_name = project_meta_by_name or {}

    projects_overview = {
        "meta": meta,
        "estimate_point_to_hours": {str(k): v for k, v in _ESTIMATE_POINT_TO_HOURS.items()},
        "projects": [_proj_stats_to_overview_json(s) for s in proj_stats],
    }

    projects_detail: list[dict[str, Any]] = []
    for s in proj_stats:
        pname = s["name"]
        pm = meta_by_name.get(pname, {}) if isinstance(meta_by_name.get(pname), dict) else {}
        projects_detail.append(
            _proj_stats_to_detail_json(
                s,
                lead=_project_lead_name(pm),
                ref_day=ref_day,
                division_rows=_project_division_table_rows(s["items"], status_type_map),
            ),
        )

    by_owner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in cycle_issues:
        if _state_bucket_for_issue(it, status_type_map) == "canceled":
            continue
        by_owner[_assignee_name(it) or "未分配"].append(it)

    members_list: list[dict[str, Any]] = []
    for owner in sorted(by_owner.keys(), key=lambda x: (x == "未分配", x)):
        items = sorted(
            by_owner[owner],
            key=lambda it: _member_issue_table_sort_key(it, status_type_map),
        )
        done_o = _filter_issues_by_assignee(grouped.done, owner)
        inprog_o = _filter_issues_by_assignee(grouped.in_progress, owner)
        plan_o = _filter_issues_by_assignee(
            grouped.in_progress + grouped.todo + grouped.backlog,
            owner,
        )
        if report_mode == "in_progress_snapshot":
            members_list.append({
                "owner": owner,
                "yesterday_summary": _owner_yesterday_summary_one_sentence(done_o, inprog_o),
                "carry_forward_plan": _owner_carry_forward_plan_one_sentence(
                    plan_o, status_type_map,
                ),
                "tasks": [_serialize_issue_task_row(it, status_type_map, now) for it in items],
            })
        else:
            members_list.append({
                "owner": owner,
                "last_week_summary": _owner_last_week_summary_one_sentence(done_o, inprog_o),
                "next_week_plan": _owner_next_week_plan_one_sentence(plan_o, status_type_map),
                "tasks": [_serialize_issue_task_row(it, status_type_map, now) for it in items],
            })

    wl_issues = workload_cycle_issues if workload_cycle_issues is not None else cycle_issues
    workload_rows = _member_aligned_workload_rows(
        _member_workload_rows(wl_issues, status_type_map, iso_week),
    )
    findings = _collect_team_risk_findings(
        cycle_issues,
        status_type_map,
        now,
        grouped,
        proj_stats,
        workload_rows,
    )
    total_open = sum(r["open"] for r in workload_rows)
    total_hours = sum(r["hours_total"] for r in workload_rows)
    workload_risks = {
        "meta": meta,
        "workload": {
            "weekly_capacity_hours": _MEMBER_WEEKLY_CAPACITY_HOURS,
            "load_formula": "合计工时(估) / 40h * 100%",
            "scope": _MEMBER_WORKLOAD_SCOPE_NOTE,
            "aligned_with": "snapshot_member",
            "estimate_point_to_hours": {str(k): v for k, v in _ESTIMATE_POINT_TO_HOURS.items()},
            "team_summary": {
                "member_count": len(workload_rows),
                "open_task_count": total_open,
                "total_estimated_hours": round(total_hours, 1),
            },
            "members": [_workload_row_to_json(r) for r in workload_rows],
        },
        "team_risks": {
            "criteria": list(_TEAM_RISK_CRITERIA_LINES),
            "finding_count": len(findings),
            "has_findings": len(findings) > 0,
            "findings": [
                {
                    "title": f["title"],
                    "basis": f["basis"],
                    "details": list(f.get("detail_lines") or []),
                    "extra_count": int(f.get("extra") or 0),
                }
                for f in findings
            ],
        },
    }

    return {
        "projects_overview": projects_overview,
        "projects_detail": {"meta": meta, "projects": projects_detail},
        "members": {"meta": meta, "members": members_list},
        "workload_risks": workload_risks,
    }


def _json_export_generated_date(now: datetime | None = None) -> str:
    """JSON 文件名日期段：脚本运行日（本地），格式 YYYY-MM-DD。"""
    ref = now or datetime.now()
    if ref.tzinfo is not None:
        return ref.astimezone().date().isoformat()
    return ref.date().isoformat()


def _default_json_filename_prefix(
    *,
    snapshot_mode: bool,
    generated_date: str,
) -> str:
    if snapshot_mode:
        return f"{generated_date}-in-progress"
    return generated_date


def write_team_weekly_json_exports(
    bundle: dict[str, dict[str, Any]],
    out_dir: Path,
    *,
    filename_prefix: str,
) -> list[Path]:
    """写入 4 个 JSON 文件，返回路径列表。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = (
        ("projects-overview", bundle["projects_overview"]),
        ("projects-detail", bundle["projects_detail"]),
        ("members", bundle["members"]),
        ("workload-risks", bundle["workload_risks"]),
    )
    paths: list[Path] = []
    prefix = f"{filename_prefix}-"
    for suffix, payload in specs:
        path = out_dir / f"{prefix}{suffix}.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        paths.append(path)
    return paths


def _render_project_member_cycle_summary_lines(
    cycle_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    grouped: GroupedIssues,
    now: datetime,
    *,
    iso_week: str,
    member_cycle_issues: list[dict[str, Any]],
    workload_cycle_issues: list[dict[str, Any]] | None = None,
    project_meta_by_name: dict[str, dict[str, Any]] | None = None,
    active_linear_projects: list[dict[str, Any]] | None = None,
    excluded_project_notes: list[str] | None = None,
    project_issues_by_name: dict[str, list[dict[str, Any]]] | None = None,
    rd_member_names: set[str] | None = None,
) -> list[str]:
    """按「项目」与「成员」对当前 Cycle 全量 issue 做结构化汇总（与上周/计划小节互补）。"""
    if not cycle_issues and not active_linear_projects:
        return []

    lines: list[str] = []
    lines.append("\n### 📁 当前迭代 · 项目与成员（全 Cycle）")

    meta_by_name = project_meta_by_name or {}
    proj_stats = _build_proj_stats_list(
        cycle_issues,
        status_type_map,
        now,
        active_linear_projects or [],
        meta_by_name,
        project_issues_by_name or {},
        rd_member_names=rd_member_names,
    )

    lines.extend(_render_project_overview_lines(proj_stats))

    # --- 2. 按项目：进度、参与人、风险、分工（HTML 表格）---
    lines.append("\n#### 2. 按项目：进度 · 参与人 · 风险 · 分工")
    ref_day = _to_local_date(now)
    for s in proj_stats:
        pname = s["name"]
        items = s["items"]
        anchor = str(s.get("detail_anchor") or _report_project_detail_anchor(pname))
        lines.append(f'\n<a id="{anchor}"></a>\n##### 📦 {pname}')
        pm = meta_by_name.get(pname, {}) if meta_by_name else {}
        if not isinstance(pm, dict):
            pm = {}
        lead = _project_lead_name(pm)
        lines.append(
            "\n" + _render_project_detail_meta_kv_table(s, lead=lead, ref_day=ref_day),
        )
        div_rows = _project_division_table_rows(items, status_type_map)
        lines.append("\n**分工**")
        if div_rows:
            lines.append("\n" + _html_table_role_owner_tasks(div_rows))
        else:
            lines.append("\n_（本 Cycle 无任务）_")
    lines.append(
        "\n> **口径**：每项目先以表格列出 Leader / 里程碑 / 进度 / 参与人 / 风险；"
        "**分工**表按 **后端 / 前端 / 测试 / 其他** 分块，**角色**、**负责人**列合并单元格；"
        "任务摘要不含任务号，超出条数按父单/标题主题合并。"
    )

    member_code_lookup = _member_week_code_stats_lookup(iso_week)

    lines.extend(
        _render_member_cycle_issues_table(
            member_cycle_issues,
            status_type_map,
            now,
            iso_week,
            grouped,
            member_code_lookup=member_code_lookup,
        ),
    )
    wl_issues = workload_cycle_issues if workload_cycle_issues is not None else cycle_issues
    workload_rows = _member_aligned_workload_rows(
        _member_workload_rows(wl_issues, status_type_map, iso_week),
    )
    lines.extend(
        _render_member_workload_lines(
            wl_issues, status_type_map, iso_week, workload_rows=workload_rows,
        ),
    )
    lines.extend(
        _render_team_risk_lines(
            cycle_issues,
            status_type_map,
            now,
            grouped,
            proj_stats,
            workload_rows,
        ),
    )

    return lines


def count_uncycled_team_issues(
    team_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    *,
    include_completed: bool = False,
) -> tuple[int, int]:
    """本团队内**可判定**为未划入任何 Cycle 的 issue 条数。

    返回 ``(count, skipped_unknown)``：``skipped_unknown`` 为因缺少 ``cycle``/``cycleId``
    而无法判断、**未计入** count 的条数。

    默认 **不含已取消**；默认 **不含已完成**（``completed``），与 Linear「无 Cycle」视图中常隐藏已完成一致。
    若需与旧口径一致（含已完成），传 ``include_completed=True`` 或使用 CLI 标志。
    """
    n = 0
    skipped = 0
    for it in team_issues:
        st_name = (it.get("status") or "").strip()
        st_type = (status_type_map.get(st_name) or "").lower()
        if st_type == "canceled":
            continue
        if not include_completed and st_type == "completed":
            continue
        mem = _issue_cycle_membership(it)
        if mem is None:
            skipped += 1
            continue
        if mem is True:
            continue
        n += 1
    return n, skipped


def _uncycled_report_lines(
    u_tot: int,
    skipped_unknown: int,
    *,
    include_completed: bool,
) -> list[str]:
    """Markdown lines for「未划入迭代」计数说明。"""
    tail = "；不含已完成" if not include_completed else ""
    lines = [
        f"- 未划入任何迭代：**{u_tot}**（口径：全 Team，不含已取消{tail}；"
        "仅统计接口中可明确判定「未关联 Cycle」的条目）"
    ]
    if skipped_unknown > 0:
        lines.append(
            f"  - _另有 **{skipped_unknown}** 条列表未返回 cycle/cycleId，无法判定是否已划入某迭代，未计入上数_"
        )
    return lines


def _mermaid_cycle_progress_inner_lines(pct: float, ratio_pct: float, time_pct: float) -> list[str]:
    """供本地 ```mermaid``` 渲染的 Mermaid 源码（不含围栏）。"""
    return [
        "%%{init: {'theme': 'base', 'themeVariables': {",
        "  'cScale0': '#B8860B',",
        "  'cScale1': '#F58518',",
        "  'cScale2': '#54A24B'",
        "}}}%%",
        "xychart-beta",
        '    title "Cycle Progress (%)"',
        (
            f'    x-axis ["完成率 {pct:.1f}%", "估点完成率 {ratio_pct:.1f}%", '
            f'"时间进度 {time_pct:.1f}%"]'
        ),
        '    y-axis "Percent" 0 --> 100',
        f"    bar [{pct:.1f}, {ratio_pct:.1f}, {time_pct:.1f}]",
    ]


def _mermaid_status_pie_inner_lines(status_items: list[tuple[str, float]]) -> list[str]:
    lines = [
        '%%{init: {"theme":"base","themeVariables":{"pie1":"#4C78A8","pie2":"#54A24B",'
        '"pie3":"#EECA3B","pie4":"#E45756"},"pie":{"showLegend":false}}}%%',
        "pie",
        '    title 当前 Cycle 状态分布',
    ]
    for name, pctv in status_items:
        lines.append(f'    "{name} {pctv:.1f}%" : {pctv:.1f}')
    return lines


def _mermaid_label_pie_inner_lines(label_items: list[tuple[str, float]]) -> list[str]:
    lines = [
        '%%{init: {"theme":"base","themeVariables":{"pie1":"#4C78A8","pie2":"#54A24B","pie3":"#EECA3B"},'
        '"pie":{"showLegend":false}}}%%',
        "pie",
        '    title demand / task / bug',
    ]
    for name, pctv in label_items:
        lines.append(f'    "{name} {pctv:.1f}%" : {pctv:.1f}')
    return lines


def _pct_share_bar(pct: float, width: int | None = None) -> str:
    """将 0–100% 映射为固定宽度条：整段长度 = 100%，与占比列数字一致（勿用数量/ max 计数归一化）。"""
    w = width if width is not None else DISTRIBUTION_PCT_BAR_WIDTH
    if w <= 0:
        return ""
    p = max(0.0, min(100.0, float(pct)))
    if p >= 100.0 - 1e-9:
        filled = w
    else:
        filled = int(math.floor(p / 100.0 * w + 1e-9))
    filled = max(0, min(w, filled))
    return "█" * filled + "░" * (w - filled)


def _stacked_strip_chars(counts: list[int], glyphs: list[str], width: int = 28) -> str:
    """按 count 比例把 width 个字符切成多段，每段用对应 glyph（单字符）重复填充。"""
    if len(counts) != len(glyphs) or not counts:
        return "░" * width
    total = sum(counts)
    if total <= 0:
        return "░" * width
    n = len(counts)
    exact = [counts[i] * width / total for i in range(n)]
    segs = [int(x) for x in exact]
    while sum(segs) < width:
        i = max(range(n), key=lambda i: exact[i] - segs[i])
        segs[i] += 1
    while sum(segs) > width:
        i = max(range(n), key=lambda i: (segs[i], counts[i]))
        if segs[i] <= 0:
            break
        segs[i] -= 1
    return "".join(glyphs[i] * segs[i] for i in range(n))


def _cycle_pace_snapshot(
    cycle: dict[str, Any],
    cycle_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    now: datetime,
) -> tuple[int, int, float | None, float | None, str, str]:
    """返回节奏快照：done_pts, total_pts, 点完成率, 时间进度, 节奏标签, 文案提示。"""
    done_pts, total_pts, ratio_pts = sum_estimate_done_and_total_pts(cycle_issues, status_type_map)
    time_frac = cycle_elapsed_fraction(cycle, now)
    if ratio_pts is None:
        return done_pts, total_pts, ratio_pts, time_frac, "—", "当前 Cycle 内估点合计为 0，无法计算节奏"
    if time_frac is None:
        if ratio_pts < 1.0 / 3:
            return done_pts, total_pts, ratio_pts, time_frac, "缓慢", "点完成率偏低（未结合日历）"
        if ratio_pts > 2.0 / 3:
            return done_pts, total_pts, ratio_pts, time_frac, "赶超", "点完成率偏高（未结合日历）"
        return done_pts, total_pts, ratio_pts, time_frac, "正常", "点完成率居中（未结合日历）"
    delta = ratio_pts - time_frac
    if delta < -_CYCLE_PACE_MARGIN:
        return done_pts, total_pts, ratio_pts, time_frac, "缓慢", f"点完成率低于时间进度约 {abs(delta) * 100:.0f} 个百分点"
    if delta > _CYCLE_PACE_MARGIN:
        return done_pts, total_pts, ratio_pts, time_frac, "赶超", f"点完成率高于时间进度约 {delta * 100:.0f} 个百分点"
    return done_pts, total_pts, ratio_pts, time_frac, "正常", f"点完成率与时间进度接近（容差 ±{int(_CYCLE_PACE_MARGIN * 100)}%）"


def _render_cycle_dashboard_lines(
    *,
    total: int,
    done: int,
    inprog: int,
    todo: int,
    backlog: int,
    n_demand: int,
    n_task: int,
    n_bug: int,
    cycle: dict[str, Any],
    cycle_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    now: datetime,
    uncycled_total: int,
    uncycled_skipped_unknown: int,
    uncycled_include_completed: bool,
    chart_style: str = "text",
) -> list[str]:
    """可视化增强版「迭代进度与风险」内容（KPI + xychart）。"""
    pct = (done / total * 100.0) if total else 0.0
    done_pts, total_pts, ratio_pts, time_frac, pace, pace_hint = _cycle_pace_snapshot(
        cycle, cycle_issues, status_type_map, now
    )
    pace_icon = {"缓慢": "🔴", "正常": "🟡", "赶超": "🟢"}.get(pace, "⚪")
    ratio_pct = (100.0 * ratio_pts) if ratio_pts is not None else 0.0
    time_pct = (100.0 * time_frac) if time_frac is not None else 0.0
    total_hours = 0.0
    done_hours = 0.0
    for it in cycle_issues:
        h = _issue_estimate_hours(it)
        if h is None:
            continue
        total_hours += h
        st_name = (it.get("status") or "").strip()
        st_type = (status_type_map.get(st_name) or "").lower()
        if st_type == "completed":
            done_hours += h

    lines: list[str] = []
    lines.append("\n### 📊 迭代进度与风险（可视化）")
    lines.append("\n#### 核心指标")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("| --- | --- |")
    lines.append(f"| 总任务数 | **{total}**（完成率 **{pct:.1f}%**） |")
    if total_hours > 0:
        lines.append(
            f"| 总工时（估算） | **{int(total_hours)}h**（工时完成率 **{(done_hours / total_hours) * 100.0:.1f}%**） |"
        )
    else:
        lines.append("| 总工时（估算） | **0h**（工时完成率 **—**） |")
    tail = "；不含已完成" if not uncycled_include_completed else ""
    lines.append(
        f"| 未纳入迭代（Team） | **{uncycled_total}**（不含已取消{tail}） |"
    )
    lines.append(f"| 节奏 | **{pace_icon} {pace}**（{pace_hint}） |")
    if uncycled_skipped_unknown > 0:
        lines.append(
            f"| 未纳入判定说明 | 接口缺少 cycle/cycleId 的 **{uncycled_skipped_unknown}** 条未计入 |"
        )

    def _mini_bar(value: float, max_value: float, width: int = DISTRIBUTION_PCT_BAR_WIDTH) -> str:
        if max_value <= 0:
            return "░" * width
        filled = int(round((value / max_value) * width))
        filled = max(0, min(width, filled))
        return ("█" * filled) + ("░" * (width - filled))

    def _sparkline(values: list[float]) -> str:
        ticks = "▁▂▃▄▅▆▇█"
        if not values:
            return ""
        vmin = min(values)
        vmax = max(values)
        if vmax <= vmin:
            return "▄" * len(values)
        chars: list[str] = []
        for v in values:
            idx = int(round((v - vmin) / (vmax - vmin) * (len(ticks) - 1)))
            idx = max(0, min(len(ticks) - 1, idx))
            chars.append(ticks[idx])
        return "".join(chars)

    comp_hist = cycle.get("completedIssueCountHistory")
    scope_hist = cycle.get("issueCountHistory")
    if isinstance(comp_hist, list) and isinstance(scope_hist, list):
        points = min(len(comp_hist), len(scope_hist))
        completion_pct_hist: list[float] = []
        scope_hist_values: list[float] = []
        for i in range(points):
            c = comp_hist[i] if isinstance(comp_hist[i], (int, float)) else 0
            s = scope_hist[i] if isinstance(scope_hist[i], (int, float)) else 0
            completion_pct_hist.append((float(c) / float(s) * 100.0) if s > 0 else 0.0)
            scope_hist_values.append(float(s))
        # 历史趋势行按产品要求移除，仅保留核心快照指标

    done_pct = ((done / total) * 100.0) if total else 0.0
    inprog_pct = ((inprog / total) * 100.0) if total else 0.0
    todo_pct = ((todo / total) * 100.0) if total else 0.0
    backlog_pct = ((backlog / total) * 100.0) if total else 0.0
    status_items: list[tuple[str, float]] = [
        ("Done", done_pct),
        ("In Progress", inprog_pct),
        ("Todo", todo_pct),
        ("Backlog/Triage", backlog_pct),
    ]
    # Mermaid pie 在部分渲染器会按值排序后再映射色板，这里按值降序输出并同步图例顺序，保证颜色一致。
    status_items = sorted(status_items, key=lambda kv: kv[1], reverse=True)
    legend_colors = ["🔵", "🟢", "🟡", "🔴"]

    label_total = n_demand + n_task + n_bug
    demand_pct = ((n_demand / label_total) * 100.0) if label_total else 0.0
    task_pct = ((n_task / label_total) * 100.0) if label_total else 0.0
    bug_pct = ((n_bug / label_total) * 100.0) if label_total else 0.0
    label_items: list[tuple[str, float]] = [
        ("demand", demand_pct),
        ("task", task_pct),
        ("bug", bug_pct),
    ]
    label_items = sorted(label_items, key=lambda kv: kv[1], reverse=True)

    progress_inner = _mermaid_cycle_progress_inner_lines(pct, ratio_pct, time_pct)
    status_pie_inner = _mermaid_status_pie_inner_lines(status_items)
    label_pie_inner = _mermaid_label_pie_inner_lines(label_items)

    def _append_text_fallback_charts() -> None:
        lines.append("\n#### 进度对比")
        lines.append("")
        lines.append("| 指标 | 百分比 | 趋势条 |")
        lines.append("| --- | --- | --- |")
        lines.append(f"| 完成率（数量） | **{pct:.1f}%** | `{_mini_bar(pct, 100)}` |")
        lines.append(f"| 估点完成率 | **{ratio_pct:.1f}%** | `{_mini_bar(ratio_pct, 100)}` |")
        if time_frac is not None:
            lines.append(f"| 时间进度 | **{time_pct:.1f}%** | `{_mini_bar(time_pct, 100)}` |")
        else:
            lines.append(f"| 时间进度 | **—** | `{_mini_bar(0, 100)}` |")

        lines.append("\n#### 状态分布")
        lines.append("")
        lines.append("| 状态 | 数量 | 占总量 | 占比条 |")
        lines.append("| --- | ---: | ---: | --- |")
        sp_done = (done / total * 100.0) if total else 0.0
        sp_ip = (inprog / total * 100.0) if total else 0.0
        sp_todo = (todo / total * 100.0) if total else 0.0
        sp_bl = (backlog / total * 100.0) if total else 0.0
        lines.append(
            f"| Done | **{done}** | {sp_done:.1f}% | `{_pct_share_bar(sp_done, DISTRIBUTION_PCT_BAR_WIDTH)}` |"
        )
        lines.append(
            f"| In Progress | **{inprog}** | {sp_ip:.1f}% | `{_pct_share_bar(sp_ip, DISTRIBUTION_PCT_BAR_WIDTH)}` |"
        )
        lines.append(
            f"| Todo | **{todo}** | {sp_todo:.1f}% | `{_pct_share_bar(sp_todo, DISTRIBUTION_PCT_BAR_WIDTH)}` |"
        )
        lines.append(
            f"| Backlog/Triage | **{backlog}** | {sp_bl:.1f}% | `{_pct_share_bar(sp_bl, DISTRIBUTION_PCT_BAR_WIDTH)}` |"
        )

        lines.append("\n#### 工作类型标签分布")
        lines.append("")
        lines.append("| 标签 | 数量 | 占已标总量 | 占比条 |")
        lines.append("| --- | ---: | ---: | --- |")
        lines.append(
            f"| demand | **{n_demand}** | {demand_pct:.1f}% | `{_pct_share_bar(demand_pct, DISTRIBUTION_PCT_BAR_WIDTH)}` |"
        )
        lines.append(
            f"| task | **{n_task}** | {task_pct:.1f}% | `{_pct_share_bar(task_pct, DISTRIBUTION_PCT_BAR_WIDTH)}` |"
        )
        lines.append(
            f"| bug | **{n_bug}** | {bug_pct:.1f}% | `{_pct_share_bar(bug_pct, DISTRIBUTION_PCT_BAR_WIDTH)}` |"
        )

    if chart_style == "mermaid":
        lines.append("\n#### 进度对比（Mermaid）")
        lines.append("\n```mermaid")
        lines.extend(progress_inner)
        lines.append("```")

        lines.append("\n#### 状态分布（Mermaid）")
        lines.append("\n```mermaid")
        lines.extend(status_pie_inner)
        lines.append("```")
        status_legend = "｜".join(f"{legend_colors[i]} {name}" for i, (name, _) in enumerate(status_items))
        lines.append(f"- 图例（与饼图同序）：{status_legend}")

        lines.append("\n#### 工作类型标签分布（Mermaid）")
        lines.append("\n```mermaid")
        lines.extend(label_pie_inner)
        lines.append("```")
        label_legend = "｜".join(f"{legend_colors[i]} {name}" for i, (name, _) in enumerate(label_items))
        lines.append(f"- 图例（与饼图同序）：{label_legend}")
    else:
        # text / dingtalk：表格 + 字符条（上传钉钉时与纯文本一致，不附带 Mermaid 源码块）
        _append_text_fallback_charts()
    return lines


def render_weekly_report_body(
    *,
    iso_week: str,
    grouped: GroupedIssues,
    now: datetime,
    cycle_issues: list[dict[str, Any]],
    member_cycle_issues: list[dict[str, Any]],
    workload_cycle_issues: list[dict[str, Any]] | None = None,
    status_type_map: dict[str, str],
    project_meta_by_name: dict[str, dict[str, Any]] | None = None,
    active_linear_projects: list[dict[str, Any]] | None = None,
    excluded_project_notes: list[str] | None = None,
    project_issues_by_name: dict[str, list[dict[str, Any]]] | None = None,
    rd_member_names: set[str] | None = None,
    cycle_notes: list[str] | None = None,
) -> str:
    """周报正文：项目与成员（全 Cycle），至「团队风险」为止；不按 Linear Team 分块。"""
    week_start, week_end = _week_date_range(iso_week)
    lines: list[str] = []
    lines.append("\n## 当前迭代（workspace）")
    lines.append(f"\n**报告周**：{iso_week}（{week_start} ~ {week_end}）")
    if cycle_notes:
        lines.append(f"**覆盖 Cycle**：{'；'.join(cycle_notes)}")
    elif not cycle_issues:
        lines.append("**覆盖 Cycle**：_上周自然周无匹配 Cycle 或暂无任务_")

    lines.extend(
        _render_project_member_cycle_summary_lines(
            cycle_issues,
            status_type_map,
            grouped,
            now,
            iso_week=iso_week,
            member_cycle_issues=member_cycle_issues,
            workload_cycle_issues=workload_cycle_issues,
            project_meta_by_name=project_meta_by_name,
            active_linear_projects=active_linear_projects,
            excluded_project_notes=excluded_project_notes,
            project_issues_by_name=project_issues_by_name,
            rd_member_names=rd_member_names,
        )
    )
    return "\n".join(lines)

def _report_folder_id() -> str:
    """可通过 ~/.superteam/config 中 DINGTALK_REPORT_FOLDER_ID 覆盖默认目录 nodeId。

    兼容用户误传“文件 nodeId”：会自动回溯到所属目录，并优先定位到祖先中的「T-Rex周报」目录。
    """
    configured = env("DINGTALK_REPORT_FOLDER_ID") or REPORT_FOLDER_ID
    return _normalize_publish_root_folder_id(configured)

def _normalize_publish_root_folder_id(node_id: str) -> str:
    nid = (node_id or "").strip()
    if not nid:
        return REPORT_FOLDER_ID
    try:
        info = _dingtalk_mcp_tools_call("get_document_info", {"nodeId": nid})
    except Exception:
        return nid
    if not isinstance(info, dict):
        return nid

    cur = nid
    node_type = str(info.get("nodeType") or "").lower()
    if node_type == "file":
        parent = info.get("folderId")
        if isinstance(parent, str) and parent.strip():
            cur = parent.strip()

    # 向上回溯，若命中「T-Rex周报」则用它作为发布根目录。
    for _ in range(8):
        try:
            meta = _dingtalk_mcp_tools_call("get_document_info", {"nodeId": cur})
        except Exception:
            break
        if not isinstance(meta, dict):
            break
        name = str(meta.get("name") or "").strip()
        nt = str(meta.get("nodeType") or "").lower()
        if name == "T-Rex周报" and nt == "folder":
            return cur
        parent = meta.get("folderId")
        if not isinstance(parent, str) or not parent.strip():
            break
        cur = parent.strip()
    return cur


def _dingtalk_week_subfolder_label(iso_week: str) -> str:
    """钉钉周目录名：两位年 + W + 两位周序号，如 2026-W15 -> 26W15。"""
    m = re.match(r"^(\d{4})-W(\d{1,2})$", iso_week.strip())
    if not m:
        raise ValueError(f"invalid iso_week for folder label: {iso_week!r}")
    year, week = int(m.group(1)), int(m.group(2))
    return f"{year % 100:02d}W{week:02d}"


def _dingtalk_year_folder_label(iso_week: str) -> str:
    """钉钉年目录名：四位年，如 2026-W15 -> 2026。"""
    m = re.match(r"^(\d{4})-W(\d{1,2})$", iso_week.strip())
    if not m:
        raise ValueError(f"invalid iso_week for year folder label: {iso_week!r}")
    return m.group(1)


def _dingtalk_node_display_name(node: dict) -> str:
    v = node.get("name") or node.get("title") or node.get("nodeName")
    return str(v).strip() if v is not None else ""


def _dingtalk_node_id(node: dict) -> str | None:
    for k in ("nodeId", "id", "dentryUuid", "dentryId"):
        v = node.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _dingtalk_node_is_folder(node: dict) -> bool:
    t = str(node.get("nodeType") or node.get("type") or node.get("contentType") or "").lower()
    if t in ("folder", "directory"):
        return True
    if node.get("isFolder") is True:
        return True
    mt = str(node.get("mimeType") or "")
    return "folder" in mt.lower()


def _dingtalk_unwrap_tool_result(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RuntimeError(f"钉钉 MCP 返回非对象: {raw!r}")
    if raw.get("success") is False:
        raise RuntimeError(str(raw.get("message") or raw.get("error") or raw))
    for key in ("data", "result"):
        inner = raw.get(key)
        if isinstance(inner, dict):
            return inner
    return raw


def _dingtalk_parse_list_nodes_page(raw: Any) -> tuple[list[dict[str, Any]], str | None]:
    inner = _dingtalk_unwrap_tool_result(raw)
    nodes = inner.get("nodes") or inner.get("nodeList") or inner.get("items") or []
    if not isinstance(nodes, list):
        nodes = []
    out: list[dict[str, Any]] = [n for n in nodes if isinstance(n, dict)]
    token = inner.get("nextPageToken") or inner.get("nextToken") or inner.get("next_page_token")
    if isinstance(token, str) and token.strip():
        return out, token.strip()
    return out, None


def _dingtalk_extract_folder_id_from_create(raw: Any) -> str:
    inner = _dingtalk_unwrap_tool_result(raw)
    for d in (inner, raw):
        if not isinstance(d, dict):
            continue
        for k in ("nodeId", "folderId", "id", "dentryUuid"):
            v = d.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    nested = inner.get("folder") or inner.get("node")
    if isinstance(nested, dict):
        nid = _dingtalk_node_id(nested)
        if nid:
            return nid
    raise RuntimeError(f"create_folder 响应中未解析到文件夹 nodeId: {raw!r}")


def _dingtalk_list_all_nodes_under(folder_id: str) -> list[dict[str, Any]]:
    all_nodes: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        args: dict[str, Any] = {"folderId": folder_id, "pageSize": 50}
        if page_token:
            args["pageToken"] = page_token
        raw = _dingtalk_mcp_tools_call("list_nodes", args)
        batch, next_tok = _dingtalk_parse_list_nodes_page(raw)
        all_nodes.extend(batch)
        if not next_tok:
            break
        page_token = next_tok
    return all_nodes


def _dingtalk_resolve_or_create_folder(parent_folder_id: str, folder_name: str) -> str:
    """在 parent 下按名字查找文件夹；不存在则创建并返回 folderId。"""
    nodes = _dingtalk_list_all_nodes_under(parent_folder_id)
    for n in nodes:
        if not _dingtalk_node_is_folder(n):
            continue
        if _dingtalk_node_display_name(n) != folder_name:
            continue
        nid = _dingtalk_node_id(n)
        if nid:
            return nid
    created = _dingtalk_mcp_tools_call("create_folder", {"name": folder_name, "folderId": parent_folder_id})
    return _dingtalk_extract_folder_id_from_create(created)


def dingtalk_resolve_team_week_folder(iso_week: str) -> tuple[str, str, str]:
    """在周报根目录下解析或创建「YYYY/YYWww」层级子目录。

    返回 (target_folder_id, base_folder_id, week_subfolder_label)。
    """
    base = _report_folder_id()
    year_label = _dingtalk_year_folder_label(iso_week)
    label = _dingtalk_week_subfolder_label(iso_week)
    try:
        year_folder_id = _dingtalk_resolve_or_create_folder(base, year_label)
        week_folder_id = _dingtalk_resolve_or_create_folder(year_folder_id, label)
        return week_folder_id, base, label
    except Exception as e:
        # 某些目录节点不允许 create_folder（但允许直接 create_document），此时回退到根目录直写。
        msg = str(e)
        if "creationNotAllowed" in msg or "invalidParameter.creationNotAllowed" in msg:
            return base, base, label
        raise


def _team_report_document_name(iso_week: str, member_group: str = "all") -> str:
    g = (member_group or "all").strip().lower()
    if g == "frontend":
        return f"{iso_week}-团队周报-前端.md"
    if g == "backend":
        return f"{iso_week}-团队周报-后端.md"
    return f"{iso_week}-团队周报.md"

def _build_publish_meta(
    iso_week: str,
    markdown: str,
    *,
    dingtalk_upload_folder_id: str | None = None,
    week_subfolder: str | None = None,
    folder_resolve_error: str | None = None,
    document_filename: str | None = None,
) -> dict[str, Any]:
    """与 weekly-report 的 publish 块结构对齐，供 Agent 调用钉钉 MCP；本机默认在配置 DINGTALK_MCP_URL 时自动上传。"""
    start, end = _week_date_range(iso_week)
    filename = document_filename or _team_report_document_name(iso_week, "all")
    base_folder_id = _report_folder_id()
    sub = week_subfolder or _dingtalk_week_subfolder_label(iso_week)
    folder_id = dingtalk_upload_folder_id if dingtalk_upload_folder_id else base_folder_id
    return {
        "ready": True,
        "target": {
            "platform": "dingtalk_docs",
            "folder_url": REPORT_FOLDER_URL,
            "folder_id": folder_id,
            "base_folder_id": base_folder_id,
            "week_subfolder": sub,
            "folder_resolve_error": folder_resolve_error,
        },
        "document": {
            "name": filename,
            "week_label": iso_week,
            "week_folder_name": sub,
            "week_range": [start, end],
            "markdown_length": len(markdown),
        },
        "mcp": {
            "check_required": True,
            "required_tools": ["list_nodes", "create_folder", "create_document"],
            "publish_tool": "create_document",
            "publish_args_template": {
                "name": filename,
                "folderId": "<resolved-week-folder-id>",
                "markdown": "<superteam-report-markdown>",
            },
            "if_missing": "请用户先在当前 Agent 中配置并授权钉钉 MCP，然后重试发布。",
        },
    }


def _content_items_to_parsed(result: dict[str, Any]) -> Any:
    structured = (result.get("structuredContent") or {}).get("result")
    if structured is not None:
        return structured
    for item in result.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            text = item.get("text", "")
            try:
                return json.loads(text)
            except Exception:
                return text
    return None


def _parse_mcp_http_response(body: str, content_type: str) -> Any:
    """解析钉钉 Docs MCP 的 HTTP 响应（plain JSON 或 SSE）。"""
    if "text/event-stream" in content_type:
        for line in body.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if "error" in data and data["error"]:
                    err = data["error"]
                    raise RuntimeError(str(err.get("message", err)))
                if "result" in data:
                    return _content_items_to_parsed(data["result"])
    else:
        data = json.loads(body)
        if "error" in data and data["error"]:
            err = data["error"]
            raise RuntimeError(str(err.get("message", err)))
        return _content_items_to_parsed(data.get("result", {}) or {})
    raise RuntimeError("MCP 响应中未找到可解析的 result")


def _dingtalk_mcp_tools_call(
    tool_name: str,
    arguments: dict[str, Any],
    timeout: int = 120,
) -> Any:
    import ssl
    import urllib.error
    import urllib.request

    mcp_url = dingtalk_mcp_url()
    if not mcp_url:
        raise RuntimeError(
            "未找到钉钉 MCP URL。请设置 DINGTALK_MCP_URL，或在 ~/.cursor/mcp.json 中配置钉钉文档 MCP；"
            "亦可写入 ~/.superteam/config。参考 skills/superteam-sync-dingtalk-kb。"
        )
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        },
        ensure_ascii=False,
    ).encode()
    req = urllib.request.Request(
        mcp_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    open_kw: dict[str, Any] = {"timeout": timeout}
    try:
        import certifi

        open_kw["context"] = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    try:
        with urllib.request.urlopen(req, **open_kw) as r:
            content_type = r.headers.get("Content-Type", "")
            body = r.read().decode()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"钉钉 MCP HTTP {e.code}: {e.read().decode(errors='replace')}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"钉钉 MCP 请求失败: {e}") from e
    return _parse_mcp_http_response(body, content_type)


def _dingtalk_doc_url_from_result(result: dict[str, Any]) -> str | None:
    for key in ("url", "documentUrl", "link", "alidocUrl", "webUrl", "docUrl"):
        v = result.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v
    data = result.get("data")
    if isinstance(data, dict):
        return _dingtalk_doc_url_from_result(data)
    return None


# 钉钉 create_document / update_document 单次 markdown 上限（留余量避免边界失败）
_DINGTALK_MARKDOWN_CHUNK_MAX = 9500


def _split_markdown_chunks(text: str, max_len: int = _DINGTALK_MARKDOWN_CHUNK_MAX) -> list[str]:
    """将超长 Markdown 切成多段，优先在空行处断开。"""
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    rest = text
    while rest:
        if len(rest) <= max_len:
            chunks.append(rest)
            break
        cut = rest.rfind("\n\n", 0, max_len)
        if cut < max_len // 2:
            cut = rest.rfind("\n", 0, max_len)
        if cut < max_len // 2:
            cut = max_len
        chunks.append(rest[:cut])
        rest = rest[cut:].lstrip("\n")
    return chunks


def _dingtalk_extract_document_id_from_create(raw: Any) -> str:
    inner = _dingtalk_unwrap_tool_result(raw)
    for d in (inner, raw if isinstance(raw, dict) else {}):
        if not isinstance(d, dict):
            continue
        for k in ("nodeId", "id", "dentryUuid", "dentryId"):
            v = d.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        nested = d.get("document") or d.get("node") or d.get("data")
        if isinstance(nested, dict):
            nid = _dingtalk_node_id(nested)
            if nid:
                return nid
    raise RuntimeError(f"create_document 响应中未解析到文档 nodeId: {raw!r}")


def _dingtalk_raise_if_failed(raw: Any, *, op: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RuntimeError(f"{op} 返回非对象: {raw!r}")
    if raw.get("success") is False:
        raise RuntimeError(str(raw.get("message") or raw.get("errorMsg") or raw.get("error") or raw))
    return raw


def dingtalk_upload_team_report_markdown(
    iso_week: str,
    markdown: str,
    *,
    upload_folder_id: str | None = None,
    document_name: str | None = None,
) -> tuple[dict[str, Any], str | None]:
    """通过 HTTP MCP 调用 create_document；返回 (原始结果 dict, 文档 URL 若可解析)。
    文档写入「YYW周」子目录（如 26W15）；upload_folder_id 若已在外部解析过可传入以避免重复 list/create。
    超长正文分块：先 create 空文档，再 overwrite 首段、append 后续（钉钉单次 markdown ≤ 10000）。
    """
    name = document_name or _team_report_document_name(iso_week, "all")
    folder_id = upload_folder_id or dingtalk_resolve_team_week_folder(iso_week)[0]
    chunks = _split_markdown_chunks(markdown)

    if len(chunks) == 1:
        raw = _dingtalk_mcp_tools_call(
            "create_document",
            {"name": name, "folderId": folder_id, "markdown": chunks[0]},
        )
        raw = _dingtalk_raise_if_failed(raw, op="create_document")
        url = _dingtalk_doc_url_from_result(raw)
        return raw, url

    raw = _dingtalk_mcp_tools_call(
        "create_document",
        {"name": name, "folderId": folder_id},
    )
    raw = _dingtalk_raise_if_failed(raw, op="create_document")
    doc_id = _dingtalk_extract_document_id_from_create(raw)
    _dingtalk_raise_if_failed(
        _dingtalk_mcp_tools_call(
            "update_document",
            {"nodeId": doc_id, "markdown": chunks[0], "mode": "overwrite"},
        ),
        op="update_document(overwrite)",
    )
    for i, part in enumerate(chunks[1:], start=2):
        _dingtalk_raise_if_failed(
            _dingtalk_mcp_tools_call(
                "update_document",
                {"nodeId": doc_id, "markdown": part, "mode": "append"},
            ),
            op=f"update_document(append #{i})",
        )
    url = _dingtalk_doc_url_from_result(raw)
    if not url:
        try:
            info = _dingtalk_mcp_tools_call("get_document_info", {"nodeId": doc_id})
            if isinstance(info, dict):
                url = _dingtalk_doc_url_from_result(info)
        except Exception:
            pass
    return {**raw, "chunk_count": len(chunks), "nodeId": doc_id}, url


def render_report(all_sections: list[str], iso_week: str, *, member_group: str = "all") -> str:
    start, end = _week_date_range(iso_week)
    now_local = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = []
    lines.append(f"# 团队周报（Linear）— 上周 {iso_week}")
    lines.append(f"\n> 对应自然周：{start} ~ {end}")
    lines.append(f"> 生成时间：{now_local}")
    g = (member_group or "all").strip().lower()
    if g == "frontend":
        lines.append("> **统计范围**：仅「前端」职能成员（成员表 `role` 匹配）。")
    elif g == "backend":
        lines.append("> **统计范围**：仅「后端」职能成员（成员表 `role` 匹配）。")
    lines.append("\n---")
    lines.extend(all_sections)
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="Generate team weekly report from Linear cycles")
    p.add_argument(
        "--week",
        "-w",
        default=None,
        help="指定 ISO 周（如 2026-W15）；省略则自动使用「上周」本年度第几周",
    )
    p.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output markdown path (default: reports/team-weekly/<week>.md)",
    )
    p.add_argument("--dry-run", action="store_true", help="Only print plan, do not fetch issues")
    p.add_argument("--include-archived-teams", action="store_true", help="Include archived teams")
    p.add_argument(
        "--format",
        "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="markdown=仅人类可读摘要；json=输出含 publish 元数据（对齐 superteam-report，供 Agent 发布）",
    )
    p.add_argument(
        "--no-publish-dingtalk",
        action="store_true",
        help="跳过生成后的钉钉上传（默认可从 DINGTALK_MCP_URL 或 ~/.cursor/mcp.json 解析钉钉 MCP）",
    )
    p.add_argument(
        "--uncycled-include-completed",
        action="store_true",
        help="「未划入迭代」计数包含已完成（Done）issue；默认不含，以对齐 Linear 无 Cycle 视图",
    )
    p.add_argument(
        "--view",
        choices=["dashboard", "text"],
        default="dashboard",
        help="迭代进度展示风格：dashboard=可视化增强（默认），text=原始纯文字结构",
    )
    p.add_argument(
        "--chart-style",
        choices=["auto", "text", "mermaid", "dingtalk"],
        default="auto",
        help=(
            "dashboard 下图表：auto=将上传钉钉时用表格+字符条（无 Mermaid），本机未上传用 mermaid；"
            "dingtalk/text=表格+字符条；mermaid=全程 ```mermaid（本地/GitHub 预览）"
        ),
    )
    p.add_argument(
        "--member-group",
        choices=["all", "frontend", "backend", "前端", "后端"],
        default=None,
        help=(
            "按成员职能过滤周报任务：数据来自 list_members（与 superteam-member list_members 同源），"
            "排除 deleted/merged/无 role；backend/后端=backend+frontend+architect 指派；"
            "frontend/前端=仅 frontend；all=不按 assignee 过滤。"
        ),
    )
    p.add_argument(
        "--publish-dingtalk",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    p.add_argument(
        "--json-dir",
        default=None,
        help=(
            "导出 4 类结构化 JSON 的目录；默认周报为 reports/team-weekly/json，"
            "进行中快照为 reports/project-daily"
        ),
    )
    p.add_argument(
        "--export-json",
        action="store_true",
        help=(
            "写入 projects-overview / projects-detail / members / workload-risks "
            "四类 JSON 分片（默认关闭；进行中快照亦需显式开启）"
        ),
    )
    p.add_argument(
        "--in-progress-snapshot",
        action="store_true",
        help=(
            "进行中项目快照（遗留）：须同时加 --export-json 才会写 reports/project-daily/；"
            "日常 pulse 请用 snapshot_sprint.py / snapshot_member.py"
        ),
    )
    p.add_argument(
        "--json-filename-prefix",
        default=None,
        help=(
            "JSON 文件名前缀（不含后缀）；默认以运行日 YYYY-MM-DD 开头，"
            "进行中快照为 YYYY-MM-DD-in-progress"
        ),
    )
    args = p.parse_args()

    snapshot_mode = bool(args.in_progress_snapshot)
    json_dir = Path(
        args.json_dir
        or ("reports/project-daily" if snapshot_mode else "reports/team-weekly/json")
    )
    if snapshot_mode and args.week:
        print(
            "提示：--in-progress-snapshot 固定使用当前 ISO 周与当前 Cycle，忽略 --week。",
            file=sys.stderr,
        )

    iso_week = _current_iso_week() if snapshot_mode else (args.week or _last_iso_week())
    report_week_start = _report_week_start_date(iso_week)
    current_week = _current_iso_week()
    out_path = Path(args.output) if args.output else Path("reports") / "team-weekly" / f"{iso_week}.md"
    dt_url = dingtalk_mcp_url()
    auto_upload_planned = (
        not snapshot_mode and not args.no_publish_dingtalk and bool(dt_url)
    )
    snapshot_now = _snapshot_yesterday_end() if snapshot_mode else _now_utc()
    win_start = _snapshot_change_window_start() if snapshot_mode else None
    win_end = snapshot_now if snapshot_mode else None
    change_window_meta: dict[str, str] | None = None
    if snapshot_mode and win_start and win_end:
        change_window_meta = {
            "start": win_start.strftime("%Y-%m-%d %H:%M"),
            "end": win_end.strftime("%Y-%m-%d %H:%M"),
        }
    if args.chart_style == "auto":
        # 钉钉导入的 Markdown 通常不把 ```mermaid 渲染成图；上传时用表格 + 字符条（与 text 相同，无 Mermaid 块）。
        chart_style = "dingtalk" if auto_upload_planned else "mermaid"
    else:
        chart_style = args.chart_style
    member_group = _normalize_member_group(args.member_group or env("TEAM_WEEKLY_MEMBER_GROUP"))
    member_names = _member_names_by_group(member_group)

    mcp = LinearMcpClient()
    now = snapshot_now if snapshot_mode else _now_utc()
    plan_preview: list[dict[str, Any]] = []
    json_bundle: dict[str, dict[str, Any]] | None = None
    cutoff_date_str: str | None = (
        _to_local_date(snapshot_now).isoformat() if snapshot_mode else None
    )
    try:
        with _StdioMcpClient(mcp._cmd) as client:
            tool_names = client.list_tools()
            teams = mcp.list_teams(client, tool_names=tool_names)
            if not args.include_archived_teams:
                teams = [t for t in teams if not t.get("archivedAt")]
            all_linear_projects = _enrich_linear_projects(
                mcp,
                client,
                tool_names,
                mcp.list_projects(client, tool_names),
            )
            project_meta_by_name = _build_project_meta_by_name(all_linear_projects)
            active_linear_projects, excluded_project_notes = _filter_linear_projects_for_report(
                all_linear_projects,
                report_week_start=report_week_start,
                ref=now.date(),
            )
            excluded_project_names = _excluded_report_project_names(
                all_linear_projects,
                ref=now.date(),
                report_week_start=report_week_start,
            )
            rd_member_names = _rd_member_names()

            for t in teams:
                team_id = t.get("id") or t.get("teamId")
                if not team_id:
                    continue
                cycles = mcp.list_cycles_for_team(client, tool_names, team_id=team_id)
                week_cycles = _pick_cycles_for_week(cycles, iso_week)
                this_week_cycles = _pick_cycles_for_week(cycles, current_week)
                cycle = week_cycles[0] if week_cycles else (this_week_cycles[0] if this_week_cycles else None)
                plan_preview.append(
                    {
                        "team": {"id": team_id, "name": t.get("name")},
                        "last_week_cycles": week_cycles,
                        "this_week_cycles": this_week_cycles,
                        "cycle": cycle,
                    }
                )

            if args.dry_run:
                print(json.dumps(
                    {
                        "mode": "in_progress_snapshot" if snapshot_mode else "weekly",
                        "week": iso_week,
                        "output": str(out_path) if not snapshot_mode else None,
                        "json_dir": str(json_dir) if snapshot_mode else None,
                        "cutoff_date": cutoff_date_str,
                        "change_window": change_window_meta,
                        "member_group": member_group,
                        "member_count": len(member_names) if member_group != "all" else None,
                        "teams": plan_preview,
                    },
                    ensure_ascii=False,
                    indent=2,
                ))
                return

            merged_status_type_map: dict[str, str] = {}
            project_issues_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
            merged_week_issues: list[dict[str, Any]] = []
            seen_issue_keys: set[str] = set()
            cycle_notes: list[str] = []

            for t in teams:
                team_id = t.get("id") or t.get("teamId")
                if not team_id:
                    continue
                team_name = str(t.get("name") or team_id)
                cycles = mcp.list_cycles_for_team(client, tool_names, team_id=team_id)
                target_cycles = _pick_cycles_for_week(cycles, iso_week)
                statuses = mcp.list_issue_statuses(client, tool_names, team_id=team_id)
                for s in statuses:
                    if isinstance(s, dict):
                        merged_status_type_map[s.get("name", "")] = s.get("type", "")

                team_all_issues = mcp.list_issues_for_team(client, tool_names, team_id=team_id)
                team_all_issues = _filter_issues_by_member_group(team_all_issues, member_names)
                team_all_issues = _filter_issues_excluding_projects(
                    team_all_issues, excluded_project_names,
                )
                for it in team_all_issues:
                    pname = _issue_project_name(it)
                    if pname != "未关联项目":
                        project_issues_by_name[pname].append(it)

                for cyc in target_cycles:
                    cycle_id = cyc.get("id") or cyc.get("cycleId") or ""
                    if not cycle_id:
                        continue
                    num = cyc.get("number")
                    cyc_label = f"{team_name} #{num}" if num is not None else team_name
                    if cyc_label not in cycle_notes:
                        cycle_notes.append(cyc_label)
                    batch = mcp.list_issues_in_cycle(
                        client, tool_names, team_id=team_id, cycle_id=cycle_id,
                    )
                    for it in batch:
                        k = _issue_key(it)
                        if k in seen_issue_keys:
                            continue
                        seen_issue_keys.add(k)
                        merged_week_issues.append(it)

            # 成员负载与 snapshot_member 同源：Cycle 全量 issue，不做成员组/过期项目过滤
            workload_cycle_issues = list(merged_week_issues)
            merged_week_issues = _filter_issues_by_member_group(merged_week_issues, member_names)
            member_cycle_issues = list(merged_week_issues)
            merged_week_issues = _filter_issues_excluding_projects(
                merged_week_issues, excluded_project_names,
            )
            _merge_issues_into_project_index(project_issues_by_name, merged_week_issues)

            json_cycle_issues = merged_week_issues
            json_active_projects = active_linear_projects
            report_mode = "weekly"

            if snapshot_mode and win_start and win_end:
                report_mode = "in_progress_snapshot"
                proj_stats_all = _build_proj_stats_list(
                    merged_week_issues,
                    merged_status_type_map,
                    now,
                    active_linear_projects,
                    project_meta_by_name,
                    dict(project_issues_by_name),
                    rd_member_names=rd_member_names,
                )
                ip_names = _in_progress_project_names_from_stats(proj_stats_all)
                json_cycle_issues = _filter_cycle_issues_for_snapshot(
                    merged_week_issues,
                    win_start=win_start,
                    win_end=win_end,
                    in_progress_project_names=ip_names,
                )
                json_active_projects = [
                    p for p in active_linear_projects
                    if str(p.get("name") or "").strip() in ip_names
                ]

            if snapshot_mode or args.export_json:
                grouped = group_issues(
                    json_cycle_issues, status_type_map=merged_status_type_map,
                )
                json_bundle = build_team_weekly_json_bundle(
                    iso_week=iso_week,
                    now=now,
                    member_group=member_group,
                    cycle_issues=json_cycle_issues,
                    workload_cycle_issues=workload_cycle_issues,
                    status_type_map=merged_status_type_map,
                    grouped=grouped,
                    project_meta_by_name=project_meta_by_name,
                    active_linear_projects=json_active_projects,
                    project_issues_by_name=dict(project_issues_by_name),
                    rd_member_names=rd_member_names,
                    cycle_notes=cycle_notes,
                    report_mode=report_mode,
                    cutoff_date=cutoff_date_str,
                    change_window=change_window_meta,
                )

            report_body = ""
            sections: list[str] = []
            if not snapshot_mode:
                weekly_grouped = group_issues(
                    merged_week_issues, status_type_map=merged_status_type_map,
                )
                report_body = render_weekly_report_body(
                    iso_week=iso_week,
                    grouped=weekly_grouped,
                    now=now,
                    cycle_issues=merged_week_issues,
                    member_cycle_issues=member_cycle_issues,
                    workload_cycle_issues=workload_cycle_issues,
                    status_type_map=merged_status_type_map,
                    project_meta_by_name=project_meta_by_name,
                    active_linear_projects=active_linear_projects,
                    excluded_project_notes=excluded_project_notes,
                    project_issues_by_name=dict(project_issues_by_name),
                    rd_member_names=rd_member_names,
                    cycle_notes=cycle_notes,
                )
                sections = [report_body]
    except FileNotFoundError:
        print(json.dumps({
            "error": "local_mcp_missing",
            "message": "npx not found. Install Node.js (includes npx) to use this skill.",
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
    except _LocalMcpError as e:
        print(json.dumps({
            "error": "local_mcp_failed",
            "message": str(e),
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    doc_filename = _team_report_document_name(iso_week, member_group)
    report = ""
    if not snapshot_mode:
        report = render_report(sections, iso_week=iso_week, member_group=member_group)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")

    json_paths: list[Path] = []
    export_json = (
        args.export_json and not args.dry_run and json_bundle is not None
    )
    if export_json:
        generated_date = _json_export_generated_date()
        if args.json_filename_prefix:
            json_prefix = str(args.json_filename_prefix)
        else:
            json_prefix = _default_json_filename_prefix(
                snapshot_mode=snapshot_mode,
                generated_date=generated_date,
            )
        json_paths = write_team_weekly_json_exports(
            json_bundle,
            json_dir,
            filename_prefix=json_prefix,
        )

    auto_upload = (
        not snapshot_mode and not args.no_publish_dingtalk and bool(dt_url)
    )
    need_folder_resolve = (
        not snapshot_mode
        and bool(dt_url)
        and (auto_upload or args.format == "json")
    )

    publish_folder_id: str | None = None
    folder_resolve_error: str | None = None
    week_subfolder = _dingtalk_week_subfolder_label(iso_week)
    publish: dict[str, Any] = {}
    dingtalk_upload: dict[str, Any] | None = None

    if need_folder_resolve:
        try:
            publish_folder_id, _, week_subfolder = dingtalk_resolve_team_week_folder(iso_week)
        except Exception as e:
            folder_resolve_error = str(e)
            if auto_upload:
                print(
                    json.dumps(
                        {
                            "error": "dingtalk_week_folder_resolve_failed",
                            "message": folder_resolve_error,
                            "local_file": str(out_path),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    file=sys.stderr,
                )
                sys.exit(1)

    if not snapshot_mode:
        publish = _build_publish_meta(
            iso_week,
            report,
            dingtalk_upload_folder_id=publish_folder_id,
            week_subfolder=week_subfolder,
            folder_resolve_error=folder_resolve_error,
            document_filename=doc_filename,
        )

    if snapshot_mode:
        dingtalk_upload = {"skipped": True, "reason": "in_progress_snapshot"}
    elif args.no_publish_dingtalk:
        dingtalk_upload = {"skipped": True, "reason": "disabled_by_flag"}
    elif not dt_url:
        dingtalk_upload = {"skipped": True, "reason": "dingtalk_mcp_url not resolved"}
        if args.format == "markdown":
            print(
                "提示：未解析到钉钉 MCP URL（请设置 DINGTALK_MCP_URL 或在 ~/.cursor/mcp.json 配置钉钉文档 MCP），已跳过上传。",
                file=sys.stderr,
            )
    else:
        try:
            raw, doc_url = dingtalk_upload_team_report_markdown(
                iso_week,
                report,
                upload_folder_id=publish_folder_id,
                document_name=doc_filename,
            )
            dingtalk_upload = {
                "ok": True,
                "result": raw,
                "url": doc_url,
                "folder_id": publish_folder_id,
                "week_subfolder": week_subfolder,
            }
        except Exception as e:
            print(
                json.dumps(
                    {
                        "error": "dingtalk_upload_failed",
                        "message": str(e),
                        "local_file": str(out_path),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
            sys.exit(1)

    if snapshot_mode and args.format == "json":
        payload = {
            "skill": "superteam-report",
            "status": "ok",
            "mode": "in_progress_snapshot",
            "week": iso_week,
            "cutoff_date": cutoff_date_str,
            "change_window": change_window_meta,
            "json_exports": [str(p) for p in json_paths],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.format == "json":
        payload: dict[str, Any] = {
            "skill": "superteam-report",
            "status": "ok",
            "week": iso_week,
            "output": str(out_path),
            "markdown": report,
            "publish": publish,
        }
        if dingtalk_upload is not None:
            payload["dingtalk"] = dingtalk_upload
        if json_paths:
            payload["json_exports"] = [str(p) for p in json_paths]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif snapshot_mode:
        print(
            json.dumps(
                {
                    "skill": "superteam-report",
                    "status": "ok",
                    "mode": "in_progress_snapshot",
                    "week": iso_week,
                    "cutoff_date": cutoff_date_str,
                    "change_window": change_window_meta,
                    "json_exports": [str(p) for p in json_paths],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"已生成团队周报：{out_path}")
        if json_paths:
            for p in json_paths:
                print(f"已导出 JSON：{p}")
        if auto_upload and dingtalk_upload and dingtalk_upload.get("url"):
            print(f"钉钉文档：{dingtalk_upload['url']}")
        elif auto_upload and dingtalk_upload and dingtalk_upload.get("ok"):
            print("钉钉文档：已创建（响应中未解析到 URL，请在钉钉目录中查看）")


if __name__ == "__main__":
    main()

