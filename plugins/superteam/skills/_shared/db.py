"""DB helpers: dual-mode (MCP client or direct psycopg2).

Mode selection:
  - SUPERTEAM_MCP_URL set -> MCP client mode (httpx, no psycopg2 needed)
  - KB_TREX_PG_URL set -> direct mode (psycopg2)
  - Both set -> MCP takes priority for query functions; write functions use direct

Write functions (get_connection, batch_insert_chunks, etc.) always use direct mode.
"""
from __future__ import annotations
import json

from config import env


# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------

def _use_mcp() -> bool:
    return bool(env("SUPERTEAM_MCP_URL"))


# ---------------------------------------------------------------------------
# MCP client helpers
# ---------------------------------------------------------------------------

class McpError(Exception):
    """Error from MCP server."""
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"MCP error ({code}): {message}")


_mcp_session_id: str | None = None


def _mcp_request(method: str, params: dict) -> dict:
    """Low-level MCP JSON-RPC request with session management."""
    import httpx

    global _mcp_session_id
    url = env("SUPERTEAM_MCP_URL")
    token = env("SUPERTEAM_API_TOKEN")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if _mcp_session_id:
        headers["Mcp-Session-Id"] = _mcp_session_id

    resp = httpx.post(
        url,
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        },
        timeout=30.0,
    )

    if resp.status_code == 429:
        raise McpError("rate_limited", "Rate limit exceeded")
    if resp.status_code == 401:
        raise McpError("auth_failed", "Invalid or missing token")
    if resp.status_code != 200:
        raise McpError("server_error", f"HTTP {resp.status_code}")

    # Save session ID from response
    sid = resp.headers.get("mcp-session-id")
    if sid:
        _mcp_session_id = sid

    # Parse SSE response — extract last "data:" line
    text = resp.text.strip()
    for line in reversed(text.splitlines()):
        if line.startswith("data: "):
            return json.loads(line[6:])

    # Fallback: try direct JSON parse
    return resp.json()


def _mcp_ensure_session():
    """Initialize MCP session if not yet established."""
    global _mcp_session_id
    if _mcp_session_id:
        return
    _mcp_request("initialize", {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        # MCP schema expects clientInfo.name + clientInfo.version (not arbitrary keys).
        "clientInfo": {"name": "superteam", "version": "1.0.0"},
    })


def _mcp_call(tool_name: str, params: dict):
    """Call a tool on the remote MCP server via HTTP."""
    _mcp_ensure_session()

    body = _mcp_request("tools/call", {
        "name": tool_name,
        "arguments": params,
    })

    if "error" in body:
        err = body["error"]
        raise McpError(err.get("code", "unknown"), err.get("message", ""))

    result = body.get("result", {})

    # Prefer structuredContent if available
    structured = result.get("structuredContent", {}).get("result")
    if structured is not None:
        return structured

    # Fallback: parse from text content
    content = result.get("content", [])
    if content and content[0].get("type") == "text":
        text = content[0]["text"]
        if not text or not text.strip():
            return None
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            raise McpError("parse_error", f"MCP returned non-JSON text: {text[:200]}")
    return result


# ---------------------------------------------------------------------------
# Query functions (dual-mode)
# ---------------------------------------------------------------------------

def search_docs(query: str, creator_id: int | None = None,
                limit: int = 10, **kwargs) -> list[dict]:
    """Search docs -- MCP mode or direct."""
    if _use_mcp():
        params = {"query": query, "limit": limit}
        if creator_id is not None:
            params["creator_id"] = creator_id
        return _mcp_call("search_docs", params)

    from queries import query_search_docs
    embedding_vec = kwargs.get("embedding")
    if embedding_vec is None:
        raise ValueError("Direct mode requires embedding vector")
    conn = get_connection()
    try:
        return query_search_docs(conn, embedding_vec, top_k=limit,
                                 creator_id=creator_id)
    finally:
        conn.close()


def list_members(name_query: str | None = None) -> list[dict]:
    if _use_mcp():
        params: dict = {}
        if name_query:
            params["name_query"] = name_query
        return _mcp_call("list_members", params)

    from queries import query_list_members
    conn = get_connection()
    try:
        return query_list_members(conn, name=name_query)
    finally:
        conn.close()


