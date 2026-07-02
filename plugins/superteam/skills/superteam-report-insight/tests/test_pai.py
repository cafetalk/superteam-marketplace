"""Unit tests for PAI v2 (Linear sprint → by_leader)."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _pai import (  # noqa: E402
    PAI_VERSION,
    build_linear_snapshot,
    build_pai_payload,
    build_project_briefing,
)


def _retail_like_project() -> dict:
    return {
        "name": "Retail Campaign",
        "project_url": "https://linear.app/t-rex/project/retail",
        "leader": "王冲",
        "status": "开发中",
        "linear_status": "In Progress",
        "open_total": 8,
        "days_to_milestone": 5,
        "next_milestone": "Beta 提测",
        "done": 2,
        "in_progress": 1,
        "todo": 4,
        "backlog": 1,
        "progress_done_pct": 18.0,
        "risk_short": "未分配×2；久未更新×1；受阻×1",
        "participants": [
            {"name": "未分配", "task_count": 2, "open_count": 2},
            {"name": "李四", "task_count": 5, "open_count": 4},
            {"name": "王冲", "task_count": 3, "open_count": 2},
        ],
    }


def test_linear_snapshot_no_spi_rdi():
    linear = build_linear_snapshot(_retail_like_project())
    assert linear["open_total"] == 8
    assert linear["risk_counts"]["受阻"] == 1


def test_project_briefing_leader_focused():
    row = build_project_briefing(_retail_like_project())
    assert row is not None
    assert row["leader"] == "王冲"
    assert "王冲" in row["briefing"]["leader_ask"]
    assert row["primary_signal"] in row["signals"]


def test_pai_payload_by_leader_only():
    sprint = {"iso_week": "2026-W25", "projects": [_retail_like_project()]}
    payload = build_pai_payload(sprint, snapshot_date=date(2026, 6, 22))
    assert payload["version"] == PAI_VERSION
    assert "projects" not in payload
    assert "by_leader" in payload
    leader = payload["by_leader"]["王冲"]
    assert leader["project_count"] == 1
    assert leader["problems"]
    assert leader["risks_aggregate"]["受阻"] == 1
    assert leader["projects"][0]["risks"]["risk_short"]
    assert leader["projects"][0]["problems"]


def test_viewer_filters_by_leader():
    sprint = {"projects": [_retail_like_project()]}
    filtered = build_pai_payload(sprint, snapshot_date=date(2026, 6, 22), viewer="王冲")
    assert list(filtered["by_leader"].keys()) == ["王冲"]
    assert filtered["leader_count"] == 1


def test_leader_aggregate_problems_include_project():
    sprint = {"projects": [_retail_like_project()]}
    payload = build_pai_payload(sprint, snapshot_date=date(2026, 6, 22))
    probs = payload["by_leader"]["王冲"]["problems"]
    assert any(p.get("project") == "Retail Campaign" for p in probs)


def test_milestone_wording_today_not_tomorrow():
    proj = _retail_like_project()
    proj["days_to_milestone"] = 0
    proj["next_milestone"] = "发布（2026-06-25）"
    proj["open_total"] = 3
    row = build_project_briefing(proj)
    assert row["primary_signal"] == "milestone_critical"
    assert "今天就是" in row["briefing"]["leader_ask"]
    assert "明天" not in row["briefing"]["leader_ask"]


def test_milestone_wording_tomorrow():
    proj = _retail_like_project()
    proj["days_to_milestone"] = 1
    proj["open_total"] = 3
    row = build_project_briefing(proj)
    assert "明天就是" in row["briefing"]["leader_ask"]
