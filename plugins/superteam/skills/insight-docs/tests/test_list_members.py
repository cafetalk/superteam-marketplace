"""Unit tests for list_members.py — tests MCP and direct modes for list/resolve."""
import json
import sys
import pytest
from unittest.mock import MagicMock, patch

# conftest.py already added SCRIPTS_DIR to sys.path and stubbed psycopg2.

import list_members as lm  # noqa: E402


FAKE_MEMBERS = [
    {"user_id": 1, "username": "alice", "real_name": "Alice Chen", "real_name_en": "Alice",
     "email": "alice@example.com", "role": "engineer", "verified": True, "aliases": "[]", "created_at": None},
    {"user_id": 2, "username": "bob", "real_name": "Bob Li", "real_name_en": "Bob",
     "email": "bob@example.com", "role": "pm", "verified": True, "aliases": "[]", "created_at": None},
]


def _run_mcp(argv, mcp_return):
    """Run lm.main() in MCP mode, return (exit_code, parsed_output)."""
    output_lines = []
    with patch.object(sys, "argv", ["list_members.py"] + argv), \
         patch("list_members.env", return_value="postgresql://fake/db"), \
         patch("db._use_mcp", return_value=True), \
         patch("db.list_members", return_value=mcp_return), \
         patch("builtins.print", side_effect=lambda *a, **kw: output_lines.append(a[0] if a else "")):
        code = lm.main()
    return code, output_lines


def _run_direct(argv, query_return):
    """Run lm.main() in direct mode, return (exit_code, parsed_output, mock_query)."""
    output_lines = []
    mock_query = MagicMock(return_value=query_return)
    mock_conn = MagicMock()
    mock_pg = sys.modules["psycopg2"]
    mock_pg.connect.return_value = mock_conn

    with patch.object(sys, "argv", ["list_members.py"] + argv), \
         patch("list_members.env", return_value="postgresql://fake/db"), \
         patch("db._use_mcp", return_value=False), \
         patch("queries.query_list_members", mock_query), \
         patch("builtins.print", side_effect=lambda *a, **kw: output_lines.append(a[0] if a else "")):
        code = lm.main()
    return code, output_lines, mock_query


class TestCmdListMcp:
    """list subcommand in MCP mode."""

    def test_no_filters_returns_all(self):
        code, lines = _run_mcp(["list"], FAKE_MEMBERS)
        assert code == 0
        result = json.loads(lines[0])
        assert len(result) == 2

    def test_name_filter_passed(self):
        code, lines = _run_mcp(["list", "--name", "张"], [FAKE_MEMBERS[0]])
        assert code == 0


class TestCmdListDirect:
    """list subcommand in direct DB mode."""

    def test_no_filters(self):
        code, lines, mock_q = _run_direct(["list"], FAKE_MEMBERS)
        assert code == 0
        mock_q.assert_called_once()
        kwargs = mock_q.call_args
        # name=None, role=None, user_id=None
        assert kwargs[1].get("name") is None or kwargs[1].get("name") == "" or not kwargs[1].get("name")

    def test_name_filter(self):
        code, lines, mock_q = _run_direct(["list", "--name", "张"], [FAKE_MEMBERS[0]])
        assert code == 0
        assert mock_q.call_args[1].get("name") == "张" or "张" in str(mock_q.call_args)

    def test_role_filter(self):
        code, lines, mock_q = _run_direct(["list", "--role", "engineer"], [FAKE_MEMBERS[0]])
        assert code == 0
        assert "engineer" in str(mock_q.call_args)

    def test_user_id_filter(self):
        code, lines, mock_q = _run_direct(["list", "--user-id", "42"], [FAKE_MEMBERS[0]])
        assert code == 0
        assert "42" in str(mock_q.call_args) or mock_q.call_args[1].get("user_id") == 42


class TestCmdResolve:
    """resolve subcommand."""

    def test_resolve_mcp_mode(self):
        output_lines = []
        with patch.object(sys, "argv", ["list_members.py", "resolve", "张伟"]), \
             patch("list_members.env", return_value="postgresql://fake/db"), \
             patch("db._use_mcp", return_value=True), \
             patch("db.resolve_member", return_value={"user_id": 99, "match_type": "exact"}) as mock_resolve, \
             patch("builtins.print", side_effect=lambda *a, **kw: output_lines.append(a[0] if a else "")):
            code = lm.main()
        assert code == 0
        result = json.loads(output_lines[0])
        assert result["user_id"] == 99

    def test_resolve_direct_mode(self):
        mock_sm_instance = MagicMock()
        mock_sm_instance.resolve.return_value = 99

        output_lines = []
        mock_pg = sys.modules["psycopg2"]
        mock_pg.connect.return_value = MagicMock()

        with patch.object(sys, "argv", ["list_members.py", "resolve", "张伟"]), \
             patch("list_members.env", return_value="postgresql://fake/db"), \
             patch("db._use_mcp", return_value=False), \
             patch("super_member.SuperMember", return_value=mock_sm_instance), \
             patch("builtins.print", side_effect=lambda *a, **kw: output_lines.append(a[0] if a else "")):
            code = lm.main()

        assert code == 0
        mock_sm_instance.resolve.assert_called_once_with("张伟", platform="")
        result = json.loads(output_lines[0])
        assert result["user_id"] == 99


class TestBackwardCompat:
    """No subcommand → defaults to list behavior."""

    def test_no_subcommand_defaults_to_list(self):
        code, lines = _run_mcp([], FAKE_MEMBERS)
        assert code == 0
        result = json.loads(lines[0])
        assert len(result) == 2

    def test_no_subcommand_with_name_filter(self):
        code, lines = _run_mcp(["--name", "张"], [FAKE_MEMBERS[0]])
        assert code == 0
