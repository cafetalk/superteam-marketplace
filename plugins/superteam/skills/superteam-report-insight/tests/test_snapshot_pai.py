"""Unit tests for snapshot_pai v2 payload shape."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _pai import build_pai_payload  # noqa: E402


def test_build_pai_payload_by_leader():
    sprint = {
        "iso_week": "2026-W22",
        "projects": [
            {
                "name": "ProjA",
                "project_url": "https://linear.app/x",
                "leader": "甲",
                "open_total": 6,
                "days_to_milestone": 5,
                "done": 1,
                "in_progress": 2,
                "todo": 3,
                "progress_done_pct": 20,
                "risk_short": "久未更新×2；未分配×1",
                "participants": [],
            },
        ],
    }
    payload = build_pai_payload(sprint, snapshot_date=date(2026, 6, 2))
    assert payload["version"] == "2"
    assert "projects" not in payload
    row = payload["by_leader"]["甲"]["projects"][0]
    assert row["project"] == "ProjA"
    assert row["briefing"]["headline"]
    assert row["moves"]
    assert "summary" in payload
