"""Unit tests for snapshot_member due_tasks counts (no Linear / PG)."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import snapshot_member as member  # noqa: E402


class _FakeGtw:
    def _state_bucket_for_issue(self, it, status_type_map):
        st = str(it.get("status") or "").lower()
        if "cancel" in st:
            return "canceled"
        if "done" in st:
            return "done"
        if "progress" in st:
            return "in_progress"
        return "todo"

    def _linear_issue_status_type_lower(self, it, status_type_map):
        if "done" in str(it.get("status") or "").lower():
            return "completed"
        return "started"

    def _parse_project_date_field(self, v):
        if not v:
            return None
        if isinstance(v, date):
            return v
        return date.fromisoformat(str(v)[:10])

    def _assignee_name(self, it):
        return it.get("assignee")


def _issue(**kw):
    base = {"status": "In Progress", "assignee": "Alice"}
    base.update(kw)
    return base


def test_per_owner_due_task_counts():
    gtw = _FakeGtw()
    ref = date(2026, 6, 3)
    issues = [
        _issue(assignee="Alice", dueDate="2026-06-01"),
        _issue(assignee="Alice", dueDate="2026-06-05"),
        _issue(assignee="Alice"),
        _issue(assignee="Bob", dueDate="2026-06-20"),
        _issue(assignee="Alice", status="Done", dueDate="2026-06-01"),
        _issue(assignee="Alice", status="Canceled", dueDate="2026-06-01"),
    ]
    counts = member.per_owner_due_task_counts(
        issues, {}, gtw=gtw, ref_day=ref, due_soon_days=7,
    )
    assert counts["Alice"] == {"overdue": 1, "due_soon": 1, "no_due_date": 1}
    assert counts["Bob"] == {"overdue": 0, "due_soon": 0, "no_due_date": 0}


def test_due_tasks_block():
    block = member._due_tasks_block(
        {"overdue": 2, "due_soon": 1, "no_due_date": 3},
        due_soon_days=7,
    )
    assert block == {
        "overdue": 2,
        "due_soon": 1,
        "no_due_date": 3,
        "due_soon_days": 7,
    }


def test_build_workspace_member_payload_one_row_per_report_member():
    class _Gtw:
        _MEMBER_WEEKLY_CAPACITY_HOURS = 40

        def _iter_report_members(self):
            return [
                {
                    "real_name": "秦鹏",
                    "user_id": "u1",
                    "role": "backend",
                    "aliases": ["qin-peng", "allen.qin"],
                },
                {
                    "real_name": "Alice",
                    "user_id": "u2",
                    "role": "frontend",
                },
            ]

        def _member_display_names(self, m):
            names = [str(m.get("real_name") or "")]
            names.extend(m.get("aliases") or [])
            return [n for n in names if n]

        def _member_owner_section_sort_key(self, owner):
            return (0, owner)

        def _week_date_range(self, iso_week):
            return "2026-06-09", "2026-06-15"

        def _state_bucket_for_issue(self, it, status_type_map):
            return "in_progress"

        def _assignee_name(self, it):
            return it.get("assignee")

        def _issue_in_member_week_activity_scope(self, it, iso_week, status_type_map):
            return True

        def _issue_project_name(self, it):
            return it.get("project") or "P"

        def _role_bucket_for_weekly(self, role):
            if "backend" in role:
                return "backend"
            if "frontend" in role:
                return "frontend"
            return None

        def _role_string_indicates_qa(self, role):
            return False

        def _member_workload_rows(self, cycle_issues, status_type_map, iso_week):
            return [
                {"owner": "qin-peng", "total": 2, "done": 0, "in_progress": 2,
                 "todo": 0, "backlog": 0, "open": 2, "active": 2, "other": 0,
                 "canceled": 0, "hours_total": 16.0, "hours_done": 0.0,
                 "hours_open": 16.0, "hours_filled": 2, "done_pct": 0.0},
                {"owner": "Alice", "total": 1, "done": 1, "in_progress": 0,
                 "todo": 0, "backlog": 0, "open": 0, "active": 1, "other": 0,
                 "canceled": 0, "hours_total": 8.0, "hours_done": 8.0,
                 "hours_open": 0.0, "hours_filled": 1, "done_pct": 100.0},
            ]

        def _workload_row_to_json(self, wl):
            return dict(wl)

        def _parse_project_date_field(self, v):
            return None

        def _linear_issue_status_type_lower(self, it, status_type_map):
            return "started"

        def _issue_risk_reasons(self, it, status_type_map, now):
            return []

        def _is_blocked_status(self, status):
            return False

        def _parse_dt(self, v):
            return None

        def _is_dt_in_iso_week(self, dt, iso_week):
            return False

    gtw = _Gtw()
    issues = [
        {"assignee": "qin-peng", "project": "Hub"},
        {"assignee": "allen.qin", "project": "Hub"},
        {"assignee": "Alice", "project": "App"},
    ]
    payload = member.build_workspace_member_payload(
        issues,
        {},
        gtw=gtw,
        iso_week="2026-W24",
        snapshot_date=date(2026, 6, 14),
        cycles=[],
        cycle_notes=[],
        code_lookup=None,
        now=date(2026, 6, 14),
    )
    names = [m["name"] for m in payload["members"]]
    assert names == sorted(["秦鹏", "Alice"], key=gtw._member_owner_section_sort_key)
    qin = next(m for m in payload["members"] if m["name"] == "秦鹏")
    assert qin["totals"]["total"] == 2
    assert qin["workload"]["in_progress"] == 2
