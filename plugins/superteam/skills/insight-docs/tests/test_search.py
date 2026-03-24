"""Unit tests for search_docs.py (read-kb-pgsql)."""
import json
import sys
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

# conftest.py already added SCRIPTS_DIR to sys.path and stubbed psycopg2.

# Stub shared modules so search_docs.py module-level imports succeed.
_config_mod = MagicMock()
_config_mod.env.return_value = "postgresql://fake/db"
sys.modules.setdefault("config", _config_mod)

_embedding_mod = MagicMock()
sys.modules.setdefault("embedding", _embedding_mod)

import search_docs as search_mod  # noqa: E402


FAKE_VEC = [0.1] * 1536


def _make_mock_conn(rows, description=None):
    """Return (conn, cur) where cur yields given rows."""
    cur = MagicMock()
    if description is None:
        cur.description = [
            ("id",), ("content",), ("doc_type",), ("file_name",),
            ("creator_id",), ("metadata",), ("score",),
        ]
    else:
        cur.description = description
    cur.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


# ---------------------------------------------------------------------------
# TestRunVectorSearch
# ---------------------------------------------------------------------------

class TestRunVectorSearch:
    """run_vector_search(conn, vec, top_k, doc_type, creator_id) receives conn directly."""

    def test_no_filters_builds_simple_query(self):
        """No doc_type, no creator_id → query has no WHERE clause."""
        rows = [(1, "hello", "guide", "file.md", 5, '{"k": "v"}', 0.1)]
        conn, cur = _make_mock_conn(rows)

        results = search_mod.run_vector_search(conn, FAKE_VEC, 5, None, None)

        executed_sql = cur.execute.call_args[0][0]
        assert "WHERE" not in executed_sql
        assert "ORDER BY" in executed_sql
        assert "LIMIT" in executed_sql
        assert len(results) == 1

    def test_doc_type_filter_parameterized(self):
        """doc_type='prd' → WHERE clause present and 'prd' appears in params."""
        rows = [(2, "content", "prd", "spec.md", 3, None, 0.2)]
        conn, cur = _make_mock_conn(rows)

        results = search_mod.run_vector_search(conn, FAKE_VEC, 5, "prd", None)

        executed_sql = cur.execute.call_args[0][0]
        executed_params = cur.execute.call_args[0][1]
        assert "WHERE" in executed_sql
        assert "doc_type = %s" in executed_sql
        assert "prd" in executed_params

    def test_combined_filters(self):
        """Both doc_type and creator_id → WHERE clause with AND."""
        rows = [(3, "text", "prd", "plan.md", 7, None, 0.3)]
        conn, cur = _make_mock_conn(rows)

        results = search_mod.run_vector_search(conn, FAKE_VEC, 5, "prd", 7)

        executed_sql = cur.execute.call_args[0][0]
        executed_params = cur.execute.call_args[0][1]
        assert "doc_type = %s" in executed_sql
        assert "creator_id = %s" in executed_sql
        assert "AND" in executed_sql
        assert "prd" in executed_params
        assert 7 in executed_params

    def test_metadata_dict_passthrough(self):
        """metadata already a dict → returned unchanged (not re-parsed)."""
        meta = {"already": "parsed"}
        rows = [(4, "content", "guide", "file.md", 1, meta, 0.4)]
        conn, cur = _make_mock_conn(rows)

        results = search_mod.run_vector_search(conn, FAKE_VEC, 5, None, None)

        assert results[0]["metadata"] is meta
        assert isinstance(results[0]["metadata"], dict)

    def test_none_score_handled(self):
        """score is None → stays None (no float conversion error)."""
        rows = [(5, "text", "guide", "file.md", 2, None, None)]
        conn, cur = _make_mock_conn(rows)

        results = search_mod.run_vector_search(conn, FAKE_VEC, 5, None, None)

        assert results[0]["score"] is None
