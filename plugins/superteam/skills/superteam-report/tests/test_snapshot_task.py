"""Unit tests for snapshot_task classify (no Linear / PG)."""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import snapshot_task as task  # noqa: E402


class _FakeGtw:
    def _state_bucket_for_issue(self, it, status_type_map):
        st = str(it.get("status") or "").lower()
        if "cancel" in st:
            return "canceled"
        if "done" in st or it.get("completedAt"):
            return "done"
        if "progress" in st:
            return "in_progress"
        return "todo"

    def _linear_issue_status_type_lower(self, it, status_type_map):
        if it.get("completedAt"):
            return "completed"
        return "started"

    def _parse_dt(self, v):
        if not v:
            return None
        if isinstance(v, datetime):
            return v
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))

    def _to_local_date(self, dt):
        return dt.astimezone(timezone.utc).date()

    def _parse_project_date_field(self, v):
        if not v:
            return None
        if isinstance(v, date):
            return v
        return date.fromisoformat(str(v)[:10])

    def _issue_label_tokens(self, it):
        raw = it.get("labels")
        if not raw or not isinstance(raw, list):
            return set()
        out = set()
        for x in raw:
            if isinstance(x, str) and x.strip():
                out.add(x.strip().lower())
            elif isinstance(x, dict):
                for key in ("name", "slug", "id"):
                    v = x.get(key)
                    if isinstance(v, str) and v.strip():
                        out.add(v.strip().lower())
        return out

    def _issue_key(self, it):
        return it.get("identifier") or it.get("id")

    def _issue_title_without_identifier(self, it):
        return it.get("title") or ""

    def _issue_project_name(self, it):
        return it.get("project") or ""

    def _assignee_name(self, it):
        return it.get("assignee")

    def _report_member_assignee_names(self):
        return {"Alice", "Bob"}

    def _member_owner_section_sort_key(self, owner):
        return (0, owner)

    def _member_workload_rows(self, issues, status_type_map, iso_week):
        owners = {self._assignee_name(it) for it in issues if self._assignee_name(it)}
        return [{"owner": o} for o in sorted(owners)]

    def _issue_in_member_week_activity_scope(self, it, iso_week, status_type_map):
        return True

    def _is_blocked_status(self, status):
        return False


def _issue(**kw):
    base = {
        "identifier": "TREX-1",
        "title": "Task",
        "status": "In Progress",
        "project": "P1",
    }
    base.update(kw)
    return base


def test_classify_completed_today():
    gtw = _FakeGtw()
    ref = date(2026, 6, 3)
    issues = [
        _issue(
            identifier="TREX-10",
            status="Done",
            completedAt="2026-06-03T10:00:00Z",
            dueDate="2026-06-01",
        ),
        _issue(
            identifier="TREX-11",
            status="Done",
            completedAt="2026-06-02T10:00:00Z",
        ),
    ]
    done, overdue, soon = task.classify_task_dimensions(
        issues,
        gtw=gtw,
        status_type_map={},
        snapshot_date=ref,
        due_soon_days=7,
    )
    assert len(done) == 1
    assert done[0]["id"] == "TREX-10"
    assert len(overdue) == 0
    assert len(soon) == 0


def test_classify_overdue_and_due_soon():
    gtw = _FakeGtw()
    ref = date(2026, 6, 3)
    issues = [
        _issue(identifier="TREX-20", dueDate="2026-06-01"),
        _issue(identifier="TREX-21", dueDate="2026-06-05"),
        _issue(identifier="TREX-22", dueDate="2026-06-15"),
        _issue(identifier="TREX-23", status="Canceled"),
    ]
    _, overdue, soon = task.classify_task_dimensions(
        issues,
        gtw=gtw,
        status_type_map={},
        snapshot_date=ref,
        due_soon_days=7,
    )
    assert [r["id"] for r in overdue] == ["TREX-20"]
    assert overdue[0]["days_overdue"] == 2
    assert [r["id"] for r in soon] == ["TREX-21"]
    assert soon[0]["days_until_due"] == 2


def test_build_assignee_due_summary_only_counts_report_members():
    gtw = _FakeGtw()
    ref = date(2026, 6, 3)
    issues = [
        _issue(assignee="Alice", dueDate="2026-06-01"),
        _issue(assignee="Alice", dueDate="2026-06-05"),
        _issue(assignee="Bob", dueDate="2026-06-01"),
        _issue(assignee="外人", dueDate="2026-06-01"),
        _issue(assignee=None, dueDate="2026-06-01"),
    ]
    assignees, team_summary = task.build_assignee_due_summary(
        issues, {}, gtw=gtw, iso_week="2026-W23", snapshot_date=ref, due_soon_days=7,
    )
    assert team_summary == {"overdue_open_total": 2, "due_soon_open_total": 1, "no_due_date_open_total": 0}
    by_name = {a["name"]: a["due_tasks"] for a in assignees}
    assert by_name["Alice"] == {"overdue": 1, "due_soon": 1, "no_due_date": 0, "due_soon_days": 7}
    assert by_name["Bob"] == {"overdue": 1, "due_soon": 0, "no_due_date": 0, "due_soon_days": 7}
    assert "外人" not in by_name


