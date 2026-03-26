#!/usr/bin/env python3
"""查询 kb_trex_source_docs，列出已同步的源文档及状态，输出 JSON。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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

    from db import get_connection
    from queries import query_list_source_docs

    conn = get_connection()
    try:
        rows = query_list_source_docs(
            conn,
            source_type=args.source_type or None,
            name=args.name or None,
            limit=args.limit,
        )
    finally:
        conn.close()

    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