def list_source_docs(filter: str | None = None) -> list[dict]:
    if _use_mcp():
        params = {}
        if filter:
            params["filter"] = filter
        return _mcp_call("list_source_docs", params)

    from queries import query_list_source_docs
    conn = get_connection()
    try:
        return query_list_source_docs(conn, source_type=filter)
    finally:
        conn.close()


def get_doc_chunks(source_sync_id: int | None = None,
                    file_name: str | None = None) -> dict | None:
    """Get full document content by reassembling chunks — MCP or direct."""
    if _use_mcp():
        params = {}
        if source_sync_id is not None:
            params["source_sync_id"] = source_sync_id
        if file_name:
            params["file_name"] = file_name
        return _mcp_call("get_doc_chunks", params)

    from queries import query_get_doc_chunks
    conn = get_connection()
    try:
        return query_get_doc_chunks(conn, source_sync_id=source_sync_id,
                                     file_name=file_name)
    finally:
        conn.close()


def get_source_doc_content(source_doc_id: int | None = None,
                            file_name: str | None = None) -> dict | None:
    """Get original source document content — MCP or direct."""
    if _use_mcp():
        params = {}
        if source_doc_id is not None:
            params["source_doc_id"] = source_doc_id
        if file_name:
            params["file_name"] = file_name
        return _mcp_call("get_source_doc_content", params)

    from queries import query_get_source_doc_content
    conn = get_connection()
    try:
        return query_get_source_doc_content(conn, source_doc_id=source_doc_id,
                                             file_name=file_name)
    finally:
        conn.close()


def resolve_member(name_string: str) -> dict | None:
    if _use_mcp():
        return _mcp_call("resolve_member", {"name_string": name_string})

    from queries import query_resolve_member
    conn = get_connection()
    try:
        return query_resolve_member(conn, name_string)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Direct-mode connection + write helpers (unchanged, admin-only)
# ---------------------------------------------------------------------------

def get_connection(conn_url: str | None = None, schema: str = "trex_hub, public"):
    """Create psycopg2 connection with search_path set."""
    import psycopg2
    url = conn_url or env("KB_TREX_PG_URL")
    if not url:
        raise RuntimeError("KB_TREX_PG_URL not set.")
    conn = psycopg2.connect(url)
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute(f"SET search_path TO {schema}")
    conn.commit()
    return conn


def batch_insert_chunks(conn, chunks: list[dict]) -> int:
    """Batch INSERT using execute_values. Does NOT commit. Returns count."""
    if not chunks:
        return 0
    from psycopg2.extras import execute_values
    cur = conn.cursor()
    sql = (
        "INSERT INTO kb_trex_team_docs "
        "(content, embedding, creator_id, doc_type, file_name, metadata, source_sync_id) "
        "VALUES %s"
    )
    values = [
        (
            c["content"],
            str(c["embedding"]),
            c.get("creator_id"),
            c.get("doc_type", ""),
            c.get("file_name", ""),
            json.dumps(c.get("metadata", {}), ensure_ascii=False),
            c.get("source_sync_id"),
        )
        for c in chunks
    ]
    execute_values(cur, sql, values, template=(
        "(%s, %s::vector, %s, %s, %s, %s::jsonb, %s)"
    ))
    cur.close()
    return len(chunks)


def delete_chunks_for_source(conn, source_sync_id: int) -> int:
    """DELETE old chunks for a source doc. Does NOT commit. Returns count deleted."""
    cur = conn.cursor()
    cur.execute("DELETE FROM kb_trex_team_docs WHERE source_sync_id = %s", (source_sync_id,))
    count = cur.rowcount
    cur.close()
    return count


def ingest_doc_chunks(conn, source_sync_id: int, chunks: list[dict]) -> dict:
    """Atomic per-doc ingest: DELETE old -> batch INSERT new -> COMMIT."""
    try:
        deleted = delete_chunks_for_source(conn, source_sync_id)
        inserted = batch_insert_chunks(conn, chunks)
        conn.commit()
        return {"deleted": deleted, "inserted": inserted}
    except Exception:
        conn.rollback()
        raise
