#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""superteam router — 意图识别 + 分发到对应 skill 脚本。

基于关键词的轻量路由，零 LLM 依赖。同一查询可命中**多条**路由（凡有关键词命中即纳入，按分数降序）。

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
    arg_extractor: str | None = None  # "doc_name" = extract document name from query


ROUTES: list[Route] = [
    Route(
        skill="superteam-git",
        script="superteam-git/scripts/query_git.py",
        keywords=[
            "提交代码", "提交", "commit", "git commit",
            "推送代码", "推送", "push", "git push",
            "git status", "git diff", "代码提交",
            "提交信息", "commit message", "提测", "merge 到 review",
        ],
        description="本地 Git 洞察与提交流程",
        status="live",
        pass_query=True,
    ),
    Route(
        skill="superteam-data",
        script="superteam-data/scripts/query_agentic_data.py",
        keywords=[
            # Product/agentic data domain (primary).
            "广告主", "项目方", "活动", "campaign", "投放", "增长", "拉新", "邀请",
            "provider", "供应商", "zktls", "quest", "alpha", "白名单",
            "badge", "anchor", "series", "系列", "链", "chain", "claim", "可领取",
            "reward", "奖励", "persona", "人群", "multiplier", "倍率",
            "project", "项目配置", "全局配置", "global config",
        ],
        description="业务数据查询 (Superteam MCP agentic_data)",
        status="live",
        pass_query=True,
    ),
    Route(
        skill="superteam-linear",
        script="superteam-linear/scripts/query_linear.py",
        keywords=[
            "迭代", "任务", "进度", "成员贡献", "bug", "缺陷",
            "story point", "sprint", "iteration", "task",
            "做了哪些", "负责什么任务", "工作量", "完成率",
            "linear", "issue", "工单", "backlog", "cycle",
        ],
        description="Linear 工单/迭代 (MCP HTTP)",
        pass_query=True,
    ),
    Route(
        skill="superteam-report-team",
        script="superteam-report-team/scripts/generate_team_weekly_report.py",
        keywords=[
            "团队周报", "团队 周报", "迭代周报", "团队迭代周报",
            "team weekly", "team report", "cycle report",
        ],
        description="团队迭代周报（Linear Cycle）",
        status="live",
        pass_query=False,
    ),
    Route(
        skill="superteam-report",
        script="superteam-report/scripts/generate_report.py",
        keywords=[
            "周报", "weekly", "report", "本周", "上周",
            "工作总结", "工作汇报",
        ],
        description="周报生成",
        status="live",
        pass_query=True,
    ),
    Route(
        skill="superteam-member",
        script="superteam-member/scripts/list_members.py",
        keywords=[
            "成员", "团队成员", "谁是", "有哪些人", "角色",
            "负责人", "开发人员", "前端", "后端", "测试",
            "产品", "设计师", "member", "team",
        ],
        description="团队成员查询",
        pass_query=False,
    ),
    Route(
        skill="superteam-knowledgebase",
        script="superteam-knowledgebase/scripts/list_source_docs.py",
        keywords=[
            "文档列表", "已同步", "同步状态", "有哪些文档",
            "文档数量", "source docs", "synced",
        ],
        description="已同步文档列表查询",
        pass_query=False,
    ),
    # Get single document by name — direct retrieval
    Route(
        skill="superteam-knowledgebase",
        script="superteam-knowledgebase/scripts/get_doc.py",
        keywords=[
            "获取文档", "查看文档", "打开文档", "读取文档",
            "文档内容", "给我看", "输出文档", "显示文档",
            "get doc", "read doc", "show doc", "fetch doc",
            ".adoc", ".md 的", ".pdf 的", ".docx",
        ],
        description="按文档名获取完整内容",
        status="live",
        pass_query=False,
        arg_extractor="doc_name",
    ),
    # Deep research mode — fetch full original documents
    Route(
        skill="superteam-knowledgebase",
        script="superteam-knowledgebase/scripts/deep_search.py",
        keywords=[
            "深入研究", "深入分析", "详细分析", "原文", "全文",
            "文档创作", "写文档", "写报告", "起草", "撰写",
            "deep", "research", "full text", "original",
            "完整内容", "完整的", "文档全文", "引用原文",
            "完整文档", "完整技术", "整个文档", "全部内容",
        ],
        description="深度搜索 — 获取原始文档全文 (研究/创作模式)",
        status="live",
    ),
    # Default fallback — superteam-knowledgebase (semantic search)
    Route(
        skill="superteam-knowledgebase",
        script="superteam-knowledgebase/scripts/search_docs.py",
        keywords=[],  # empty = catch-all
        description="语义搜索 (RAG)",
        status="live",
    ),
]


