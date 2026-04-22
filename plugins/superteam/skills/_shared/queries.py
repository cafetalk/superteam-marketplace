"""Shared SQL query functions. Pure queries — take a connection, return data.

Used by both local skill scripts (direct psycopg2) and MCP server (via Dockerfile COPY).
"""
from __future__ import annotations
import json


def query_search_docs(conn, embedding_vec: list[float], top_k: int = 5,
                      doc_type: str | None = None,
                      creator_id: int | None = None) -> list[dict]:
    """Vector similarity search over kb_trex_team_docs."""
    cur = conn.cursor()
    vec_str = "[" + ",".join(str(x) for x in embedding_vec) + "]"

    where_parts: list[str] = []
    params: list = []
    if doc_type:
        where_parts.append("c.doc_type = %s")
        params.append(doc_type)
    if creator_id is not None:
        where_parts.append("c.creator_id = %s")
        params.append(creator_id)
    where_clause = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

    sql = (
        "SELECT c.id, c.content, c.doc_type, c.file_name, c.creator_id, c.metadata, "
        "(c.embedding <=> %s::vector) AS score, "
        "s.source_type, s.source_url "
        "FROM kb_trex_team_docs c "
        "LEFT JOIN kb_trex_source_docs s ON c.source_sync_id = s.id"
        f"{where_clause} "
        "ORDER BY c.embedding <=> %s::vector LIMIT %s"
    )
    cur.execute(sql, [vec_str] + params + [vec_str, top_k])
    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    for row in rows:
        if isinstance(row.get("metadata"), dict):
            pass
        elif row.get("metadata"):
            try:
                row["metadata"] = json.loads(str(row["metadata"]))
            except (json.JSONDecodeError, TypeError):
                pass
        row["score"] = float(row["score"]) if row.get("score") is not None else None

        meta = row.get("metadata") or {}
        if isinstance(meta, dict):
            row["title"] = meta.get("title", row.get("file_name", ""))
            row["chunk_index"] = meta.get("chunk_index")
            row["total_chunks"] = meta.get("total_chunks")
            if not row.get("source_type"):
                row["source_type"] = meta.get("source", "")
        else:
            row["title"] = row.get("file_name", "")
        row.setdefault("source_type", "")
        row.setdefault("source_url", None)
        del row["metadata"]

    cur.close()

    # Deduplicate: same content prefix across different file versions
    seen: set[str] = set()
    deduped: list[dict] = []
    for row in rows:
        key = row.get("content", "")[:200]
        if key not in seen:
            seen.add(key)
            deduped.append(row)

    # Adjacent chunk expansion: fetch surrounding chunks for richer context
    if deduped:
        _expand_adjacent_chunks(conn, deduped)

    return deduped


def _expand_adjacent_chunks(conn, rows: list[dict], window: int = 1) -> None:
    """Expand each search result with adjacent chunks from the same document.

    Mutates rows in-place, adding a 'context' field with concatenated content
    from chunk_index ± window.
    """
    cur = conn.cursor()
    for row in rows:
        ci = row.get("chunk_index")
        if ci is None:
            row["context"] = row.get("content", "")
            row["context_range"] = None
            continue

        # Get source_sync_id from the chunk
        cur.execute(
            "SELECT source_sync_id FROM kb_trex_team_docs WHERE id = %s",
            (row["id"],),
        )
        ssid_row = cur.fetchone()
        if not ssid_row:
            row["context"] = row.get("content", "")
            row["context_range"] = None
            continue

        source_sync_id = ssid_row[0]
        lo = max(0, ci - window)
        hi = ci + window

        cur.execute(
            "SELECT content, (metadata->>'chunk_index')::int AS ci "
            "FROM kb_trex_team_docs "
            "WHERE source_sync_id = %s "
            "  AND (metadata->>'chunk_index')::int BETWEEN %s AND %s "
            "ORDER BY ci",
            (source_sync_id, lo, hi),
        )
        adjacent = cur.fetchall()
        if adjacent:
            row["context"] = "\n\n".join(str(r[0]) for r in adjacent)
            row["context_range"] = [lo, hi]
        else:
            row["context"] = row.get("content", "")
            row["context_range"] = None
    cur.close()


