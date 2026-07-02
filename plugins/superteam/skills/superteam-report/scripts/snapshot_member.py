#!/usr/bin/env python3
"""TREX-493：workspace 级「成员本周快照」（与 snapshot_sprint 对齐，每天执行）。

默认统计**快照日所在自然周**（``_iso_week_for_date(snapshot_date)``），与 sprint 日快照节奏相同，每天更新。
每人包含：本周参与项目及待开始/进行中/完成数量、Cycle 负载、Git 代码变更、风险信号。

Usage:
  python skills/superteam-report/scripts/snapshot_member.py --upload
  python skills/superteam-report/scripts/snapshot_member.py --week 2026-W21 --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

_SHARED = Path(__file__).resolve().parents[2] / "_shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from pulse_snapshot_common import (
    cycle_to_json,
    default_pulse_out_root,
    default_snapshot_date,
    issue_pulse_bucket,
    linear_client,
    list_teams,
    load_report_module,
    resolve_out_dir,
    status_type_map_for_team,
    upload_envelopes_to_pg,
    write_pulse_file,
)

MEMBER_TEAM_KEY = "trex"

# 即将逾期：due 落在 (snapshot_date, snapshot_date+N]（与 snapshot_task 一致）
DEFAULT_DUE_SOON_DAYS = 7


def _member_risks(
    owner: str,
    cycle_issues: list[dict[str, Any]],
    *,
    status_type_map: dict[str, str],
    gtw: Any,
    now: Any,
    workload: dict[str, Any],
    assignee_names: set[str] | None = None,
) -> dict[str, Any]:
    """成员风险摘要（Linear 任务标签 + 负载，无 SPI/RDI/OCI）。"""
    risk_counts: dict[str, int] = defaultdict(int)
    open_n = 0
    for it in cycle_issues:
        who = (gtw._assignee_name(it) or "").strip()
        if assignee_names:
            if who not in assignee_names:
                continue
        elif who != owner:
            continue
        if gtw._state_bucket_for_issue(it, status_type_map) in ("done", "canceled"):
            continue
        open_n += 1
        for r in gtw._issue_risk_reasons(it, status_type_map, now):
            risk_counts[r] += 1
    risk_short = "；".join(
        f"{k}×{v}" for k, v in sorted(risk_counts.items(), key=lambda x: -x[1])
    )
    load_pct = workload.get("load_percent")
    return {
        "open_tasks": open_n,
        "risk_counts": dict(risk_counts),
        "risk_short": risk_short,
        "load_high": bool(workload.get("load_high")),
        "load_percent": load_pct,
    }


def _triple_task_bucket(
    it: dict[str, Any],
    status_type_map: dict[str, str],
    gtw: Any,
) -> str:
    """待开始 / 进行中 / 完成 三分类（In Review 并入进行中）。"""
    if gtw._state_bucket_for_issue(it, status_type_map) == "done":
        return "done"
    b = issue_pulse_bucket(it, status_type_map, gtw)
    if b in ("in_progress", "in_review", "blocked"):
        return "in_progress"
    return "todo"


def _completed_in_week(
    it: dict[str, Any],
    iso_week: str,
    gtw: Any,
    status_type_map: dict[str, str],
) -> bool:
    if gtw._state_bucket_for_issue(it, status_type_map) != "done":
        st = gtw._linear_issue_status_type_lower(it, status_type_map)
        if st != "completed":
            return False
    dt = gtw._parse_dt(it.get("completedAt"))
    if not dt:
        return False
    return gtw._is_dt_in_iso_week(dt, iso_week)


def _member_primary_name(m: dict[str, Any]) -> str:
    return str(m.get("real_name") or m.get("realName") or m.get("username") or "").strip()


def _member_assignee_alias_set(m: dict[str, Any], gtw: Any) -> set[str]:
    return {n.strip() for n in gtw._member_display_names(m) if n and str(n).strip()}


def _merge_int_metric_dicts(*parts: dict[str, int]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for part in parts:
        for key, val in part.items():
            out[key] += int(val or 0)
    return dict(out)


def _merge_workload_rows(rows: list[dict[str, Any]], *, owner: str) -> dict[str, Any]:
    if not rows:
        return {
            "owner": owner,
            "total": 0,
            "done": 0,
            "in_progress": 0,
            "todo": 0,
            "backlog": 0,
            "open": 0,
            "active": 0,
            "other": 0,
            "canceled": 0,
            "hours_total": 0.0,
            "hours_done": 0.0,
            "hours_open": 0.0,
            "hours_filled": 0,
            "done_pct": 0.0,
        }
    if len(rows) == 1:
        return {**rows[0], "owner": owner}
    merged: dict[str, Any] = {
        "owner": owner,
        "total": 0,
        "done": 0,
        "in_progress": 0,
        "todo": 0,
        "backlog": 0,
        "open": 0,
        "active": 0,
        "other": 0,
        "canceled": 0,
        "hours_total": 0.0,
        "hours_done": 0.0,
        "hours_open": 0.0,
        "hours_filled": 0,
    }
    for row in rows:
        for key in (
            "total", "done", "in_progress", "todo", "backlog", "open",
            "active", "other", "canceled", "hours_filled",
        ):
            merged[key] += int(row.get(key) or 0)
        for key in ("hours_total", "hours_done", "hours_open"):
            merged[key] += float(row.get(key) or 0.0)
    n_active = int(merged["active"])
    merged["done_pct"] = (int(merged["done"]) / n_active * 100.0) if n_active else 0.0
    return merged


def _lookup_code_stats(
    code_lookup: dict[str, dict[str, int]] | None,
    aliases: set[str],
) -> dict[str, int] | None:
    if not code_lookup:
        return None
    for alias in aliases:
        stats = code_lookup.get(alias)
        if stats:
            return stats
    return None


def _role_fields(gtw: Any, report_m: dict[str, Any] | None) -> dict[str, Any]:
    if not report_m:
        return {"role": "", "role_bucket": "other"}
    role = str(report_m.get("role") or "")
    bucket = gtw._role_bucket_for_weekly(role)
    if bucket:
        return {"role": role, "role_bucket": bucket}
    if gtw._role_string_indicates_qa(role):
        return {"role": role, "role_bucket": "test"}
    return {"role": role, "role_bucket": "other"}


def _projects_breakdown_for_member(
    issues: list[dict[str, Any]],
    owner: str,
    *,
    assignee_names: set[str] | None = None,
    iso_week: str,
    status_type_map: dict[str, str],
    gtw: Any,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """上周报告周内有状态变化的任务，按项目汇总三态数量。"""
    names = assignee_names if assignee_names is not None else {owner}
    by_proj: dict[str, dict[str, int]] = defaultdict(
        lambda: {"done": 0, "in_progress": 0, "todo": 0},
    )
    for it in issues:
        if gtw._state_bucket_for_issue(it, status_type_map) == "canceled":
            continue
        if (gtw._assignee_name(it) or "").strip() not in names:
            continue
        if not gtw._issue_in_member_week_activity_scope(it, iso_week, status_type_map):
            continue
        pname = gtw._issue_project_name(it)
        cat = _triple_task_bucket(it, status_type_map, gtw)
        by_proj[pname][cat] += 1

    projects: list[dict[str, Any]] = []
    totals = {"done": 0, "in_progress": 0, "todo": 0, "total": 0}
    for pname in sorted(by_proj.keys()):
        c = by_proj[pname]
        total = c["done"] + c["in_progress"] + c["todo"]
        totals["done"] += c["done"]
        totals["in_progress"] += c["in_progress"]
        totals["todo"] += c["todo"]
        totals["total"] += total
        projects.append({
            "project": pname,
            "done": c["done"],
            "in_progress": c["in_progress"],
            "todo": c["todo"],
            "total": total,
        })
    return projects, totals


def _per_owner_cycle_extras(
    issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    *,
    gtw: Any,
    iso_week: str,
) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(
        lambda: {"in_review": 0, "blocked": 0, "done_this_week": 0},
    )
    for it in issues:
        if gtw._state_bucket_for_issue(it, status_type_map) == "canceled":
            continue
        owner = gtw._assignee_name(it) or "未分配"
        b = issue_pulse_bucket(it, status_type_map, gtw)
        if b == "in_review":
            out[owner]["in_review"] += 1
        if b == "blocked":
            out[owner]["blocked"] += 1
        if _completed_in_week(it, iso_week, gtw, status_type_map):
            out[owner]["done_this_week"] += 1
    return out


def _issue_due_date(gtw: Any, it: dict[str, Any]) -> date | None:
    for key in ("dueDate", "targetDate", "endDate"):
        d = gtw._parse_project_date_field(it.get(key))
        if d is not None:
            return d
    return None


def _is_open_cycle_issue(
    it: dict[str, Any],
    status_type_map: dict[str, str],
    gtw: Any,
) -> bool:
    bucket = gtw._state_bucket_for_issue(it, status_type_map)
    if bucket in ("canceled", "done"):
        return False
    if gtw._linear_issue_status_type_lower(it, status_type_map) == "completed":
        return False
    return True


def per_owner_due_task_counts(
    issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    *,
    gtw: Any,
    ref_day: date,
    due_soon_days: int = DEFAULT_DUE_SOON_DAYS,
) -> dict[str, dict[str, int]]:
    """Cycle 内未完成任务：按 assignee 汇总已逾期 / 即将逾期 / 无截止时间。"""
    out: dict[str, dict[str, int]] = defaultdict(
        lambda: {"overdue": 0, "due_soon": 0, "no_due_date": 0},
    )
    due_soon_end = ref_day + timedelta(days=due_soon_days)
    for it in issues:
        if not _is_open_cycle_issue(it, status_type_map, gtw):
            continue
        owner = gtw._assignee_name(it) or "未分配"
        due = _issue_due_date(gtw, it)
        if due is None:
            out[owner]["no_due_date"] += 1
        elif due < ref_day:
            out[owner]["overdue"] += 1
        elif ref_day < due <= due_soon_end:
            out[owner]["due_soon"] += 1
    return out


def _due_tasks_block(
    counts: dict[str, int],
    *,
    due_soon_days: int,
) -> dict[str, Any]:
    return {
        "overdue": int(counts.get("overdue") or 0),
        "due_soon": int(counts.get("due_soon") or 0),
        "no_due_date": int(counts.get("no_due_date") or 0),
        "due_soon_days": due_soon_days,
    }


def _workload_block(
    wl: dict[str, Any],
    *,
    gtw: Any,
    extras: dict[str, int],
) -> dict[str, Any]:
    base = gtw._workload_row_to_json(wl)
    todo = int(base.get("todo") or 0)
    backlog = int(base.get("backlog") or 0)
    return {
        **base,
        "active": int(wl.get("active") or 0),
        "other": int(wl.get("other") or 0),
        "canceled": int(wl.get("canceled") or 0),
        "todo_and_backlog": todo + backlog,
        "in_review": int(extras.get("in_review") or 0),
        "blocked": int(extras.get("blocked") or 0),
        "done_this_week": int(extras.get("done_this_week") or 0),
        "done_pct": round(float(wl.get("done_pct") or 0.0), 1),
    }


def _code_block(
    stats: dict[str, int] | None,
) -> dict[str, Any] | None:
    if not stats:
        return None
    ins = int(stats.get("insertions") or 0)
    dels = int(stats.get("deletions") or 0)
    if ins == 0 and dels == 0 and int(stats.get("active_days") or 0) == 0:
        return None
    return {
        "insertions": ins,
        "deletions": dels,
        "net_lines": ins - dels,
        "active_days": int(stats.get("active_days") or 0),
    }


def build_workspace_member_payload(
    cycle_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    *,
    gtw: Any,
    iso_week: str,
    snapshot_date: date,
    cycles: list[dict[str, Any]],
    cycle_notes: list[str],
    code_lookup: dict[str, dict[str, int]] | None,
    now: datetime,
) -> dict[str, Any]:
    week_start_s, week_end_s = gtw._week_date_range(iso_week)
    report_members = list(gtw._iter_report_members())
    owner_extras = _per_owner_cycle_extras(
        cycle_issues, status_type_map, gtw=gtw, iso_week=iso_week,
    )
    owner_due = per_owner_due_task_counts(
        cycle_issues,
        status_type_map,
        gtw=gtw,
        ref_day=snapshot_date,
        due_soon_days=DEFAULT_DUE_SOON_DAYS,
    )
    workload_by_owner = {
        str(r.get("owner") or ""): r
        for r in gtw._member_workload_rows(cycle_issues, status_type_map, iso_week)
    }

    members: list[dict[str, Any]] = []
    for report_m in sorted(
        report_members,
        key=lambda m: gtw._member_owner_section_sort_key(_member_primary_name(m)),
    ):
        owner = _member_primary_name(report_m)
        if not owner:
            continue
        aliases = _member_assignee_alias_set(report_m, gtw)
        projects, totals = _projects_breakdown_for_member(
            cycle_issues,
            owner,
            assignee_names=aliases,
            iso_week=iso_week,
            status_type_map=status_type_map,
            gtw=gtw,
        )
        alias_workloads = [
            workload_by_owner[alias]
            for alias in aliases
            if alias in workload_by_owner
        ]
        wl = _merge_workload_rows(alias_workloads, owner=owner)
        extras = _merge_int_metric_dicts(
            *(owner_extras.get(alias, {}) for alias in aliases),
        )
        workload = _workload_block(wl, gtw=gtw, extras=extras)
        code_stats = _lookup_code_stats(code_lookup, aliases)
        uid = str(report_m.get("user_id") or report_m.get("id") or "") or None
        members.append({
            "name": owner,
            "user_id": uid,
            **_role_fields(gtw, report_m),
            "totals": totals,
            "projects": projects,
            "workload": workload,
            "due_tasks": _due_tasks_block(
                _merge_int_metric_dicts(
                    *(owner_due.get(alias, {}) for alias in aliases),
                ),
                due_soon_days=DEFAULT_DUE_SOON_DAYS,
            ),
            "code": _code_block(code_stats),
            "risks": _member_risks(
                owner,
                cycle_issues,
                status_type_map=status_type_map,
                gtw=gtw,
                now=now,
                workload=workload,
                assignee_names=aliases,
            ),
        })

    # cycles[] 仍保留 Linear cycle 的 id/number 便于定位，但 starts/ends 口径改为本次统计窗口
    # （用户看报表时更直观：这里表达的是“统计覆盖的时间范围”，不是 Linear Cycle 的自然起止）
    cycles_json: list[dict[str, Any]] = []
    for c in cycles:
        base = cycle_to_json(c, gtw)
        cycles_json.append({
            **base,
            "starts_at": week_start_s,
            "ends_at": week_end_s,
        })
    high_load = [m["name"] for m in members if (m.get("risks") or {}).get("load_high")]

    def _sum_due(key: str) -> int:
        return sum(int((m.get("due_tasks") or {}).get(key) or 0) for m in members)

    return {
        "section": "成员上周快照",
        "iso_week": iso_week,
        "snapshot_date": snapshot_date.isoformat(),
        "team": MEMBER_TEAM_KEY,
        "week_start": week_start_s,
        "week_end": week_end_s,
        "cycles": cycles_json,
        "cycle_notes": cycle_notes,
        "weekly_capacity_hours": gtw._MEMBER_WEEKLY_CAPACITY_HOURS,
        "load_formula": "合计工时(估) / 40h * 100%",
        "data_scope": {
            "iso_week": f"当前自然周 {iso_week}（周一至周日），与 sprint 日快照节奏一致",
            "cycle_selection": "各 Team 与 iso_week 重叠的全部 Cycle，issue 去重合并",
            "project_counts": (
                "仅统计报告周内有进行中/已完成/In Review 状态变化的任务（"
                "与周报 §3 任务表过滤一致）；按当前 Linear 状态归入待开始/进行中/完成"
            ),
            "workload": (
                "报告周内 completedAt 完成 + 当前进行中/In Review/受阻 + "
                "Todo/Backlog 且 due 在本周（与团队周报 §4 同源；不做成员组/过期项目过滤）"
            ),
            "due_tasks": (
                "Cycle 内未完成任务：已逾期（due 早于 snapshot_date）、"
                f"即将逾期（due 在 7 日内，不含已逾期）、无 dueDate/targetDate/endDate；"
                "与周报 §5「逾期未完成」口径一致"
            ),
            "code": "daily_report_snapshots（source=git）按 iso_week 自然周汇总 insertions/deletions/active_days",
            "risks": "今日洞察四维度（排期压力=负载%、风险密度、责任集中度、交付动量）；含 risk_short 黄红摘要",
            "members": "成员表内全部工程/测试角色；无任务、无负载、无代码变更时也保留空记录",
        },
        "team_summary": {
            "member_count": len(members),
            "participants_with_week_activity": len(
                [m for m in members if int((m.get("totals") or {}).get("total") or 0) > 0],
            ),
            "high_load_members": high_load,
            "overdue_open_total": _sum_due("overdue"),
            "due_soon_open_total": _sum_due("due_soon"),
            "no_due_date_open_total": _sum_due("no_due_date"),
        },
        "members": members,
    }


def _fetch_merged_cycle_issues(
    *,
    gtw: Any,
    mcp: Any,
    client: Any,
    tool_names: set[str],
    iso_week: str,
    include_archived_teams: bool,
) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]], list[str]]:
    teams = list_teams(gtw, mcp, client, tool_names, include_archived=include_archived_teams)
    merged_status: dict[str, str] = {}
    merged_issues: list[dict[str, Any]] = []
    seen: set[str] = set()
    cycles_hit: list[dict[str, Any]] = []
    cycle_notes: list[str] = []

    for t in teams:
        team_id = t.get("id") or t.get("teamId")
        if not team_id:
            continue
        team_name = str(t.get("name") or team_id)
        for s in mcp.list_issue_statuses(client, tool_names, team_id=team_id):
            if isinstance(s, dict):
                merged_status[s.get("name", "")] = s.get("type", "")

        cycles_all = mcp.list_cycles_for_team(client, tool_names, team_id=team_id)
        target_cycles = gtw._pick_cycles_for_week(cycles_all, iso_week)
        for cyc in target_cycles:
            cid = str(cyc.get("id") or cyc.get("cycleId") or "")
            if not cid:
                continue
            cycles_hit.append(cyc)
            num = cyc.get("number")
            label = f"{team_name} #{num}" if num is not None else team_name
            if label not in cycle_notes:
                cycle_notes.append(label)
            batch = mcp.list_issues_in_cycle(
                client, tool_names, team_id=team_id, cycle_id=cid,
            )
            for it in batch:
                k = gtw._issue_key(it)
                if k in seen:
                    continue
                seen.add(k)
                merged_issues.append(it)

    return merged_issues, merged_status, cycles_hit, cycle_notes


def snapshot_member(
    *,
    snapshot_date: date,
    out_root: Path,
    iso_week: str | None = None,
    dry_run: bool = False,
    upload_to_pg: bool = False,
    include_archived_teams: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    gtw = load_report_module()
    week = iso_week or gtw._iso_week_for_date(snapshot_date)
    now = gtw._now_utc()
    out_dir = resolve_out_dir(out_root, snapshot_date)
    code_lookup = gtw._member_week_code_stats_lookup(week)

    results: list[dict[str, Any]] = []
    envelopes: list[dict[str, Any]] = []

    for client, mcp, tool_names in linear_client(gtw):
        cycle_issues, status_map, cycles, cycle_notes = _fetch_merged_cycle_issues(
            gtw=gtw,
            mcp=mcp,
            client=client,
            tool_names=tool_names,
            iso_week=week,
            include_archived_teams=include_archived_teams,
        )
        payload = build_workspace_member_payload(
            cycle_issues,
            status_map,
            gtw=gtw,
            iso_week=week,
            snapshot_date=snapshot_date,
            cycles=cycles,
            cycle_notes=cycle_notes,
            code_lookup=code_lookup,
            now=now,
        )
        envelope = {
            "type": "member",
            "period": "weekly",
            "snapshot_date": snapshot_date.isoformat(),
            "team": MEMBER_TEAM_KEY,
            "iso_week": week,
            "payload": payload,
        }
        entry: dict[str, Any] = {
            "team": MEMBER_TEAM_KEY,
            "type": "member",
            "period": "weekly",
            "iso_week": week,
            "member_count": len(payload.get("members") or []),
            "cycle_issue_count": len(cycle_issues),
            "payload": payload,
        }
        if not dry_run:
            entry["file"] = str(write_pulse_file(out_dir, envelope))
        if upload_to_pg and not dry_run:
            envelopes.append(envelope)
        results.append(entry)

    upload_count = 0
    if upload_to_pg and not dry_run:
        upload_count = upload_envelopes_to_pg(envelopes)
        for entry in results:
            entry["uploaded"] = True

    return results, upload_count


def main() -> int:
    p = argparse.ArgumentParser(
        description="Member daily pulse — 成员本周快照（当前自然周，每天更新）",
    )
    p.add_argument("--date", default=None, help="snapshot_date YYYY-MM-DD（默认今天）")
    p.add_argument(
        "--week",
        default=None,
        help="ISO 周（如 2026-W21）；默认当前自然周",
    )
    p.add_argument(
        "--out-dir",
        default=str(default_pulse_out_root()),
        help="输出根目录 <out-dir>/<YYYY-MM-DD>/（默认 ~/.superteam/pulse）",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--upload",
        action="store_true",
        help="写入 JSON 后 upsert 到 sp_trex_pulse（需 KB_TREX_PG_URL）",
    )
    p.add_argument("--include-archived-teams", action="store_true")
    args = p.parse_args()

    snapshot_date = default_snapshot_date(args.date)
    out_root = Path(args.out_dir)
    gtw = load_report_module()
    resolved_week = args.week or gtw._iso_week_for_date(snapshot_date)

    try:
        rows, upload_count = snapshot_member(
            snapshot_date=snapshot_date,
            out_root=out_root,
            iso_week=args.week,
            dry_run=args.dry_run,
            upload_to_pg=args.upload,
            include_archived_teams=args.include_archived_teams,
        )
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "type": "member",
                "period": "weekly",
                "snapshot_date": snapshot_date.isoformat(),
                "iso_week": resolved_week,
                "out_dir": str(resolve_out_dir(out_root, snapshot_date)),
                "uploaded": bool(args.upload and not args.dry_run),
                "upload_count": upload_count,
                "teams": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