def test_build_task_payload_structure():
    payload = task.build_task_payload(
        completed_today=[{"id": "A"}],
        overdue=[{"id": "B", "assignee": "Alice"}],
        due_soon=[{"id": "C", "assignee": "Alice"}, {"id": "D", "assignee": "Bob"}],
        in_review_count=3,
        longest_in_review_entered_at="2026-05-28T10:00:00+00:00",
        longest_in_review={
            "entered_at": "2026-05-28T10:00:00+00:00",
            "days_in_review": 6,
            "task": {"id": "TREX-9"},
        },
        product_created_pending=[{"id": "P1"}],
        by_assignee=[{"name": "Alice", "due_tasks": {"overdue": 1, "due_soon": 1, "no_due_date": 0, "due_soon_days": 7}}],
        team_summary={"overdue_open_total": 1, "due_soon_open_total": 1, "no_due_date_open_total": 0},
        snapshot_date=date(2026, 6, 3),
        iso_week="2026-W23",
        due_soon_days=7,
        issue_pool_size=100,
        cycle_issue_count=50,
        cycle_notes=["trex #7"],
    )
    assert payload["summary"]["completed_today_count"] == 1
    assert payload["summary"]["overdue_count"] == 1
    assert payload["summary"]["due_soon_count"] == 1
    assert payload["team_summary"]["overdue_open_total"] == 1
    assert payload["summary"]["in_review_count"] == 3
    assert payload["summary"]["longest_in_review_entered_at"] == "2026-05-28T10:00:00+00:00"
    assert payload["summary"]["product_created_pending_count"] == 1
    dims = payload["dimensions"]
    assert dims["completed_today"]["count"] == 1
    assert dims["overdue"]["count"] == 1
    assert dims["due_soon"]["window_days"] == 7
    assert dims["in_review"]["count"] == 3
    assert dims["in_review"]["longest_in_review_entered_at"] == "2026-05-28T10:00:00+00:00"
    assert dims["product_created_pending"]["count"] == 1


def test_list_in_review_excludes_prd_and_technical_review():
    gtw = _FakeGtw()
    issues = [
        _issue(identifier="TREX-30", status="In Review"),
        _issue(identifier="TREX-31", status="In Review"),
        _issue(identifier="TREX-32", status="Prd Review"),
        _issue(identifier="TREX-33", status="Technical Review"),
        _issue(identifier="TREX-34", status="In Progress"),
        _issue(identifier="TREX-35", status="Canceled"),
    ]
    rows = task.list_in_review_issues(issues, gtw=gtw, status_type_map={})
    assert [r["identifier"] for r in rows] == ["TREX-30", "TREX-31"]


def test_entered_at_from_state_history_nodes():
    gtw = _FakeGtw()
    nodes = [
        {
            "startedAt": "2026-05-20T08:00:00Z",
            "endedAt": "2026-05-25T08:00:00Z",
            "state": {"name": "In Progress"},
        },
        {
            "startedAt": "2026-05-25T08:00:00Z",
            "endedAt": None,
            "state": {"name": "In Review"},
        },
    ]
    entered = task._entered_at_from_state_history_nodes(nodes, gtw=gtw)
    assert entered == datetime(2026, 5, 25, 8, 0, tzinfo=timezone.utc)


def test_longest_in_review_metric_picks_earliest_entered():
    gtw = _FakeGtw()
    ref = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
    issues = [
        _issue(
            identifier="TREX-50",
            status="In Review",
            updatedAt="2026-05-30T10:00:00Z",
        ),
        _issue(
            identifier="TREX-51",
            status="In Review",
            updatedAt="2026-05-20T10:00:00Z",
        ),
    ]
    metric = task.longest_in_review_metric(issues, gtw=gtw, ref_now=ref, graphql_cache={})
    assert metric is not None
    assert metric["task"]["id"] == "TREX-51"
    assert metric["entered_at_source"] == "updatedAt_fallback"
    assert metric["days_in_review"] == 14


def test_classify_product_created_pending():
    gtw = _FakeGtw()
    ref = date(2026, 6, 3)
    req_label = ["Requirement"]
    issues = [
        _issue(identifier="TREX-40", status="Todo", createdBy="产品甲", labels=req_label),
        _issue(identifier="TREX-41", status="Prd Review", createdBy="产品甲", labels=req_label),
        _issue(identifier="TREX-42", status="Technical Review", createdBy="产品甲", labels=req_label),
        _issue(identifier="TREX-43", status="Todo", createdBy="研发乙"),
        _issue(
            identifier="TREX-46",
            status="Todo",
            createdBy="研发乙",
            labels=req_label,
        ),
        _issue(identifier="TREX-44", status="In Progress", createdBy="产品甲", labels=req_label),
        _issue(identifier="TREX-45", status="Todo", createdBy="产品甲", labels=req_label),
    ]
    issues[-1]["status"] = "Canceled"
    rows = task.classify_product_created_pending(
        issues,
        gtw=gtw,
        status_type_map={},
        ref_day=ref,
    )
    assert [r["id"] for r in rows] == ["TREX-40", "TREX-41", "TREX-42", "TREX-46"]
    assert rows[0]["created_by"] == "产品甲"
    assert rows[3]["created_by"] == "研发乙"
