"""Tests for queries.py — pure SQL query functions."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_mock_conn(rows, columns):
    """Create a mock psycopg2 connection that returns given rows."""
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchall.return_value = rows
    cur.description = [(col, None, None, None, None, None, None) for col in columns]
    return conn, cur


class TestQuerySearchDocs:
    def test_basic(self):
        from queries import query_search_docs

        columns = ["id", "content", "doc_type", "file_name", "creator_id",
                    "metadata", "score", "source_type", "source_url"]
        rows = [
            (1, "test content", "prd", "test.md", 3,
             json.dumps({"title": "Test Doc", "chunk_index": 1, "total_chunks": 5}),
             0.25, "dingtalk", "https://example.com"),
        ]
        conn, cur = _make_mock_conn(rows, columns)

        vec = [0.1] * 1536
        results = query_search_docs(conn, vec, top_k=5)

        assert len(results) == 1
        assert results[0]["title"] == "Test Doc"
        assert results[0]["score"] == 0.25
        assert results[0]["chunk_index"] == 1
        cur.execute.assert_called_once()

    def test_with_filters(self):
        from queries import query_search_docs

        columns = ["id", "content", "doc_type", "file_name", "creator_id",
                    "metadata", "score", "source_type", "source_url"]
        conn, cur = _make_mock_conn([], columns)

        vec = [0.1] * 1536
        query_search_docs(conn, vec, top_k=3, doc_type="prd", creator_id=5)

        sql_called = cur.execute.call_args[0][0]
        assert "c.doc_type = %s" in sql_called
        assert "c.creator_id = %s" in sql_called


class TestQueryListMembers:
    def test_no_filter(self):
        from queries import query_list_members

        columns = ["user_id", "username", "real_name", "real_name_en",
                    "email", "role", "verified", "aliases", "created_at"]
        rows = [(1, "alice", "Alice", "Alice", "alice@example.com", "dev", True, "[]", "2026-01-01")]
        conn, cur = _make_mock_conn(rows, columns)

        results = query_list_members(conn)
        assert len(results) == 1
        assert results[0]["username"] == "alice"

    def test_with_name_filter(self):
        from queries import query_list_members

        columns = ["user_id", "username", "real_name", "real_name_en",
                    "email", "role", "verified", "aliases", "created_at"]
        conn, cur = _make_mock_conn([], columns)

        query_list_members(conn, name="alice")
        sql_called = cur.execute.call_args[0][0]
        assert "ILIKE" in sql_called


class TestQueryListSourceDocs:
    def test_basic(self):
        from queries import query_list_source_docs

        columns = ["id", "source_type", "source_doc_id", "file_name",
                    "last_edited_at", "last_synced_at", "sync_version"]
        rows = [(1, "dingtalk", "doc123", "test.md", "2026-01-01", "2026-01-02", 1)]
        conn, cur = _make_mock_conn(rows, columns)

        results = query_list_source_docs(conn)
        assert len(results) == 1
        assert results[0]["source_type"] == "dingtalk"


class TestQueryResolveMember:
    def test_exact_match(self):
        from queries import query_resolve_member

        columns = ["user_id", "username", "real_name", "real_name_en",
                    "email", "role", "aliases"]
        rows = [(3, "peter", "Peter", "Peter", "peter@example.com", "dev", '["pete"]')]

        conn = MagicMock()
        # First cursor: member list
        cur1 = MagicMock()
        cur1.fetchall.return_value = rows
        cur1.description = [(col, None, None, None, None, None, None) for col in columns]
        conn.cursor.return_value = cur1

        result = query_resolve_member(conn, "Peter")
        assert result is not None
        assert result["user_id"] == 3
        assert result["match_type"] == "exact"

    def test_no_match(self):
        from queries import query_resolve_member

        columns = ["user_id", "username", "real_name", "real_name_en",
                    "email", "role", "aliases"]

        conn = MagicMock()
        # First cursor: empty member list
        cur1 = MagicMock()
        cur1.fetchall.return_value = []
        cur1.description = [(col, None, None, None, None, None, None) for col in columns]
        # Second cursor: alias lookup returns None
        cur2 = MagicMock()
        cur2.fetchone.return_value = None
        conn.cursor.side_effect = [cur1, cur2]

        result = query_resolve_member(conn, "UnknownPerson")
        assert result is None
