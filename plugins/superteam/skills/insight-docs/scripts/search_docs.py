#!/usr/bin/env python3
"""
团队文档向量检索：自然语言问题 → 1536 维向量 → pgvector 相似度搜索 → 输出 JSON。
依赖：KB_TREX_PG_URL；DASHSCOPE_API_KEY 或 OPENAI_API_KEY。
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
from embedding import get_embedding
from queries import query_search_docs


def main() -> int:
    parser = argparse.ArgumentParser(description="Vector search over kb_trex_team_docs.")
    parser.add_argument("query", help="Natural language question or search phrase.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--doc-type", choices=[
        "prd", "tech-design", "reference", "guide", "explanation",
        "decision", "meeting-notes", "weekly-report", "plan",
        "changelog", "other",
    ])
    parser.add_argument("--creator-id", type=int)
    parser.add_argument("--output-format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    from db import _use_mcp, search_docs

    if _use_mcp():
        # MCP mode: server handles embedding + search
        try:
            rows = search_docs(args.query, creator_id=args.creator_id, limit=args.top_k)
        except Exception as e:
            print(f"MCP search failed: {e}", file=sys.stderr)
            return 1
    else:
        # Direct mode: local embedding + psycopg2
        conn_url = env("KB_TREX_PG_URL")
        if not conn_url:
            print("KB_TREX_PG_URL not set.", file=sys.stderr)
            return 1

        try:
            embedding = get_embedding(args.query)
        except Exception as e:
            print(f"Embedding failed: {e}", file=sys.stderr)
            return 1
        if len(embedding) != 1536:
            print(f"Embedding dim {len(embedding)} != 1536", file=sys.stderr)
            return 1

        import psycopg2
        conn = psycopg2.connect(conn_url)
        cur = conn.cursor()
        cur.execute("SET search_path TO trex_hub, public")
        conn.commit()

        try:
            rows = query_search_docs(conn, embedding, args.top_k, args.doc_type, args.creator_id)
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
