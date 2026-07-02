"""PAI scheduler tests (方案 B)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _scheduler import (  # noqa: E402
    add_schedule,
    compute_next_run,
    disable_schedule,
    is_due,
    load_store,
    parse_every,
    parse_schedule_intent,
    run_due_schedules,
    save_store,
)


@pytest.fixture
def schedules_file(tmp_path, monkeypatch):
    import _scheduler as sched_mod

    path = tmp_path / "pai" / "schedules.json"
    monkeypatch.setattr(sched_mod, "schedules_path", lambda: path)
    return path


def test_parse_every_compact():
    assert parse_every("3h") == ("3h", 10800)
    assert parse_every("30m") == ("30m", 1800)
    assert parse_every("每3小时") == ("3h", 10800)


def test_add_and_list_schedule(schedules_file):
    out = add_schedule(job="daily", every="3h", schedule_id="test-daily-3h")
    assert out["status"] == "scheduled"
    assert schedules_file.is_file()
    rows = load_store()["schedules"]
    assert len(rows) == 1
    assert rows[0]["job"] == "daily"
    assert rows[0]["trigger"]["seconds"] == 10800


def test_run_due_executes_when_past(schedules_file, monkeypatch):
    add_schedule(job="daily", every="1h", schedule_id="due-1h")
    store = load_store()
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    store["schedules"][0]["next_run_at"] = past.isoformat()
    save_store(store)

    calls: list[dict] = []

    def fake_executor(plan, **kwargs):
        calls.append({"plan": plan, "kwargs": kwargs})
        return {"status": "ok", "results": []}

    out = run_due_schedules(fake_executor)
    assert out["due_count"] == 1
    assert len(calls) == 1
    assert calls[0]["plan"]["source"].startswith("job:daily")
    updated = load_store()["schedules"][0]
    assert updated["last_status"] == "ok"
    assert updated["next_run_at"]


def test_run_due_skips_future(schedules_file):
    add_schedule(job="daily", every="3h", schedule_id="future")
    store = load_store()
    future = datetime.now(timezone.utc) + timedelta(hours=5)
    store["schedules"][0]["next_run_at"] = future.isoformat()
    save_store(store)

    out = run_due_schedules(lambda *a, **k: {"status": "ok"})
    assert out["due_count"] == 0
    assert out["runs"] == []


def test_disable_schedule(schedules_file):
    add_schedule(job="daily", every="3h", schedule_id="x")
    disable_schedule("x")
    row = load_store()["schedules"][0]
    assert row["enabled"] is False
    assert is_due(row) is False


def test_parse_schedule_intent_every_3h():
    intent = parse_schedule_intent("每3小时刷新一次看板")
    assert intent is not None
    assert intent["action"] == "add"
    assert intent["job"] == "daily"
    assert intent["every"] == "3h"
    assert intent["id"] == "pulse-daily"


def test_replace_same_job_schedule(schedules_file):
    add_schedule(job="daily", every="3h")
    assert len(load_store()["schedules"]) == 1
    assert load_store()["schedules"][0]["id"] == "pulse-daily"
    assert load_store()["schedules"][0]["trigger"]["every"] == "3h"

    out = add_schedule(job="daily", every="1h")
    rows = load_store()["schedules"]
    assert len(rows) == 1
    assert rows[0]["id"] == "pulse-daily"
    assert rows[0]["trigger"]["every"] == "1h"
    assert out["status"] == "updated"


def test_replace_removes_legacy_interval_ids(schedules_file):
    save_store({
        "version": 1,
        "schedules": [{
            "id": "pulse-daily-3h",
            "job": "daily",
            "enabled": True,
            "trigger": {"type": "interval", "every": "3h", "seconds": 10800},
            "next_run_at": "2026-07-01T00:00:00+08:00",
            "created_at": "2026-07-01T00:00:00+08:00",
        }],
    })
    out = add_schedule(job="daily", every="1h")
    rows = load_store()["schedules"]
    assert len(rows) == 1
    assert rows[0]["id"] == "pulse-daily"
    assert out.get("replaced_ids") == ["pulse-daily-3h"]


def test_parse_schedule_intent_immediate_phrase_returns_none():
    assert parse_schedule_intent("更新看板") is None


def test_daily_at_trigger():
    trigger = {"type": "daily_at", "every": "1d", "seconds": 86400, "at": "08:00"}
    base = datetime(2026, 7, 1, 9, 0, tzinfo=timezone(timedelta(hours=8)))
    nxt = compute_next_run(trigger, after=base)
    assert nxt.hour == 8
    assert nxt.day == 2
