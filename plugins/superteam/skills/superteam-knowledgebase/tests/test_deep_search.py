"""Unit tests for deep_search.py and query_get_source_doc_content."""
import json
import sys
import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

# conftest.py already added SCRIPTS_DIR to sys.path and stubbed psycopg2.

_config_mod = MagicMock()
_config_mod.env.return_value = "postgresql://fake/db"
sys.modules.setdefault("config", _config_mod)

_embedding_mod = MagicMock()
sys.modules.setdefault("embedding", _embedding_mod)

import deep_search as deep_mod  # noqa: E402

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
SHARED_DIR = Path(__file__).parent.parent.parent / "_shared"
sys.path.insert(0, str(SHARED_DIR))
import queries as queries_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_CHUNKS = [
    {"id": 1, "content": "chunk1 about product", "doc_type": "prd",
     "file_name": "prd-v1.md", "creator_id": 5, "score": 0.05,
     "title": "prd-v1.md", "source_type": "dingtalk", "source_url": "https://example.com/1",
     "context": "chunk1 about product", "chunk_index": 0, "total_chunks": 3},
    {"id": 2, "content": "chunk2 about product", "doc_type": "prd",
     "file_name": "prd-v1.md", "creator_id": 5, "score": 0.08,
     "title": "prd-v1.md", "source_type": "dingtalk", "source_url": "https://example.com/1",
     "context": "chunk2 about product", "chunk_index": 1, "total_chunks": 3},
    {"id": 3, "content": "design overview", "doc_type": "tech-design",
     "file_name": "arch-design.md", "creator_id": 7, "score": 0.12,
     "title": "arch-design.md", "source_type": "notion", "source_url": None,
     "context": "design overview", "chunk_index": 0, "total_chunks": 1},
]

FAKE_FULL_DOC = {
    "id": 10,
    "file_name": "prd-v1.md",
    "source_type": "dingtalk",
    "source_url": "https://example.com/1",
    "local_path": "/home/user/.superteam/source_docs/dingtalk/prd-v1.md",
    "content": "# PRD v1\n\nFull original content here...\n\nMore details...",
}


# ---------------------------------------------------------------------------
# Tests: _unique_source_docs
# ---------------------------------------------------------------------------

class TestUniqueSourceDocs:

    def test_deduplicates_by_file_name(self):
        result = deep_mod._unique_source_docs(FAKE_CHUNKS)
        file_names = [d["file_name"] for d in result]
        assert len(file_names) == 2
        assert "prd-v1.md" in file_names
        assert "arch-design.md" in file_names

    def test_keeps_best_score(self):
        result = deep_mod._unique_source_docs(FAKE_CHUNKS)
        prd = next(d for d in result if d["file_name"] == "prd-v1.md")
        # lower score = better match (cosine distance)
        assert prd["score"] == 0.05

    def test_sorted_by_score(self):
        result = deep_mod._unique_source_docs(FAKE_CHUNKS)
        scores = [d["score"] for d in result]
        assert scores == sorted(scores)

    def test_empty_input(self):
        assert deep_mod._unique_source_docs([]) == []

    def test_skips_empty_file_names(self):
        chunks = [{"content": "no name", "score": 0.1}]
        assert deep_mod._unique_source_docs(chunks) == []


# ---------------------------------------------------------------------------
# Tests: deep_search (MCP mode)
# ---------------------------------------------------------------------------

class TestDeepSearchMcp:

    @patch("deep_search._use_mcp", return_value=True)
    @patch("deep_search.search_docs", return_value=FAKE_CHUNKS)
    @patch("deep_search.get_source_doc_content", return_value=FAKE_FULL_DOC)
    def test_returns_full_documents(self, mock_content, mock_search, _):
        result = deep_mod.deep_search("产品功能", max_docs=2)

        assert result["mode"] == "deep"
        assert result["search_hits"] == 3
        assert result["unique_docs_found"] == 2
        assert result["documents_retrieved"] == 2
        assert result["documents"][0]["content"] == FAKE_FULL_DOC["content"]

    @patch("deep_search._use_mcp", return_value=True)
    @patch("deep_search.search_docs", return_value=FAKE_CHUNKS)
    @patch("deep_search.get_source_doc_content", return_value=None)
    def test_fallback_to_chunks_when_no_original(self, mock_content, mock_search, _):
        result = deep_mod.deep_search("产品功能", max_docs=1)

        assert len(result["documents"]) == 1
        doc = result["documents"][0]
        assert doc.get("note") is not None  # indicates chunk fallback
        assert "chunk1" in doc["content"]

    @patch("deep_search._use_mcp", return_value=True)
    @patch("deep_search.search_docs", return_value=[])
    def test_empty_search_results(self, mock_search, _):
        result = deep_mod.deep_search("nonexistent topic")

        assert result["documents"] == []
        assert result["search_hits"] == 0

    @patch("deep_search._use_mcp", return_value=True)
    @patch("deep_search.search_docs", side_effect=Exception("MCP down"))
    def test_search_error(self, mock_search, _):
        result = deep_mod.deep_search("test query")

        assert "error" in result
        assert result["documents"] == []

    @patch("deep_search._use_mcp", return_value=True)
    @patch("deep_search.search_docs", return_value=FAKE_CHUNKS)
    @patch("deep_search.get_source_doc_content", return_value=FAKE_FULL_DOC)
    def test_max_docs_limits_output(self, mock_content, mock_search, _):
        result = deep_mod.deep_search("test", max_docs=1)
        assert len(result["documents"]) == 1

    @patch("deep_search._use_mcp", return_value=True)
    @patch("deep_search.search_docs", return_value=FAKE_CHUNKS)
    @patch("deep_search.get_source_doc_content")
    def test_get_source_doc_exception_falls_back(self, mock_content, mock_search, _):
        mock_content.side_effect = Exception("disk error")

        result = deep_mod.deep_search("test", max_docs=1)
        assert len(result["documents"]) == 1
        assert result["documents"][0].get("note") is not None


