"""Read ``trex_hub.daily_report_snapshots`` for team weekly report code stats.

Typical row: ``source='git'``, ``payload`` JSON with ``files[]`` where ``kind='user'``
and ``user.stats.insertions`` / ``user.stats.deletions`` (GitLab 日报切片).

Direct DB only (``KB_TREX_PG_URL``); callers open connection via ``db.get_connection``.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date
from typing import Any


DEFAULT_GIT_SNAPSHOT_SOURCE = "git"


def _norm_person_key(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip()).casefold()


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def extract_person_code_stats_from_payload(payload: Any) -> list[tuple[str, int, int]]:
    """从单日 ``payload`` 提取 (显示名, insertions, deletions) 列表。

    支持：
    - ``files[]`` 中 ``kind=user`` → ``user.stats``
    - 顶层 ``insertions``/``deletions`` + ``real_name``/``username``/``name``
    - ``members[]`` 日报采集结构 → ``git.summary.total_*``
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return []
    if not isinstance(payload, dict):
        return []

    out: list[tuple[str, int, int]] = []

    top_ins = payload.get("insertions")
    top_del = payload.get("deletions")
    if top_ins is not None or top_del is not None:
        name = str(
            payload.get("real_name")
            or payload.get("username")
            or payload.get("member")
            or payload.get("name")
            or "",
        ).strip()
        if name:
            out.append((name, _as_int(top_ins), _as_int(top_del)))

    for item in payload.get("files") or []:
        if not isinstance(item, dict) or item.get("kind") != "user":
            continue
        user = item.get("user")
        if not isinstance(user, dict):
            continue
        name = str(user.get("name") or "").strip()
        if not name:
            continue
        stats = user.get("stats") if isinstance(user.get("stats"), dict) else {}
        out.append((
            name,
            _as_int(stats.get("insertions")),
            _as_int(stats.get("deletions")),
        ))

    for member in payload.get("members") or []:
        if not isinstance(member, dict):
            continue
        name = str(
            member.get("real_name")
            or member.get("username")
            or "",
        ).strip()
        if not name:
            continue
        git = member.get("git") if isinstance(member.get("git"), dict) else {}
        summary = git.get("summary") if isinstance(git.get("summary"), dict) else {}
        ins = _as_int(summary.get("total_insertions") or summary.get("insertions"))
        dels = _as_int(summary.get("total_deletions") or summary.get("deletions"))
        if ins or dels:
            out.append((name, ins, dels))

    return out


def query_daily_report_snapshots(
    conn,
    *,
    start_date: date,
    end_date: date,
    source: str = DEFAULT_GIT_SNAPSHOT_SOURCE,
) -> list[dict[str, Any]]:
    """按日期区间读取 ``daily_report_snapshots`` 行（含 ``payload`` 已解析为 dict）。"""
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    cur = conn.cursor()
    cur.execute(
        """
        SELECT report_date, source, payload, generated_at
        FROM daily_report_snapshots
        WHERE source = %s
          AND report_date >= %s
          AND report_date <= %s
        ORDER BY report_date ASC
        """,
        (source, start_date, end_date),
    )
    rows: list[dict[str, Any]] = []
    for report_date, src, payload, generated_at in cur.fetchall():
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        elif payload is None:
            payload = {}
        rows.append({
            "report_date": report_date,
            "source": src,
            "payload": payload,
            "generated_at": generated_at,
        })
    cur.close()
    return rows


def aggregate_code_stats_by_snapshot_name(
    conn,
    *,
    start_date: date,
    end_date: date,
    source: str = DEFAULT_GIT_SNAPSHOT_SOURCE,
) -> dict[str, dict[str, int]]:
    """按 ``payload`` 内人员显示名汇总区间代码行数。

    返回 ``{snapshot_name: {insertions, deletions, active_days}}``。
    """
    totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"insertions": 0, "deletions": 0, "active_days": 0},
    )
    day_seen: dict[str, set[date]] = defaultdict(set)

    for row in query_daily_report_snapshots(
        conn, start_date=start_date, end_date=end_date, source=source,
    ):
        rd = row["report_date"]
        if not isinstance(rd, date):
            continue
        for name, ins, dels in extract_person_code_stats_from_payload(row["payload"]):
            bucket = totals[name]
            bucket["insertions"] += ins
            bucket["deletions"] += dels
            if ins or dels:
                day_seen[name].add(rd)

    for name, days in day_seen.items():
        totals[name]["active_days"] = len(days)

    return dict(totals)


