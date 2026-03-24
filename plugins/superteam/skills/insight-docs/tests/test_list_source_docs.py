"""Unit tests for list_source_docs.py (read-kb-pgsql)."""
import json
import sys
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

# conftest.py already added SCRIPTS_DIR to sys.path and stubbed psycopg2.

import list_source_docs as list_source_docs_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COLUMNS = ("id", "source_type", "source_doc_id", "file_name", "last_edited_at", "last_synced_at", "sync_version")


def _make_mock_conn(rows, columns=_COLUMNS):
    cur = MagicMock()
    cur.description = [(c,) for c in columns]
    cur.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


def _run_main(argv, rows, columns=None):
    """Run list_source_docs.main() and return (exit_code, output_lines, cursor)."""
    if columns is None:
        columns = _COLUMNS
    conn, cur = _make_mock_conn(rows, columns)
    output_lines = []

    # psycopg2 is imported INSIDE main() function body (not module-level),
    # so we patch it via sys.modules which is where `import psycopg2` resolves.
    mock_pg = sys.modules["psycopg2"]
    mock_pg.connect.return_value = conn

    with patch.object(sys, "argv", ["list_source_docs.py"] + argv), \
         patch("list_source_docs.env", return_value="postgresql://fake/db"), \
         patch("builtins.print", side_effect=lambda *a, **kw: output_lines.append(a[0] if a else "")):
        code = list_source_docs_mod.main()

    return code, output_lines, cur


# ---------------------------------------------------------------------------
# TestListSourceDocs
# ---------------------------------------------------------------------------

class TestListSourceDocs:
    def test_no_filters_default_limit_50(self):
        """No flags → no WHERE clause; LIMIT param is 50 (default)."""
        rows = [(1, "dingtalk", "doc-1", "README.md", None, None, 1)]
        code, lines, cur = _run_main([], rows)

        assert code == 0
        sql = cur.execute.call_args[0][0]
        params = cur.execute.call_args[0][1]
        assert "WHERE" not in sql
        assert "LIMIT" in sql
        assert 50 in params

    def test_source_type_filter(self):
        """--source-type dingtalk → WHERE source_type = %s with 'dingtalk' in params."""
        rows = [(2, "dingtalk", "doc-2", "spec.md", None, None, 1)]
        code, lines, cur = _run_main(["--source-type", "dingtalk"], rows)

        assert code == 0
        sql = cur.execute.call_args[0][0]
        params = cur.execute.call_args[0][1]
        assert "source_type = %s" in sql
        assert "dingtalk" in params

    def test_name_filter_ilike(self):
        """--name 'report' → WHERE file_name ILIKE '%report%'."""
        rows = [(3, "google_drive", "doc-3", "weekly-report.md", None, None, 2)]
        code, lines, cur = _run_main(["--name", "report"], rows)

        assert code == 0
        sql = cur.execute.call_args[0][0]
        params = cur.execute.call_args[0][1]
        assert "file_name ILIKE %s" in sql
        assert any("report" in str(p) for p in params)

    def test_custom_limit(self):
        """--limit 10 → LIMIT param is 10."""
        rows = []
        code, lines, cur = _run_main(["--limit", "10"], rows)

        assert code == 0
        params = cur.execute.call_args[0][1]
        assert 10 in params

    def test_timestamp_formatting(self):
        """last_edited_at / last_synced_at datetime → converted to str in JSON output."""
        dt = datetime(2025, 6, 1, 12, 0, 0)
        rows = [(4, "dingtalk", "doc-4", "plan.md", dt, dt, 1)]
        code, lines, cur = _run_main([], rows)

        assert code == 0
        json_str = next(l for l in lines if isinstance(l, str) and l.startswith("["))
        result = json.loads(json_str)
        assert len(result) == 1
        # Both timestamp fields must be strings, not datetime objects
        assert isinstance(result[0]["last_edited_at"], str)
        assert isinstance(result[0]["last_synced_at"], str)

    def test_combined_filters(self):
        """--source-type + --name → WHERE with AND; both params present."""
        rows = [(5, "google_drive", "doc-5", "design-doc.md", None, None, 3)]
        code, lines, cur = _run_main(["--source-type", "google_drive", "--name", "design"], rows)

        assert code == 0
        sql = cur.execute.call_args[0][0]
        params = cur.execute.call_args[0][1]
        assert "AND" in sql
        assert "source_type = %s" in sql
        assert "file_name ILIKE %s" in sql
        assert "google_drive" in params
        assert any("design" in str(p) for p in params)
