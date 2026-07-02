"""Unit tests for Linear project scope filter (_linear_project_scope_reason)."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import generate_team_weekly_report as gtw  # noqa: E402

REF = date(2026, 6, 12)
WEEK_START = date(2026, 6, 9)


def _pm(
    *,
    name: str = "trex",
    status_type: str = "started",
    status_name: str = "In Progress",
    start: str | None = "2026-06-01",
    target: str | None = "2026-06-30",
) -> dict:
    return {
        "name": name,
        "status": {"type": status_type, "name": status_name},
        "startDate": start,
        "targetDate": target,
    }


def _reason(pm: dict) -> str | None:
    return gtw._linear_project_scope_reason(
        pm, ref=REF, report_week_start=WEEK_START,
    )


def test_in_progress_within_window_included():
    assert _reason(_pm()) is None


def test_planned_status_included():
    assert _reason(_pm(status_type="planned", status_name="Planned")) is None


def test_in_progress_before_start_still_included_by_status():
    assert _reason(_pm(start="2026-06-15")) is None


def test_in_progress_after_target_still_included_by_status():
    assert _reason(_pm(target="2026-06-10")) is None


def test_backlog_excluded():
    reason = _reason(_pm(status_type="backlog", status_name="Backlog"))
    assert reason is not None
    assert "Planned / In Progress" in reason


def test_backlog_included_for_product_pending_exclusion():
    projects = [
        _pm(name="active"),
        _pm(name="backlog_proj", status_type="backlog", status_name="Backlog"),
        _pm(name="done", status_type="completed", status_name="Completed"),
    ]
    excluded = gtw._excluded_report_project_names_for_product_pending(
        projects, ref=REF, report_week_start=WEEK_START,
    )
    assert excluded == {"done"}


def test_canceled_excluded():
    reason = _reason(_pm(status_type="canceled", status_name="Canceled"))
    assert reason is not None
    assert "Planned / In Progress" in reason


def test_completed_excluded_even_within_date_window():
    reason = _reason(_pm(status_type="completed", status_name="Completed"))
    assert reason is not None
    assert "Planned / In Progress" in reason


def test_completed_outside_window_excluded():
    reason = _reason(
        _pm(
            status_type="completed",
            status_name="Completed",
            start="2026-06-15",
            target="2026-06-30",
        ),
    )
    assert reason is not None
    assert "Planned / In Progress" in reason


def test_no_target_date_included_when_in_progress():
    assert _reason(_pm(target=None)) is None


def test_no_dates_included_when_in_progress():
    assert _reason(_pm(start=None, target=None)) is None


def test_filter_linear_projects_for_report():
    projects = [
        _pm(name="active"),
        _pm(
            name="done",
            status_type="completed",
            status_name="Completed",
            start="2026-06-01",
            target="2026-06-30",
        ),
        _pm(
            name="future",
            status_type="completed",
            status_name="Completed",
            start="2026-06-20",
        ),
    ]
    active, notes = gtw._filter_linear_projects_for_report(
        projects, report_week_start=WEEK_START, ref=REF,
    )
    assert {p["name"] for p in active} == {"active"}
    assert len(notes) == 2
    assert any("done" in n for n in notes)
    assert any("future" in n for n in notes)
