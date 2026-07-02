"""PAI planner tests (no worker execution)."""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _planner import plan_from_job, plan_from_prompt  # noqa: E402


def _step_ids(plan: dict) -> list[str]:
    return [s["id"] for s in plan["steps"]]


def test_job_daily_matches_run_reports_all():
    plan = plan_from_job("daily", snapshot_date="2026-06-20")
    assert _step_ids(plan) == [
        "pulse-daily",
        "pulse-task-daily",
        "pulse-pai-daily",
        "pulse-member-daily",
    ]
    assert plan["snapshot_date"] == "2026-06-20"


def test_prompt_sprint_and_insight_only():
    plan = plan_from_prompt("只要 sprint 和 insight，日期今天")
    assert _step_ids(plan) == ["pulse-daily", "pulse-pai-daily"]


def test_insight_adds_sprint_dependency():
    plan = plan_from_prompt("重跑 pai 洞察")
    ids = _step_ids(plan)
    assert "pulse-pai-daily" in ids
    assert ids.index("pulse-daily") < ids.index("pulse-pai-daily")


def test_team_weekly_job():
    plan = plan_from_prompt("生成本周团队周报")
    assert _step_ids(plan) == ["team-weekly"]


def test_exclude_member():
    plan = plan_from_prompt("今日 pulse 全量但不要成员")
    ids = _step_ids(plan)
    assert "pulse-member-daily" not in ids
    assert "pulse-daily" in ids


def test_extract_date_from_prompt():
    plan = plan_from_prompt("回填 2026-06-12 的 pulse")
    assert plan["snapshot_date"] == "2026-06-12"


def test_empty_prompt_defaults_daily():
    plan = plan_from_prompt("")
    assert len(_step_ids(plan)) == 4
