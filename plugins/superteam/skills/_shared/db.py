"""DB helpers: connection, batch insert, atomic per-doc ingest."""
from __future__ import annotations
import json

import psycopg2
from psycopg2.extras import execute_values

from config import env


def get_connection(conn_url: str | None = None, schema: str = "trex_hub, public"):
    """Create psycopg2 connection with search_path set."""
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
    """Atomic per-doc ingest: DELETE old -> batch INSERT new -> COMMIT.

    Returns {"deleted": N, "inserted": M}.
    """
    try:
        deleted = delete_chunks_for_source(conn, source_sync_id)
        inserted = batch_insert_chunks(conn, chunks)
        conn.commit()
        return {"deleted": deleted, "inserted": inserted}
    except Exception:
        conn.rollback()
        raise
