#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hub router — 意图识别 + 分发到对应 skill 脚本。

基于关键词的轻量路由，零 LLM 依赖。

Usage:
    python route.py --query "PRD 里提到了什么功能"
    python route.py --query "迭代25进度如何"
    python route.py --query "帮我生成本周周报"
    python route.py --query "张三做了哪些任务" --execute
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parent.parent.parent  # skills/


# ---------------------------------------------------------------------------
# Route definitions
# ---------------------------------------------------------------------------
@dataclass
class Route:
    """A routing rule: keywords → skill + script."""
    skill: str
    script: str  # relative to SKILLS_ROOT
    keywords: list[str] = field(default_factory=list)
    description: str = ""
    status: str = "live"  # live | skeleton | placeholder
    pass_query: bool = True  # pass raw query as positional arg


ROUTES: list[Route] = [
    Route(
        skill="insight-data",
        script="insight-data/scripts/query_tasks.py",
        keywords=[
            "迭代", "任务", "进度", "成员贡献", "bug", "缺陷",
            "story point", "sprint", "iteration", "task",
            "做了哪些", "负责什么任务", "工作量", "完成率",
        ],
        description="任务/迭代数据查询 (AGE + SQL)",
        status="skeleton",
        pass_query=False,
    ),
    Route(
        skill="weekly-report",
        script="weekly-report/scripts/generate_report.py",
        keywords=[
            "周报", "weekly", "report", "本周", "上周",
            "工作总结", "工作汇报",
        ],
        description="周报生成",
        status="skeleton",
        pass_query=False,
    ),
    Route(
        skill="insight-docs",
        script="insight-docs/scripts/list_members.py",
        keywords=[
            "成员", "团队成员", "谁是", "有哪些人", "角色",
            "负责人", "开发人员", "前端", "后端", "测试",
            "产品", "设计师", "member", "team",
        ],
        description="团队成员查询",
        pass_query=False,
    ),
    Route(
        skill="insight-docs",
        script="insight-docs/scripts/list_source_docs.py",
        keywords=[
            "文档列表", "已同步", "同步状态", "有哪些文档",
            "文档数量", "source docs", "synced",
        ],
        description="已同步文档列表查询",
        pass_query=False,
    ),
    # Default fallback — insight-docs (semantic search)
    Route(
        skill="insight-docs",
        script="insight-docs/scripts/search_docs.py",
        keywords=[],  # empty = catch-all
        description="语义搜索 (RAG)",
        status="live",
    ),
]


# ---------------------------------------------------------------------------
# Router logic
# ---------------------------------------------------------------------------
def classify_intent(query: str) -> Route:
    """Match query against keyword routes. Returns best-matching Route."""
    query_lower = query.lower()

    best_route: Route | None = None
    best_score = 0

    for route in ROUTES:
        if not route.keywords:
            continue  # skip catch-all in scoring
        score = sum(1 for kw in route.keywords if kw in query_lower)
        if score > best_score:
            best_score = score
            best_route = route

    # If no keyword matched, fall back to insight-docs (last route)
    if best_score == 0 or best_route is None:
        best_route = ROUTES[-1]

    return best_route


def build_result(query: str, route: Route) -> dict:
    """Build structured routing result."""
    script_path = SKILLS_ROOT / route.script
    return {
        "query": query,
        "skill": route.skill,
        "script": route.script,
        "script_exists": script_path.exists(),
        "description": route.description,
        "status": route.status,
    }


def execute_route(query: str, route: Route) -> int:
    """Execute the target skill script with the query."""
    script_path = SKILLS_ROOT / route.script

    if not script_path.exists():
        print(json.dumps({
            "error": f"script not found: {route.script}",
            "skill": route.skill,
            "status": route.status,
        }, ensure_ascii=False, indent=2))
        return 1

    if route.status == "placeholder":
        print(json.dumps({
            "skill": route.skill,
            "message": "功能开发中",
            "status": "placeholder",
        }, ensure_ascii=False, indent=2))
        return 0

    cmd = [sys.executable, str(script_path)]
    if route.pass_query:
        cmd.append(query)

    print(f"🔀 routing to {route.skill}: {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd)
    return result.returncode


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="hub router — intent classification + skill dispatch"
    )
    parser.add_argument(
        "--query", "-q", required=True,
        help="User's natural language query"
    )
    parser.add_argument(
        "--execute", "-x", action="store_true",
        help="Execute the matched skill script (default: just classify)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON (default for classify mode)"
    )
    args = parser.parse_args()

    route = classify_intent(args.query)

    if args.execute:
        sys.exit(execute_route(args.query, route))
    else:
        result = build_result(args.query, route)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
