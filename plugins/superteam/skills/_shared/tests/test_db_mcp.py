"""Tests for db.py MCP client mode."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import db  # noqa: E402


class TestModeDetection:
    def test_use_mcp_true_when_url_set(self):
        with patch("db.env", side_effect=lambda k, **kw: "https://example.com/mcp" if k == "SUPERTEAM_MCP_URL" else None):
            assert db._use_mcp() is True

    def test_use_mcp_false_when_url_not_set(self):
        with patch("db.env", side_effect=lambda k, **kw: None):
            assert db._use_mcp() is False


class TestMcpCall:
    def _mock_httpx(self, status_code, json_body=None):
        """Create a mock httpx module with a mocked post response."""
        mock_httpx = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        if json_body is not None:
            mock_resp.json.return_value = json_body
        mock_httpx.post.return_value = mock_resp
        return mock_httpx

    def test_successful_call(self):
        mock_httpx = self._mock_httpx(200, {
            "result": {
                "content": [{"type": "text", "text": json.dumps([{"id": 1}])}]
            }
        })

        with patch("db.env", side_effect=lambda k, **kw: {
            "SUPERTEAM_MCP_URL": "https://example.com/mcp",
            "SUPERTEAM_API_TOKEN": "test-token",
        }.get(k)):
            with patch.dict("sys.modules", {"httpx": mock_httpx}):
                result = db._mcp_call("search_docs", {"query": "test"})
                assert result == [{"id": 1}]

    def test_rate_limited(self):
        mock_httpx = self._mock_httpx(429)

        with patch("db.env", side_effect=lambda k, **kw: "val"):
            with patch.dict("sys.modules", {"httpx": mock_httpx}):
                try:
                    db._mcp_call("test", {})
                    assert False, "Should have raised"
                except db.McpError as e:
                    assert e.code == "rate_limited"

    def test_auth_failed(self):
        mock_httpx = self._mock_httpx(401)

        with patch("db.env", side_effect=lambda k, **kw: "val"):
            with patch.dict("sys.modules", {"httpx": mock_httpx}):
                try:
                    db._mcp_call("test", {})
                    assert False, "Should have raised"
                except db.McpError as e:
                    assert e.code == "auth_failed"


class TestDualModeDispatch:
    def test_search_docs_mcp_mode(self):
        with patch("db._use_mcp", return_value=True), \
             patch("db._mcp_call", return_value=[{"id": 1}]) as mock_call:
            result = db.search_docs("test query", limit=5)
            assert result == [{"id": 1}]
            mock_call.assert_called_once_with("search_docs", {"query": "test query", "limit": 5})

    def test_list_members_mcp_mode(self):
        with patch("db._use_mcp", return_value=True), \
             patch("db._mcp_call", return_value=[]) as mock_call:
            result = db.list_members(name_query="alice")
            assert result == []
            mock_call.assert_called_once_with("list_members", {"name_query": "alice"})

    def test_resolve_member_mcp_mode(self):
        with patch("db._use_mcp", return_value=True), \
             patch("db._mcp_call", return_value={"user_id": 3}) as mock_call:
            result = db.resolve_member("Peter")
            assert result == {"user_id": 3}
            mock_call.assert_called_once_with("resolve_member", {"name_string": "Peter"})
