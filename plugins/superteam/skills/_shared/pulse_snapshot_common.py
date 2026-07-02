"""TREX-493 pulse 快照：sprint / task / member / pai 共用落盘、入库与 Linear 口径桥接。"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator

_SHARED_DIR = Path(__file__).resolve().parent
REPO_ROOT = _SHARED_DIR.parent.parent
REPORT_MODULE = (
    REPO_ROOT / "skills" / "superteam-report" / "scripts" / "generate_team_weekly_report.py"
)


def load_report_module():
    spec = importlib.util.spec_from_file_location("gtw_pulse", REPORT_MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {REPORT_MODULE}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def team_slug(team: dict[str, Any]) -> str:
    for key in ("key", "slug", "name"):
        v = team.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip().lower().replace(" ", "-")
    tid = str(team.get("id") or team.get("teamId") or "unknown")
    return tid[:8]


def write_pulse_file(out_dir: Path, envelope: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    team = envelope.get("team") or "unknown"
    period = envelope.get("period") or "daily"
    ptype = envelope.get("type") or "pulse"
    path = out_dir / f"{team}-{ptype}-{period}.json"
    path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def issue_pulse_bucket(it: dict[str, Any], status_type_map: dict[str, str], gtw: Any) -> str:
    bucket = gtw._state_bucket_for_issue(it, status_type_map)
    if bucket == "canceled":
        return "skip"
    if gtw._is_blocked_status(it.get("status")):
        return "blocked"
    if bucket == "done":
        return "done"
    status_name = str(it.get("status") or "").lower()
    if "review" in status_name:
        return "in_review"
    if bucket == "in_progress":
        return "in_progress"
    if bucket in ("todo", "backlog"):
        return "todo"
    st = gtw._linear_issue_status_type_lower(it, status_type_map)
    if st == "started":
        return "in_progress"
    if st == "completed":
        return "done"
    if st == "unstarted":
        return "todo"
    return "todo"


def list_teams(gtw: Any, mcp: Any, client: Any, tool_names: set[str], *, include_archived: bool) -> list[dict[str, Any]]:
    teams = mcp.list_teams(client, tool_names=tool_names)
    if not include_archived:
        teams = [t for t in teams if not t.get("archivedAt")]
    return teams


def status_type_map_for_team(
    mcp: Any, client: Any, tool_names: set[str], team_id: str,
) -> dict[str, str]:
    out: dict[str, str] = {}
    for s in mcp.list_issue_statuses(client, tool_names, team_id=team_id):
        if isinstance(s, dict):
            out[s.get("name", "")] = s.get("type", "")
    return out


def linear_client(gtw: Any) -> Iterator[tuple[Any, Any, set[str]]]:
    """yield (client, mcp, tool_names)."""
    mcp = gtw.LinearMcpClient()
    try:
        with gtw._StdioMcpClient(mcp._cmd) as client:
            yield client, mcp, client.list_tools()
    except gtw._LocalMcpError as e:
        raise RuntimeError(str(e)) from e


def default_pulse_out_root() -> Path:
    """默认 pulse 落盘根目录（项目外，见 ``config.pulse_output_root``）。"""
    from config import pulse_output_root

    return pulse_output_root()


def resolve_out_dir(out_root: Path, snapshot_date: date) -> Path:
    root = Path(out_root).expanduser()
    if not root.is_absolute():
        root = (REPO_ROOT / root).resolve()
    return root / snapshot_date.isoformat()


def default_snapshot_date(value: str | None) -> date:
    if value:
        return date.fromisoformat(value)
    return datetime.now().astimezone().date()


def cycle_to_json(cycle: dict[str, Any], gtw: Any) -> dict[str, Any]:
    starts = gtw._parse_dt(str(cycle.get("startsAt") or ""))
    ends = gtw._parse_dt(str(cycle.get("endsAt") or ""))
    return {
        "id": str(cycle.get("id") or cycle.get("cycleId") or ""),
        "number": cycle.get("number"),
        "starts_at": gtw._to_local_date(starts).isoformat() if starts else None,
        "ends_at": gtw._to_local_date(ends).isoformat() if ends else None,
    }


def upload_envelopes_to_pg(envelopes: list[dict[str, Any]]) -> int:
    """将 envelope 列表写入 sp_trex_pulse（``pulse.upsert_pulse``，单事务）。"""
    if not envelopes:
        return 0
    from config import env
    from db import get_connection
    from pulse import upsert_pulse

    if not env("KB_TREX_PG_URL"):
        raise RuntimeError(
            "KB_TREX_PG_URL not set — 无法入库 sp_trex_pulse，请在 ~/.superteam/config 配置",
        )
    conn = get_connection()
    try:
        for envelope in envelopes:
            snap = envelope["snapshot_date"]
            snapshot_date = snap if isinstance(snap, date) else date.fromisoformat(str(snap))
            upsert_pulse(
                conn,
                snapshot_date=snapshot_date,
                type=str(envelope["type"]),
                payload=envelope["payload"],
                period=str(envelope["period"]),
                team=str(envelope.get("team") or "").strip(),
                generated_at=datetime.utcnow(),
            )
        count = len(envelopes)
        conn.commit()
        return count
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def resolve_target_cycles(
    mcp: Any,
    client: Any,
    tool_names: set[str],
    *,
    team_id: str,
    iso_week: str,
    gtw: Any,
) -> list[dict[str, Any]]:
    """与 snapshot_sprint 一致：优先当前 Cycle，否则取与 iso_week 重叠的最近一个。"""
    current = mcp.list_cycles_current(client, tool_names, team_id=team_id)
    if current:
        return current[:1]
    cycles_all = mcp.list_cycles_for_team(client, tool_names, team_id=team_id)
    week_cycles = gtw._pick_cycles_for_week(cycles_all, iso_week)
    return week_cycles[:1] if week_cycles else []
