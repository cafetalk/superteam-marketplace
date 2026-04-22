#!/usr/bin/env python3
"""Deep search: chunk search → identify top docs → fetch original full text.

For deep research / document creation scenarios where full original context
is needed, not just chunk snippets.

Flow:
  1. Vector search to find relevant chunks (same as search_docs.py)
  2. Deduplicate to unique source documents
  3. Fetch original full text for each unique doc via get_source_doc_content
  4. Output combined results with full document content

Usage:
    python deep_search.py "PRD 里提到了什么功能"
    python deep_search.py "产品架构设计" --max-docs 3
    python deep_search.py "技术方案" --output-format text
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent / "_shared"))
from config import env
from db import _use_mcp, search_docs, get_source_doc_content


def _unique_source_docs(search_results: list[dict]) -> list[dict]:
    """Extract unique source documents from search results.

    Groups chunks by file_name, keeping the best-scoring chunk per doc.
    Returns list of {"file_name": str, "source_sync_id": int|None, "score": float, "snippet": str}.
    """
    seen: dict[str, dict] = {}
    for r in search_results:
        fname = r.get("file_name") or r.get("title") or ""
        if not fname:
            continue
        if fname not in seen or (r.get("score") or 1) < (seen[fname].get("score") or 1):
            seen[fname] = {
                "file_name": fname,
                "source_sync_id": r.get("source_sync_id"),
                "score": r.get("score"),
                "snippet": (r.get("content") or "")[:200],
                "source_type": r.get("source_type", ""),
                "source_url": r.get("source_url"),
            }
    return sorted(seen.values(), key=lambda x: x.get("score") or 1)


def deep_search(query: str, top_k: int = 10, max_docs: int = 3,
                creator_id: int | None = None) -> dict:
    """Perform deep search: chunk search → full doc retrieval.

    Args:
        query: Natural language search query.
        top_k: Number of chunks to search (cast a wider net).
        max_docs: Maximum unique documents to retrieve full text for.
        creator_id: Optional filter by creator.

    Returns:
        dict with "query", "documents" (list of full doc results), "search_hits" count.
    """
    # Step 1: Chunk search (wider net)
    if _use_mcp():
        try:
            chunks = search_docs(query, creator_id=creator_id, limit=top_k)
        except Exception as e:
            return {"error": f"Search failed: {e}", "documents": []}
    else:
        conn_url = env("KB_TREX_PG_URL")
        if not conn_url:
            return {"error": "KB_TREX_PG_URL not set", "documents": []}

        from embedding import get_embedding
        from queries import query_search_docs
        import psycopg2

        try:
            embedding = get_embedding(query)
        except Exception as e:
            return {"error": f"Embedding failed: {e}", "documents": []}

        conn = psycopg2.connect(conn_url)
        cur = conn.cursor()
        cur.execute("SET search_path TO trex_hub, public")
        conn.commit()
        try:
            chunks = query_search_docs(conn, embedding, top_k, creator_id=creator_id)
        finally:
            conn.close()

    if not chunks:
        return {"query": query, "documents": [], "search_hits": 0}

    # Step 2: Deduplicate to unique source docs
    unique_docs = _unique_source_docs(chunks)

    # Step 3: Fetch full text for top N documents
    documents = []
    for doc_info in unique_docs[:max_docs]:
        try:
            full_doc = get_source_doc_content(file_name=doc_info["file_name"])
        except Exception:
            full_doc = None

        if full_doc and full_doc.get("content"):
            documents.append({
                "file_name": doc_info["file_name"],
                "source_type": doc_info.get("source_type", ""),
                "source_url": doc_info.get("source_url"),
                "relevance_score": doc_info.get("score"),
                "content": full_doc["content"],
                "content_length": len(full_doc["content"]),
            })
        else:
            # Fallback: use the chunk snippet + context
            matching_chunks = [
                c for c in chunks
                if (c.get("file_name") or c.get("title") or "") == doc_info["file_name"]
            ]
            combined = "\n\n".join(
                c.get("context") or c.get("content", "") for c in matching_chunks
            )
            documents.append({
                "file_name": doc_info["file_name"],
                "source_type": doc_info.get("source_type", ""),
                "source_url": doc_info.get("source_url"),
                "relevance_score": doc_info.get("score"),
                "content": combined,
                "content_length": len(combined),
                "note": "Original file unavailable; content assembled from chunks",
            })

    return {
        "query": query,
        "mode": "deep",
        "search_hits": len(chunks),
        "unique_docs_found": len(unique_docs),
        "documents_retrieved": len(documents),
        "documents": documents,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deep search: full document retrieval for research/writing"
    )
    parser.add_argument("query", help="Natural language search query")
    parser.add_argument("--top-k", type=int, default=10,
                        help="Chunk search breadth (default: 10)")
    parser.add_argument("--max-docs", type=int, default=3,
                        help="Max full documents to retrieve (default: 3)")
    parser.add_argument("--creator-id", type=int)
    parser.add_argument("--output-format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    result = deep_search(
        args.query,
        top_k=args.top_k,
        max_docs=args.max_docs,
        creator_id=args.creator_id,
    )

    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    if args.output_format == "text":
        print(f"Deep Search: {args.query}")
        print(f"Found {result['search_hits']} chunks across "
              f"{result['unique_docs_found']} docs, "
              f"retrieved {result['documents_retrieved']} full documents\n")
        for i, doc in enumerate(result["documents"], 1):
            print(f"{'='*60}")
            print(f"  Document {i}: {doc['file_name']}")
            print(f"  Source: {doc.get('source_type', '')} | "
                  f"Score: {doc.get('relevance_score', 'N/A')}")
            if doc.get("source_url"):
                print(f"  URL: {doc['source_url']}")
            if doc.get("note"):
                print(f"  Note: {doc['note']}")
            print(f"  Length: {doc['content_length']} chars")
            print(f"{'='*60}")
            print(doc["content"])
            print()
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
