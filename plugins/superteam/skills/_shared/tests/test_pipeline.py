"""Tests for _shared/pipeline.py — per-doc pipeline."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
import pipeline


class TestProcessAndIngestDoc:
    def test_chunks_and_ingests(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.rowcount = 0

        with patch("pipeline.get_embeddings_batch", return_value=[[0.1]*1536, [0.2]*1536]), \
             patch("pipeline.batch_insert_chunks", return_value=2), \
             patch("pipeline.delete_chunks_for_source", return_value=0):
            result = pipeline.process_and_ingest_doc(
                conn=mock_conn,
                content="# 新人入职手册\n\n## 第一步\ngit clone\n\n## 第二步\n配置环境",
                title="新人入职手册",
                source_doc_id="page-1",
                source_sync_id=42,
                source="notion",
            )
        assert result["status"] == "ok"
        assert result["chunks_inserted"] > 0
        assert result["doc_type"] in {"guide", "other"}

    def test_no_embed_uses_zero_vectors(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.rowcount = 0

        with patch("pipeline.batch_insert_chunks", return_value=1) as mock_insert, \
             patch("pipeline.delete_chunks_for_source", return_value=0):
            result = pipeline.process_and_ingest_doc(
                conn=mock_conn, content="hello world", title="test",
                source_doc_id="d1", source_sync_id=1, source="test",
                no_embed=True,
            )
        chunks_arg = mock_insert.call_args[0][1]
        assert chunks_arg[0]["embedding"] == [0.0] * 1536

    def test_empty_content_returns_zero_chunks(self):
        mock_conn = MagicMock()
        result = pipeline.process_and_ingest_doc(
            conn=mock_conn, content="", title="empty",
            source_doc_id="d1", source_sync_id=1, source="test",
        )
        assert result["chunks_inserted"] == 0

    def test_doc_type_classification(self):
        mock_conn = MagicMock()
        with patch("pipeline.batch_insert_chunks", return_value=1) as mock_insert, \
             patch("pipeline.delete_chunks_for_source", return_value=0):
            result = pipeline.process_and_ingest_doc(
                conn=mock_conn,
                content="# 会议纪要\n\n### 日期：2024-03-15\n参会人员：张三\n议题：Q1 review",
                title="会议纪要",
                source_doc_id="d1", source_sync_id=1, source="test",
                no_embed=True,
            )
        assert result["doc_type"] == "meeting-notes"

    def test_rollback_on_insert_failure(self):
        mock_conn = MagicMock()
        with patch("pipeline.delete_chunks_for_source", return_value=0), \
             patch("pipeline.batch_insert_chunks", side_effect=Exception("db error")):
            try:
                pipeline.process_and_ingest_doc(
                    conn=mock_conn, content="some content", title="test",
                    source_doc_id="d1", source_sync_id=1, source="test",
                    no_embed=True,
                )
            except Exception:
                pass
        mock_conn.rollback.assert_called()
