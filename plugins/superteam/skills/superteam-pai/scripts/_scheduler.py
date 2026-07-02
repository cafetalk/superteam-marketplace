"""PAI 定时调度（方案 B）：注册表 + run-due 唤醒，不在进程内 sleep。"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_SHARED = _SCRIPTS.parent.parent / "_shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from config import superteam_home  # noqa: E402

from _planner import plan_from_job  # noqa: E402

_SCHEDULE_VERSION = 1
_EVERY_RE = re.compile(
    r"(?:(\d+)\s*(?:小时|个小时|h|hr|hours?))"
    r"|(?:(\d+)\s*(?:分钟|分|m|min|minutes?))"
    r"|(?:(\d+)\s*(?:天|日|d|days?))",
    re.IGNORECASE,
)
_AT_TIME_RE = re.compile(r"(?:每天|每日)\s*(\d{1,2})[:：](\d{2})")
_SCHEDULE_ADD_RE = re.compile(
    r"(每|每隔|定时|周期)",
)
_SCHEDULE_DISABLE_RE = re.compile(
    r"(取消|停止|关闭|禁用).{0,12}(定时|周期|自动)",
)


def schedules_path() -> Path:
    return superteam_home() / "pai" / "schedules.json"


def _now() -> datetime:
    return datetime.now().astimezone()


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_every(text: str) -> tuple[str, int]:
    """解析间隔字符串，返回 (规范化 every, 秒数)。"""
    raw = (text or "").strip().lower()
    if not raw:
        raise ValueError("empty interval")

    # 紧凑写法：3h / 30m / 1d
    compact = re.fullmatch(r"(\d+)(h|m|d)", raw)
    if compact:
        n, unit = int(compact.group(1)), compact.group(2)
        if unit == "h":
            return f"{n}h", n * 3600
        if unit == "m":
            return f"{n}m", n * 60
        return f"{n}d", n * 86400

    m = _EVERY_RE.search(text or "")
    if not m:
        raise ValueError(f"cannot parse interval from '{text}'")
    if m.group(1):
        n = int(m.group(1))
        return f"{n}h", n * 3600
    if m.group(2):
        n = int(m.group(2))
        return f"{n}m", n * 60
    n = int(m.group(3))
    return f"{n}d", n * 86400


def parse_daily_at(text: str) -> tuple[int, int] | None:
    """「每天 8:00」→ (hour, minute)。"""
    m = _AT_TIME_RE.search(text or "")
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        raise ValueError(f"invalid time {hour}:{minute}")
    return hour, minute


def build_trigger(*, every: str | None = None, at_time: tuple[int, int] | None = None) -> dict[str, Any]:
    if at_time is not None:
        hour, minute = at_time
        every_norm, seconds = "1d", 86400
        return {
            "type": "daily_at",
            "every": every_norm,
            "seconds": seconds,
            "at": f"{hour:02d}:{minute:02d}",
        }
    every_norm, seconds = parse_every(every or "")
    return {"type": "interval", "every": every_norm, "seconds": seconds}


def compute_next_run(trigger: dict[str, Any], *, after: datetime | None = None) -> datetime:
    base = after or _now()
    if trigger.get("type") == "daily_at":
        hour, minute = (int(x) for x in str(trigger["at"]).split(":"))
        candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= base:
            candidate += timedelta(days=1)
        return candidate
    seconds = int(trigger["seconds"])
    return base + timedelta(seconds=seconds)


def load_store() -> dict[str, Any]:
    path = schedules_path()
    if not path.is_file():
        return {"version": _SCHEDULE_VERSION, "schedules": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("schedules.json must be a JSON object")
    data.setdefault("version", _SCHEDULE_VERSION)
    data.setdefault("schedules", [])
    return data


def save_store(store: dict[str, Any]) -> Path:
    path = schedules_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def list_schedules(*, enabled_only: bool = False) -> list[dict[str, Any]]:
    rows = load_store().get("schedules") or []
    if enabled_only:
        return [r for r in rows if r.get("enabled", True)]
    return list(rows)


def _find_schedule(store: dict[str, Any], schedule_id: str) -> dict[str, Any] | None:
    for row in store.get("schedules") or []:
        if row.get("id") == schedule_id:
            return row
    return None


def canonical_schedule_id(job: str) -> str:
    """每个 job 仅保留一条定时任务，固定 id。"""
    return f"pulse-{job}"


def _find_schedule_by_job(store: dict[str, Any], job: str) -> dict[str, Any] | None:
    for row in store.get("schedules") or []:
        if row.get("job") == job:
            return row
    return None


def add_schedule(
    *,
    job: str,
    every: str | None = None,
    at_time: tuple[int, int] | None = None,
    schedule_id: str | None = None,
    note: str | None = None,
    enabled: bool = True,
    run_now: bool = False,
) -> dict[str, Any]:
    trigger = build_trigger(every=every, at_time=at_time)
    now = _now()
    sid = schedule_id or canonical_schedule_id(job)
    entry: dict[str, Any] = {
        "id": sid,
        "job": job,
        "enabled": enabled,
        "trigger": trigger,
        "last_run_at": None,
        "last_status": None,
        "next_run_at": _iso(compute_next_run(trigger, after=now)),
        "created_at": _iso(now),
        "note": note,
    }

    store = load_store()
    schedules = store.setdefault("schedules", [])
    replaced_ids = [
        r.get("id")
        for r in schedules
        if r.get("job") == job and r.get("id") != sid
    ]
    schedules = [r for r in schedules if r.get("job") != job or r.get("id") == sid]

    existing = _find_schedule({"schedules": schedules}, sid)
    if existing:
        entry["created_at"] = existing.get("created_at") or entry["created_at"]
        entry["last_run_at"] = existing.get("last_run_at")
        entry["last_status"] = existing.get("last_status")
        schedules = [entry if r.get("id") == sid else r for r in schedules]
        status = "updated"
    else:
        schedules.append(entry)
        status = "scheduled"

    store["schedules"] = schedules
    path = save_store(store)
    result: dict[str, Any] = {
        "status": status,
        "path": str(path),
        "schedule": entry,
    }
    if replaced_ids:
        result["replaced_ids"] = replaced_ids
    if run_now:
        entry["next_run_at"] = _iso(now)
        save_store(store)
    return result


def disable_schedule(schedule_id: str) -> dict[str, Any]:
    store = load_store()
    row = _find_schedule(store, schedule_id)
    if not row:
        raise ValueError(f"schedule not found: {schedule_id}")
    row["enabled"] = False
    save_store(store)
    return {"status": "disabled", "schedule": row}


def is_due(row: dict[str, Any], *, now: datetime | None = None) -> bool:
    if not row.get("enabled", True):
        return False
    nxt = _parse_iso(row.get("next_run_at"))
    if nxt is None:
        return True
    return (now or _now()) >= nxt


def mark_run_result(row: dict[str, Any], *, outcome_status: str, started_at: datetime) -> None:
    trigger = row.get("trigger") or {}
    row["last_run_at"] = _iso(started_at)
    row["last_status"] = outcome_status
    row["next_run_at"] = _iso(compute_next_run(trigger, after=started_at))


def run_due_schedules(
    executor,
    *,
    dry_run: bool = False,
    fail_fast: bool = False,
) -> dict[str, Any]:
    """执行所有到期 schedule；executor 为 execute_plan 函数。"""
    now = _now()
    store = load_store()
    due_rows = [r for r in (store.get("schedules") or []) if is_due(r, now=now)]
    runs: list[dict[str, Any]] = []

    for row in due_rows:
        sid = row.get("id")
        job = row.get("job") or "daily"
        execution_plan = plan_from_job(job)
        item: dict[str, Any] = {
            "schedule_id": sid,
            "job": job,
            "plan": execution_plan,
            "dry_run": dry_run,
        }
        if dry_run:
            item["status"] = "planned"
            runs.append(item)
            continue

        started = _now()
        try:
            outcome = executor(execution_plan, continue_on_error=not fail_fast)
            item["outcome"] = outcome
            item["status"] = outcome.get("status", "failed")
        except (RuntimeError, FileNotFoundError) as e:
            item["status"] = "error"
            item["error"] = str(e)
        mark_run_result(row, outcome_status=item["status"], started_at=started)
        runs.append(item)

    if not dry_run and due_rows:
        save_store(store)

    return {
        "status": "ok",
        "checked_at": _iso(now),
        "due_count": len(due_rows),
        "runs": runs,
    }


def parse_schedule_intent(text: str) -> dict[str, Any] | None:
    """自然语言 → schedule 操作（注册/禁用），非立即执行。"""
    raw = (text or "").strip()
    if not raw:
        return None
    t = raw.lower()

    if _SCHEDULE_DISABLE_RE.search(raw):
        return {"action": "disable", "id": None}

    if not _SCHEDULE_ADD_RE.search(raw):
        return None

    job = "daily"
    if any(k in t for k in ("insight", "pai", "洞察")) and "看板" not in t:
        job = "insight"
    elif any(k in t for k in ("sprint", "项目进度")):
        job = "sprint"
    elif "member" in t or "成员" in t:
        job = "member"
    elif "task" in t or "任务" in t:
        job = "task"

    at_time = parse_daily_at(raw)
    every: str | None = None
    if at_time is None:
        m = _EVERY_RE.search(raw)
        if m:
            if m.group(1):
                every = f"{m.group(1)}h"
            elif m.group(2):
                every = f"{m.group(2)}m"
            else:
                every = f"{m.group(3)}d"
        elif re.search(r"每小时|每一小时|1小时", raw):
            every = "1h"
        elif re.search(r"每半天|12小时", raw):
            every = "12h"
        else:
            return None

    return {
        "action": "add",
        "job": job,
        "every": every,
        "at_time": at_time,
        "id": canonical_schedule_id(job),
        "note": raw,
    }


def handle_schedule_intent(intent: dict[str, Any], *, run_now: bool = False) -> dict[str, Any]:
    action = intent.get("action")
    if action == "disable":
        rows = [r for r in list_schedules(enabled_only=True)]
        if not rows:
            return {"status": "noop", "message": "no enabled schedules"}
        if len(rows) == 1:
            return disable_schedule(rows[0]["id"])
        return {
            "status": "ambiguous",
            "message": "multiple enabled schedules; use: schedule disable --id <id>",
            "schedules": [{"id": r["id"], "job": r.get("job")} for r in rows],
        }
    if action == "add":
        return add_schedule(
            job=intent["job"],
            every=intent.get("every"),
            at_time=intent.get("at_time"),
            schedule_id=intent.get("id"),
            note=intent.get("note"),
            run_now=run_now,
        )
    raise ValueError(f"unknown schedule action: {action}")
