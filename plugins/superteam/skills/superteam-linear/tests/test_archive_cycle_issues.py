"""Unit tests for archive_cycle_issues.py."""
import json
import sys
from unittest.mock import patch

import pytest

import archive_cycle_issues as aci  # noqa: E402


def _run(argv):
    output_lines = []
    with patch.object(sys, "argv", ["archive_cycle_issues.py"] + argv), \
         patch("builtins.print", side_effect=lambda *a, **kw: output_lines.append(a[0] if a else "")):
        code = aci.main()
    return code, output_lines


def test_requires_scope():
    code, lines = _run([])
    assert code == 1
    result = json.loads(lines[0])
    assert result["ok"] is False
    assert result["error_code"] == "INVALID_ARGUMENT"


def test_rejects_mixed_issue_ids_and_filters():
    code, lines = _run(["--cycle", "Cycle 1", "--issue-id", "TREX-1"])
    assert code == 1
    result = json.loads(lines[0])
    assert result["ok"] is False
    assert result["error_code"] == "INVALID_ARGUMENT"


@pytest.mark.parametrize("bad_first", ["0", "-1"])
def test_rejects_non_positive_first(bad_first):
    code, lines = _run(["--cycle", "Cycle 1", "--first", bad_first])
    assert code == 1
    result = json.loads(lines[0])
    assert result["ok"] is False
    assert result["error_code"] == "INVALID_ARGUMENT"


def test_issue_ids_are_split_trimmed_and_deduplicated():
    issue_ids = aci._normalize_issue_ids(["TREX-1,TREX-2", " TREX-2 , TREX-3 ", "TREX-1"])
    assert issue_ids == ["TREX-1", "TREX-2", "TREX-3"]


def test_parse_cycle_selector_supports_numeric_forms():
    assert aci._parse_cycle_selector("9")["number"] == 9
    assert aci._parse_cycle_selector("Cycle 9")["number"] == 9
    assert aci._parse_cycle_selector("Sprint Alpha")["name"] == "Sprint Alpha"


def test_build_issues_query_omits_null_cycle_filter_for_project_only():
    query, variables = aci._build_issues_query("World Cup", None)
    assert "project: { name: { eq: $project } }" in query
    assert "cycle:" not in query
    assert variables["project"] == "World Cup"


def test_normalize_issue_uses_cycle_number_when_name_missing():
    issue = {
        "id": "1",
        "identifier": "TREX-1",
        "title": "Done task",
        "state": {"name": "Done", "type": "completed"},
        "archivedAt": None,
        "cycle": {"id": "c1", "name": None, "number": 9},
    }
    normalized = aci._normalize_issue(issue)
    assert normalized["cycle"] == "Cycle 9"


def test_dry_run_output_envelope_for_cycle():
    fake_issue = {
        "id": "TREX-1",
        "identifier": "TREX-1",
        "title": "Done task",
        "state": {"name": "Done", "type": "completed"},
        "archivedAt": None,
    }
    with patch("archive_cycle_issues._load_list_issues", return_value=[fake_issue]):
        code, lines = _run(["--cycle", "Cycle 1"])
    assert code == 0
    result = json.loads(lines[0])
    assert result["skill"] == "superteam-linear"
    assert result["tool"] == "archive_cycle_issues"
    assert result["mode"] == "dry-run"
    assert result["input_type"] == "cycle"
    assert result["filters"]["cycle"] == "Cycle 1"


def test_project_dry_run_filters_terminal_and_non_terminal_issues():
    fake_issues = [
        {"id": "1", "identifier": "TREX-1", "title": "Done task", "state": {"name": "Done", "type": "completed"}, "archivedAt": None},
        {"id": "2", "identifier": "TREX-2", "title": "Canceled task", "state": {"name": "Canceled", "type": "canceled"}, "archivedAt": None},
        {"id": "3", "identifier": "TREX-3", "title": "Active task", "state": {"name": "In Progress", "type": "started"}, "archivedAt": None},
        {"id": "4", "identifier": "TREX-4", "title": "Archived task", "state": {"name": "Done", "type": "completed"}, "archivedAt": "2026-01-01T00:00:00.000Z"},
    ]
    with patch("archive_cycle_issues._load_list_issues", return_value=fake_issues):
        code, lines = _run(["--project", "World Cup"])
    assert code == 0
    result = json.loads(lines[0])
    assert result["input_type"] == "project"
    assert result["scanned"] == 4
    assert result["matched"] == 2
    assert [x["id"] for x in result["eligible"]] == ["TREX-1", "TREX-2"]
    skipped = {x["id"]: x["reason"] for x in result["skipped"]}
    ignored = {x["id"]: x["reason"] for x in result["ignored"]}
    assert ignored["TREX-3"] == "not_done_or_canceled"
    assert skipped["TREX-4"] == "already_archived"