def query_get_doc_chunks(conn, source_sync_id: int | None = None,
                         file_name: str | None = None) -> dict | None:
    """Retrieve all chunks for a document, ordered by chunk_index.

    Returns {"file_name": str, "total_chunks": int, "full_text": str, "chunks": list}
    or None if not found. Identify document by source_sync_id or file_name.
    """
    cur = conn.cursor()

    if source_sync_id is not None:
        cur.execute(
            "SELECT id, content, file_name, (metadata->>'chunk_index')::int AS ci, "
            "(metadata->>'total_chunks')::int AS tc "
            "FROM kb_trex_team_docs "
            "WHERE source_sync_id = %s "
            "ORDER BY ci NULLS LAST",
            (source_sync_id,),
        )
    elif file_name:
        cur.execute(
            "SELECT id, content, file_name, (metadata->>'chunk_index')::int AS ci, "
            "(metadata->>'total_chunks')::int AS tc "
            "FROM kb_trex_team_docs "
            "WHERE file_name ILIKE %s "
            "ORDER BY ci NULLS LAST",
            (f"%{file_name}%",),
        )
    else:
        cur.close()
        return None

    rows = cur.fetchall()
    cur.close()

    if not rows:
        return None

    chunks = [{"id": r[0], "content": r[1], "chunk_index": r[3]} for r in rows]
    full_text = "\n\n".join(r[1] for r in rows)
    fname = rows[0][2]
    total = rows[0][4] or len(rows)

    return {
        "file_name": fname,
        "total_chunks": total,
        "full_text": full_text,
        "chunks": chunks,
    }


def query_list_members(conn, name: str | None = None,
                       role: str | None = None,
                       user_id: int | None = None) -> list[dict]:
    """List team members with optional filters."""
    cur = conn.cursor()
    where_parts: list[str] = []
    params: list = []

    if user_id is not None:
        where_parts.append("user_id = %s")
        params.append(user_id)
    if name:
        where_parts.append(
            "(real_name ILIKE %s OR username ILIKE %s"
            " OR real_name_en ILIKE %s OR email ILIKE %s)"
        )
        params.extend([f"%{name}%"] * 4)
    if role:
        where_parts.append("role = %s")
        params.append(role)

    where_clause = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
    cur.execute(
        f"SELECT user_id, username, real_name, real_name_en, email, role,"
        f" verified, aliases, created_at"
        f" FROM kb_trex_team_members{where_clause} ORDER BY user_id",
        params,
    )
    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()

    for row in rows:
        if row.get("created_at"):
            row["created_at"] = str(row["created_at"])
    return rows


def query_list_source_docs(conn, source_type: str | None = None,
                           name: str | None = None,
                           limit: int = 50) -> list[dict]:
    """List synced source documents."""
    cur = conn.cursor()
    where_parts: list[str] = []
    params: list = []

    if source_type:
        where_parts.append("source_type = %s")
        params.append(source_type)
    if name:
        where_parts.append("file_name ILIKE %s")
        params.append(f"%{name}%")

    where_clause = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
    params.append(limit)
    cur.execute(
        f"SELECT id, source_type, source_doc_id, file_name, "
        f"last_edited_at, last_synced_at, sync_version "
        f"FROM kb_trex_source_docs{where_clause} "
        f"ORDER BY last_synced_at DESC LIMIT %s",
        params,
    )
    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()

    for row in rows:
        for k in ("last_edited_at", "last_synced_at"):
            if row.get(k):
                row[k] = str(row[k])
    return rows


