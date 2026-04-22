"""Tests for query_linear stdout parsing (no MCP)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from query_linear_stdout_json import extract_insight_linear_payload  # noqa: E402


def test_extract_prefers_save_issue_result_with_id():
    noise = '[999] {"jsonrpc": "2.0", "id": 1, "method": "initialize"}\n'
    tool = {
        "skill": "superteam-linear",
        "type": "tool_call",
        "tool": "save_issue",
        "result": {"id": "ACB-91", "url": "https://linear.app/x/ACB-91", "title": "T"},
    }
    text = noise + json.dumps(tool, ensure_ascii=False)
    out = extract_insight_linear_payload(text)
    assert out.get("skill") == "superteam-linear"
    assert out["result"]["id"] == "ACB-91"


def test_extract_list_issues_after_logs():
    logs = "[1] Connecting...\n" + '{"jsonrpc": "2.0", "id": 3}\n'
    wrapper = {
        "skill": "superteam-linear",
        "result": {"issues": [{"id": "ACB-1", "title": "A"}], "hasNextPage": False},
    }
    text = logs + json.dumps(wrapper)
    out = extract_insight_linear_payload(text)
    assert out["result"]["issues"][0]["id"] == "ACB-1"


def test_extract_empty():
    assert extract_insight_linear_payload("") == {}
    assert extract_insight_linear_payload("no json here") == {}


if __name__ == "__main__":
    test_extract_prefers_save_issue_result_with_id()
    test_extract_list_issues_after_logs()
    test_extract_empty()
    print("ok")
