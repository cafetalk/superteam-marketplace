#!/usr/bin/env python3
"""任务日快照：今日完成 / 已逾期 / 即将逾期 → sp_trex_pulse (type=task, period=daily)。

Usage:
  python skills/superteam-report/scripts/snapshot_task.py --dry-run
  python skills/superteam-report/scripts/snapshot_task.py --upload
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

_SHARED = Path(__file__).resolve().parents[2] / "_shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from pulse_snapshot_common import (
    default_pulse_out_root,
    default_snapshot_date,
    linear_client,
    list_teams,
    load_report_module,
    resolve_out_dir,
    upload_envelopes_to_pg,
    write_pulse_file,
)
from snapshot_member import (
    _due_tasks_block,
    _fetch_merged_cycle_issues,
    _projects_breakdown_for_member,
    per_owner_due_task_counts,
)
from snapshot_sprint import _load_config_env, _post_linear_graphql

TASK_TEAM_KEY = "trex"
TASK_TYPE = "task"
PERIOD_DAILY = "daily"

# 即将逾期：due 落在 (今日, 今日+N]（不含已逾期）
DEFAULT_DUE_SOON_DAYS = 7

# Linear 状态名（归一化后小写、多空格折叠）精确匹配
IN_REVIEW_STATUS_NORM = "in review"
PRODUCT_PENDING_STATUS_NORMS = frozenset({"todo", "prd review", "technical review"})

_LINEAR_ISSUE_IN_REVIEW_ENTERED_QUERY = """
query IssueInReviewEntered($id: String!) {
  issue(id: $id) {
    id
    identifier
    stateHistory(last: 50) {
      nodes {
        startedAt
        endedAt
        state { name }
      }
    }
    history(last: 50) {
      nodes {
        createdAt
        fromState { name }
        toState { name }
      }
    }
  }
}
"""


def _snapshot_ref_datetime(gtw: Any, snapshot_date: date) -> datetime:
    now = gtw._now_utc()
    if gtw._to_local_date(now) <= snapshot_date:
        return now
    local_tz = now.tzinfo
    return datetime.combine(snapshot_date, time(23, 59, 59), tzinfo=local_tz)


def _norm_status_name(name: str) -> str:
    return " ".join((name or "").strip().lower().split())



REQUIREMENT_LABEL_NORM = "requirement"


def _has_requirement_label(gtw: Any, it: dict[str, Any]) -> bool:
    """labels 含 Requirement（大小写不敏感）。"""
    return REQUIREMENT_LABEL_NORM in gtw._issue_label_tokens(it)


def _issue_due_date(gtw: Any, it: dict[str, Any]) -> date | None:
    for key in ("dueDate", "targetDate", "endDate"):
        d = gtw._parse_project_date_field(it.get(key))
        if d is not None:
            return d
    return None


def _serialize_task_row(
    it: dict[str, Any],
    *,
    gtw: Any,
    ref_day: date,
    kind: str,
) -> dict[str, Any]:
    due = _issue_due_date(gtw, it)
    completed = gtw._parse_dt(it.get("completedAt"))
    row: dict[str, Any] = {
        "id": gtw._issue_key(it),
        "title": gtw._issue_title_without_identifier(it),
        "url": str(it.get("url") or "").strip() or None,
        "project": gtw._issue_project_name(it),
        "assignee": gtw._assignee_name(it) or None,
        "status": str(it.get("status") or "").strip() or None,
        "team": str(it.get("team") or it.get("teamName") or "").strip() or None,
        "due_date": due.isoformat() if due else None,
        "completed_at": completed.isoformat() if completed else None,
    }
    if kind == "overdue" and due is not None:
        row["days_overdue"] = (ref_day - due).days
    if kind == "due_soon" and due is not None:
        row["days_until_due"] = (due - ref_day).days
    return row


def _sort_completed(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: (r.get("project") or "", r.get("id") or ""))


def _sort_by_due_urgency(
    rows: list[dict[str, Any]],
    *,
    overdue: bool,
) -> list[dict[str, Any]]:
    key = "days_overdue" if overdue else "days_until_due"
    return sorted(
        rows,
        key=lambda r: (-int(r.get(key) or 0), r.get("project") or "", r.get("id") or ""),
    )


def classify_task_dimensions(
    issues: list[dict[str, Any]],
    *,
    gtw: Any,
    status_type_map: dict[str, str],
    snapshot_date: date,
    due_soon_days: int = DEFAULT_DUE_SOON_DAYS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """返回 (completed_today, overdue, due_soon) 三条 issue 列表（dict 行）。"""
    ref_day = snapshot_date
    due_soon_end = ref_day + timedelta(days=due_soon_days)

    completed_today: list[dict[str, Any]] = []
    overdue: list[dict[str, Any]] = []
    due_soon: list[dict[str, Any]] = []

    for it in issues:
        bucket = gtw._state_bucket_for_issue(it, status_type_map)
        if bucket == "canceled":
            continue

        completed = gtw._parse_dt(it.get("completedAt"))
        if bucket == "done" or gtw._linear_issue_status_type_lower(it, status_type_map) == "completed":
            if completed and gtw._to_local_date(completed) == ref_day:
                completed_today.append(
                    _serialize_task_row(it, gtw=gtw, ref_day=ref_day, kind="completed_today"),
                )
            continue

        due = _issue_due_date(gtw, it)
        if due is None:
            continue

        if due < ref_day:
            overdue.append(_serialize_task_row(it, gtw=gtw, ref_day=ref_day, kind="overdue"))
        elif ref_day < due <= due_soon_end:
            due_soon.append(_serialize_task_row(it, gtw=gtw, ref_day=ref_day, kind="due_soon"))

    return (
        _sort_completed(completed_today),
        _sort_by_due_urgency(overdue, overdue=True),
        _sort_by_due_urgency(due_soon, overdue=False),
    )


def _is_in_review_issue(
    it: dict[str, Any],
    *,
    gtw: Any,
    status_type_map: dict[str, str],
) -> bool:
    if gtw._state_bucket_for_issue(it, status_type_map) == "canceled":
        return False
    return _norm_status_name(str(it.get("status") or "")) == IN_REVIEW_STATUS_NORM


def list_in_review_issues(
    issues: list[dict[str, Any]],
    *,
    gtw: Any,
    status_type_map: dict[str, str],
) -> list[dict[str, Any]]:
    """状态名为 In Review（不含 Prd Review / Technical Review）的未取消任务。"""
    return [
        it for it in issues
        if _is_in_review_issue(it, gtw=gtw, status_type_map=status_type_map)
    ]


def _entered_at_from_state_history_nodes(
    nodes: list[Any],
    *,
    gtw: Any,
) -> datetime | None:
    """当前仍在 In Review 的 stateHistory 片段的 startedAt。"""
    for n in nodes:
        if not isinstance(n, dict):
            continue
        state = n.get("state") if isinstance(n.get("state"), dict) else {}
        if _norm_status_name(str(state.get("name") or "")) != IN_REVIEW_STATUS_NORM:
            continue
        if n.get("endedAt"):
            continue
        started = gtw._parse_dt(n.get("startedAt"))
        if started is not None:
            return started
    return None


def _entered_at_from_issue_history_nodes(
    nodes: list[Any],
    *,
    gtw: Any,
) -> datetime | None:
    """最近一次迁入 In Review 的 history.createdAt。"""
    latest: datetime | None = None
    for n in nodes:
        if not isinstance(n, dict):
            continue
        to_state = n.get("toState") if isinstance(n.get("toState"), dict) else {}
        if _norm_status_name(str(to_state.get("name") or "")) != IN_REVIEW_STATUS_NORM:
            continue
        created = gtw._parse_dt(n.get("createdAt"))
        if created is not None and (latest is None or created > latest):
            latest = created
    return latest


def _fetch_in_review_entered_graphql(issue_key: str) -> dict[str, Any] | None:
    api_key = _load_config_env("LINEAR_API_KEY") or _load_config_env("LINEAR_MCP_TOKEN")
    if not api_key:
        return None
    api_url = _load_config_env("LINEAR_API_URL") or "https://api.linear.app/graphql"
    payload = _post_linear_graphql(
        api_url,
        api_key,
        _LINEAR_ISSUE_IN_REVIEW_ENTERED_QUERY,
        {"id": issue_key},
    )
    if not isinstance(payload, dict) or payload.get("_error"):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    issue = data.get("issue")
    return issue if isinstance(issue, dict) else None


def resolve_in_review_entered_at(
    it: dict[str, Any],
    *,
    gtw: Any,
    graphql_cache: dict[str, dict[str, Any] | None] | None = None,
) -> tuple[datetime | None, str]:
    """返回 (进入 In Review 的时刻, 来源标签)。"""
    issue_key = str(gtw._issue_key(it) or "").strip()
    if issue_key:
        cache = graphql_cache if graphql_cache is not None else {}
        if issue_key not in cache:
            cache[issue_key] = _fetch_in_review_entered_graphql(issue_key)
        gql_issue = cache.get(issue_key)
        if isinstance(gql_issue, dict):
            state_nodes = ((gql_issue.get("stateHistory") or {}).get("nodes") or [])
            entered = _entered_at_from_state_history_nodes(state_nodes, gtw=gtw)
            if entered is not None:
                return entered, "linear_stateHistory"
            hist_nodes = ((gql_issue.get("history") or {}).get("nodes") or [])
            entered = _entered_at_from_issue_history_nodes(hist_nodes, gtw=gtw)
            if entered is not None:
                return entered, "linear_history"

    updated = gtw._parse_dt(it.get("updatedAt"))
    if updated is not None:
        return updated, "updatedAt_fallback"
    return None, "unknown"


def longest_in_review_metric(
    in_review_issues: list[dict[str, Any]],
    *,
    gtw: Any,
    ref_now: datetime,
    graphql_cache: dict[str, dict[str, Any] | None] | None = None,
) -> dict[str, Any] | None:
    """In Review 持续时间最长的任务及其进入 In Review 的时刻。"""
    best_issue: dict[str, Any] | None = None
    best_entered: datetime | None = None
    best_source = "unknown"

    for it in in_review_issues:
        entered, source = resolve_in_review_entered_at(
            it, gtw=gtw, graphql_cache=graphql_cache,
        )
        if entered is None:
            continue
        if best_entered is None or entered < best_entered:
            best_issue = it
            best_entered = entered
            best_source = source

    if best_issue is None or best_entered is None:
        return None

    days_in_review = max(0, (ref_now - best_entered).days)
    return {
        "entered_at": best_entered.isoformat(),
        "entered_at_source": best_source,
        "days_in_review": days_in_review,
        "task": {
            "id": gtw._issue_key(best_issue),
            "title": gtw._issue_title_without_identifier(best_issue),
            "url": str(best_issue.get("url") or "").strip() or None,
            "project": gtw._issue_project_name(best_issue),
            "assignee": gtw._assignee_name(best_issue) or None,
        },
    }


def classify_product_created_pending(
    issues: list[dict[str, Any]],
    *,
    gtw: Any,
    status_type_map: dict[str, str],
    ref_day: date,
) -> list[dict[str, Any]]:
    """labels 含 Requirement 且状态为 Todo / Prd Review / Technical Review 的任务列表。"""
    rows: list[dict[str, Any]] = []
    for it in issues:
        if gtw._state_bucket_for_issue(it, status_type_map) == "canceled":
            continue
        if not _has_requirement_label(gtw, it):
            continue
        st_norm = _norm_status_name(str(it.get("status") or "").strip())
        if st_norm not in PRODUCT_PENDING_STATUS_NORMS:
            continue
        creator = str(it.get("createdBy") or "").strip()
        row = _serialize_task_row(it, gtw=gtw, ref_day=ref_day, kind="product_created_pending")
        row["created_by"] = creator or None
        rows.append(row)
    return sorted(rows, key=lambda r: (r.get("project") or "", r.get("id") or ""))


def _filter_rows_to_assignee_names(
    rows: list[dict[str, Any]],
    *,
    assignee_names: set[str],
) -> list[dict[str, Any]]:
    if not assignee_names:
        return []
    return [
        r for r in rows
        if (str(r.get("assignee") or "").strip() in assignee_names)
    ]


def build_assignee_due_summary(
    cycle_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    *,
    gtw: Any,
    iso_week: str,
    snapshot_date: date,
    due_soon_days: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """按 assignee 汇总逾期/即将逾期（与 snapshot_member members[] + team_summary 同源）。"""
    known_members = gtw._report_member_assignee_names()
    owner_due = per_owner_due_task_counts(
        cycle_issues,
        status_type_map,
        gtw=gtw,
        ref_day=snapshot_date,
        due_soon_days=due_soon_days,
    )
    workload_by_owner = {
        str(r.get("owner") or ""): r
        for r in gtw._member_workload_rows(cycle_issues, status_type_map, iso_week)
    }
    assignees: list[dict[str, Any]] = []
    for owner in sorted(known_members, key=gtw._member_owner_section_sort_key):
        _, totals = _projects_breakdown_for_member(
            cycle_issues,
            owner,
            iso_week=iso_week,
            status_type_map=status_type_map,
            gtw=gtw,
        )
        wl = workload_by_owner.get(owner)
        if not wl and totals["total"] == 0:
            continue
        assignees.append({
            "name": owner,
            "due_tasks": _due_tasks_block(
                owner_due.get(owner, {}),
                due_soon_days=due_soon_days,
            ),
        })

    def _sum_due(key: str) -> int:
        return sum(int((a.get("due_tasks") or {}).get(key) or 0) for a in assignees)

    team_summary = {
        "overdue_open_total": _sum_due("overdue"),
        "due_soon_open_total": _sum_due("due_soon"),
        "no_due_date_open_total": _sum_due("no_due_date"),
    }
    return assignees, team_summary


def build_task_payload(
    *,
    completed_today: list[dict[str, Any]],
    overdue: list[dict[str, Any]],
    due_soon: list[dict[str, Any]],
    in_review_count: int,
    longest_in_review_entered_at: str | None,
    longest_in_review: dict[str, Any] | None,
    product_created_pending: list[dict[str, Any]],
    by_assignee: list[dict[str, Any]],
    team_summary: dict[str, int],
    snapshot_date: date,
    iso_week: str,
    due_soon_days: int,
    issue_pool_size: int,
    cycle_issue_count: int,
    cycle_notes: list[str],
) -> dict[str, Any]:
    overdue_total = int(team_summary.get("overdue_open_total") or 0)
    due_soon_total = int(team_summary.get("due_soon_open_total") or 0)
    return {
        "section": "任务日快照",
        "snapshot_date": snapshot_date.isoformat(),
        "team": TASK_TEAM_KEY,
        "iso_week": iso_week,
        "due_soon_days": due_soon_days,
        "cycle_notes": cycle_notes,
        "summary": {
            "completed_today_count": len(completed_today),
            "overdue_count": overdue_total,
            "due_soon_count": due_soon_total,
            "in_review_count": in_review_count,
            "longest_in_review_entered_at": longest_in_review_entered_at,
            "product_created_pending_count": len(product_created_pending),
            "issue_pool_size": issue_pool_size,
            "cycle_issue_count": cycle_issue_count,
        },
        "team_summary": team_summary,
        "by_assignee": by_assignee,
        "dimensions": {
            "completed_today": {
                "label": "今日完成",
                "metric": "completed_today_count",
                "count": len(completed_today),
                "rule": "completedAt 落在 snapshot_date 当日（本地日历）",
                "issues": completed_today,
            },
            "overdue": {
                "label": "已逾期",
                "metric": "overdue_count",
                "count": overdue_total,
                "rule": (
                    "与 snapshot_member 一致：当前自然周 Cycle 内未完成任务、"
                    "due 早于 snapshot_date；team_summary 仅累加 members[] 内 assignee"
                ),
                "issue_pool": "cycle",
                "issues": overdue,
                "by_assignee": by_assignee,
            },
            "due_soon": {
                "label": "即将逾期",
                "metric": "due_soon_count",
                "count": due_soon_total,
                "rule": (
                    f"与 snapshot_member 一致：Cycle 内未完成、"
                    f"due 在 (snapshot_date, snapshot_date+{due_soon_days}]；"
                    f"team_summary 仅累加 members[] 内 assignee"
                ),
                "window_days": due_soon_days,
                "issue_pool": "cycle",
                "issues": due_soon,
                "by_assignee": by_assignee,
            },
            "in_review": {
                "label": "In Review",
                "metric": "in_review_count",
                "count": in_review_count,
                "rule": "状态名精确为 In Review（不含 Prd Review / Technical Review）；已取消除外",
                "longest_in_review_entered_at": longest_in_review_entered_at,
                "longest_in_review_entered_at_metric": "longest_in_review_entered_at",
                "longest_in_review_entered_at_rule": (
                    "当前 In Review 任务中持续时间最长者；"
                    "优先 Linear stateHistory.startedAt，"
                    "其次 history 迁入 In Review 的 createdAt，"
                    "最后回退 issue.updatedAt"
                ),
                "longest_in_review": longest_in_review,
            },
            "product_created_pending": {
                "label": "产品待推进",
                "metric": "product_created_pending_count",
                "count": len(product_created_pending),
                "rule": (
                    "labels 含 Requirement；"
                    "状态为 Todo / Prd Review / Technical Review；"
                    "issue 池含 Backlog 状态 Linear Project（其余维度仍仅 Planned/In Progress）"
                ),
                "statuses": ["Todo", "Prd Review", "Technical Review"],
                "issues": product_created_pending,
            },
        },
        "data_scope": {
            "source": "Linear MCP list_issues(team) 全 workspace 合并去重",
            "teams": "全部未归档 Team",
            "excluded_projects": "与 sprint 一致：非 Planned/In Progress 的 Linear Project（不含 Backlog）",
            "excluded_projects_product_pending": (
                "product_created_pending 专用：仅排除 Completed/Canceled 等项目，"
                "保留 Backlog + Planned + In Progress"
            ),
            "due_field": "dueDate → targetDate → endDate（首个可解析日历日）",
            "requirement_label": "product_created_pending：issue labels 含 Requirement（大小写不敏感）",
            "in_review_entered_at": (
                "Linear GraphQL stateHistory / history（需 LINEAR_API_KEY）；"
                "无密钥时回退 updatedAt"
            ),
            "due_by_assignee": (
                "与 snapshot_member 完全一致：各 Team 与 iso_week 重叠的 Cycle issue 合并去重；"
                "无过期项目过滤；team_summary 与 members[].due_tasks 累加口径相同"
            ),
        },
    }


def _fetch_merged_workspace_issues(
    *,
    gtw: Any,
    mcp: Any,
    client: Any,
    tool_names: set[str],
    iso_week: str,
    snapshot_date: date,
    include_archived_teams: bool,
) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    report_week_start = gtw._report_week_start_date(iso_week)
    ref_now = _snapshot_ref_datetime(gtw, snapshot_date)
    all_linear_projects = gtw._enrich_linear_projects(
        mcp,
        client,
        tool_names,
        mcp.list_projects(client, tool_names),
    )
    excluded_project_names = gtw._excluded_report_project_names(
        all_linear_projects,
        ref=ref_now.date(),
        report_week_start=report_week_start,
    )
    excluded_product_pending_names = gtw._excluded_report_project_names_for_product_pending(
        all_linear_projects,
        ref=ref_now.date(),
        report_week_start=report_week_start,
    )

    merged_status: dict[str, str] = {}
    merged: list[dict[str, Any]] = []
    merged_product_pending: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_product_pending: set[str] = set()

    for t in list_teams(gtw, mcp, client, tool_names, include_archived=include_archived_teams):
        team_id = t.get("id") or t.get("teamId")
        if not team_id:
            continue
        for s in mcp.list_issue_statuses(client, tool_names, team_id=team_id):
            if isinstance(s, dict):
                merged_status[s.get("name", "")] = s.get("type", "")

        batch = mcp.list_issues_for_team(client, tool_names, team_id=team_id)
        for it in gtw._filter_issues_excluding_projects(batch, excluded_project_names):
            k = gtw._issue_key(it)
            if not k or k in seen:
                continue
            seen.add(k)
            merged.append(it)
        for it in gtw._filter_issues_excluding_projects(batch, excluded_product_pending_names):
            k = gtw._issue_key(it)
            if not k or k in seen_product_pending:
                continue
            seen_product_pending.add(k)
            merged_product_pending.append(it)

    return merged, merged_status, merged_product_pending


def snapshot_task(
    *,
    snapshot_date: date,
    out_root: Path,
    dry_run: bool = False,
    upload_to_pg: bool = False,
    include_archived_teams: bool = False,
    due_soon_days: int = DEFAULT_DUE_SOON_DAYS,
) -> tuple[dict[str, Any], int]:
    gtw = load_report_module()
    iso_week = gtw._iso_week_for_date(snapshot_date)
    out_dir = resolve_out_dir(out_root, snapshot_date)
    envelopes: list[dict[str, Any]] = []

    for client, mcp, tool_names in linear_client(gtw):
        issues, status_map, issues_for_product_pending = _fetch_merged_workspace_issues(
            gtw=gtw,
            mcp=mcp,
            client=client,
            tool_names=tool_names,
            iso_week=iso_week,
            snapshot_date=snapshot_date,
            include_archived_teams=include_archived_teams,
        )
        cycle_issues, cycle_status_map, _cycles, cycle_notes = _fetch_merged_cycle_issues(
            gtw=gtw,
            mcp=mcp,
            client=client,
            tool_names=tool_names,
            iso_week=iso_week,
            include_archived_teams=include_archived_teams,
        )
        completed, _, _ = classify_task_dimensions(
            issues,
            gtw=gtw,
            status_type_map=status_map,
            snapshot_date=snapshot_date,
            due_soon_days=due_soon_days,
        )
        _, overdue, due_soon = classify_task_dimensions(
            cycle_issues,
            gtw=gtw,
            status_type_map=cycle_status_map,
            snapshot_date=snapshot_date,
            due_soon_days=due_soon_days,
        )
        ref_now = _snapshot_ref_datetime(gtw, snapshot_date)
        in_review_issues = list_in_review_issues(
            issues,
            gtw=gtw,
            status_type_map=status_map,
        )
        in_review_count = len(in_review_issues)
        graphql_cache: dict[str, dict[str, Any] | None] = {}
        longest_in_review = longest_in_review_metric(
            in_review_issues,
            gtw=gtw,
            ref_now=ref_now,
            graphql_cache=graphql_cache,
        )
        longest_in_review_entered_at = (
            longest_in_review.get("entered_at") if longest_in_review else None
        )
        product_created_pending = classify_product_created_pending(
            issues_for_product_pending,
            gtw=gtw,
            status_type_map=status_map,
            ref_day=snapshot_date,
        )
        by_assignee, team_summary = build_assignee_due_summary(
            cycle_issues,
            cycle_status_map,
            gtw=gtw,
            iso_week=iso_week,
            snapshot_date=snapshot_date,
            due_soon_days=due_soon_days,
        )
        included_assignees = {a["name"] for a in by_assignee}
        overdue = _filter_rows_to_assignee_names(overdue, assignee_names=included_assignees)
        due_soon = _filter_rows_to_assignee_names(due_soon, assignee_names=included_assignees)
        payload = build_task_payload(
            completed_today=completed,
            overdue=overdue,
            due_soon=due_soon,
            in_review_count=in_review_count,
            longest_in_review_entered_at=longest_in_review_entered_at,
            longest_in_review=longest_in_review,
            product_created_pending=product_created_pending,
            by_assignee=by_assignee,
            team_summary=team_summary,
            snapshot_date=snapshot_date,
            iso_week=iso_week,
            due_soon_days=due_soon_days,
            issue_pool_size=len(issues),
            cycle_issue_count=len(cycle_issues),
            cycle_notes=cycle_notes,
        )
        envelope = {
            "snapshot_date": snapshot_date.isoformat(),
            "team": TASK_TEAM_KEY,
            "type": TASK_TYPE,
            "period": PERIOD_DAILY,
            "payload": payload,
        }
        entry: dict[str, Any] = {
            "team": TASK_TEAM_KEY,
            "type": TASK_TYPE,
            "period": PERIOD_DAILY,
            "summary": payload["summary"],
            "payload": payload,
        }
        upload_count = 0
        if not dry_run:
            entry["file"] = str(write_pulse_file(out_dir, envelope))
            if upload_to_pg:
                upload_count = upload_envelopes_to_pg([envelope])
                entry["uploaded"] = True
        return entry, upload_count

    raise RuntimeError("Linear MCP 未返回可用客户端")


def main() -> int:
    p = argparse.ArgumentParser(description="任务日快照 — 今日完成 / 已逾期 / 即将逾期")
    p.add_argument("--date", default=None, help="snapshot_date YYYY-MM-DD（默认今天）")
    p.add_argument(
        "--out-dir",
        default=str(default_pulse_out_root()),
        help="pulse 根目录（默认 ~/.superteam/pulse）",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--upload", action="store_true", help="落盘 + upsert sp_trex_pulse")
    p.add_argument("--include-archived-teams", action="store_true")
    p.add_argument(
        "--due-soon-days",
        type=int,
        default=DEFAULT_DUE_SOON_DAYS,
        help=f"即将逾期窗口天数（默认 {DEFAULT_DUE_SOON_DAYS}）",
    )
    args = p.parse_args()

    snapshot_date = default_snapshot_date(args.date)
    out_root = Path(args.out_dir)

    try:
        entry, upload_count = snapshot_task(
            snapshot_date=snapshot_date,
            out_root=out_root,
            dry_run=args.dry_run,
            upload_to_pg=args.upload,
            include_archived_teams=args.include_archived_teams,
            due_soon_days=max(1, int(args.due_soon_days)),
        )
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "type": TASK_TYPE,
                "period": PERIOD_DAILY,
                "team": TASK_TEAM_KEY,
                "snapshot_date": snapshot_date.isoformat(),
                "out_dir": str(resolve_out_dir(out_root, snapshot_date)),
                "uploaded": bool(args.upload and not args.dry_run),
                "upload_count": upload_count,
                "entry": entry,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
