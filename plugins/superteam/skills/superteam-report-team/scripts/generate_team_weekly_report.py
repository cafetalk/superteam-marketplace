#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""superteam-report-team generator — 基于 Linear Cycle 为 workspace 全部 Team 生成周报。

只读：通过本机 Linear MCP（`mcp-remote https://mcp.linear.app/mcp`）的 stdio JSON-RPC
调用 tools/list / tools/call 拉取 Team / Cycle / Issue 数据，生成 Markdown。

Usage:
  python generate_team_weekly_report.py
  # 默认：上周（本地自然周对应的 ISO 周），无需传 --week
  python generate_team_weekly_report.py --week 2026-W15
  python generate_team_weekly_report.py --output reports/team-weekly/2026-W15.md
  python generate_team_weekly_report.py --dry-run
  # 配置了钉钉 MCP（DINGTALK_MCP_URL 或 ~/.cursor/mcp.json）时自动上传；可用 --no-publish-dingtalk 关闭
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


# Load shared config helper (keeps architecture: skill script imports _shared/config.py only)
_sys_path_shared = str(Path(__file__).resolve().parent.parent.parent / "_shared")
if _sys_path_shared not in sys.path:
    sys.path.insert(0, _sys_path_shared)

from config import dingtalk_mcp_url, env  # noqa: E402
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
                "clientInfo": {"name": "superteam-report-team", "version": "0.1.0"},
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


def _last_iso_week(now: datetime | None = None) -> str:
    """上一自然周（周一至周日）对应的 ISO 周，用于周报标题与落盘文件名。"""
    now = now or datetime.now()
    d = now.date()
    days_since_mon = d.weekday()  # Mon=0
    mon_this_week = d - timedelta(days=days_since_mon)
    mon_last_week = mon_this_week - timedelta(days=7)
    y, w, _ = mon_last_week.isocalendar()
    return f"{y}-W{w:02d}"


def _week_date_range(iso_week: str) -> tuple[str, str]:
    year, week = iso_week.split("-W")
    monday = datetime.strptime(f"{year}-W{int(week)}-1", "%G-W%V-%u")
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


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
        *,
        first: int = 30,
    ) -> list[dict[str, Any]]:
        """按 team 拉取 cycles（不依赖 current 状态），用于按时间窗口匹配目标周。"""
        tool_names = tool_names or client.list_tools()
        tool = self._pick(tool_names, "list_cycles", "linear_list_cycles")
        data = client.call_tool(tool, {"teamId": team_id, "first": first})
        return data if isinstance(data, list) else []

    def list_issue_statuses(self, client: _StdioMcpClient, tool_names: set[str] | None, team_id: str) -> list[dict[str, Any]]:
        tool_names = tool_names or client.list_tools()
        tool = self._pick(tool_names, "list_issue_statuses", "linear_list_issue_statuses")
        data = client.call_tool(tool, {"team": team_id})
        return data if isinstance(data, list) else []

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
        status_name = (it.get("status") or "").strip()
        status_type = status_type_map.get(status_name)
        g = _state_group_from_type(status_type)
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
    # 用户显式提供的个人周报链接兜底（可被 JSON 配置覆盖）
    out.setdefault(
        "项钧",
        "https://alidocs.dingtalk.com/i/nodes/6LeBq413JAzzgxd3CBORemqN8DOnGvpb?utm_scene=team_space",
    )
    return out


def _dingtalk_node_url(node: dict[str, Any]) -> str | None:
    for k in ("url", "documentUrl", "webUrl", "docUrl", "link"):
        v = node.get(k)
        if isinstance(v, str) and v.startswith("http"):
            return v
    return None


