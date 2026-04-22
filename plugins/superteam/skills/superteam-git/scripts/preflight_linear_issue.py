#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""创建 Linear 任务前的重复风险预检（供 superteam-git 提交流程使用）。

侧重：**拟创建标题是否与「已有」issue（含进行中/历史）过于相似**，避免误建新单。
若问题是「同一轮流程里 save_issue 被调两次导致两条一模一样的新单」，请用
`save_linear_issue_once.py`（短时去重），而不是仅靠本脚本。

拉取 assignee=me 的 issues，在本地与拟创建标题做相似度匹配，输出单一 JSON（stdout），
便于 Agent 解析；不因 MCP 日志混入 stdout 而失败（见 query_linear_stdout_json.extract_insight_linear_payload）。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from query_linear_stdout_json import extract_insight_linear_payload

_SKILLS_ROOT = Path(__file__).resolve().parent.parent.parent
_QUERY_LINEAR = _SKILLS_ROOT / "superteam-linear" / "scripts" / "query_linear.py"

_CLOSED_STATUSES = frozenset(
    s.lower()
    for s in (
        "Done",
        "Canceled",
        "Cancelled",
        "已完成",
        "已关闭",
        "取消",
    )
)


def normalize_title(s: str) -> str:
    t = (s or "").lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t


def title_match_level(proposed: str, existing: str) -> str:
    """返回 exact | strong | weak | 空。"""
    a, b = normalize_title(proposed), normalize_title(existing)
    if not a or not b:
        return ""
    if a == b:
        return "exact"
    min_len = 8
    if len(a) >= min_len and a in b:
        return "strong"
    if len(b) >= min_len and b in a:
        return "strong"
    ta = {x for x in re.split(r"[^\w\u4e00-\u9fff]+", a) if len(x) > 1}
    tb = {x for x in re.split(r"[^\w\u4e00-\u9fff]+", b) if len(x) > 1}
    if not ta or not tb:
        return ""
    inter = len(ta & tb)
    if inter == 0:
        return ""
    jacc = inter / len(ta | tb)
    if jacc >= 0.55:
        return "strong"
    if jacc >= 0.35:
        return "weak"
    return ""


def _is_closed_issue(issue: dict[str, Any]) -> bool:
    st = str(issue.get("status") or "").strip().lower()
    return st in _CLOSED_STATUSES or any(c in st for c in ("done", "cancel", "complete", "closed"))


def analyze_duplicate_risk(
    proposed_title: str,
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    open_hits: list[dict[str, Any]] = []
    closed_hits: list[dict[str, Any]] = []

    for issue in issues:
        iid = str(issue.get("id") or "").strip()
        title = str(issue.get("title") or "").strip()
        if not iid or not title:
            continue
        level = title_match_level(proposed_title, title)
        if not level:
            continue
        row = {
            "id": iid,
            "title": title,
            "status": str(issue.get("status") or ""),
            "url": str(issue.get("url") or ""),
            "match_level": level,
        }
        if _is_closed_issue(issue):
            closed_hits.append(row)
        else:
            open_hits.append(row)

    # 优先展示 exact/strong
    def _sort_key(h: dict[str, Any]) -> tuple[int, str]:
        lv = h.get("match_level", "")
        pri = 0 if lv == "exact" else 1 if lv == "strong" else 2
        return pri, h.get("id", "")

    open_hits.sort(key=_sort_key)
    closed_hits.sort(key=_sort_key)

    if open_hits:
        top = open_hits[0]
        if top.get("match_level") == "exact":
            risk = "high"
            recommendation = "link_existing"
        elif top.get("match_level") == "strong":
            risk = "medium"
            recommendation = "link_existing"
        else:
            risk = "low"
            recommendation = "confirm_or_link"
    else:
        risk = "none"
        recommendation = "ok_to_create"

    return {
        "proposed_title": proposed_title,
        "risk": risk,
        "recommendation": recommendation,
        "open_matches": open_hits[:12],
        "closed_matches": closed_hits[:8],
        "policy": {
            "block_save_issue_without_user_confirm": risk in ("high", "medium"),
            "must_offer_existing_in_ask_question": bool(open_hits),
        },
    }


def _fetch_my_issues(first: int, assignee: str) -> list[dict[str, Any]]:
    if not _QUERY_LINEAR.is_file():
        return []
    args_json = json.dumps(
        {"assignee": assignee, "includeArchived": False, "first": first},
        ensure_ascii=False,
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(_QUERY_LINEAR),
            "--tool",
            "list_issues",
            "--args-json",
            args_json,
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    raw = (proc.stdout or "") + "\n" + (proc.stderr or "")
    payload = extract_insight_linear_payload(raw)
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        return []
    issues = result.get("issues")
    if not isinstance(issues, list):
        return []
    out: list[dict[str, Any]] = []
    for item in issues:
        if isinstance(item, dict):
            out.append(item)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight: duplicate Linear issue risk for a new title.")
    parser.add_argument("--title", required=True, help="拟创建的 issue 标题")
    parser.add_argument("--assignee", default="me", help="list_issues assignee（默认 me）")
    parser.add_argument("--first", type=int, default=80, help="拉取最近 N 条我的任务做比对")
    args = parser.parse_args()

    issues = _fetch_my_issues(first=args.first, assignee=args.assignee)
    report = analyze_duplicate_risk(args.title, issues)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
