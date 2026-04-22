#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hub / CLI bridge: call Superteam MCP agentic_data tools (read-only).

Business/product data only (campaigns, advertisers, badges, providers, in-app quests, etc.).
Not for Linear issues, engineering sprint/task tracking, or DingTalk sheet iteration sync.

Uses the same HTTP MCP client as skills/_shared/db.py (SUPERTEAM_MCP_URL + token).

Without --tool, picks a tool from lightweight keyword heuristics on the query string.
For precise calls, pass --tool and optional --json-args.

Usage:
    python query_agentic_data.py "Last Odyssey 广告主"
    python query_agentic_data.py --tool list_advertiser --name "Last Odyssey"
    python query_agentic_data.py --tool list_anchor_series --chain-id 1962
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_SHARED = Path(__file__).resolve().parent.parent.parent / "_shared"
sys.path.insert(0, str(_SHARED))

from db import McpError, _mcp_call  # noqa: E402


def mcp_call_tool(tool_name: str, arguments: dict | None = None):
    """Call a Superteam MCP tool by name (HTTP JSON-RPC). Hub / superteam-data CLI bridge."""
    return _mcp_call(tool_name, arguments or {})


def _strip_noise(text: str, noise: list[str]) -> str:
    t = text
    for w in noise:
        t = t.replace(w, " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _quoted_phrase(q: str) -> str | None:
    m = re.search(r'[""「](.+?)[""」]', q)
    if m:
        return m.group(1).strip()
    return None


def _plan_from_query(query: str) -> tuple[str, dict]:
    """Best-effort NL -> (tool, args). Defaults to list_projects."""
    q = query.strip()
    ql = q.lower()

    noise_adv = [
        "查询", "查一下", "查", "帮我", "请", "的", "有哪些", "什么",
        "广告主", "项目方", "advertiser",
    ]
    noise_prov = [
        "查询", "查一下", "查", "帮我", "请", "的", "有哪些",
        "供应商", "provider", "zktls",
    ]

    if "供应商" in q or "provider" in ql or "zktls" in ql:
        sub = _strip_noise(q, noise_prov)
        return "search_providers", {"query": sub or q, "limit": 10}

    if "广告主" in q or "项目方" in q or "advertiser" in ql:
        phrase = _quoted_phrase(q)
        if phrase:
            return "list_advertiser", {"name": phrase, "page": 1, "size": 50}
        sub = _strip_noise(q, noise_adv)
        if sub and len(sub) >= 2:
            return "list_advertiser", {"name": sub, "page": 1, "size": 50}
        return "list_advertiser", {"page": 1, "size": 100}

    if "活动" in q or "campaign" in ql:
        return "list_campaigns", {"page": 1, "size": 20}

    if "series" in ql or "系列" in q or "badge" in ql or "anchor" in ql:
        m = re.search(r"\b(\d{3,6})\b", q)
        if m:
            return "list_anchor_series", {
                "chainId": m.group(1),
                "pageNum": 1,
                "pageSize": 100,
            }

    if ("项目" in q and ("列表" in q or "哪些" in q)) or "list project" in ql:
        return "list_projects", {}

    return "list_projects", {}


def main() -> int:
    p = argparse.ArgumentParser(description="Call agentic_data via Superteam MCP")
    p.add_argument("query", nargs="?", default="", help="Natural language query (from Hub)")
    p.add_argument("--tool", help="MCP tool name (e.g. list_advertiser)")
    p.add_argument(
        "--json-args",
        default="{}",
        help='JSON object merged into tool arguments when --tool is set (default "{}")',
    )
    p.add_argument("--name", help="Shorthand for list_advertiser name filter")
    p.add_argument("--chain-id", dest="chain_id", help="Shorthand for list_anchor_series chainId")
    args = p.parse_args()

    if not args.tool:
        tool, params = _plan_from_query(args.query or "")
    else:
        try:
            extra = json.loads(args.json_args)
            if not isinstance(extra, dict):
                raise ValueError("json-args must be an object")
        except (json.JSONDecodeError, ValueError) as e:
            print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2))
            return 1
        tool = args.tool
        params = dict(extra)
        if args.name:
            params.setdefault("name", args.name)
        if args.chain_id:
            params.setdefault("chainId", str(args.chain_id))

    # Drop None values so MCP gets omitted optional fields
    params = {k: v for k, v in params.items() if v is not None}

    try:
        out = mcp_call_tool(tool, params)
        envelope = {
            "skill": "superteam-data",
            "tool": tool,
            "arguments": params,
            "result": out,
        }
        print(json.dumps(envelope, ensure_ascii=False, indent=2))
        return 0
    except McpError as e:
        print(json.dumps({
            "skill": "superteam-data",
            "tool": tool,
            "arguments": params,
            "error": str(e),
            "code": getattr(e, "code", "mcp_error"),
        }, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