def _dingtalk_personal_report_url_map(owner_names: list[str], folder_id: str) -> dict[str, str]:
    """从同目录文档中自动匹配成员个人周报链接。

    约定：目录内均为个人周报/团队周报文档，按“姓名在文档名中出现”匹配。
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
        # 优先：文档名同时包含姓名与“周报”
        for name, u in docs:
            if owner in name:
                out[owner] = u
                break
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
    return f"  - {_issue_title_line(it)} · 持有人：**{who}**"


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


def _member_names_by_group(group: str) -> set[str]:
    """从成员表读取职能分组，返回可用于匹配 assignee 的名字集合。"""
    if group == "all":
        return set()
    try:
        members = list_members()
    except Exception:
        return set()

    def _is_target_role(role: str) -> bool:
        r = (role or "").strip().lower()
        if group == "frontend":
            return ("前端" in r) or ("frontend" in r) or ("front-end" in r) or (r == "fe")
        if group == "backend":
            return ("后端" in r) or ("backend" in r) or ("back-end" in r) or (r == "be")
        return False

    names: set[str] = set()
    for m in members:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "")
        if not _is_target_role(role):
            continue
        for key in ("real_name", "realName", "username", "real_name_en", "realNameEn", "email"):
            v = m.get(key)
            if isinstance(v, str) and v.strip():
                names.add(v.strip())
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
    point_to_hours = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}
    total_hours = 0.0
    done_hours = 0.0
    for it in cycle_issues:
        p = _issue_estimate_points(it)
        if p is None:
            continue
        h = float(point_to_hours.get(int(p), 0))
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


def _cycle_brief_summary_lines(
    *,
    cycle_issues: list[dict[str, Any]],
) -> list[str]:
    """当前 Cycle 内容摘要：按主题归纳全部任务内容，最多三句话。"""
    if not cycle_issues:
        return []
    theme_counts: dict[str, int] = defaultdict(int)
    for it in cycle_issues:
        theme = _title_theme(str(it.get("title") or ""))
        if _TASK_NUM_THEME.match(theme):
            # Task 序号类标题不作为主题句，避免「Task1/Task2」语义过弱。
            continue
        theme_counts[theme] += 1
    if not theme_counts:
        return []
    ordered = sorted(theme_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top = ordered[:3]
    lines: list[str] = []
    lines.append("\n### 🧭 当前 Cycle 摘要")
    for idx, (theme, cnt) in enumerate(top, start=1):
        if idx == 1:
            lines.append(f"- 本迭代主要聚焦在「{theme}」相关工作，共 **{cnt}** 项任务。")
        elif idx == 2:
            lines.append(f"- 次核心内容为「{theme}」，当前覆盖 **{cnt}** 项，属于并行推进的第二主线。")
        else:
            lines.append(f"- 另外「{theme}」相关共 **{cnt}** 项，构成当前迭代的补充工作面。")
    return lines


def render_team_section(
    team: dict[str, Any],
    cycle: dict[str, Any] | None,
    grouped: GroupedIssues | None,
    now: datetime,
    cycle_issues: list[dict[str, Any]] | None = None,
    discussion_block: str = "",
    uncycled_total: int = 0,
    uncycled_skipped_unknown: int = 0,
    uncycled_include_completed: bool = False,
    status_type_map: dict[str, str] | None = None,
    view: str = "dashboard",
    chart_style: str = "text",
    owner_weekly_url_map: dict[str, str] | None = None,
    progress_planned_items: list[dict[str, Any]] | None = None,
    progress_done_items: list[dict[str, Any]] | None = None,
    weekly_plan_items: list[dict[str, Any]] | None = None,
) -> str:
    lines: list[str] = []
    lines.append(f"\n## Team：{team['name']}")

    if not cycle:
        lines.append("\n**当前 Cycle**：_未找到（该 Team 可能未启用 Cycle 或暂无 active cycle）_")
        lines.append("\n- 待确认：该 Team 的迭代管理口径（Cycle/Project/Milestone）")
        lines.append("\n### ❓ 未划入迭代的任务")
        lines.append("")
        lines.extend(_uncycled_report_lines(
            uncycled_total,
            uncycled_skipped_unknown,
            include_completed=uncycled_include_completed,
        ))
        return "\n".join(lines)

    starts_at = cycle.get("startsAt")
    ends_at = cycle.get("endsAt")
    lines.append(f"\n**当前 Cycle**：#{cycle.get('number')}（{starts_at} ~ {ends_at}）")

    if not grouped:
        return "\n".join(lines)

    total = len(grouped.done) + len(grouped.in_progress) + len(grouped.todo) + len(grouped.backlog)
    done = len(grouped.done)
    inprog = len(grouped.in_progress)
    todo = len(grouped.todo)
    in_cycle_backlog = len(grouped.backlog)
    pct = (done / total * 100.0) if total else 0.0
    u_tot = uncycled_total

    cissues = cycle_issues if cycle_issues is not None else []
    n_demand, n_task, n_bug = count_cycle_issues_by_work_labels(cissues)
    est = summarize_cycle_estimates(cissues)

    _div = "\n---\n"

    if view == "dashboard":
        lines.extend(_cycle_brief_summary_lines(cycle_issues=cissues))
        lines.append(_div)
        lines.extend(_render_cycle_dashboard_lines(
            total=total,
            done=done,
            inprog=inprog,
            todo=todo,
            backlog=in_cycle_backlog,
            n_demand=n_demand,
            n_task=n_task,
            n_bug=n_bug,
            cycle=cycle,
            cycle_issues=cissues,
            status_type_map=status_type_map or {},
            now=now,
            uncycled_total=uncycled_total,
            uncycled_skipped_unknown=uncycled_skipped_unknown,
            uncycled_include_completed=uncycled_include_completed,
            chart_style=chart_style,
        ))
        lines.append(_div)
    else:
        lines.extend(_cycle_brief_summary_lines(cycle_issues=cissues))
        lines.append(_div)
        lines.append("\n### 📊 迭代进度与风险")
        # 1. 当前 Cycle 规模与进度
        lines.append("\n**1. 当前 Cycle 规模与进度**")
        lines.append(f"- 总任务数：**{total}**")
        lines.append(f"- 完成率（按数量）：**{pct:.1f}%**")
        lines.extend(format_cycle_pace_lines(cycle, cissues, status_type_map or {}, now))

        lines.append(_div)

        # 2. 按工作类型标签（与 issue 上 demand/task/bug 标签对应）
        lines.append("\n**2. 按工作类型标签（demand / task / bug）**")
        lines.append(f"- 需求数（**demand**）：**{n_demand}**")
        lines.append(f"- 任务数（**task**）：**{n_task}**")
        lines.append(f"- Bug 数（**bug**）：**{n_bug}**")

        lines.append(_div)

        # 3. 状态分布（仅限当前 Cycle 内 issue）
        lines.append("\n**3. 状态分布（当前 Cycle）**")
        lines.append(f"- 已完成：**{done}**")
        lines.append(f"- 进行中：**{inprog}**")
        lines.append(f"- 待开始：**{todo}**")
        lines.append(f"- Cycle 内 Backlog/Triage：**{in_cycle_backlog}**")

        lines.append(_div)

    # 5. Team 级补充（非当前 Cycle 维度）
    if view != "dashboard":
        lines.append("\n**5. Team 范围补充**")
        lines.extend(_uncycled_report_lines(
            u_tot,
            uncycled_skipped_unknown,
            include_completed=uncycled_include_completed,
        ))

    blocked_issues, risk_lines = detect_risks(grouped.in_progress, cissues, now=now)

    lines.append(_div)
    lines.append("\n**风险与受阻（当前 Cycle）**")

    if blocked_issues:
        lines.append("\n#### 🚫 受阻任务（Blocked）")
        lines.append(f"_当前 Cycle 内状态为 Blocked/阻塞，共 **{len(blocked_issues)}** 项。_")
        for it in blocked_issues[:35]:
            lines.append(_risk_line_with_owner(it))
        if len(blocked_issues) > 35:
            lines.append(f"  - _… 另有 {len(blocked_issues) - 35} 项未列出_")

    if risk_lines:
        lines.append("\n#### ⚠️ 其他风险提示（自动识别）")
        lines.extend(risk_lines)
    elif not blocked_issues:
        lines.append("\n#### ⚠️ 其他风险提示（自动识别）")
        lines.append("_未发现明显风险信号_")

    planned_items = progress_planned_items if progress_planned_items is not None else grouped.in_progress
    done_items = progress_done_items if progress_done_items is not None else grouped.done
    done_ip = done_items + planned_items
    owner_url_map = owner_weekly_url_map or _member_weekly_report_url_map()
    lines.append("\n### ✅ 上周进展（计划中 + 已完成）")
    if done_ip:
        overview = summarize_titles_by_theme(done_ip[:120])
        if overview:
            lines.append("\n#### 总览")
            lines.extend(overview)
        lines.append("\n#### 明细（按负责人）")
        merged_by_owner: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        for it in done_items:
            merged_by_owner[_assignee_name(it) or "未分配"].append(("已完成", it))
        for it in planned_items:
            merged_by_owner[_assignee_name(it) or "未分配"].append(("计划中", it))
        for owner, pairs in sorted(merged_by_owner.items(), key=lambda kv: kv[0]):
            lines.append(f"\n- **{owner}**")
            owner_done = [it for label, it in pairs if label == "已完成"]
            owner_inprog = [it for label, it in pairs if label == "计划中"]
            owner_summary = summarize_owner_progress(
                owner,
                owner_done,
                owner_inprog,
                cissues,
                status_type_map or {},
                max_sentences=5,
            )
            for s in owner_summary:
                lines.append(f"  - {s}")
            owner_key = owner.strip()
            report_url = owner_url_map.get(owner_key) or owner_url_map.get(owner)
            if not report_url:
                for k, v in owner_url_map.items():
                    kk = k.strip()
                    if owner_key in kk or kk in owner_key:
                        report_url = v
                        break
            if not report_url and owner_key == "项钧":
                report_url = "https://alidocs.dingtalk.com/i/nodes/6LeBq413JAzzgxd3CBORemqN8DOnGvpb?utm_scene=team_space"
            if report_url:
                lines.append(f"  - 个人周报地址：[钉钉文档]({report_url})")
            else:
                lines.append("  - 个人周报地址：待补充")
    else:
        lines.append("\n_无_")

    if discussion_block:
        lines.append(discussion_block)

    plan = weekly_plan_items if weekly_plan_items is not None else (grouped.todo + grouped.in_progress)
    lines.append("\n### 📋 本周计划")
    if plan:
        overview = summarize_titles_by_theme(plan[:120])
        if overview:
            lines.append("\n#### 总览")
            lines.extend(overview)
        lines.append("\n#### 明细（按负责人）")
        by_owner = _group_by_assignee(plan)
        for owner, items in sorted(by_owner.items(), key=lambda kv: kv[0]):
            lines.append(f"\n- **{owner}**")
            owner_plan_summary = summarize_owner_plan(owner, items[:60], max_sentences=5)
            for s in owner_plan_summary:
                lines.append(f"  - {s}")
            owner_key = owner.strip()
            report_url = owner_url_map.get(owner_key) or owner_url_map.get(owner)
            if not report_url:
                for k, v in owner_url_map.items():
                    kk = k.strip()
                    if owner_key in kk or kk in owner_key:
                        report_url = v
                        break
            if not report_url and owner_key == "项钧":
                report_url = "https://alidocs.dingtalk.com/i/nodes/6LeBq413JAzzgxd3CBORemqN8DOnGvpb?utm_scene=team_space"
            if report_url:
                lines.append(f"  - 个人周报地址：[钉钉文档]({report_url})")
            else:
                lines.append("  - 个人周报地址：待补充")
    else:
        lines.append("\n_无_")

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
                "markdown": "<superteam-report-team-markdown>",
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


def dingtalk_upload_team_report_markdown(
    iso_week: str,
    markdown: str,
    *,
    upload_folder_id: str | None = None,
    document_name: str | None = None,
) -> tuple[dict[str, Any], str | None]:
    """通过 HTTP MCP 调用 create_document；返回 (原始结果 dict, 文档 URL 若可解析)。
    文档写入「YYW周」子目录（如 26W15）；upload_folder_id 若已在外部解析过可传入以避免重复 list/create。
    """
    name = document_name or _team_report_document_name(iso_week, "all")
    folder_id = upload_folder_id or dingtalk_resolve_team_week_folder(iso_week)[0]
    raw = _dingtalk_mcp_tools_call(
        "create_document",
        {"name": name, "folderId": folder_id, "markdown": markdown},
    )
    if not isinstance(raw, dict):
        raise RuntimeError(f"create_document 返回非对象: {raw!r}")
    if raw.get("success") is False:
        raise RuntimeError(str(raw.get("message") or raw.get("error") or raw))
    url = _dingtalk_doc_url_from_result(raw)
    return raw, url


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
    lines.append("\n---")
    lines.append("_Generated by superteam-report-team_")
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
        help="按成员职能过滤周报范围：frontend/前端、backend/后端；默认 all（全部成员）。",
    )
    p.add_argument(
        "--publish-dingtalk",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = p.parse_args()

    iso_week = args.week or _last_iso_week()
    current_week = _current_iso_week()
    out_path = Path(args.output) if args.output else Path("reports") / "team-weekly" / f"{iso_week}.md"
    dt_url = dingtalk_mcp_url()
    auto_upload_planned = not args.no_publish_dingtalk and bool(dt_url)
    if args.chart_style == "auto":
        # 钉钉导入的 Markdown 通常不把 ```mermaid 渲染成图；上传时用表格 + 字符条（与 text 相同，无 Mermaid 块）。
        chart_style = "dingtalk" if auto_upload_planned else "mermaid"
    else:
        chart_style = args.chart_style
    member_group = _normalize_member_group(args.member_group or env("TEAM_WEEKLY_MEMBER_GROUP"))
    member_names = _member_names_by_group(member_group)
    owner_weekly_url_map: dict[str, str] = _member_weekly_report_url_map()
    personal_report_lookup_folder_id: str | None = None
    if dt_url:
        try:
            personal_report_lookup_folder_id, _, _ = dingtalk_resolve_team_week_folder(iso_week)
        except Exception:
            # 目录解析失败时回退到手工配置映射；不影响主流程
            personal_report_lookup_folder_id = None

    mcp = LinearMcpClient()
    now = _now_utc()
    sections: list[str] = []
    plan_preview: list[dict[str, Any]] = []
    try:
        with _StdioMcpClient(mcp._cmd) as client:
            tool_names = client.list_tools()
            teams = mcp.list_teams(client, tool_names=tool_names)
            if not args.include_archived_teams:
                teams = [t for t in teams if not t.get("archivedAt")]

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
                        "week": iso_week,
                        "output": str(out_path),
                        "member_group": member_group,
                        "member_count": len(member_names) if member_group != "all" else None,
                        "teams": plan_preview,
                    },
                    ensure_ascii=False,
                    indent=2,
                ))
                return

            for t in teams:
                team_id = t.get("id") or t.get("teamId")
                if not team_id:
                    continue
                cycles = mcp.list_cycles_for_team(client, tool_names, team_id=team_id)
                last_week_cycles = _pick_cycles_for_week(cycles, iso_week)
                this_week_cycles = _pick_cycles_for_week(cycles, current_week)
                cycle = last_week_cycles[0] if last_week_cycles else (this_week_cycles[0] if this_week_cycles else None)
                statuses = mcp.list_issue_statuses(client, tool_names, team_id=team_id)
                status_type_map = {s.get("name", ""): s.get("type", "") for s in statuses if isinstance(s, dict)}
                team_all_issues = mcp.list_issues_for_team(client, tool_names, team_id=team_id)
                team_all_issues = _filter_issues_by_member_group(team_all_issues, member_names)
                uncycled_total, uncycled_skipped = count_uncycled_team_issues(
                    team_all_issues,
                    status_type_map,
                    include_completed=args.uncycled_include_completed,
                )

                if not cycle:
                    sections.append(
                        render_team_section(
                            {"name": t.get("name", str(team_id))},
                            None,
                            None,
                            now=now,
                            uncycled_total=uncycled_total,
                            uncycled_skipped_unknown=uncycled_skipped,
                            uncycled_include_completed=args.uncycled_include_completed,
                            view=args.view,
                            chart_style=chart_style,
                            owner_weekly_url_map=owner_weekly_url_map,
                        )
                    )
                    continue

                # 必须用 cycle 条件查询：全量 list_issues(team) 返回的 issue 往往无 cycle 字段，本地 filter 会得到空列表
                week_issues: list[dict[str, Any]] = []
                seen_keys: set[str] = set()
                for cyc in last_week_cycles:
                    cycle_id = cyc.get("id") or cyc.get("cycleId") or ""
                    if not cycle_id:
                        continue
                    batch = mcp.list_issues_in_cycle(client, tool_names, team_id=team_id, cycle_id=cycle_id)
                    for it in batch:
                        k = _issue_key(it)
                        if k in seen_keys:
                            continue
                        seen_keys.add(k)
                        week_issues.append(it)
                week_issues = _filter_issues_by_member_group(week_issues, member_names)
                grouped = group_issues(week_issues, status_type_map=status_type_map)

                this_week_issues: list[dict[str, Any]] = []
                seen_plan_keys: set[str] = set()
                for cyc in this_week_cycles:
                    cycle_id = cyc.get("id") or cyc.get("cycleId") or ""
                    if not cycle_id:
                        continue
                    batch = mcp.list_issues_in_cycle(client, tool_names, team_id=team_id, cycle_id=cycle_id)
                    for it in batch:
                        k = _issue_key(it)
                        if k in seen_plan_keys:
                            continue
                        seen_plan_keys.add(k)
                        this_week_issues.append(it)
                this_week_issues = _filter_issues_by_member_group(this_week_issues, member_names)

                def _status_type(it: dict[str, Any]) -> str:
                    sname = (it.get("status") or "").strip()
                    return (status_type_map.get(sname) or "").lower()

                progress_done_items = [
                    it
                    for it in week_issues
                    if _status_type(it) == "completed"
                    and (
                        _is_dt_in_iso_week(_parse_dt(it.get("completedAt")), iso_week)
                        or _is_dt_in_iso_week(_parse_dt(it.get("updatedAt")), iso_week)
                    )
                ]
                progress_planned_items = [
                    it
                    for it in week_issues
                    if _status_type(it) == "unstarted"
                    and _is_dt_in_iso_week(_parse_dt(it.get("updatedAt")), iso_week)
                ]
                weekly_plan_items = [
                    it for it in this_week_issues if _status_type(it) in ("started", "unstarted")
                ]
                disc = fetch_discussion_hints_from_comments(
                    mcp, client, tool_names, grouped.in_progress,
                )
                if personal_report_lookup_folder_id:
                    owner_names = list({
                        _assignee_name(it)
                        for it in (progress_done_items + progress_planned_items + weekly_plan_items)
                        if _assignee_name(it)
                    })
                    need_lookup = [n for n in owner_names if n not in owner_weekly_url_map]
                    if need_lookup:
                        try:
                            auto_map = _dingtalk_personal_report_url_map(
                                need_lookup,
                                personal_report_lookup_folder_id,
                            )
                            owner_weekly_url_map.update(auto_map)
                        except Exception:
                            pass
                sections.append(
                    render_team_section(
                        {"name": t.get("name", str(team_id))},
                        cycle,
                        grouped,
                        now=now,
                        cycle_issues=week_issues,
                        discussion_block=disc,
                        uncycled_total=uncycled_total,
                        uncycled_skipped_unknown=uncycled_skipped,
                        uncycled_include_completed=args.uncycled_include_completed,
                        status_type_map=status_type_map,
                        view=args.view,
                        chart_style=chart_style,
                        owner_weekly_url_map=owner_weekly_url_map,
                        progress_planned_items=progress_planned_items,
                        progress_done_items=progress_done_items,
                        weekly_plan_items=weekly_plan_items,
                    )
                )
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
    report = render_report(sections, iso_week=iso_week, member_group=member_group)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    auto_upload = not args.no_publish_dingtalk and bool(dt_url)
    need_folder_resolve = bool(dt_url) and (
        auto_upload or args.format == "json"
    )

    publish_folder_id: str | None = None
    folder_resolve_error: str | None = None
    week_subfolder = _dingtalk_week_subfolder_label(iso_week)

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

    publish = _build_publish_meta(
        iso_week,
        report,
        dingtalk_upload_folder_id=publish_folder_id,
        week_subfolder=week_subfolder,
        folder_resolve_error=folder_resolve_error,
        document_filename=doc_filename,
    )
    dingtalk_upload: dict[str, Any] | None = None

    if args.no_publish_dingtalk:
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

    if args.format == "json":
        payload: dict[str, Any] = {
            "skill": "superteam-report-team",
            "status": "ok",
            "week": iso_week,
            "output": str(out_path),
            "markdown": report,
            "publish": publish,
        }
        if dingtalk_upload is not None:
            payload["dingtalk"] = dingtalk_upload
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"已生成团队周报：{out_path}")
        if auto_upload and dingtalk_upload and dingtalk_upload.get("url"):
            print(f"钉钉文档：{dingtalk_upload['url']}")
        elif auto_upload and dingtalk_upload and dingtalk_upload.get("ok"):
            print("钉钉文档：已创建（响应中未解析到 URL，请在钉钉目录中查看）")


if __name__ == "__main__":
    main()