# ---------------------------------------------------------------------------
# Router logic
# ---------------------------------------------------------------------------
def classify_intents(query: str) -> list[tuple[Route, int]]:
    """Return all routes with at least one keyword hit, sorted by score desc.

    Ties preserve declaration order in ROUTES (stable index).
    If nothing matches, returns the catch-all route (last entry) with score 0.
    """
    query_lower = query.lower()
    scored: list[tuple[int, int, Route]] = []
    for i, route in enumerate(ROUTES):
        if not route.keywords:
            continue
        score = sum(1 for kw in route.keywords if kw in query_lower)
        if score > 0:
            scored.append((score, i, route))

    if not scored:
        return [(ROUTES[-1], 0)]

    # Sort by score desc, then declaration order asc
    scored.sort(key=lambda t: (-t[0], t[1]))

    # If best match is not ready, keep legacy behavior: fall back to search_docs only
    best = scored[0][2]
    if best.status in ("skeleton", "placeholder"):
        print(
            f"  [superteam] {best.skill} is {best.status}, falling back to search_docs",
            file=sys.stderr,
        )
        return [(ROUTES[-1], 0)]

    # Multi-route: include all live matches with existing scripts.
    # This prevents dispatching to routes that are configured but not packaged.
    out: list[tuple[Route, int]] = []
    for (s, _i, r) in scored:
        if r.status != "live":
            continue
        if not (SKILLS_ROOT / r.script).exists():
            continue
        out.append((r, s))
    return out or [(ROUTES[-1], 0)]


def build_result(query: str, scored_routes: list[tuple[Route, int]]) -> dict:
    """Build structured routing result (multi-route)."""
    routes_out: list[dict] = []
    for route, score in scored_routes:
        script_path = SKILLS_ROOT / route.script
        routes_out.append({
            "skill": route.skill,
            "script": route.script,
            "script_exists": script_path.exists(),
            "description": route.description,
            "status": route.status,
            "score": score,
        })

    primary = scored_routes[0][0]
    primary_path = SKILLS_ROOT / primary.script
    return {
        "query": query,
        "routes": routes_out,
        "route_count": len(routes_out),
        # backward compat — first route
        "skill": primary.skill,
        "script": primary.script,
        "script_exists": primary_path.exists(),
        "description": primary.description,
        "status": primary.status,
    }


def _extract_doc_name(query: str) -> str | None:
    """Extract a document name from the query string."""
    quoted = re.findall(r'[""「](.+?)[""」]', query)
    if quoted:
        return quoted[0].strip()

    ext_match = re.search(r'(?:^|\s)([\w\u4e00-\u9fff][\w\u4e00-\u9fff.\-]*\.(adoc|md|pdf|docx?))', query)
    if ext_match:
        return ext_match.group(1).strip()

    noise_words = [
        "获取文档", "查看文档", "打开文档", "读取文档", "输出文档", "显示文档",
        "给我看", "文档内容", "get doc", "read doc", "show doc", "fetch doc",
        "完整内容", "完整的", "全文", "原文", "内容",
        "的", "这个", "那个", "文档", "这篇", "那篇",
        "请", "帮我", "我要", "给我", "看下", "看一下",
    ]
    cleaned = query
    for w in noise_words:
        cleaned = cleaned.replace(w, " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned and len(cleaned) >= 2:
        return cleaned
    return None


def _run_one(query: str, route: Route) -> subprocess.CompletedProcess:
    script_path = SKILLS_ROOT / route.script
    cmd = [sys.executable, str(script_path)]
    if route.arg_extractor == "doc_name":
        doc_name = _extract_doc_name(query)
        if doc_name:
            cmd.extend(["--name", doc_name])
        else:
            payload = {
                "error": "无法从查询中提取文档名，请用引号指定文档名",
                "hint": '示例: 获取文档 "Campaign领奖技术方案"',
                "query": query,
            }
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout=json.dumps(payload, ensure_ascii=False, indent=2),
                stderr="",
            )
    elif route.pass_query:
        cmd.append(query)
    return subprocess.run(cmd, capture_output=True, text=True)


def execute_routes(query: str, scored_routes: list[tuple[Route, int]]) -> int:
    """Run matched routes. Single route: inherit stdout/stderr; multi: JSON envelope."""
    if len(scored_routes) == 1:
        route = scored_routes[0][0]
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

    # Multiple routes: capture each, emit one JSON
    executions: list[dict] = []
    any_fail = False
    for route, score in scored_routes:
        script_path = SKILLS_ROOT / route.script
        if not script_path.exists():
            executions.append({
                "skill": route.skill,
                "script": route.script,
                "exit_code": 1,
                "error": "script not found",
            })
            any_fail = True
            continue

        if route.status == "placeholder":
            executions.append({
                "skill": route.skill,
                "script": route.script,
                "exit_code": 0,
                "stdout": json.dumps({
                    "skill": route.skill,
                    "message": "功能开发中",
                    "status": "placeholder",
                }, ensure_ascii=False),
                "stderr": "",
            })
            continue

        cmd = [sys.executable, str(script_path)]
        if route.pass_query:
            cmd.append(query)

        print(f"🔀 routing to {route.skill}: {' '.join(cmd)}", file=sys.stderr)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            any_fail = True
        executions.append({
            "skill": route.skill,
            "script": route.script,
            "score": score,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        })

    print(json.dumps({
        "query": query,
        "route_count": len(scored_routes),
        "executions": executions,
    }, ensure_ascii=False, indent=2))
    return 1 if any_fail else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="superteam router — intent classification + skill dispatch"
    )
    parser.add_argument(
        "--query", "-q", required=True,
        help="User's natural language query"
    )
    parser.add_argument(
        "--execute", "-x", action="store_true",
        help="Execute matched skill script(s) (default: just classify)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON (default for classify mode)"
    )
    args = parser.parse_args()

    scored = classify_intents(args.query)

    if args.execute:
        sys.exit(execute_routes(args.query, scored))
    else:
        result = build_result(args.query, scored)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
