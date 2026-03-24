#!/usr/bin/env python3
"""CLI for kb_trex_team_members with subcommands: list, resolve, review, alias."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from scripts/ dir without installing package
_SHARED_DIR = Path(__file__).parent.parent.parent / "_shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))

from config import env  # noqa: E402


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_list(args) -> int:
    """List members with optional filters."""
    conn_url = env("KB_TREX_PG_URL")
    if not conn_url:
        print("KB_TREX_PG_URL not set.", file=sys.stderr)
        return 1

    import psycopg2
    conn = psycopg2.connect(conn_url)
    cur = conn.cursor()
    cur.execute("SET search_path TO trex_hub, public")

    where_parts: list[str] = []
    params: list = []

    user_id = getattr(args, "user_id", None)
    name = getattr(args, "name", "") or ""
    role = getattr(args, "role", "") or ""

    if user_id is not None:
        where_parts.append("user_id = %s")
        params.append(user_id)
    if name:
        where_parts.append(
            "(real_name ILIKE %s OR username ILIKE %s"
            " OR real_name_en ILIKE %s OR email ILIKE %s)"
        )
        params.extend([f"%{name}%"] * 4)
    if role:
        where_parts.append("role = %s")
        params.append(role)

    where_clause = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
    cur.execute(
        f"SELECT user_id, username, real_name, real_name_en, email, role,"
        f" verified, aliases, created_at"
        f" FROM kb_trex_team_members{where_clause} ORDER BY user_id",
        params,
    )
    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()

    for row in rows:
        if row.get("created_at"):
            row["created_at"] = str(row["created_at"])

    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def cmd_resolve(args) -> int:
    """Resolve a keyword to a user_id via SuperMember."""
    from super_member import SuperMember

    conn_url = env("KB_TREX_PG_URL")
    if not conn_url:
        print("KB_TREX_PG_URL not set.", file=sys.stderr)
        return 1

    import psycopg2
    conn = psycopg2.connect(conn_url)

    sm = SuperMember(conn)
    platform = getattr(args, "platform", "") or ""
    user_id = sm.resolve(args.keyword, platform=platform)
    conn.close()

    print(json.dumps({"keyword": args.keyword, "platform": platform, "user_id": user_id},
                     ensure_ascii=False, indent=2))
    return 0


def cmd_review(args) -> int:
    """Manage kb_trex_member_review_queue (list/approve/reject)."""
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
        f"UPDATE kb_trex_member_review_queue SET status = %s WHERE id = ANY(%s)",
        (new_status, ids),
    )
    conn.commit()
    cur.close()
    conn.close()
    print(json.dumps({"updated": len(ids), "status": new_status}))
    return 0


def cmd_alias(args) -> int:
    """Manage kb_trex_member_aliases (list/delete)."""
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
            "SELECT id, alias, platform, user_id FROM kb_trex_member_aliases ORDER BY id"
        )
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


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query kb_trex_team_members.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Top-level args for backward compatibility (when no subcommand given)
    parser.add_argument("--name", default="", help="Fuzzy match on real_name/username/real_name_en/email.")
    parser.add_argument("--role", default="", help="Exact match on role.")
    parser.add_argument("--user-id", type=int, default=None, dest="user_id",
                        help="Exact match on user_id.")

    subparsers = parser.add_subparsers(dest="command")

    # --- list ---
    p_list = subparsers.add_parser("list", help="List members (default).")
    p_list.add_argument("--name", default="", help="Fuzzy match on real_name/username/real_name_en/email.")
    p_list.add_argument("--role", default="", help="Exact match on role.")
    p_list.add_argument("--user-id", type=int, default=None, dest="user_id",
                        help="Exact match on user_id.")

    # --- resolve ---
    p_resolve = subparsers.add_parser("resolve", help="Resolve a name/alias to user_id.")
    p_resolve.add_argument("keyword", help="Name or alias to resolve.")
    p_resolve.add_argument("--platform", default="", help="Platform context (e.g. github).")

    # --- review ---
    p_review = subparsers.add_parser("review", help="Manage member review queue.")
    p_review.add_argument("action", choices=["list", "approve", "reject"],
                          help="Action to perform.")
    p_review.add_argument("--ids", type=int, nargs="+", default=[],
                          help="IDs to approve/reject.")

    # --- alias ---
    p_alias = subparsers.add_parser("alias", help="Manage member aliases.")
    p_alias.add_argument("action", choices=["list", "delete"], help="Action to perform.")
    p_alias.add_argument("--alias-id", type=int, default=None, dest="alias_id",
                         help="Alias ID to delete.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        # Backward compat: default to list behavior using top-level args
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
