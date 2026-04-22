"""Tests for save_linear_issue_once guard logic (no MCP)."""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from save_linear_issue_once import (  # noqa: E402
    find_reusable_entry,
    normalize_title,
    pick_recent_matching_issue,
)


def test_find_reusable_entry_hit():
    now = 1000.0
    entries = [
        {
            "title_norm": normalize_title("Fix Bug"),
            "issue_id": "ACB-1",
            "url": "u1",
            "title": "Fix Bug",
            "ts": now - 30,
            "assignee": "me",
        }
    ]
    r = find_reusable_entry(entries, normalize_title("fix  bug"), "me", now, 180)
    assert r is not None
    assert r["issue_id"] == "ACB-1"


def test_pick_recent_matching_issue_team_and_time_window():
    now = 1_000_000.0
    title = "Fix Thing"
    tn = normalize_title(title)
    issues = [
        {
            "id": "OLD-1",
            "title": title,
            "team": "trex",
            "createdAt": "2020-01-01T00:00:00.000Z",
        },
        {
            "id": "NEW-9",
            "title": title,
            "team": "trex",
            "createdAt": "2026-04-13T10:00:00.000Z",
        },
        {
            "id": "OTHER",
            "title": "Other",
            "team": "trex",
            "createdAt": "2026-04-13T10:00:00.000Z",
        },
    ]
    ts_new = datetime(2026, 4, 13, 10, 0, 0, tzinfo=timezone.utc).timestamp()
    assert pick_recent_matching_issue(issues, tn, "trex", ts_new + 60, within_sec=3600)["id"] == "NEW-9"


def test_pick_recent_matching_issue_outside_window_returns_none():
    now = 1_000_000_000.0  # far from 2020 issue
    title = "X"
    issues = [{"id": "A", "title": "X", "team": "t", "createdAt": "2020-01-01T00:00:00.000Z"}]
    assert pick_recent_matching_issue(issues, normalize_title("X"), "t", now, within_sec=300) is None


def test_find_reusable_entry_miss_expired():
    now = 1000.0
    entries = [
        {
            "title_norm": normalize_title("Old"),
            "issue_id": "ACB-2",
            "ts": now - 500,
            "assignee": "me",
        }
    ]
    assert find_reusable_entry(entries, normalize_title("Old"), "me", now, 180) is None


if __name__ == "__main__":
    test_find_reusable_entry_hit()
    test_find_reusable_entry_miss_expired()
    print("ok")
