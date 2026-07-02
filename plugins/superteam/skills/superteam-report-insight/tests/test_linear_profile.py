"""Tests for Linear profile URL helpers."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_SHARED = Path(__file__).resolve().parents[2] / "_shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from linear_profile import (  # noqa: E402
    build_member_profile_index,
    leader_profile_url_from_project_meta,
    linear_profile_url,
    linear_workspace_from_url,
    profile_slug_from_lead,
)
from _pai import build_pai_payload  # noqa: E402


def test_linear_workspace_from_project_url():
    assert linear_workspace_from_url("https://linear.app/t-rex-v1/project/foo") == "t-rex-v1"


def test_profile_slug_from_lead_email():
    assert profile_slug_from_lead({"email": "zhifeng.li@example.com"}) == "zhifeng.li"


def test_linear_profile_url_format():
    assert linear_profile_url("t-rex-v1", "zhifeng.li") == (
        "https://linear.app/t-rex-v1/profiles/zhifeng.li"
    )


def test_member_profile_index_skips_without_email():
    idx = build_member_profile_index(
        [{"real_name": "李嘉琳", "username": "li-jialin", "role": "backend"}],
        workspace="t-rex-v1",
    )
    assert "李嘉琳" not in idx


def test_member_profile_index_by_real_name():
    idx = build_member_profile_index(
        [{"real_name": "李治锋", "email": "zhifeng.li@trex.xyz", "role": "dev"}],
        workspace="t-rex-v1",
    )
    assert idx["李治锋"] == "https://linear.app/t-rex-v1/profiles/zhifeng.li"


def test_pai_by_leader_has_linear_profile_url():
    sprint = {
        "projects": [
            {
                "name": "Proj",
                "leader": "李治锋",
                "leader_profile_url": "https://linear.app/t-rex-v1/profiles/zhifeng.li",
                "project_url": "https://linear.app/t-rex-v1/project/x",
                "open_total": 1,
                "done": 0,
                "in_progress": 1,
                "todo": 0,
                "progress_done_pct": 0,
                "participants": [],
            },
        ],
    }
    payload = build_pai_payload(sprint, snapshot_date=date(2026, 6, 25))
    leader = payload["by_leader"]["李治锋"]
    assert leader["linear_profile_url"] == "https://linear.app/t-rex-v1/profiles/zhifeng.li"


def test_leader_profile_from_project_meta():
    pm = {"lead": {"name": "李治锋", "email": "zhifeng.li@trex.xyz"}}
    assert leader_profile_url_from_project_meta(pm, workspace="t-rex-v1") == (
        "https://linear.app/t-rex-v1/profiles/zhifeng.li"
    )
