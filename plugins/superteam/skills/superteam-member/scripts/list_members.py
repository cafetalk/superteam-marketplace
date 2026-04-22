#!/usr/bin/env python3
"""CLI for kb_trex_team_members with subcommands: list, resolve, review, alias."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Sandbox-safe: avoid writing __pycache__ in readonly environments.
sys.dont_write_bytecode = True

# Allow running from scripts/ dir without installing package
_SHARED_DIR = Path(__file__).parent.parent.parent / "_shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))
_CORE_DIR = Path(__file__).parent.parent / "core"
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from config import env  # noqa: E402


def _get_conn():
    conn_url = env("KB_TREX_PG_URL")
    if not conn_url:
        print("KB_TREX_PG_URL not set.", file=sys.stderr)
        sys.exit(1)
    import psycopg2
    conn = psycopg2.connect(conn_url)
    cur = conn.cursor()
    cur.execute("SET search_path TO trex_hub, public")
    cur.close()
    return conn


def cmd_list(args) -> int:
    from db import _use_mcp, list_members as mcp_list_members
    if _use_mcp():
        name = getattr(args, "name", "") or None
        rows = mcp_list_members(name_query=name)
    else:
        from queries import query_list_members
        conn = _get_conn()
        try:
            rows = query_list_members(
                conn,
                name=getattr(args, "name", "") or None,
                role=getattr(args, "role", "") or None,
                user_id=getattr(args, "user_id", None),
            )
        finally:
            conn.close()
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def cmd_resolve(args) -> int:
    from db import _use_mcp

    if _use_mcp():
        from db import resolve_member
        result = resolve_member(args.keyword)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    from super_member import SuperMember
    conn = _get_conn()
    sm = SuperMember(conn)
    platform = getattr(args, "platform", "") or ""
    user_id = sm.resolve(args.keyword, platform=platform)
    conn.close()

    print(json.dumps({"keyword": args.keyword, "platform": platform, "user_id": user_id}, ensure_ascii=False, indent=2))
    return 0


def cmd_review(args) -> int:
    conn_url = env("KB_TREX_PG_URL")
    if not conn_url:
        print("KB_TREX_PG_URL not set.", file=sys.stderr)
        return 1

    import psycopg2
    conn = psycopg2.connect(conn_url)
    cur = conn.cursor()
    cur.execute("SET search_path TO trex_hub, public")

    action = args.action
    if action == "list":
        cur.execute(
            "SELECT id, raw_name, email, platform, resolved_user_id, reason, status"
            " FROM kb_trex_member_review_queue ORDER BY id"
        )
        columns = [desc[0] for desc in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        cur.close()
        conn.close()
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    ids = getattr(args, "ids", None) or []
    if not ids:
        print("--ids required for approve/reject.", file=sys.stderr)
        cur.close()
        conn.close()
        return 1

    new_status = "approved" if action == "approve" else "rejected"
    cur.execute(
        "UPDATE kb_trex_member_review_queue SET status = %s WHERE id = ANY(%s)",
        (new_status, ids),
    )
    conn.commit()
    cur.close()
    conn.close()
    print(json.dumps({"updated": len(ids), "status": new_status}))
    return 0


def cmd_alias(args) -> int:
    conn_url = env("KB_TREX_PG_URL")
    if not conn_url:
        print("KB_TREX_PG_URL not set.", file=sys.stderr)
        return 1

    import psycopg2
    conn = psycopg2.connect(conn_url)
    cur = conn.cursor()
    cur.execute("SET search_path TO trex_hub, public")

    action = args.action
    if action == "list":
        cur.execute("SELECT id, alias, platform, user_id FROM kb_trex_member_aliases ORDER BY id")
        columns = [desc[0] for desc in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        cur.close()
        conn.close()
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    alias_id = getattr(args, "alias_id", None)
    if not alias_id:
        print("--alias-id required for delete.", file=sys.stderr)
        cur.close()
        conn.close()
        return 1

    cur.execute("DELETE FROM kb_trex_member_aliases WHERE id = %s", (alias_id,))
    conn.commit()
    cur.close()
    conn.close()
    print(json.dumps({"deleted_id": alias_id}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query kb_trex_team_members.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--name", default="", help="Fuzzy match on real_name/username/real_name_en/email.")
    parser.add_argument("--role", default="", help="Exact match on role.")
    parser.add_argument("--user-id", type=int, default=None, dest="user_id", help="Exact match on user_id.")

    subparsers = parser.add_subparsers(dest="command")
    p_list = subparsers.add_parser("list", help="List members (default).")
    p_list.add_argument("--name", default="", help="Fuzzy match on real_name/username/real_name_en/email.")
    p_list.add_argument("--role", default="", help="Exact match on role.")
    p_list.add_argument("--user-id", type=int, default=None, dest="user_id", help="Exact match on user_id.")

    p_resolve = subparsers.add_parser("resolve", help="Resolve a name/alias to user_id.")
    p_resolve.add_argument("keyword", help="Name or alias to resolve.")
    p_resolve.add_argument("--platform", default="", help="Platform context (e.g. github).")

    p_review = subparsers.add_parser("review", help="Manage member review queue.")
    p_review.add_argument("action", choices=["list", "approve", "reject"], help="Action to perform.")
    p_review.add_argument("--ids", type=int, nargs="+", default=[], help="IDs to approve/reject.")

    p_alias = subparsers.add_parser("alias", help="Manage member aliases.")
    p_alias.add_argument("action", choices=["list", "delete"], help="Action to perform.")
    p_alias.add_argument("--alias-id", type=int, default=None, dest="alias_id", help="Alias ID to delete.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        return cmd_list(args)
    if args.command == "list":
        return cmd_list(args)
    if args.command == "resolve":
        return cmd_resolve(args)
    if args.command == "review":
        return cmd_review(args)
    if args.command == "alias":
        return cmd_alias(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
