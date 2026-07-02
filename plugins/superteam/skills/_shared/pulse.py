"""Shared upsert + payload builders for sp_trex_pulse.

- upsert_pulse / read_latest_pulse / read_pulse_on — generic CRUD, used by all snapshot types
- compute_kb_pulse_payload — knowledge_base specific aggregation

Direct-mode only (writes go through psycopg2). Read path can go through this
module from Hub reader scripts, or through MCP for remote users.
"""
from __future__ import annotations
import json
from datetime import date, datetime, timedelta
from typing import Any


VALID_TYPES = {"knowledge_base", "sprint", "member", "pai", "task"}
VALID_PERIODS = {"daily", "weekly"}


def upsert_pulse(
    conn,
    *,
    snapshot_date: date,
    type: str,
    payload: dict[str, Any],
    period: str = "daily",
    team: str = "",
    generated_at: datetime | None = None,
) -> None:
    """Upsert one row into sp_trex_pulse.

    PK is (snapshot_date, type, period, team) — re-runs overwrite payload
    atomically. Does NOT commit; caller controls transaction.
    """
    if type not in VALID_TYPES:
        raise ValueError(f"invalid type {type!r}; expected one of {sorted(VALID_TYPES)}")
    if period not in VALID_PERIODS:
        raise ValueError(f"invalid period {period!r}; expected one of {sorted(VALID_PERIODS)}")
    if not isinstance(payload, dict):
        raise TypeError(f"payload must be dict, got {payload.__class__.__name__}")

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sp_trex_pulse "
        "(snapshot_date, type, period, team, payload, generated_at) "
        "VALUES (%s, %s, %s, %s, %s::jsonb, %s) "
        "ON CONFLICT (snapshot_date, type, period, team) DO UPDATE SET "
        "payload = EXCLUDED.payload, "
        "generated_at = EXCLUDED.generated_at, "
        "updated_at = now()",
        (
            snapshot_date,
            type,
            period,
            team,
            json.dumps(payload, ensure_ascii=False),
            generated_at,
        ),
    )
    cur.close()


def read_latest_pulse(
    conn,
    *,
    type: str,
    period: str = "daily",
    team: str = "",
) -> dict | None:
    """Read the most recent pulse row for a given type/period/team.

    Returns {"snapshot_date", "payload", "generated_at"} or None.
    """
    if type not in VALID_TYPES:
        raise ValueError(f"invalid type {type!r}")

    cur = conn.cursor()
    cur.execute(
        "SELECT snapshot_date, payload, generated_at "
        "FROM sp_trex_pulse "
        "WHERE type = %s AND period = %s AND team = %s "
        "ORDER BY snapshot_date DESC LIMIT 1",
        (type, period, team),
    )
    row = cur.fetchone()
    cur.close()

    if not row:
        return None

    snap_date, payload, generated_at = row
    if isinstance(payload, str):
        payload = json.loads(payload)
    return {
        "snapshot_date": str(snap_date),
        "payload": payload,
        "generated_at": str(generated_at) if generated_at else None,
    }


def read_pulse_on(
    conn,
    *,
    type: str,
    snapshot_date: date,
    period: str = "daily",
    team: str = "",
) -> dict | None:
    """Read pulse row for an explicit snapshot_date. Returns same shape as read_latest_pulse."""
    if type not in VALID_TYPES:
        raise ValueError(f"invalid type {type!r}")

    cur = conn.cursor()
    cur.execute(
        "SELECT snapshot_date, payload, generated_at "
        "FROM sp_trex_pulse "
        "WHERE type = %s AND period = %s AND team = %s AND snapshot_date = %s",
        (type, period, team, snapshot_date),
    )
    row = cur.fetchone()
    cur.close()

    if not row:
        return None

    snap_date, payload, generated_at = row
    if isinstance(payload, str):
        payload = json.loads(payload)
    return {
        "snapshot_date": str(snap_date),
        "payload": payload,
        "generated_at": str(generated_at) if generated_at else None,
    }


# ---------------------------------------------------------------------------
# Knowledge-base payload computation
# ---------------------------------------------------------------------------

def compute_kb_pulse_payload(conn, snapshot_date: date) -> dict[str, Any]:
    """Aggregate kb_trex_* tables into a knowledge_base pulse payload.

    All time comparisons use snapshot_date 23:59:59 UTC as the upper bound so
    backfill runs produce the same result as a live run on that day.
    """
    end_ts = datetime.combine(snapshot_date, datetime.max.time())
    cur = conn.cursor()

    # total_docs and by_source_type — docs created on or before snapshot_date
    cur.execute(
        "SELECT source_type, COUNT(*) "
        "FROM kb_trex_source_docs "
        "WHERE created_at <= %s "
        "GROUP BY source_type",
        (end_ts,),
    )
    by_source_type: dict[str, int] = {}
    total_docs = 0
    for stype, cnt in cur.fetchall():
        by_source_type[stype] = cnt
        total_docs += cnt

    # synced_today — docs first added (created_at) on snapshot_date
    cur.execute(
        "SELECT COUNT(*) FROM kb_trex_source_docs "
        "WHERE created_at::date = %s",
        (snapshot_date,),
    )
    synced_today: int = cur.fetchone()[0]

    # updated_today — docs whose content changed (last_edited_at) on snapshot_date
    cur.execute(
        "SELECT COUNT(*) FROM kb_trex_source_docs "
        "WHERE last_edited_at IS NOT NULL "
        "AND (last_edited_at AT TIME ZONE 'UTC')::date = %s",
        (snapshot_date,),
    )
    updated_today: int = cur.fetchone()[0]

    # last_sync_at — most recent last_synced_at up to end of snapshot_date
    cur.execute(
        "SELECT MAX(last_synced_at) FROM kb_trex_source_docs "
        "WHERE last_synced_at <= %s",
        (end_ts,),
    )
    last_sync_at = cur.fetchone()[0]

    # last_sync_doc_count — docs synced in the same minute window as last_sync_at
    last_sync_doc_count = 0
    if last_sync_at:
        window_start = last_sync_at - timedelta(minutes=1)
        cur.execute(
            "SELECT COUNT(*) FROM kb_trex_source_docs "
            "WHERE last_synced_at BETWEEN %s AND %s",
            (window_start, last_sync_at),
        )
        last_sync_doc_count = cur.fetchone()[0]

    # total_chunks — rows in kb_trex_team_docs (embedding chunks)
    cur.execute(
        "SELECT COUNT(*) FROM kb_trex_team_docs "
        "WHERE created_at <= %s",
        (end_ts,),
    )
    total_chunks: int = cur.fetchone()[0]

    # members_total — all team members (not time-scoped; membership is current)
    cur.execute("SELECT COUNT(*) FROM kb_trex_team_members")
    members_total: int = cur.fetchone()[0]

    # by_doc_type — docs created on or before snapshot_date
    cur.execute(
        "SELECT doc_type, COUNT(*) "
        "FROM kb_trex_source_docs "
        "WHERE created_at <= %s "
        "GROUP BY doc_type",
        (end_ts,),
    )
    by_doc_type: dict[str, int] = {
        (dt or "unknown"): cnt for dt, cnt in cur.fetchall()
    }

    cur.close()

    return {
        "total_docs": total_docs,
        "by_source_type": by_source_type,
        "synced_today": synced_today,
        "updated_today": updated_today,
        "last_sync_at": last_sync_at.isoformat() if last_sync_at else None,
        "last_sync_doc_count": last_sync_doc_count,
        "total_chunks": total_chunks,
        "members_total": members_total,
        "by_doc_type": by_doc_type,
    }