def _member_display_names(m: dict[str, Any]) -> list[str]:
    """与团队周报 ``_member_display_names`` 一致：匹配 Linear assignee / 日报人名。"""
    seen: set[str] = set()
    out: list[str] = []

    def _add(s: str) -> None:
        t = s.strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)

    for key in ("real_name", "realName", "username", "real_name_en", "realNameEn", "email"):
        v = m.get(key)
        if isinstance(v, str):
            _add(v)
            if key == "email" and "@" in v:
                _add(v.split("@", 1)[0])
    raw_aliases = m.get("aliases")
    if isinstance(raw_aliases, str) and raw_aliases.strip():
        try:
            parsed = json.loads(raw_aliases)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            for a in parsed:
                if isinstance(a, str):
                    _add(a)
    elif isinstance(raw_aliases, list):
        for a in raw_aliases:
            if isinstance(a, str):
                _add(a)
    return out


def build_member_code_stats_lookup(
    conn,
    *,
    start_date: date,
    end_date: date,
    member_rows: list[dict[str, Any]],
    source: str = DEFAULT_GIT_SNAPSHOT_SOURCE,
) -> dict[str, dict[str, int]]:
    """将快照人名映射到成员表主显示名（``real_name`` 优先），供 §3 owner 查询。

    返回的 key 包含成员表各别名 + ``real_name``，value 为同一汇总对象。
    """
    by_snapshot = aggregate_code_stats_by_snapshot_name(
        conn,
        start_date=start_date,
        end_date=end_date,
        source=source,
    )
    if not by_snapshot:
        return {}

    snap_index: dict[str, str] = {}
    for snap_name in by_snapshot:
        snap_index[_norm_person_key(snap_name)] = snap_name

    lookup: dict[str, dict[str, int]] = {}

    def _attach_aliases(stats: dict[str, int], names: list[str]) -> None:
        for nm in names:
            s = (nm or "").strip()
            if s:
                lookup[s] = stats

    for member in member_rows:
        if not isinstance(member, dict):
            continue
        primary = str(member.get("real_name") or member.get("username") or "").strip()
        if not primary:
            continue
        merged = {"insertions": 0, "deletions": 0, "active_days": 0}
        matched_days: set[date] = set()

        matched_snap_names: set[str] = set()
        for alias in _member_display_names(member):
            snap_name = snap_index.get(_norm_person_key(alias))
            if not snap_name or snap_name in matched_snap_names:
                continue
            matched_snap_names.add(snap_name)
            st = by_snapshot[snap_name]
            merged["insertions"] += st["insertions"]
            merged["deletions"] += st["deletions"]
            merged["active_days"] = max(merged["active_days"], st["active_days"])

        if merged["insertions"] or merged["deletions"]:
            _attach_aliases(merged, _member_display_names(member))
            _attach_aliases(merged, [primary])

    return lookup


def load_weekly_member_code_stats_lookup(
    iso_week: str,
    *,
    member_rows: list[dict[str, Any]] | None = None,
    source: str = DEFAULT_GIT_SNAPSHOT_SOURCE,
) -> dict[str, dict[str, int]] | None:
    """按 ISO 周加载成员代码统计；无 DB 或查询失败时返回 ``None``。"""
    from config import env  # noqa: WPS433

    if not env("KB_TREX_PG_URL"):
        return None

    try:
        from db import get_connection  # noqa: WPS433
    except Exception:
        return None

    if member_rows is None:
        try:
            from db import list_members  # noqa: WPS433
            member_rows = list_members() or []
        except Exception:
            member_rows = []

    week_start, week_end = _iso_week_to_dates(iso_week)
    try:
        conn = get_connection()
        try:
            return build_member_code_stats_lookup(
                conn,
                start_date=week_start,
                end_date=week_end,
                member_rows=member_rows,
                source=source,
            )
        finally:
            conn.close()
    except Exception:
        return None


def _iso_week_to_dates(iso_week: str) -> tuple[date, date]:
    """Parse ``YYYY-Www`` to Monday..Sunday (duplicated lightly to avoid import cycle)."""
    m = re.match(r"^(\d{4})-W(\d{1,2})$", (iso_week or "").strip(), re.I)
    if not m:
        raise ValueError(f"invalid iso_week: {iso_week!r}")
    y, w = int(m.group(1)), int(m.group(2))
    return date.fromisocalendar(y, w, 1), date.fromisocalendar(y, w, 7)