def test_project_cycle_dry_run_uses_combined_scope():
    with patch("archive_cycle_issues._load_list_issues", return_value=[] ) as mock_load:
        code, lines = _run(["--project", "World Cup", "--cycle", "Cycle 1"])
    assert code == 0
    result = json.loads(lines[0])
    assert result["input_type"] == "project_cycle"
    mock_load.assert_called_once_with(project="World Cup", cycle="Cycle 1", first=200, graphql_timeout=45)


def test_issue_id_dry_run_keeps_fetch_failures():
    fake_issues = [
        {"id": "1", "identifier": "TREX-1", "title": "Done task", "state": {"name": "Done", "type": "completed"}, "archivedAt": None},
        {"id": "2", "identifier": "TREX-2", "title": "Active task", "state": {"name": "Todo", "type": "unstarted"}, "archivedAt": None},
    ]
    fake_failures = [{"id": "TREX-404", "reason": "fetch_failed", "message": "not found"}]
    with patch("archive_cycle_issues._load_issue_ids", return_value=(fake_issues, fake_failures)):
        code, lines = _run(["--issue-id", "TREX-1,TREX-2", "--issue-id", "TREX-404"])
    assert code == 0
    result = json.loads(lines[0])
    assert result["input_type"] == "issue_ids"
    assert [x["id"] for x in result["eligible"]] == ["TREX-1"]
    assert result["failed"] == fake_failures


def test_execute_requires_linear_api_key():
    fake_issues = [
        {"id": "1", "identifier": "TREX-1", "title": "Done task", "state": {"name": "Done", "type": "completed"}, "archivedAt": None},
    ]
    with patch("archive_cycle_issues._load_list_issues", return_value=fake_issues), \
         patch("archive_cycle_issues._graphql_config", return_value=None):
        code, lines = _run(["--cycle", "Cycle 1", "--execute"])
    assert code == 1
    result = json.loads(lines[0])
    assert result["ok"] is False
    assert result["error_code"] == "config_missing"


def test_execute_archives_eligible_issues_and_continues_on_failure():
    fake_issues = [
        {"id": "1", "identifier": "TREX-1", "title": "Done task", "state": {"name": "Done", "type": "completed"}, "archivedAt": None},
        {"id": "2", "identifier": "TREX-2", "title": "Canceled task", "state": {"name": "Canceled", "type": "canceled"}, "archivedAt": None},
        {"id": "3", "identifier": "TREX-3", "title": "Active task", "state": {"name": "In Progress", "type": "started"}, "archivedAt": None},
    ]

    def fake_archive(issue, config):
        if issue["id"] == "TREX-2":
            raise RuntimeError("boom")
        return {"id": issue["id"], "title": issue["title"], "state": issue["state"]}

    with patch("archive_cycle_issues._load_list_issues", return_value=fake_issues), \
         patch("archive_cycle_issues._graphql_config", return_value={"api_url": "u", "api_key": "k"}), \
         patch("archive_cycle_issues._archive_issue", side_effect=fake_archive):
        code, lines = _run(["--cycle", "Cycle 1", "--execute"])
    assert code == 0
    result = json.loads(lines[0])
    assert result["mode"] == "execute"
    assert [x["id"] for x in result["archived"]] == ["TREX-1"]
    assert result["failed"][0]["id"] == "TREX-2"
    assert result["failed"][0]["reason"] == "archive_failed"
    ignored = {x["id"]: x["reason"] for x in result["ignored"]}
    assert ignored["TREX-3"] == "not_done_or_canceled"
