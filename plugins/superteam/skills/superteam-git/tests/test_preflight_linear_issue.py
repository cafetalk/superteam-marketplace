"""Tests for preflight_linear_issue title matching (no Linear MCP)."""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from preflight_linear_issue import (  # noqa: E402
    analyze_duplicate_risk,
    normalize_title,
    title_match_level,
)


def test_normalize_title():
    assert normalize_title("  Foo   Bar  ") == "foo bar"


def test_title_match_level_exact():
    assert title_match_level("Fix login", "fix login") == "exact"


def test_title_match_level_strong_substring():
    assert title_match_level("git增加多工作区", "feat: git增加多工作区与分支") == "strong"


def test_analyze_duplicate_risk_open_exact():
    issues = [
        {
            "id": "ACB-1",
            "title": "Same Title",
            "status": "In Progress",
            "url": "https://linear.app/x/issue/ACB-1",
        }
    ]
    r = analyze_duplicate_risk("Same Title", issues)
    assert r["risk"] == "high"
    assert r["recommendation"] == "link_existing"
    assert r["policy"]["block_save_issue_without_user_confirm"] is True
    assert len(r["open_matches"]) == 1


def test_analyze_duplicate_risk_done_only():
    issues = [
        {
            "id": "ACB-2",
            "title": "Same Title",
            "status": "Done",
            "url": "https://linear.app/x/issue/ACB-2",
        }
    ]
    r = analyze_duplicate_risk("Same Title", issues)
    assert r["risk"] == "none"
    assert r["recommendation"] == "ok_to_create"
    assert not r["open_matches"]
    assert r["closed_matches"]


if __name__ == "__main__":
    test_normalize_title()
    test_title_match_level_exact()
    test_title_match_level_strong_substring()
    test_analyze_duplicate_risk_open_exact()
    test_analyze_duplicate_risk_done_only()
    print("ok")
