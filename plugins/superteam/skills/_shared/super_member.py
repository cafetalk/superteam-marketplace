"""Smart team member resolver with LLM fallback.

Resolution order:
  1. Exact match (real_name, real_name_en, username, email, aliases) — case-insensitive
  2. Email parameter override
  3. Alias cache (alias.lower(), platform) → user_id
  4. In-memory dedup cache — avoids repeated LLM calls per sync run
  5. LLM match — uses DashScope qwen-plus to find fuzzy match
  6. Fallback — create unverified member, never block
"""
from __future__ import annotations
import json
import os
from typing import Optional

from config import env


def _ensure_dashscope_key() -> bool:
    if os.environ.get("DASHSCOPE_API_KEY"):
        return True
    key = env("DASHSCOPE_API_KEY")
    if key:
        os.environ["DASHSCOPE_API_KEY"] = key
        return True
    return False


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
            "llm_match": 0,
            "new": 0,
            "error": 0,
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

        # Step 4: LLM match
        try:
            action, uid, reason = self._llm_match(stripped, email, platform)
        except Exception:
            self._stats["error"] += 1
            result = self._create_unverified_member(stripped, email, platform)
            self._dedup[dedup_key] = result
            return result

        if action == "match" and uid is not None:
            self._stats["llm_match"] += 1
            self._write_alias(stripped, platform, uid)
            self._aliases[alias_key] = uid
            self._review_queue.append({
                "raw_name": stripped,
                "email": email,
                "platform": platform,
                "resolved_user_id": uid,
                "reason": reason,
                "status": "approved",
            })
            self._dedup[dedup_key] = uid
            return uid
        else:
            # "new" — create unverified member
            self._stats["new"] += 1
            result = self._create_unverified_member(stripped, email, platform)
            self._review_queue.append({
                "raw_name": stripped,
                "email": email,
                "platform": platform,
                "resolved_user_id": result,
                "reason": reason,
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

    def _llm_match(self, raw_name: str, email: Optional[str], platform: str) -> tuple[str, Optional[int], str]:
        """Call DashScope LLM to match raw_name against known members.

        Returns (action, user_id_or_None, reason).
        action is "match" or "new".
        """
        try:
            import dashscope
            from dashscope import Generation
        except ImportError:
            raise RuntimeError("dashscope SDK not available") from None

        if not _ensure_dashscope_key():
            raise RuntimeError("DASHSCOPE_API_KEY not configured")

        # Build a compact member list for the prompt (exclude sensitive fields)
        members_for_prompt = []
        for m in self._members:
            members_for_prompt.append({
                "user_id": m["user_id"],
                "username": m.get("username"),
                "real_name": m.get("real_name"),
                "real_name_en": m.get("real_name_en"),
                "email": m.get("email"),
                "aliases": m.get("aliases") or [],
            })

        prompt = f"""你是团队成员匹配助手。判断新发现的文档作者是否为已有团队成员。

已有成员列表：
{json.dumps(members_for_prompt, ensure_ascii=False, indent=2)}

新发现的作者：
- 名字: {raw_name}
- 邮箱: {email or "未知"}
- 来源平台: {platform}

请判断这个作者是否为列表中的某位成员。考虑以下匹配依据：
- 中文名与英文名/拼音对应（如 "秦鹏" = "Peng Qin" = "allen.qin"）
- 邮箱前缀与 username 对应
- aliases 列表中的别名

返回严格 JSON（不要 markdown）：
{{"action": "match", "user_id": 19, "reason": "邮箱前缀 allen.qin 与 username 匹配"}}
或
{{"action": "new", "reason": "无法匹配到任何已有成员"}}"""

        response = Generation.call(
            model="qwen-plus",
            prompt=prompt,
            result_format="message",
            temperature=0.0,
            top_p=0.8,
            seed=42,
            max_tokens=256,
        )

        if response.status_code != 200:
            raise RuntimeError(f"LLM API error: {response.status_code} {response.message}")

        content = response.output.choices[0].message.content.strip()
        # Strip any markdown code fences
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        parsed = json.loads(content)
        action = parsed.get("action", "new")
        uid = parsed.get("user_id")
        reason = parsed.get("reason", "")

        if action == "match" and uid is not None:
            return "match", int(uid), reason
        return "new", None, reason

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

    def _fallback_create(self, raw_name: str, email: Optional[str], platform: str) -> int:
        """Alias for _create_unverified_member used as explicit fallback label."""
        return self._create_unverified_member(raw_name, email, platform)
