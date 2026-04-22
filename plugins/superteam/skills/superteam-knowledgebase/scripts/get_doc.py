#!/usr/bin/env python3
"""Retrieve full document content by name or source_doc_id.

For cases where the user already knows which document they want.
Calls get_source_doc_content (MCP or direct) to return original text.

Usage:
    python get_doc.py --name "Campaign领奖v1.0"
    python get_doc.py --id 9
    python get_doc.py --name "Campaign 领奖技术方案" --output-format text
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent / "_shared"))
from db import get_source_doc_content


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Get full document content by name or source_doc_id."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--name", help="Document file_name (fuzzy match)")
    group.add_argument("--id", type=int, dest="doc_id",
                       help="Source document ID (exact match)")
    parser.add_argument("--output-format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    try:
        result = get_source_doc_content(
            source_doc_id=args.doc_id,
            file_name=args.name,
        )
    except Exception as e:
        print(f"Failed to retrieve document: {e}", file=sys.stderr)
        return 1

    if not result or not result.get("content"):
        target = f"id={args.doc_id}" if args.doc_id else f"name={args.name}"
        print(json.dumps({
            "error": f"Document not found or content unavailable: {target}",
        }, ensure_ascii=False, indent=2))
        return 1

    if args.output_format == "text":
        print(f"📄 {result['file_name']}")
        print(f"   Source: {result.get('source_type', 'unknown')}")
        if result.get("source_url"):
            print(f"   URL: {result['source_url']}")
        print(f"   Length: {len(result['content'])} chars")
        print("=" * 60)
        print(result["content"])
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
