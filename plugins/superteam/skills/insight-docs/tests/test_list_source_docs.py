"""Unit tests for list_source_docs.py — tests MCP and direct modes."""
import json
import sys
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

# conftest.py already added SCRIPTS_DIR to sys.path and stubbed psycopg2.

import list_source_docs as list_source_docs_mod  # noqa: E402


FAKE_DOCS = [
    {"id": 1, "source_type": "dingtalk", "source_doc_id": "doc-1",
     "file_name": "README.md", "last_edited_at": None, "last_synced_at": None, "sync_version": 1},
]


def _run_mcp(argv, mcp_return):
    """Run main() in MCP mode."""
    output_lines = []
    with patch.object(sys, "argv", ["list_source_docs.py"] + argv), \
         patch("list_source_docs.env", return_value="postgresql://fake/db"), \
         patch("db._use_mcp", return_value=True), \
         patch("db.list_source_docs", return_value=mcp_return), \
         patch("builtins.print", side_effect=lambda *a, **kw: output_lines.append(a[0] if a else "")):
        code = list_source_docs_mod.main()
    return code, output_lines


def _run_direct(argv, query_return):
    """Run main() in direct mode."""
    output_lines = []
    mock_query = MagicMock(return_value=query_return)
    mock_conn = MagicMock()

    with patch.object(sys, "argv", ["list_source_docs.py"] + argv), \
         patch("list_source_docs.env", return_value="postgresql://fake/db"), \
         patch("db._use_mcp", return_value=False), \
         patch("db.get_connection", return_value=mock_conn), \
         patch("queries.query_list_source_docs", mock_query), \
         patch("builtins.print", side_effect=lambda *a, **kw: output_lines.append(a[0] if a else "")):
        code = list_source_docs_mod.main()
    return code, output_lines, mock_query


class TestMcpMode:
    def test_no_filters(self):
        code, lines = _run_mcp([], FAKE_DOCS)
        assert code == 0
        result = json.loads(lines[0])
        assert len(result) == 1

    def test_source_type_filter(self):
        code, lines = _run_mcp(["--source-type", "dingtalk"], FAKE_DOCS)
        assert code == 0


class TestDirectMode:
    def test_no_filters_default_limit(self):
        code, lines, mock_q = _run_direct([], FAKE_DOCS)
        assert code == 0
        mock_q.assert_called_once()
        assert mock_q.call_args[1].get("limit") == 50

    def test_source_type_filter(self):
        code, lines, mock_q = _run_direct(["--source-type", "dingtalk"], FAKE_DOCS)
        assert code == 0
        assert mock_q.call_args[1].get("source_type") == "dingtalk"

    def test_name_filter(self):
        code, lines, mock_q = _run_direct(["--name", "report"], FAKE_DOCS)
        assert code == 0
        assert mock_q.call_args[1].get("name") == "report"

    def test_custom_limit(self):
        code, lines, mock_q = _run_direct(["--limit", "10"], [])
        assert code == 0
        assert mock_q.call_args[1].get("limit") == 10

    def test_combined_filters(self):
        code, lines, mock_q = _run_direct(
            ["--source-type", "google_drive", "--name", "design"], FAKE_DOCS)
        assert code == 0
        assert mock_q.call_args[1].get("source_type") == "google_drive"
        assert mock_q.call_args[1].get("name") == "design"

    def test_timestamp_formatting(self):
        """Timestamps from query_list_source_docs are already strings."""
        dt_str = "2025-06-01 12:00:00"
        docs = [{"id": 4, "source_type": "dingtalk", "source_doc_id": "doc-4",
                 "file_name": "plan.md", "last_edited_at": dt_str,
                 "last_synced_at": dt_str, "sync_version": 1}]
        code, lines, _ = _run_direct([], docs)
        assert code == 0
        result = json.loads(lines[0])
        assert isinstance(result[0]["last_edited_at"], str)
