#!/usr/bin/env python3
"""Member profile management for kb_trex_team_members."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Sandbox-safe: avoid writing __pycache__ in readonly environments.
sys.dont_write_bytecode = True

_SHARED_DIR = Path(__file__).parent.parent.parent / "_shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))

from config import env  # noqa: E402


def _error(code: str, message: str, extra: dict | None = None) -> int:
    payload = {"ok": False, "error_code": code, "message": message}
    if extra:
        payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1


def _ok(payload: dict) -> int:
    payload = {"ok": True, **payload}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _get_conn():
    conn_url = env("KB_TREX_PG_URL")
    if not conn_url:
        return None, _error("CONFIG_MISSING", "KB_TREX_PG_URL not set.")
    import psycopg2

    conn = psycopg2.connect(conn_url)
    cur = conn.cursor()
    cur.execute("SET search_path TO trex_hub, public")
    cur.close()
    return conn, None


def _validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def _fetch_member(cur, user_id: int) -> dict | None:
    cur.execute(
        """
        SELECT user_id, username, real_name, real_name_en, email, role, aliases, verified
        FROM kb_trex_team_members
        WHERE user_id = %s
        """,
        (user_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    cols = [d[0] for d in cur.description]
    data = dict(zip(cols, row))
    aliases = data.get("aliases")
    if isinstance(aliases, str):
        try:
            data["aliases"] = json.loads(aliases)
        except Exception:
            data["aliases"] = []
    return data


def _write_audit(cur, target_user_id: int, operator_user_id: int, action: str, before: dict, after: dict) -> None:
    cur.execute(
        """
        INSERT INTO kb_trex_member_audit_logs
            (target_user_id, operator_user_id, action, before_data, after_data)
        VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)
        """,
        (
            target_user_id,
            operator_user_id,
            action,
            json.dumps(before, ensure_ascii=False),
            json.dumps(after, ensure_ascii=False),
        ),
    )


def _is_undefined_table_error(err: Exception) -> bool:
    pgcode = getattr(err, "pgcode", None)
    if pgcode == "42P01":
        return True
    msg = str(err).lower()
    return "kb_trex_member_audit_logs" in msg and ("does not exist" in msg or "undefined table" in msg)


def _try_write_audit(
    cur,
    target_user_id: int,
    operator_user_id: int | None,
    action: str,
    before: dict,
    after: dict,
    no_audit: bool,
) -> dict:
    if operator_user_id is None:
        return {"written": False, "skipped_reason": "missing_operator_user_id"}
    if no_audit:
        return {"written": False, "skipped_reason": "disabled_by_flag"}
    try:
        _write_audit(cur, target_user_id, operator_user_id, action, before, after)
        return {"written": True}
    except Exception as e:
        if _is_undefined_table_error(e):
            return {"written": False, "skipped_reason": "audit_table_missing"}
        raise


def cmd_get(args) -> int:
    conn, err = _get_conn()
    if err:
        return err
    try:
        cur = conn.cursor()
        member = _fetch_member(cur, args.user_id)
        if not member:
            return _error("NOT_FOUND", "member not found", {"user_id": args.user_id})
        return _ok({"member": member})
    finally:
        conn.close()


def cmd_update(args) -> int:
    updates: dict[str, object] = {}
    if args.real_name is not None:
        v = args.real_name.strip()
        if not v:
            return _error("INVALID_ARGUMENT", "real_name cannot be empty.")
        updates["real_name"] = v
    if args.real_name_en is not None:
        updates["real_name_en"] = args.real_name_en.strip() or None
    if args.username is not None:
        v = args.username.strip()
        if not v:
            return _error("INVALID_ARGUMENT", "username cannot be empty.")
        updates["username"] = v
    if args.role is not None:
        updates["role"] = args.role.strip() or None
    if args.email is not None:
        v = args.email.strip()
        if v and not _validate_email(v):
            return _error("INVALID_ARGUMENT", "invalid email format.")
        updates["email"] = v or None

    if not updates:
        return _error("INVALID_ARGUMENT", "at least one update field is required.")

    conn, err = _get_conn()
    if err:
        return err
    try:
        cur = conn.cursor()
        before = _fetch_member(cur, args.user_id)
        if not before:
            return _error("NOT_FOUND", "member not found", {"user_id": args.user_id})

        set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
        vals = list(updates.values()) + [args.user_id]
        cur.execute(f"UPDATE kb_trex_team_members SET {set_clause} WHERE user_id = %s", vals)

        after = _fetch_member(cur, args.user_id)
        audit = _try_write_audit(
            cur,
            args.user_id,
            args.operator_user_id,
            "update_profile",
            before,
            after,
            args.no_audit,
        )
        conn.commit()

        changed = [k for k in ["username", "real_name", "real_name_en", "email", "role"] if before.get(k) != after.get(k)]
        return _ok(
            {
                "action": "update_profile",
                "target_user_id": args.user_id,
                "operator_user_id": args.operator_user_id,
                "changed_fields": changed,
                "before": before,
                "after": after,
                "audit": audit,
            }
        )
    except Exception as e:
        conn.rollback()
        return _error("INTERNAL_ERROR", str(e))
    finally:
        conn.close()


def cmd_set_aliases(args) -> int:
    try:
        aliases = json.loads(args.aliases_json)
    except Exception:
        return _error("INVALID_ARGUMENT", "aliases_json must be a valid JSON array.")
    if not isinstance(aliases, list):
        return _error("INVALID_ARGUMENT", "aliases_json must be a JSON array.")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in aliases:
        s = str(item).strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(s)

    conn, err = _get_conn()
    if err:
        return err
    try:
        cur = conn.cursor()
        before = _fetch_member(cur, args.user_id)
        if not before:
            return _error("NOT_FOUND", "member not found", {"user_id": args.user_id})

        cur.execute(
            "UPDATE kb_trex_team_members SET aliases = %s::jsonb WHERE user_id = %s",
            (json.dumps(normalized, ensure_ascii=False), args.user_id),
        )
        after = _fetch_member(cur, args.user_id)
        audit = _try_write_audit(
            cur,
            args.user_id,
            args.operator_user_id,
            "set_aliases",
            before,
            after,
            args.no_audit,
        )
        conn.commit()
        return _ok(
            {
                "action": "set_aliases",
                "target_user_id": args.user_id,
                "operator_user_id": args.operator_user_id,
                "before_aliases": before.get("aliases") or [],
                "after_aliases": after.get("aliases") or [],
                "audit": audit,
            }
        )
    except Exception as e:
        conn.rollback()
        return _error("INTERNAL_ERROR", str(e))
    finally:
        conn.close()


def cmd_append_alias(args) -> int:
    alias = args.alias.strip()
    if not alias:
        return _error("INVALID_ARGUMENT", "alias cannot be empty.")

    conn, err = _get_conn()
    if err:
        return err
    try:
        cur = conn.cursor()
        before = _fetch_member(cur, args.user_id)
        if not before:
            return _error("NOT_FOUND", "member not found", {"user_id": args.user_id})

        aliases = before.get("aliases") or []
        lower_existing = {str(a).lower() for a in aliases}
        if alias.lower() not in lower_existing:
            aliases = aliases + [alias]
            cur.execute(
                "UPDATE kb_trex_team_members SET aliases = %s::jsonb WHERE user_id = %s",
                (json.dumps(aliases, ensure_ascii=False), args.user_id),
            )

        after = _fetch_member(cur, args.user_id)
        audit = _try_write_audit(
            cur,
            args.user_id,
            args.operator_user_id,
            "append_alias",
            before,
            after,
            args.no_audit,
        )
        conn.commit()
        return _ok(
            {
                "action": "append_alias",
                "target_user_id": args.user_id,
                "operator_user_id": args.operator_user_id,
                "before_aliases": before.get("aliases") or [],
                "after_aliases": after.get("aliases") or [],
                "audit": audit,
            }
        )
    except Exception as e:
        conn.rollback()
        return _error("INTERNAL_ERROR", str(e))
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage kb_trex_team_members.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_get = sub.add_parser("get", help="Get one member by user_id.")
    p_get.add_argument("--user-id", type=int, required=True, dest="user_id")

    p_update = sub.add_parser("update", help="Update member profile fields.")
    p_update.add_argument("--operator-user-id", type=int, required=False, default=None, dest="operator_user_id")
    p_update.add_argument("--user-id", type=int, required=True, dest="user_id")
    p_update.add_argument("--real-name", default=None)
    p_update.add_argument("--real-name-en", default=None)
    p_update.add_argument("--username", default=None)
    p_update.add_argument("--role", default=None)
    p_update.add_argument("--email", default=None)
    p_update.add_argument("--no-audit", action="store_true", help="Skip audit log write.")

    p_set = sub.add_parser("set-aliases", help="Replace aliases with given JSON array.")
    p_set.add_argument("--operator-user-id", type=int, required=False, default=None, dest="operator_user_id")
    p_set.add_argument("--user-id", type=int, required=True, dest="user_id")
    p_set.add_argument("--aliases-json", required=True, dest="aliases_json")
    p_set.add_argument("--no-audit", action="store_true", help="Skip audit log write.")

    p_append = sub.add_parser("append-alias", help="Append one alias if not exists.")
    p_append.add_argument("--operator-user-id", type=int, required=False, default=None, dest="operator_user_id")
    p_append.add_argument("--user-id", type=int, required=True, dest="user_id")
    p_append.add_argument("--alias", required=True)
    p_append.add_argument("--no-audit", action="store_true", help="Skip audit log write.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "get":
        return cmd_get(args)
    if args.command == "update":
        return cmd_update(args)
    if args.command == "set-aliases":
        return cmd_set_aliases(args)
    if args.command == "append-alias":
        return cmd_append_alias(args)
    return _error("INVALID_ARGUMENT", "unknown command.")


if __name__ == "__main__":
    sys.exit(main())
