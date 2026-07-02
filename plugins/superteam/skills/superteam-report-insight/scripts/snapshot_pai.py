#!/usr/bin/env python3
"""PAI v2 日快照：由 Linear sprint 派生 Project Lead 项目简报。

不重复拉 Linear；依赖同日 ``type=sprint`` 快照（本地 JSON 或 PG）。

Usage:
  python skills/superteam-report-insight/scripts/snapshot_pai.py --upload
  python skills/superteam-report-insight/scripts/snapshot_pai.py --date 2026-06-24 --viewer 王冲
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_SKILLS = _SCRIPTS.parent.parent
_SHARED = _SKILLS / "_shared"
for _p in (_SCRIPTS, _SHARED):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from linear_profile import build_member_profile_index, linear_workspace_from_url  # noqa: E402
from _pai import PAI_VERSION, build_pai_payload  # noqa: E402
from pulse_snapshot_common import (  # noqa: E402
    default_pulse_out_root,
    default_snapshot_date,
    load_report_module,
    resolve_out_dir,
    upload_envelopes_to_pg,
    write_pulse_file,
)

PAI_TEAM_KEY = "trex"
SPRINT_TYPE = "sprint"
PAI_TYPE = "pai"
PERIOD_DAILY = "daily"


def _sprint_json_path(out_dir: Path) -> Path:
    return out_dir / f"{PAI_TEAM_KEY}-{SPRINT_TYPE}-{PERIOD_DAILY}.json"


def _load_json_envelope(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def load_sprint_payload(
    snapshot_date: date,
    out_root: Path,
    *,
    allow_pg: bool = True,
) -> dict[str, Any] | None:
    out_dir = resolve_out_dir(out_root, snapshot_date)
    local = _load_json_envelope(_sprint_json_path(out_dir))
    if local and isinstance(local.get("payload"), dict):
        return local["payload"]

    if not allow_pg:
        return None

    from config import env  # noqa: E402
    from db import get_connection  # noqa: E402
    from pulse import read_pulse_on  # noqa: E402

    if not env("KB_TREX_PG_URL"):
        return None
    conn = get_connection()
    try:
        row = read_pulse_on(
            conn,
            type=SPRINT_TYPE,
            snapshot_date=snapshot_date,
            period=PERIOD_DAILY,
            team=PAI_TEAM_KEY,
        )
    finally:
        conn.close()
    if row and isinstance(row.get("payload"), dict):
        return row["payload"]
    return None


def _slug_viewer(name: str) -> str:
    s = "".join(c if c.isalnum() else "-" for c in name.strip().lower())
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")[:32] or "viewer"


def _load_leader_profile_index(sprint_payload: dict[str, Any]) -> dict[str, str]:
    projects = sprint_payload.get("projects") or []
    workspace = linear_workspace_from_url(
        str((projects[0] or {}).get("project_url") or "") if projects else None,
    )
    try:
        gtw = load_report_module()
        members = [m for m in gtw._iter_report_members() if isinstance(m, dict)]
        return build_member_profile_index(members, workspace=workspace)
    except Exception:
        return {}


def snapshot_pai(
    *,
    snapshot_date: date,
    out_root: Path,
    dry_run: bool = False,
    upload_to_pg: bool = False,
    viewer: str | None = None,
) -> tuple[dict[str, Any], int]:
    sprint_payload = load_sprint_payload(snapshot_date, out_root, allow_pg=True)
    if not sprint_payload:
        raise RuntimeError(
            f"未找到 {snapshot_date} 的 sprint 快照。"
            f"请先运行: bash scripts/run_reports.sh pulse-daily"
        )

    yesterday_payload = load_sprint_payload(snapshot_date - timedelta(days=1), out_root, allow_pg=True)
    profile_index = _load_leader_profile_index(sprint_payload)
    payload = build_pai_payload(
        sprint_payload,
        yesterday_sprint_payload=yesterday_payload,
        snapshot_date=snapshot_date,
        viewer=viewer,
        leader_profile_index=profile_index,
    )

    team_key = PAI_TEAM_KEY if not viewer else f"{PAI_TEAM_KEY}-{_slug_viewer(viewer)}"
    out_dir = resolve_out_dir(out_root, snapshot_date)
    envelope = {
        "snapshot_date": snapshot_date.isoformat(),
        "team": team_key,
        "type": PAI_TYPE,
        "period": PERIOD_DAILY,
        "payload": payload,
    }
    if viewer:
        envelope["viewer"] = viewer

    entry: dict[str, Any] = {
        "team": team_key,
        "type": PAI_TYPE,
        "period": PERIOD_DAILY,
        "version": PAI_VERSION,
        "summary": payload.get("summary"),
        "project_count": payload.get("project_count", 0),
        "leader_count": payload.get("leader_count", 0),
        "needs_attention_count": payload.get("needs_attention_count", 0),
        "needs_attention": int(payload.get("needs_attention_count") or 0) > 0,
        "payload": payload,
    }
    if viewer:
        entry["viewer"] = viewer

    upload_count = 0
    if not dry_run:
        entry["file"] = str(write_pulse_file(out_dir, envelope))
        if upload_to_pg:
            upload_count = upload_envelopes_to_pg([envelope])
            entry["uploaded"] = True
    return entry, upload_count


def main() -> int:
    p = argparse.ArgumentParser(description="PAI v2 — Linear sprint → Project Lead 简报")
    p.add_argument("--date", default=None, help="snapshot_date YYYY-MM-DD（默认今天）")
    p.add_argument(
        "--out-dir",
        default=str(default_pulse_out_root()),
        help="pulse 根目录（默认 ~/.superteam/pulse）",
    )
    p.add_argument("--viewer", default=None, help="仅输出该 Project Lead 的项目（姓名）")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--upload", action="store_true")
    args = p.parse_args()

    snapshot_date = default_snapshot_date(args.date)
    out_root = Path(args.out_dir)

    try:
        entry, upload_count = snapshot_pai(
            snapshot_date=snapshot_date,
            out_root=out_root,
            dry_run=args.dry_run,
            upload_to_pg=args.upload,
            viewer=(args.viewer.strip() if args.viewer else None),
        )
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "type": PAI_TYPE,
                "version": PAI_VERSION,
                "period": PERIOD_DAILY,
                "team": entry.get("team"),
                "snapshot_date": snapshot_date.isoformat(),
                "out_dir": str(resolve_out_dir(out_root, snapshot_date)),
                "uploaded": bool(args.upload and not args.dry_run),
                "upload_count": upload_count,
                "entry": entry,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
