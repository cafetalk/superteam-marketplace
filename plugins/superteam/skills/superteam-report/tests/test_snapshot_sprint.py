"""Tests for snapshot_sprint project progress counts."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))
import snapshot_sprint as ss  # noqa: E402


class _GtwStub:
    @staticmethod
    def _state_bucket_for_issue(it: dict, status_type_map: dict) -> str:
        name = (it.get("status") or "").strip()
        t = (status_type_map.get(name) or "").lower()
        if t == "completed":
            return "done"
        if t == "started":
            return "in_progress"
        if t == "canceled":
            return "canceled"
        return "todo"

    _count_cycle_issue_buckets = staticmethod(
        __import__("generate_team_weekly_report", fromlist=["_count_cycle_issue_buckets"])
        ._count_cycle_issue_buckets
    )


def test_apply_project_wide_progress_overrides_phase_subset():
    status_map = {"Done": "completed", "In Progress": "started", "Todo": "unstarted"}
    project_issues = [
        {"status": "Done", "assignee": "dev-a"},
        {"status": "Done", "assignee": "dev-b"},
        {"status": "In Progress", "assignee": "qa-x"},
        {"status": "Todo", "assignee": "dev-c"},
    ]
    row = {
        "done": 0,
        "in_progress": 1,
        "todo": 0,
        "backlog": 0,
        "other": 0,
        "todo_and_backlog": 0,
        "progress_done_pct": 0.0,
        "progress_label": "测试进度",
    }
    ss._apply_project_wide_progress(
        row, project_issues, gtw=_GtwStub(), status_type_map=status_map,
    )
    assert row["done"] == 2
    assert row["in_progress"] == 1
    assert row["todo"] == 1
    assert row["progress_done_pct"] == 50.0
    assert row["progress_label"] == "项目进度"
    assert row["progress_label_phase"] == "测试进度"
    assert row["progress_scope"] == "project"


def test_enrich_project_status_fields():
    row = {"status_label": "开发中"}
    pm = {"status": {"name": "In Progress", "type": "started"}}
    ss._enrich_project_status_fields(
        row,
        gtw=SimpleNamespace(_project_linear_status_name=lambda _pm: "In Progress"),
        proj_stat={"status_label": "开发中", "linear_status": "In Progress"},
        project_meta=pm,
    )
    assert row["status"] == "开发中"
    assert row["linear_status"] == "In Progress"
    assert row["linear_status_type"] == "started"