# ---------------------------------------------------------------------------
# Tests: deep_search CLI
# ---------------------------------------------------------------------------

class TestDeepSearchCli:

    @patch("deep_search._use_mcp", return_value=True)
    @patch("deep_search.search_docs", return_value=FAKE_CHUNKS)
    @patch("deep_search.get_source_doc_content", return_value=FAKE_FULL_DOC)
    def test_cli_json_output(self, mock_content, mock_search, _, capsys):
        with patch.object(sys, "argv", ["deep_search.py", "产品功能"]):
            code = deep_mod.main()
        assert code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["mode"] == "deep"

    @patch("deep_search._use_mcp", return_value=True)
    @patch("deep_search.search_docs", return_value=FAKE_CHUNKS)
    @patch("deep_search.get_source_doc_content", return_value=FAKE_FULL_DOC)
    def test_cli_text_output(self, mock_content, mock_search, _, capsys):
        with patch.object(sys, "argv",
                          ["deep_search.py", "产品功能", "--output-format", "text"]):
            code = deep_mod.main()
        assert code == 0
        output = capsys.readouterr().out
        assert "Deep Search" in output
        assert "prd-v1.md" in output


# ---------------------------------------------------------------------------
# Tests: query_get_source_doc_content (shared queries)
# ---------------------------------------------------------------------------

class TestQueryGetSourceDocContent:

    def _make_conn(self, fetchone_return=None):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = fetchone_return
        return conn, cur

    def test_returns_none_when_no_args(self):
        conn, _ = self._make_conn()
        result = queries_mod.query_get_source_doc_content(conn)
        assert result is None

    def test_returns_none_when_not_found(self):
        conn, _ = self._make_conn(fetchone_return=None)
        result = queries_mod.query_get_source_doc_content(conn, source_doc_id=999)
        assert result is None

    @patch("builtins.open", mock_open(read_data="# Full original content"))
    @patch("os.path.isfile", return_value=True)
    def test_reads_from_disk(self, mock_isfile):
        row = (10, "doc.md", "dingtalk", "https://url", "/path/to/doc.md")
        conn, _ = self._make_conn(fetchone_return=row)

        result = queries_mod.query_get_source_doc_content(conn, source_doc_id=10)

        assert result["file_name"] == "doc.md"
        assert result["content"] == "# Full original content"
        assert result["local_path"] == "/path/to/doc.md"

    @patch("os.path.isfile", return_value=False)
    def test_falls_back_to_chunks(self, mock_isfile):
        row = (10, "doc.md", "dingtalk", None, "/missing/path")
        conn, cur = self._make_conn(fetchone_return=row)

        # Mock the chunk fallback
        with patch.object(queries_mod, "query_get_doc_chunks",
                          return_value={"full_text": "reassembled chunks"}):
            result = queries_mod.query_get_source_doc_content(conn, source_doc_id=10)

        assert result["content"] == "reassembled chunks"

    @patch("os.path.isfile", return_value=False)
    def test_no_content_when_no_file_and_no_chunks(self, mock_isfile):
        row = (10, "doc.md", "notion", None, None)
        conn, _ = self._make_conn(fetchone_return=row)

        with patch.object(queries_mod, "query_get_doc_chunks", return_value=None):
            result = queries_mod.query_get_source_doc_content(conn, source_doc_id=10)

        assert result["content"] is None

    def test_file_name_search(self):
        row = (10, "my-prd.md", "google-drive", None, None)
        conn, cur = self._make_conn(fetchone_return=row)

        with patch("os.path.isfile", return_value=False), \
             patch.object(queries_mod, "query_get_doc_chunks", return_value=None):
            result = queries_mod.query_get_source_doc_content(
                conn, file_name="prd"
            )

        assert result["file_name"] == "my-prd.md"
        # Verify ILIKE query was used
        call_args = cur.execute.call_args
        assert "ILIKE" in call_args[0][0]
