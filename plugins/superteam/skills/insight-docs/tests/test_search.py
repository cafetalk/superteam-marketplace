"""Unit tests for search_docs.py — tests both MCP and direct modes."""
import json
import sys
import pytest
from unittest.mock import MagicMock, patch

# conftest.py already added SCRIPTS_DIR to sys.path and stubbed psycopg2.

_config_mod = MagicMock()
_config_mod.env.return_value = "postgresql://fake/db"
sys.modules.setdefault("config", _config_mod)

_embedding_mod = MagicMock()
sys.modules.setdefault("embedding", _embedding_mod)

import search_docs as search_mod  # noqa: E402


FAKE_VEC = [0.1] * 1536
FAKE_RESULTS = [
    {"id": 1, "content": "hello", "doc_type": "guide", "file_name": "file.md",
     "creator_id": 5, "score": 0.1, "title": "file.md", "source_type": "",
     "source_url": None, "context": "hello", "context_range": None},
]


class TestMcpMode:
    """When _use_mcp() returns True, search_docs delegates to db.search_docs."""

    def test_mcp_search_returns_results(self):
        with patch("search_docs._use_mcp", return_value=True), \
             patch("search_docs.search_docs", return_value=FAKE_RESULTS) as mock_search, \
             patch.object(sys, "argv", ["search_docs.py", "hello"]), \
             patch("builtins.print") as mock_print:
            code = search_mod.main()

        assert code == 0
        mock_search.assert_called_once()
        output = mock_print.call_args[0][0]
        envelope = json.loads(output)
        assert envelope["total_results"] == 1
        assert envelope["results"][0]["content"] == "hello"

    def test_mcp_search_error_returns_1(self):
        with patch("search_docs._use_mcp", return_value=True), \
             patch("search_docs.search_docs", side_effect=Exception("fail")), \
             patch.object(sys, "argv", ["search_docs.py", "hello"]), \
             patch("builtins.print"):
            code = search_mod.main()
        assert code == 1


class TestDirectMode:
    """When _use_mcp() returns False, script uses embedding + queries.query_search_docs."""

    def test_direct_search_returns_results(self):
        mock_query = MagicMock(return_value=FAKE_RESULTS)
        mock_conn = MagicMock()

        with patch("search_docs._use_mcp", return_value=False), \
             patch("search_docs.env", return_value="postgresql://fake/db"), \
             patch("embedding.get_embedding", return_value=FAKE_VEC), \
             patch.dict(sys.modules, {"queries": MagicMock(query_search_docs=mock_query)}), \
             patch("psycopg2.connect", return_value=mock_conn), \
             patch.object(sys, "argv", ["search_docs.py", "hello", "--top-k", "3"]), \
             patch("builtins.print") as mock_print:
            code = search_mod.main()

        assert code == 0
        output = mock_print.call_args[0][0]
        envelope = json.loads(output)
        assert envelope["total_results"] == 1

    def test_direct_mode_no_pg_url_returns_1(self):
        with patch("search_docs._use_mcp", return_value=False), \
             patch("search_docs.env", return_value=""), \
             patch.object(sys, "argv", ["search_docs.py", "hello"]), \
             patch("builtins.print"):
            code = search_mod.main()
        assert code == 1

    def test_text_output_format(self):
        with patch("search_docs._use_mcp", return_value=True), \
             patch("search_docs.search_docs", return_value=FAKE_RESULTS), \
             patch.object(sys, "argv", ["search_docs.py", "hello", "--output-format", "text"]), \
             patch("builtins.print") as mock_print:
            code = search_mod.main()

        assert code == 0
        all_output = " ".join(str(a) for a in [c[0][0] for c in mock_print.call_args_list if c[0]])
        assert "hello" in all_output
