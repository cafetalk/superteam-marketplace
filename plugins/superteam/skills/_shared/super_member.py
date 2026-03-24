"""Smart team member resolver — exact match + alias cache only.

Resolution order:
  1. Exact match (real_name, real_name_en, username, email, aliases) — case-insensitive
  2. Email parameter override
  3. Alias cache (alias.lower(), platform) → user_id
  4. In-memory dedup cache
  5. Fallback — create unverified member, never block
"""
from __future__ import annotations
import json
from typing import Optional

from config import env


class SuperMember:
    """Resolve raw author names/emails to kb_trex_team_members.user_id."""

    def __init__(self, conn) -> None:
        self._conn = conn
        self._members: list[dict] = self._load_members()
        self._aliases: dict[tuple[str, str], int] = self._load_aliases()
        # In-memory dedup: (raw_name.lower(), platform) → user_id
        self._dedup: dict[tuple[str, str], int] = {}
        # Stats counters
        self._stats: dict[str, int] = {
            "exact": 0,
            "alias": 0,
            "dedup": 0,
            "new": 0,
        }
        # Review queue items to flush
        self._review_queue: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, raw_name: str, email: Optional[str] = None, platform: str = "") -> int:
        """Resolve a raw name (and optional email) to a user_id.

        Returns an integer user_id. Never raises — falls back to creating
        an unverified member entry.
        """
        # Handle empty/blank input immediately
        stripped = (raw_name or "").strip()
        if not stripped:
            return self._create_unverified_member(raw_name, email, platform)

        # Step 1: Exact match in members list
        uid = self._exact_match(stripped, email)
        if uid is not None:
            self._stats["exact"] += 1
            return uid

        # Step 2: Alias cache lookup
        alias_key = (stripped.lower(), platform)
        if alias_key in self._aliases:
            self._stats["alias"] += 1
            return self._aliases[alias_key]

        # Step 3: In-memory dedup
        dedup_key = (stripped.lower(), platform)
        if dedup_key in self._dedup:
            self._stats["dedup"] += 1
            return self._dedup[dedup_key]

        # Step 4: Fallback — create unverified member
        self._stats["new"] += 1
        result = self._create_unverified_member(stripped, email, platform)
        self._review_queue.append({
            "raw_name": stripped,
            "email": email,
            "platform": platform,
            "resolved_user_id": result,
            "reason": "no exact or alias match",
            "status": "pending",
        })
        self._dedup[dedup_key] = result
        return result

    def flush_review_queue(self) -> list[dict]:
        """Batch insert accumulated review items into kb_trex_member_review_queue.

        Returns the list of items flushed.
        """
        if not self._review_queue:
            return []

        items = list(self._review_queue)
        self._review_queue.clear()

        if self._conn is None:
            return items

        try:
            cur = self._conn.cursor()
            for item in items:
                cur.execute(
                    """
                    INSERT INTO kb_trex_member_review_queue
                        (raw_name, email, platform, resolved_user_id, reason, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        item["raw_name"],
                        item.get("email"),
                        item.get("platform"),
                        item.get("resolved_user_id"),
                        item.get("reason"),
                        item.get("status", "pending"),
                    ),
                )
            self._conn.commit()
        except Exception:
            pass

        return items

    def get_stats(self) -> dict:
        """Return a copy of the resolution statistics."""
        return dict(self._stats)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_members(self) -> list[dict]:
        """SELECT all members from kb_trex_team_members."""
        try:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT user_id, username, real_name, real_name_en, email, role, aliases, verified "
                "FROM kb_trex_team_members"
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in rows]
        except Exception:
            return []

    def _load_aliases(self) -> dict[tuple[str, str], int]:
        """SELECT alias cache from kb_trex_member_aliases.

        Returns {(alias.lower(), platform): user_id}.
        """
        try:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT alias, platform, user_id FROM kb_trex_member_aliases"
            )
            rows = cur.fetchall()
            return {(row[0].lower(), row[1]): row[2] for row in rows}
        except Exception:
            return {}

    def _exact_match(self, raw_name: str, email: Optional[str]) -> Optional[int]:
        """Case-insensitive exact match against members fields and aliases list."""
        name_lower = raw_name.lower()
        email_lower = (email or "").lower()

        for member in self._members:
            uid = member["user_id"]

            # Match by email parameter (highest priority after blank check)
            if email_lower and (member.get("email") or "").lower() == email_lower:
                return uid

            # Match by real_name
            if (member.get("real_name") or "").lower() == name_lower:
                return uid

            # Match by real_name_en
            if (member.get("real_name_en") or "").lower() == name_lower:
                return uid

            # Match by username
            if (member.get("username") or "").lower() == name_lower:
                return uid

            # Match by email field
            if (member.get("email") or "").lower() == name_lower:
                return uid

            # Match by aliases list
            aliases = member.get("aliases") or []
            if isinstance(aliases, str):
                try:
                    aliases = json.loads(aliases)
                except Exception:
                    aliases = []
            if any(a.lower() == name_lower for a in aliases):
                return uid

        return None

    def _create_unverified_member(self, raw_name: str, email: Optional[str], platform: str = "") -> int:
        """INSERT an unverified member row and return its new user_id."""
        try:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO kb_trex_team_members
                    (username, real_name, real_name_en, email, role, aliases, verified)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING user_id
                """,
                (
                    raw_name,       # username placeholder
                    raw_name,       # real_name placeholder
                    None,
                    email,
                    None,
                    json.dumps([]),
                    False,
                ),
            )
            row = cur.fetchone()
            self._conn.commit()
            return row[0]
        except Exception:
            try:
                self._conn.rollback()
            except Exception:
                pass
            return -1

    def _write_alias(self, alias: str, platform: str, user_id: int) -> None:
        """INSERT alias mapping, ignore if already exists."""
        try:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO kb_trex_member_aliases (alias, platform, user_id)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (alias.lower(), platform, user_id),
            )
            self._conn.commit()
        except Exception:
            try:
                self._conn.rollback()
            except Exception:
                pass

