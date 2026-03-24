"""Tests for _shared/db.py — batch insert + atomic doc ingest."""
import json, sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, str(Path(__file__).parent.parent))
import db


class TestGetConnection:
    def test_sets_search_path(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        with patch("psycopg2.connect", return_value=mock_conn):
            conn = db.get_connection("postgres://test")
        mock_cur.execute.assert_called_with("SET search_path TO trex_hub, public")
        mock_conn.commit.assert_called_once()


class TestBatchInsertChunks:
    def test_inserts_all_chunks(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        chunks = [
            {"content": "c1", "embedding": [0.1]*1536, "creator_id": 5,
             "doc_type": "prd", "file_name": "f.md", "metadata": {}, "source_sync_id": 1},
            {"content": "c2", "embedding": [0.2]*1536, "creator_id": 5,
             "doc_type": "prd", "file_name": "f.md", "metadata": {}, "source_sync_id": 1},
        ]
        with patch("db.execute_values"):
            count = db.batch_insert_chunks(mock_conn, chunks)
        assert count == 2
        mock_cur.close.assert_called_once()

    def test_empty_chunks_returns_zero(self):
        mock_conn = MagicMock()
        assert db.batch_insert_chunks(mock_conn, []) == 0


class TestDeleteChunksForSource:
    def test_deletes_by_source_sync_id(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.rowcount = 5
        count = db.delete_chunks_for_source(mock_conn, 42)
        assert count == 5
        mock_cur.execute.assert_called_once()
        args = mock_cur.execute.call_args[0]
        assert "DELETE" in args[0]
        assert args[1] == (42,)


class TestIngestDocChunks:
    def test_deletes_then_inserts_then_commits(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.rowcount = 3
        chunks = [
            {"content": "c1", "embedding": [0.1]*1536, "creator_id": 5,
             "doc_type": "guide", "file_name": "g.md", "metadata": {}, "source_sync_id": 42},
        ]
        with patch("db.execute_values"):
            result = db.ingest_doc_chunks(mock_conn, source_sync_id=42, chunks=chunks)
        assert result["deleted"] == 3
        assert result["inserted"] == 1
        mock_conn.commit.assert_called()

    def test_rollback_on_error(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        # First call (DELETE) succeeds, second call (execute_values in batch_insert) fails
        mock_cur.rowcount = 0
        # We need to make batch_insert_chunks fail
        with patch("db.execute_values", side_effect=Exception("insert failed")):
            try:
                db.ingest_doc_chunks(mock_conn, 42, [{"content": "c1", "embedding": [0.1]*1536,
                    "creator_id": 5, "doc_type": "prd", "file_name": "f", "metadata": {}, "source_sync_id": 42}])
            except Exception:
                pass
        mock_conn.rollback.assert_called()
