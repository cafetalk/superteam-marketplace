#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Poll recent purchases API and persist deduplicated records."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

DEFAULT_URL = "https://baolem.com/api/membership/recent-purchases"


def _record_key(item: dict[str, Any]) -> str:
    """Build a stable dedupe key for one purchase row."""
    return "|".join(
        [
            str(item.get("loginCode", "")),
            str(item.get("usedAt", "")),
            str(item.get("membershipName", "")),
            str(item.get("actionText", "")),
        ]
    )


def _load_seen_keys(output_file: Path) -> set[str]:
    """Load existing keys from output file, safe for malformed lines."""
    seen: set[str] = set()
    if not output_file.exists():
        return seen

    with output_file.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                key = _record_key(row)
                if key:
                    seen.add(key)
    return seen


def _fetch_with_curl(url: str, timeout_sec: int) -> dict[str, Any]:
    cmd = [
        "curl",
        "-sS",
        "--max-time",
        str(timeout_sec),
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"curl failed: {proc.stderr.strip() or 'unknown error'}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid json from api: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("invalid payload: top-level JSON must be object")
    return payload


def _append_new_rows(
    output_file: Path,
    rows: list[dict[str, Any]],
    seen: set[str],
) -> int:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    inserted = 0
    with output_file.open("a", encoding="utf-8") as f:
        for row in rows:
            key = _record_key(row)
            if not key or key in seen:
                continue
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            seen.add(key)
            inserted += 1
    return inserted


def _poll_once(url: str, output_file: Path, timeout_sec: int, seen: set[str]) -> int:
    payload = _fetch_with_curl(url, timeout_sec)
    if payload.get("success") is not True:
        raise RuntimeError(f"api success=false, payload={payload}")

    data = payload.get("data")
    if not isinstance(data, list):
        raise RuntimeError("api payload missing data list")

    rows = [item for item in data if isinstance(item, dict)]
    return _append_new_rows(output_file, rows, seen)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="每隔固定时间拉取 recent-purchases，并去重落盘"
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"请求地址（默认：{DEFAULT_URL}）",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="轮询间隔秒数（默认 300 秒）",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="curl 超时秒数（默认 20）",
    )
    parser.add_argument(
        "--output",
        default="data/recent_purchases.jsonl",
        help="输出文件（jsonl，每行一条记录）",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="只执行一次，不循环",
    )
    args = parser.parse_args()

    output_file = Path(args.output).expanduser().resolve()
    seen = _load_seen_keys(output_file)
    print(f"[init] loaded {len(seen)} existing records from {output_file}")

    while True:
        try:
            inserted = _poll_once(args.url, output_file, args.timeout, seen)
            print(f"[ok] inserted={inserted}, total_seen={len(seen)}")
        except Exception as exc:  # keep running on transient errors
            print(f"[error] {exc}", file=sys.stderr)

        if args.once:
            break
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    main()
