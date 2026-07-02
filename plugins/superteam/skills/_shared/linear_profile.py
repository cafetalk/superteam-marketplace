"""Linear 用户 profile 页 URL 拼装（workspace/profiles/<slug>）。"""
from __future__ import annotations

import re
from typing import Any

_DEFAULT_WORKSPACE = "t-rex-v1"
_WORKSPACE_RE = re.compile(r"https?://linear\.app/([^/]+)/", re.I)
_PROFILE_URL_RE = re.compile(r"https?://linear\.app/[^/]+/profiles/([^/?#]+)", re.I)


def linear_workspace_from_url(url: str | None, *, default: str = _DEFAULT_WORKSPACE) -> str:
    if not url:
        return default
    m = _WORKSPACE_RE.match(str(url).strip())
    return m.group(1) if m else default


def profile_slug_from_lead(lead: Any) -> str | None:
    """从 Linear Project.lead 对象提取 profile slug（优先 email 本地段）。"""
    if not isinstance(lead, dict):
        return None
    raw_url = lead.get("url")
    if isinstance(raw_url, str) and raw_url.strip():
        m = _PROFILE_URL_RE.search(raw_url.strip())
        if m:
            return m.group(1).lower()
    email = lead.get("email")
    if isinstance(email, str) and "@" in email:
        return email.split("@", 1)[0].strip().lower() or None
    return None


def linear_profile_url(workspace: str, slug: str) -> str:
    ws = (workspace or _DEFAULT_WORKSPACE).strip().strip("/")
    sl = (slug or "").strip().strip("/")
    return f"https://linear.app/{ws}/profiles/{sl}"


def leader_profile_url_from_project_meta(
    pm: dict[str, Any],
    *,
    workspace: str,
) -> str | None:
    slug = profile_slug_from_lead(pm.get("lead"))
    if not slug:
        return None
    return linear_profile_url(workspace, slug)


def _norm_person(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def build_member_profile_index(
    members: list[dict[str, Any]],
    *,
    workspace: str,
    name_keys: tuple[str, ...] = (
        "real_name", "realName", "username", "real_name_en", "realNameEn", "email",
    ),
) -> dict[str, str]:
    """成员表姓名/别名 → Linear profile URL（仅 email @ 前段为 slug）。"""
    index: dict[str, str] = {}
    for m in members:
        if not isinstance(m, dict):
            continue
        email = str(m.get("email") or "").strip()
        if "@" not in email:
            continue
        url = linear_profile_url(workspace, email.split("@", 1)[0])
        seen: set[str] = set()

        def _add_alias(alias: str) -> None:
            key = _norm_person(alias)
            if key and key not in seen:
                seen.add(key)
                index[key] = url

        for key in name_keys:
            v = m.get(key)
            if isinstance(v, str) and v.strip():
                _add_alias(v.strip())
                if key == "email" and "@" in v:
                    _add_alias(v.split("@", 1)[0])
        raw_aliases = m.get("aliases")
        if isinstance(raw_aliases, list):
            for a in raw_aliases:
                if isinstance(a, str):
                    _add_alias(a)
        elif isinstance(raw_aliases, str) and raw_aliases.strip():
            try:
                import json
                parsed = json.loads(raw_aliases)
            except Exception:
                parsed = None
            if isinstance(parsed, list):
                for a in parsed:
                    if isinstance(a, str):
                        _add_alias(a)
    return index
