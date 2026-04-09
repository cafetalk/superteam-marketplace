"""Per-doc pipeline: chunk -> classify -> embed -> ingest."""
from __future__ import annotations
import sys

from chunking import chunk_text, chunk_smart, chunk_with_llm, classify_by_regex, DOC_TYPES
from embedding import get_embeddings_batch
from db import batch_insert_chunks, delete_chunks_for_source


def process_and_ingest_doc(
    conn,
    content: str,
    title: str,
    source_doc_id: str,
    source_sync_id: int,
    source: str,
    is_spreadsheet: bool = False,
    chunk_size: int = 1500,
    overlap: int = 200,
    use_llm: bool = False,
    llm_model: str = "qwen-plus",
    no_embed: bool = False,
    creator_id: int | None = None,
) -> dict:
    """Per-doc pipeline: chunk -> classify -> embed -> atomic ingest.

    Transaction: DELETE old chunks -> INSERT new -> COMMIT.
    Returns {"status", "chunks_inserted", "doc_type", "deleted"}.
    """
    if not content or not content.strip():
        return {"status": "ok", "chunks_inserted": 0, "doc_type": "other", "deleted": 0}

    # 1. Chunk
    cs = 0 if is_spreadsheet else chunk_size
    if use_llm and not is_spreadsheet:
        chunks, doc_type = chunk_with_llm(content, title=title, model=llm_model)
    else:
        chunks = chunk_smart(content, max_chars=cs, overlap=overlap)
        doc_type = classify_by_regex(title, content[:2000])

    if not chunks:
        return {"status": "ok", "chunks_inserted": 0, "doc_type": doc_type, "deleted": 0}

    # 2. Embed
    if no_embed:
        embeddings = [[0.0] * 1536] * len(chunks)
    else:
        embeddings = get_embeddings_batch([c[:512] for c in chunks])

    # 3. Build chunk records
    file_name = title or source_doc_id
    chunk_records = []
    for i, (text, emb) in enumerate(zip(chunks, embeddings)):
        chunk_records.append({
            "content": text,
            "embedding": emb,
            "creator_id": creator_id,
            "doc_type": doc_type,
            "file_name": file_name,
            "metadata": {
                "source": source,
                "source_doc_id": source_doc_id,
                "title": title,
                "chunk_index": i + 1,
                "total_chunks": len(chunks),
            },
            "source_sync_id": source_sync_id,
        })

    # 4. Atomic ingest: DELETE old + INSERT new + COMMIT
    try:
        deleted = delete_chunks_for_source(conn, source_sync_id)
        inserted = batch_insert_chunks(conn, chunk_records)
        conn.commit()
        return {"status": "ok", "chunks_inserted": inserted, "doc_type": doc_type, "deleted": deleted}
    except Exception:
        conn.rollback()
        raise
