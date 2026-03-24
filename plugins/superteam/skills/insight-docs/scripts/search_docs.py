#!/usr/bin/env python3
"""
团队文档向量检索：预计算向量 → pgvector 相似度搜索 → 输出 JSON。
依赖：KB_TREX_PG_URL。
向量由宿主 agent 预计算后通过 --embedding 参数传入。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent / "_shared"))
from config import env


def run_vector_search(conn, vec: list[float], top_k: int,
                      doc_type: str | None, creator_id: int | None) -> list[dict]:
    cur = conn.cursor()
    vec_str = "[" + ",".join(str(x) for x in vec) + "]"

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
        f"FROM kb_trex_team_docs c "
        f"LEFT JOIN kb_trex_source_docs s ON c.source_sync_id = s.id"
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
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Vector search over kb_trex_team_docs.")
    parser.add_argument("query", help="Natural language question or search phrase.")
    parser.add_argument("--embedding", required=True,
                        help="Pre-computed 1536-dim embedding vector as JSON array. "
                             "Must be provided by the host agent.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--doc-type", choices=[
        "prd", "tech-design", "reference", "guide", "explanation",
        "decision", "meeting-notes", "weekly-report", "plan",
        "changelog", "other",
    ])
    parser.add_argument("--creator-id", type=int)
    parser.add_argument("--output-format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    conn_url = env("KB_TREX_PG_URL")
    if not conn_url:
        print("KB_TREX_PG_URL not set.", file=sys.stderr)
        return 1

    try:
        embedding = json.loads(args.embedding)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"Invalid --embedding JSON: {e}", file=sys.stderr)
        return 1
    if not isinstance(embedding, list) or len(embedding) != 1536:
        print(f"Embedding must be a 1536-dim array, got {type(embedding).__name__} "
              f"len={len(embedding) if isinstance(embedding, list) else 'N/A'}",
              file=sys.stderr)
        return 1

    import psycopg2
    conn = psycopg2.connect(conn_url)
    cur = conn.cursor()
    cur.execute("SET search_path TO trex_hub, public")
    conn.commit()

    try:
        rows = run_vector_search(conn, embedding, args.top_k, args.doc_type, args.creator_id)
    except Exception as e:
        print(f"Search failed: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    envelope = {
        "query": args.query,
        "skill": "insight-docs",
        "total_results": len(rows),
        "results": rows,
    }

    if args.output_format == "text":
        print(f"Query: {args.query}  ({len(rows)} results)\n")
        for i, r in enumerate(rows, 1):
            title = r.get("title") or r.get("file_name") or ""
            src = r.get("source_type") or ""
            url = r.get("source_url") or ""
            chunk_info = ""
            if r.get("chunk_index") and r.get("total_chunks"):
                chunk_info = f" chunk {r['chunk_index']}/{r['total_chunks']}"
            print(f"--- Result {i} (score={r.get('score'):.4f}{chunk_info}) ---")
            print(f"  [{src}] {title}")
            if url:
                print(f"  {url}")
            print(r.get("content", ""))
            print(f"  [doc_type={r.get('doc_type')} creator_id={r.get('creator_id')}]")
    else:
        print(json.dumps(envelope, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