def query_get_source_doc_content(conn, source_doc_id: int | None = None,
                                  file_name: str | None = None) -> dict | None:
    """Read the original source document content from local disk.

    Looks up the local_path in kb_trex_source_docs, then reads the file.
    Returns {"file_name": str, "source_type": str, "content": str, "local_path": str}
    or None if not found or file doesn't exist on disk.
    """
    import os

    cur = conn.cursor()

    if source_doc_id is not None:
        cur.execute(
            "SELECT id, file_name, source_type, source_url, local_path "
            "FROM kb_trex_source_docs WHERE id = %s",
            (source_doc_id,),
        )
    elif file_name:
        cur.execute(
            "SELECT id, file_name, source_type, source_url, local_path "
            "FROM kb_trex_source_docs WHERE file_name ILIKE %s "
            "ORDER BY last_synced_at DESC LIMIT 1",
            (f"%{file_name}%",),
        )
    else:
        cur.close()
        return None

    row = cur.fetchone()
    cur.close()

    if not row:
        return None

    doc_id, fname, source_type, source_url, local_path = row

    result = {
        "id": doc_id,
        "file_name": fname,
        "source_type": source_type or "",
        "source_url": source_url or "",
        "local_path": local_path or "",
        "content": None,
    }

    # Primary: read file from disk (shared mount between MCP server and sync server)
    # local_path in DB may use sync server's path; translate via SUPERTEAM_SOURCE_DIR
    read_path = local_path
    source_dir = os.environ.get("SUPERTEAM_SOURCE_DIR")
    if local_path and source_dir:
        # Extract relative part after source_docs/ (e.g. "dingtalk/xxx.md")
        marker = "/source_docs/"
        idx = local_path.find(marker)
        if idx >= 0:
            read_path = os.path.join(source_dir, local_path[idx + len(marker):])

    if read_path and os.path.isfile(read_path):
        try:
            with open(read_path, "r", encoding="utf-8") as f:
                result["content"] = f.read()
        except (OSError, UnicodeDecodeError):
            result["content"] = None

    # Fallback: reassemble from chunks (only if file not found or read failed)
    if result["content"] is None:
        chunk_result = query_get_doc_chunks(conn, source_sync_id=doc_id)
        if chunk_result:
            result["content"] = chunk_result["full_text"]

    return result


def query_resolve_member(conn, name_string: str) -> dict | None:
    """Read-only member lookup by name. Returns match or None.

    Checks: real_name, real_name_en, username, email, aliases (case-insensitive).
    Does NOT create entries — pure read-only.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, username, real_name, real_name_en, email, role, aliases "
        "FROM kb_trex_team_members"
    )
    columns = [desc[0] for desc in cur.description]
    members = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()

    name_lower = name_string.lower()

    for m in members:
        for field in ("real_name", "real_name_en", "username", "email"):
            if (m.get(field) or "").lower() == name_lower:
                return {**m, "match_type": "exact", "confidence": 1.0}

        aliases = m.get("aliases") or []
        if isinstance(aliases, str):
            try:
                aliases = json.loads(aliases)
            except Exception:
                aliases = []
        if any(a.lower() == name_lower for a in aliases):
            return {**m, "match_type": "alias", "confidence": 1.0}

    # Check alias cache table
    cur2 = conn.cursor()
    cur2.execute(
        "SELECT user_id FROM kb_trex_member_aliases WHERE LOWER(alias) = %s",
        (name_lower,),
    )
    alias_row = cur2.fetchone()
    cur2.close()

    if alias_row:
        uid = alias_row[0]
        cur3 = conn.cursor()
        cur3.execute(
            "SELECT user_id, username, real_name, real_name_en, email, role, aliases "
            "FROM kb_trex_team_members WHERE user_id = %s",
            (uid,),
        )
        row = cur3.fetchone()
        cur3.close()
        if row:
            member = dict(zip(columns, row))
            return {**member, "match_type": "alias_cache", "confidence": 0.9}

    return None
