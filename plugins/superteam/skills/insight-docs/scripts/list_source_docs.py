#!/usr/bin/env python3
"""查询 kb_trex_source_docs，列出已同步的源文档及状态，输出 JSON。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from scripts/ dir without installing package
_SHARED_DIR = Path(__file__).parent.parent.parent / "_shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))

from config import env  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="List synced source documents from kb_trex_source_docs.")
    parser.add_argument("--source-type", default="", help="Filter by source_type (dingtalk, google_drive, etc.).")
    parser.add_argument("--name", default="", help="Fuzzy match on file_name.")
    parser.add_argument("--limit", type=int, default=50, help="Max rows (default 50).")
    args = parser.parse_args()

    conn_url = env("KB_TREX_PG_URL")
    if not conn_url:
        print("KB_TREX_PG_URL not set.", file=sys.stderr)
        return 1

    import psycopg2
    conn = psycopg2.connect(conn_url)
    cur = conn.cursor()
    cur.execute("SET search_path TO trex_hub, public")

    where_parts: list[str] = []
    params: list = []
    if args.source_type:
        where_parts.append("source_type = %s")
        params.append(args.source_type)
    if args.name:
        where_parts.append("file_name ILIKE %s")
        params.append(f"%{args.name}%")

    where_clause = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
    params.append(args.limit)
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
    conn.close()

    for row in rows:
        for k in ("last_edited_at", "last_synced_at"):
            if row.get(k):
                row[k] = str(row[k])

    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
