#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""superteam-report generator v2.

v2 目标：
1) 支持本周/上周时间窗口（周一到周日）
2) 聚合 superteam-linear 任务信息（上周完成/进行中）
3) 聚合 superteam-git 代码改动分析（上周做了什么）
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import socket
import subprocess
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

SKILLS_ROOT = Path(__file__).resolve().parent.parent.parent
_SHARED = str(SKILLS_ROOT / "_shared")
if _SHARED not in sys.path:
    sys.path.insert(0, _SHARED)
from config import env  # type: ignore

REPORT_ROOT_FOLDER_URL = "https://alidocs.dingtalk.com/i/nodes/ZgpG2NdyVXrr9A0bCAkYARkl8MwvDqPk?utm_scene=team_space"
REPORT_ROOT_FOLDER_ID = "ZgpG2NdyVXrr9A0bCAkYARkl8MwvDqPk"


def _safe_json_from_stdout(text: str) -> dict[str, Any]:
    """Extract last JSON object from mixed stdout logs."""
    text = text.strip()
    for idx in range(len(text) - 1, -1, -1):
        if text[idx] == "{":
            candidate = text[idx:]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return {}


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _resolve_week_mode(query: str, week_arg: str | None) -> str:
    if week_arg in ("this", "last"):
        return week_arg
    q = (query or "").lower()
    if "本周" in q or "this week" in q:
        return "this"
    if "上周" in q or "last week" in q:
        return "last"
    # /superteam-report 默认生成上周
    return "last"


def _week_range(week_mode: str) -> tuple[date, date]:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    if week_mode == "last":
        monday = monday - timedelta(days=7)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _in_range(dt: datetime | None, start: datetime, end: datetime) -> bool:
    if dt is None:
        return False
    return start <= dt <= end


def _run_script(script_rel: str, args: list[str]) -> dict[str, Any]:
    script = SKILLS_ROOT / script_rel
    cmd = [sys.executable, str(script)] + args
    proc = subprocess.run(cmd, capture_output=True, text=True)
    payload = _safe_json_from_stdout(proc.stdout)
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "payload": payload,
        "cmd": cmd,
    }


def _extract_linear_issues(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = (payload.get("result", {}) or {})
    issues = result.get("issues", [])
    if isinstance(issues, list):
        return issues
    return []


def _extract_member_name(issue: dict[str, Any]) -> str:
    assignee = issue.get("assignee")
    if isinstance(assignee, str) and assignee.strip():
        return assignee.strip()
    if isinstance(assignee, dict):
        for key in ("displayName", "name", "fullName"):
            value = assignee.get(key)
            if value:
                return str(value)
    for key in ("assigneeName", "assigneeDisplayName", "creatorName"):
        value = issue.get(key)
        if value:
            return str(value)
    return ""


def _extract_cycle_info(issue: dict[str, Any]) -> dict[str, str]:
    cycle = issue.get("cycle")
    if isinstance(cycle, dict):
        return {
            "id": str(cycle.get("id") or ""),
            "name": str(cycle.get("name") or ""),
            "number": str(cycle.get("number") or ""),
            "startsAt": str(cycle.get("startsAt") or ""),
            "endsAt": str(cycle.get("endsAt") or ""),
        }
    return {
        "id": str(issue.get("cycleId") or ""),
        "name": str(issue.get("cycleName") or ""),
        "number": str(issue.get("cycleNumber") or ""),
        "startsAt": str(issue.get("cycleStartsAt") or ""),
        "endsAt": str(issue.get("cycleEndsAt") or ""),
    }


def _extract_linear_page_info(payload: dict[str, Any]) -> dict[str, Any]:
    result = (payload.get("result", {}) or {})
    page_info = result.get("pageInfo", {})
    if isinstance(page_info, dict):
        return page_info
    # 兼容某些返回结构
    issues = result.get("issues")
    if isinstance(issues, dict):
        nested = issues.get("pageInfo", {})
        if isinstance(nested, dict):
            return nested
    return {}


def _build_cycle_lookup(issues: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Resolve cycle id -> display fields (name/number/date) via list_cycles."""
    team_ids: set[str] = set()
    for issue in issues:
        tid = str(issue.get("teamId") or "").strip()
        if tid:
            team_ids.add(tid)

    cycle_lookup: dict[str, dict[str, str]] = {}
    for team_id in sorted(team_ids):
        for cycle_type in ("current", "previous", "next"):
            args = [
                "--tool",
                "list_cycles",
                "--args-json",
                json.dumps({"teamId": team_id, "type": cycle_type}, ensure_ascii=False),
            ]
            resp = _run_script("superteam-linear/scripts/query_linear.py", args)
            payload = resp.get("payload", {}) or {}
            rows = payload.get("result", [])
            if not isinstance(rows, list):
                continue
            for cy in rows:
                if not isinstance(cy, dict):
                    continue
                cid = str(cy.get("id") or "").strip()
                if not cid:
                    continue
                name = str(cy.get("name") or "").strip()
                num = str(cy.get("number") or "").strip()
                if not name and num:
                    name = f"Cycle {num}"
                cycle_lookup[cid] = {
                    "id": cid,
                    "name": name,
                    "number": num,
                    "startsAt": str(cy.get("startsAt") or ""),
                    "endsAt": str(cy.get("endsAt") or ""),
                }
    return cycle_lookup


def _collect_linear(member: str, start: datetime, end: datetime, first: int) -> dict[str, Any]:
    args = [
        "--tool", "list_issues",
        "--args-json", json.dumps({"assignee": member, "first": first}, ensure_ascii=False),
    ]
    result = _run_script("superteam-linear/scripts/query_linear.py", args)
    payload = result.get("payload", {}) or {}
    issues = _extract_linear_issues(payload)
    page_info = _extract_linear_page_info(payload)
    cycle_lookup = _build_cycle_lookup(issues)

    completed: list[dict[str, Any]] = []
    in_progress: list[dict[str, Any]] = []
    todo: list[dict[str, Any]] = []
    tasks_in_window: list[dict[str, Any]] = []
    candidate_names: list[str] = []
    cycle_counter: dict[str, int] = {}
    cycle_ranges: dict[str, dict[str, str]] = {}

    for issue in issues:
        member_name = _extract_member_name(issue)
        if member_name:
            candidate_names.append(member_name)
        created_at = _parse_dt(issue.get("createdAt"))
        updated_at = _parse_dt(issue.get("updatedAt"))
        completed_at = _parse_dt(issue.get("completedAt"))
        started_at = _parse_dt(issue.get("startedAt"))
        status_text = str(issue.get("status") or "")
        status_text_lower = status_text.lower()

        touched = (
            _in_range(created_at, start, end)
            or _in_range(updated_at, start, end)
            or _in_range(completed_at, start, end)
        )
        row = {
            "id": issue.get("id"),
            "identifier": str(issue.get("identifier") or "").strip(),
            "title": issue.get("title"),
            "status": status_text,
            "url": issue.get("url"),
            "updatedAt": issue.get("updatedAt"),
            "completedAt": issue.get("completedAt"),
            "createdAt": issue.get("createdAt"),
            "startedAt": issue.get("startedAt"),
            "estimate": issue.get("estimate"),
            "assigneeName": member_name,
        }
        cycle_info = _extract_cycle_info(issue)
        if cycle_info.get("id") and not cycle_info.get("name"):
            resolved = cycle_lookup.get(cycle_info["id"], {})
            if resolved:
                cycle_info["name"] = str(resolved.get("name") or cycle_info.get("name") or "")
                cycle_info["number"] = str(resolved.get("number") or cycle_info.get("number") or "")
                cycle_info["startsAt"] = str(resolved.get("startsAt") or cycle_info.get("startsAt") or "")
                cycle_info["endsAt"] = str(resolved.get("endsAt") or cycle_info.get("endsAt") or "")
        row["cycleName"] = cycle_info.get("name", "")
        row["cycleId"] = cycle_info.get("id", "")
        row["cycleStartsAt"] = cycle_info.get("startsAt", "")
        row["cycleEndsAt"] = cycle_info.get("endsAt", "")
        cycle_name = cycle_info.get("name", "") or "未归属迭代"
        cycle_counter[cycle_name] = cycle_counter.get(cycle_name, 0) + 1
        cycle_ranges[cycle_name] = {
            "startsAt": cycle_info.get("startsAt", ""),
            "endsAt": cycle_info.get("endsAt", ""),
        }

        is_todo = any(s in status_text_lower for s in ["todo", "to do", "backlog", "unstarted", "planned", "待办"])
        if is_todo and (
            touched or _in_range(created_at, start, end) or _in_range(started_at, start, end)
        ):
            todo.append(row)

        if not touched:
            continue
        tasks_in_window.append(row)

        if completed_at and _in_range(completed_at, start, end):
            completed.append(row)
        else:
            # 未在窗口内完成的任务里，排除明确结束态，归到进行中池子
            status_text_norm = (row.get("status") or "").lower()
            is_closed = any(
                s in status_text_norm for s in ["done", "complete", "cancel", "closed", "已完成", "已关闭", "取消"]
            )
            if not is_closed:
                in_progress.append(row)

    stderr = result.get("stderr", "") or ""
    payload_err = (payload.get("message") or payload.get("error") or "") if result["exit_code"] != 0 else ""
    fetch_error = payload_err
    if result["exit_code"] != 0 and not fetch_error:
        # 尝试从 stderr 抽取更可读的根因
        m = re.search(r"(ENOTFOUND\s+[^\s]+)", stderr)
        if m:
            fetch_error = f"网络解析失败：{m.group(1)}"
        elif "fetch failed" in stderr:
            fetch_error = "网络连接失败：fetch failed"
        elif stderr.strip():
            fetch_error = stderr.strip().splitlines()[-1]

    return {
        "member_name": candidate_names[0] if candidate_names else member,
        "issues_total_in_window": len(completed) + len(in_progress),
        "issues_fetched": len(issues),
        "tasks_in_window_total": len(tasks_in_window),
        "tasks_in_window": tasks_in_window,
        "completed": completed,
        "in_progress": in_progress,
        "todo": todo,
        "cycles": [
            {
                "name": k,
                "issue_count": v,
                "startsAt": cycle_ranges.get(k, {}).get("startsAt", ""),
                "endsAt": cycle_ranges.get(k, {}).get("endsAt", ""),
            }
            for k, v in sorted(
                cycle_counter.items(),
                key=lambda x: (x[0] == "未归属迭代", -x[1], x[0]),
            )
        ],
        "page_info": page_info,
        "raw_fetch_exit_code": result["exit_code"],
        "raw_stderr": stderr,
        "raw_stdout": result.get("stdout", ""),
        "fetch_error": fetch_error,
    }


def _collect_git(week_start: date, week_end: date) -> dict[str, Any]:
    result = _run_script(
        "superteam-git/scripts/query_git.py",
        [
            "--since-date",
            week_start.isoformat(),
            "--until-date",
            week_end.isoformat(),
            "--max-analyze",
            "1000000",
            "--format",
            "json",
        ],
    )
    payload = result.get("payload") or {}
    return {
        "summary": payload.get("summary", {}),
        "commits": payload.get("commits", []),
        "project_summaries": payload.get("project_summaries", []),
        "global_analysis": payload.get("global_analysis", {}),
        "raw_fetch_exit_code": result["exit_code"],
    }


def _resolve_git_workspace_hint() -> dict[str, Any]:
    raw = env("SUPERTEAM_GIT_WORKSPACE")
    if not raw or not str(raw).strip():
        return {
            "configured": False,
            "path": "",
            "paths": [],
            "source": "missing",
        }
    segments = [s.strip() for s in str(raw).split(os.pathsep) if s.strip()]
    paths = [str(Path(s).expanduser().resolve()) for s in segments]
    return {
        "configured": True,
        "path": ", ".join(paths),
        "paths": paths,
        "source": "SUPERTEAM_GIT_WORKSPACE",
    }


def _check_linear_network_precondition() -> dict[str, Any]:
    host = "mcp.linear.app"
    try:
        socket.getaddrinfo(host, 443)
        return {"ok": True, "host": host, "reason": ""}
    except OSError as e:
        return {
            "ok": False,
            "host": host,
            "reason": f"无法解析 {host}（{e.__class__.__name__}: {e}）",
        }


def _md_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("|", "\\|").replace("\n", "<br>")
    return text.strip()


def _task_issue_label(task: dict[str, Any]) -> str:
    """Human-readable issue key (e.g. ACB-49); fallback to internal id."""
    ident = str(task.get("identifier") or "").strip()
    if ident:
        return ident
    return str(task.get("id") or "")


def _commit_text_lower(commit: dict[str, Any]) -> str:
    msg = str(commit.get("message_full") or commit.get("message") or "")
    work = str(commit.get("work_summary") or "")
    impact = str(commit.get("impact_summary") or "")
    return f"{msg} {work} {impact}".lower()


def _task_ref_matches_in_lower(task: dict[str, Any], text_lower: str) -> bool:
    """True if Linear internal id or identifier (e.g. ACB-49) appears in text."""
    tid = str(task.get("id") or "").strip().lower()
    if tid and tid in text_lower:
        return True
    ident = str(task.get("identifier") or "").strip().lower()
    return bool(ident and ident in text_lower)


def _task_title_match_candidates(title: str) -> list[str]:
    """Substrings to try against commit message / summaries (full title + segments after :|)."""
    raw = (title or "").strip()
    if not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        t = s.strip()
        if len(t) < 4:
            return
        key = t.casefold()
        if key in seen:
            return
        seen.add(key)
        out.append(t)

    add(raw)
    for part in re.split(r"[:：|]+", raw):
        add(part)
    return out


def _task_title_matches_in_lower(task: dict[str, Any], haystack_lower: str) -> bool:
    """True if task title (or a long enough segment) appears in commit text.

    Complements token overlap: superteam-git keeps full `message`; users often paste
    Linear title or the descriptive part after `TEAM-123:` into commit bodies.
    """
    for cand in _task_title_match_candidates(str(task.get("title") or "")):
        if cand.casefold() in haystack_lower:
            return True
    return False


def _build_task_commit_links(
    completed: list[dict[str, Any]],
    in_progress: list[dict[str, Any]],
    commits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    all_tasks = completed + in_progress
    links: list[dict[str, Any]] = []
    for task in all_tasks:
        task_id = str(task.get("id") or "")
        task_identifier = str(task.get("identifier") or "").strip()
        task_title = str(task.get("title") or "")
        task_status = str(task.get("status") or "")
        matched: list[str] = []
        for c in commits:
            text = _commit_text_lower(c)
            if _task_ref_matches_in_lower(task, text) or _task_title_matches_in_lower(task, text):
                matched.append(str(c.get("commit") or "")[:8])
        links.append(
            {
                "task_id": task_id,
                "task_identifier": task_identifier,
                "task_title": task_title,
                "task_status": task_status,
                "commit_refs": ", ".join([m for m in matched if m]) if matched else "",
            }
        )
    return links


def _tokenize_text(text: str) -> list[str]:
    raw = (text or "").lower()
    parts = re.split(r"[^a-z0-9\u4e00-\u9fff_/\-\.]+", raw)
    tokens: list[str] = []
    for p in parts:
        p = p.strip("._-/")
        if len(p) < 2:
            continue
        if p in {"task", "issue", "feat", "fix", "done", "todo", "test", "this", "week"}:
            continue
        tokens.append(p)
    return tokens


def _task_keywords(task: dict[str, Any]) -> set[str]:
    text = " ".join(
        [
            str(task.get("id") or ""),
            str(task.get("identifier") or ""),
            str(task.get("title") or ""),
            str(task.get("status") or ""),
        ]
    )
    return set(_tokenize_text(text))


def _commit_code_tokens(commit: dict[str, Any]) -> set[str]:
    files = commit.get("files", []) or []
    evidence = commit.get("evidence", []) or []
    changes = commit.get("detailed_changes", []) or []
    code_text = str(commit.get("code_evidence_text") or "")
    joined = " ".join([str(x) for x in files + evidence + changes] + [code_text])
    return set(_tokenize_text(joined))


def _commit_message_tokens(commit: dict[str, Any]) -> set[str]:
    text = str(commit.get("message_full") or commit.get("message") or "")
    return set(_tokenize_text(text))


def _match_tasks_with_code(
    tasks: list[dict[str, Any]],
    commits: list[dict[str, Any]],
    max_commits_per_task: int = 4,
) -> list[dict[str, Any]]:
    commit_vectors: list[tuple[dict[str, Any], set[str], set[str]]] = [
        (c, _commit_code_tokens(c), _commit_message_tokens(c)) for c in commits
    ]
    linked: list[dict[str, Any]] = []
    for task in tasks:
        keywords = _task_keywords(task)
        has_title = bool(str(task.get("title") or "").strip())
        if not keywords and not has_title:
            linked.append({"task": task, "matches": []})
            continue
        scored: list[tuple[float, dict[str, Any], list[str]]] = []
        for commit, code_tokens, msg_tokens in commit_vectors:
            code_overlap = sorted(list(keywords.intersection(code_tokens)))
            msg_overlap = sorted(list(keywords.intersection(msg_tokens)))
            haystack = _commit_text_lower(commit)
            task_ref_hit = _task_ref_matches_in_lower(task, haystack)
            task_title_hit = _task_title_matches_in_lower(task, haystack)
            if not code_overlap and not msg_overlap and not task_ref_hit and not task_title_hit:
                continue
            # 平衡策略：代码证据为主（70%），message 为辅（30%），任务号/标题子串命中额外加分
            denom = max(len(keywords), 1)
            code_cov = len(code_overlap) / denom
            msg_cov = len(msg_overlap) / denom
            code_specificity = sum(1.0 / (1.0 + math.log(2 + len(t))) for t in code_overlap)
            msg_specificity = sum(1.0 / (1.0 + math.log(2 + len(t))) for t in msg_overlap)
            code_score = code_cov * 0.75 + min(code_specificity, 1.0) * 0.25
            msg_score = msg_cov * 0.7 + min(msg_specificity, 1.0) * 0.3
            id_bonus = 0.2 if task_ref_hit else 0.0
            title_bonus = 0.18 if task_title_hit else 0.0
            score = round(code_score * 0.7 + msg_score * 0.3 + id_bonus + title_bonus, 4)
            if score < 0.1:
                continue
            merged_overlap = (code_overlap + [t for t in msg_overlap if t not in code_overlap])[:6]
            if task_title_hit and not merged_overlap:
                merged_overlap = ["任务标题与提交说明一致"]
            scored.append((score, commit, merged_overlap))
        scored.sort(key=lambda x: x[0], reverse=True)
        matches = []
        for score, commit, overlap in scored[:max_commits_per_task]:
            matches.append(
                {
                    "score": score,
                    "overlap_tokens": overlap,
                    "commit": str(commit.get("commit") or "")[:8],
                    "repo": commit.get("repo"),
                    "files": (commit.get("files") or [])[:3],
                    "evidence": (commit.get("evidence") or [])[:3],
                }
            )
        linked.append({"task": task, "matches": matches})
    return linked


def _group_tasks_by_cycle(tasks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for t in tasks:
        cname = str(t.get("cycleName") or "未归属迭代")
        grouped.setdefault(cname, []).append(t)
    return grouped


def _project_code_changes(project: dict[str, Any]) -> list[str]:
    changes: list[str] = []
    for c in project.get("representative_commits", []) or []:
        for dc in c.get("detailed_changes", []) or []:
            text = str(dc or "").strip()
            if text and text not in changes:
                changes.append(text)
        work = str(c.get("work") or "").strip()
        if work and work not in changes:
            changes.append(work)
    return changes


def _project_change_summary(project: dict[str, Any]) -> str:
    works: list[str] = []
    for c in project.get("representative_commits", []) or []:
        work = str(c.get("work") or "").strip()
        if work and work not in works:
            works.append(work)
    top_works = "；".join(works[:3]) if works else "本周期以工程优化与功能迭代为主"

    impacts = [
        str(x.get("impact") or "").strip()
        for x in (project.get("impact_focus") or [])
        if str(x.get("impact") or "").strip()
    ]
    top_impacts = "；".join(impacts[:2]) if impacts else "系统影响需结合提交上下文复核"

    return f"代码改动主要围绕：{top_works}。整体技术影响：{top_impacts}。"


def _cycle_name(task: dict[str, Any]) -> str:
    return str(task.get("cycleName") or "未归属迭代")


def _cycle_sort_key(name: str) -> tuple[int, int, str]:
    n = str(name or "")
    if n == "未归属迭代":
        return (2, 9999, n)
    m = re.search(r"cycle\s*(\d+)", n, flags=re.IGNORECASE)
    if m:
        return (0, int(m.group(1)), n)
    return (1, 0, n)


def _ordered_cycle_names(*task_groups: list[dict[str, Any]]) -> list[str]:
    names: set[str] = set()
    for tasks in task_groups:
        for t in tasks:
            names.add(_cycle_name(t))
    return sorted(names, key=_cycle_sort_key)


def _quality_text_by_matches(matches: list[dict[str, Any]]) -> str:
    if not matches:
        return "未建立稳定代码关联，建议补充更明确的模块/接口关键词后复核。"

    top = matches[0]
    score = float(top.get("score", 0) or 0)
    linked = len(matches)
    overlap = len(top.get("overlap_tokens", []) or [])

    if score >= 0.6:
        return (
            f"高置信关联（score={score:.2f}，命中关键词 {overlap} 个，关联提交 {linked} 条），"
            "交付链路清晰，可直接用于周会复盘。"
        )
    if score >= 0.35:
        return (
            f"中等置信关联（score={score:.2f}，命中关键词 {overlap} 个，关联提交 {linked} 条），"
            "建议结合任务备注进行二次确认。"
        )
    return (
        f"低置信关联（score={score:.2f}，命中关键词 {overlap} 个，关联提交 {linked} 条），"
        "建议人工补充任务上下文后再判定交付质量。"
    )


def _render_markdown(
    member: str,
    week_mode: str,
    week_start: date,
    week_end: date,
    linear_data: dict[str, Any],
    git_data: dict[str, Any],
    git_workspace_hint: dict[str, Any],
) -> str:
    display_name = str(linear_data.get("member_name") or member)
    week_label = "本周" if week_mode == "this" else "上周"
    sync_date = week_end + timedelta(days=1)
    gsum = git_data.get("summary", {}) or {}
    insertions = int(gsum.get("total_insertions", 0) or 0)
    deletions = int(gsum.get("total_deletions", 0) or 0)
    net = insertions - deletions
    net_trend = "代码库持续瘦身 ✅" if net < 0 else "代码能力持续增长 ✅"
    projects = git_data.get("project_summaries", []) or []
    completed = linear_data.get("completed", []) or []
    in_progress = linear_data.get("in_progress", []) or []
    todo = linear_data.get("todo", []) or []
    report_cycles = _ordered_cycle_names(completed, in_progress, todo)
    cycle_text = "、".join(report_cycles[:3]) if report_cycles else "未识别到迭代"
    top_domains = [str(p.get("project_name")) for p in projects[:2] if p.get("project_name")]
    core_domains = "、".join(top_domains) if top_domains else "暂无显著集中域"

    lines: list[str] = []
    lines.append(f"# 🚀 研发周报 | {display_name}")
    lines.append(f"**周期：** {week_start.strftime('%Y.%m.%d')} - {week_end.strftime('%Y.%m.%d')}")
    lines.append(f"**同步日期：** {sync_date.strftime('%Y.%m.%d')} (周一)")
    lines.append(f"**关联迭代：** {cycle_text}")
    lines.append("")
    if not bool(git_workspace_hint.get("configured")):
        lines.append("")
        lines.append(
            f"> ⚠️ 未检测到 `SUPERTEAM_GIT_WORKSPACE` 配置，当前使用默认路径 `{_md_cell(git_workspace_hint.get('path'))}` 扫描 Git 仓库。"
        )
        lines.append(
            "> 建议在 `~/.superteam/config` 中配置该项：可以避免扫描错目录、漏统计你的真实提交，提升周报准确性。"
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("### 📊 一、 工程与代码影响力指标 (Code Impact & Health)")
    lines.append("> **Agent 逻辑：** 基于 `/superteam-git` 深度分析本周提交。排除自动生成的代码或锁定文件 (如 `package-lock.json`)，提取真实的工程贡献。")
    lines.append("")
    lines.append(f"* **{week_label}代码产出（总览）：** `+{insertions}` 行 / `-{deletions}` 行（净精简: `{net}` 行，{net_trend}）")
    lines.append(f"* **核心触达域（总览）：** 本周改动主要集中在 `{core_domains}`。")
    lines.append("* **按工程汇报：**")
    if projects:
        for p in projects[:5]:
            project_name = _md_cell(p.get("project_name"))
            p_ins = int(p.get("insertions", 0) or 0)
            p_del = int(p.get("deletions", 0) or 0)
            lines.append(
                f"  * **{project_name}：** `+{p_ins}` / `-{p_del}`，提交 {int(p.get('commit_count', 0) or 0)} 次。"
            )
            lines.append(f"    * **代码改动汇总：** {_md_cell(_project_change_summary(p))}")
    else:
        lines.append("  * 暂无工程级别改动数据。")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("### 🎯 二、 核心技术交付 (Key Deliverables)")
    lines.append("> **Agent 逻辑：** 先按 Linear Cycle 聚合，再在每个迭代内展开任务与代码证据。")
    lines.append("")
    lines.append("#### 迭代汇总")
    lines.append("")
    cycle_done_map = _group_tasks_by_cycle(completed)
    if cycle_done_map:
        for c_name in _ordered_cycle_names(completed):
            tasks_in_cycle = cycle_done_map.get(c_name, [])
            if not tasks_in_cycle:
                continue
            lines.append(f"* **{_md_cell(c_name)}：** {len(tasks_in_cycle)} 个完成任务")
    else:
        lines.append("* 本周期未检索到可汇总的完成任务迭代。")

    lines.append("")
    lines.append("#### 迭代内任务内容")
    lines.append("")
    if linear_data.get("raw_fetch_exit_code", 0) != 0:
        err = linear_data.get("fetch_error") or "Linear 查询失败（请检查网络/MCP 授权）"
        lines.append(f"* Linear 拉取失败：{_md_cell(err)}")
        lines.append("")
        lines.append("1. **[待补充] 核心交付 A**")
        lines.append("   * **技术决策与实现：** 待补充。")
        lines.append("   * **交付质量：** 待补充。")
        lines.append("")
    else:
        commit_items = git_data.get("commits", []) or []
        linked_done = _match_tasks_with_code(completed, commit_items)
        linked_by_task_id = {
            str(e["task"].get("id") or ""): e for e in linked_done
        }
        if completed:
            for c_name in _ordered_cycle_names(completed):
                tasks_in_cycle = cycle_done_map.get(c_name, [])
                if not tasks_in_cycle:
                    continue
                lines.append(f"#### {_md_cell(c_name)}")
                lines.append("")
                for idx, it in enumerate(tasks_in_cycle[:10], start=1):
                    entry = linked_by_task_id.get(str(it.get("id") or ""), {"matches": []})
                    matches = entry.get("matches", [])
                    lines.append(
                        f"{idx}. **[{_md_cell(_task_issue_label(it))}] {_md_cell(it.get('title'))}**"
                    )
                    if matches:
                        refs = ", ".join([f"{m['repo']}@{m['commit']}" for m in matches])
                        lines.append(
                            f"   * **技术决策与实现：** 关联代码提交 `{refs}`。"
                        )
                        lines.append(f"   * **交付质量：** {_quality_text_by_matches(matches)}")
                    else:
                        lines.append("   * **技术决策与实现：** 当前未匹配到高置信代码提交（可能是流程/评审类任务）。")
                        lines.append(f"   * **交付质量：** {_quality_text_by_matches(matches)}")
                    lines.append("")
        else:
            lines.append("1. **[无完成任务]**")
            lines.append("   * **技术决策与实现：** 本周期未检索到 `Done` 状态任务。")
            lines.append("   * **交付质量：** 建议核对 Linear 权限或时间窗口设置。")
            lines.append("")

    lines.append("#### 本周提交明细（全部）")
    lines.append("")
    if commit_items:
        for c in commit_items:
            commit_short = _md_cell(str(c.get("commit") or "")[:8])
            repo = _md_cell(c.get("repo") or "")
            msg = _md_cell(str(c.get("message_full") or c.get("message") or "").splitlines()[0])
            lines.append(f"- `{repo}@{commit_short}` {msg}")
    else:
        lines.append("- 本周期未检索到提交明细。")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("### ⚠️ 三、 任务异常预警与工时健康度 (Anomalies & Health Check)")
    lines.append("> **Agent 逻辑：** 交叉对比 Linear 的 `Estimate`、`Started At` 和当前状态。")
    lines.append("")
    red_alerts: list[tuple[dict[str, Any], int]] = []
    yellow_alerts: list[tuple[dict[str, Any], int]] = []
    now = datetime.now().astimezone()
    for it in in_progress:
        status_lower = str(it.get("status") or "").lower()
        started_dt = _parse_dt(str(it.get("startedAt") or "")) or _parse_dt(str(it.get("createdAt") or ""))
        updated_dt = _parse_dt(str(it.get("updatedAt") or ""))
        if started_dt:
            days = (now - started_dt).days
            if days >= 5:
                red_alerts.append((it, days))
        if "review" in status_lower and updated_dt:
            hours = int((now - updated_dt).total_seconds() // 3600)
            if hours >= 48:
                yellow_alerts.append((it, hours))

    in_progress_by_cycle = _group_tasks_by_cycle(in_progress)
    if in_progress_by_cycle:
        for c_name in _ordered_cycle_names(in_progress):
            tasks_in_cycle = in_progress_by_cycle.get(c_name, [])
            if not tasks_in_cycle:
                continue
            lines.append(f"* **{_md_cell(c_name)}：** 进行中 {len(tasks_in_cycle)} 个任务")
            cycle_red = [(it, d) for it, d in red_alerts if _cycle_name(it) == c_name]
            cycle_yellow = [(it, h) for it, h in yellow_alerts if _cycle_name(it) == c_name]
            if cycle_red:
                issue, days = cycle_red[0]
                lines.append(
                    f"  * 🔴 耗时异常：[{_md_cell(_task_issue_label(issue))}] {_md_cell(issue.get('title'))}，"
                    f"状态 `{_md_cell(issue.get('status'))}` 已持续 {days} 天。"
                )
            if cycle_yellow:
                issue, hours = cycle_yellow[0]
                lines.append(
                    f"  * 🟡 流转异常：[{_md_cell(_task_issue_label(issue))}] {_md_cell(issue.get('title'))}，"
                    f"`Review` 停留约 {hours} 小时。"
                )
            if not cycle_red and not cycle_yellow:
                lines.append("  * 🟢 该迭代进行中任务整体流转正常。")
    else:
        lines.append("* 本周期未检索到进行中任务，无需异常预警。")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("### 🔵 四、 本周架构演进与开发计划 (This Week's Focus)")
    lines.append("> **Agent 逻辑：** 抓取 Linear 中本周的 `To Do`，重点突出技术挑战。")
    lines.append("")
    if todo:
        todo_by_cycle = _group_tasks_by_cycle(todo)
        for c_name in _ordered_cycle_names(todo):
            tasks_in_cycle = todo_by_cycle.get(c_name, [])
            if not tasks_in_cycle:
                continue
            lines.append(f"* **{_md_cell(c_name)}：**")
            for idx, it in enumerate(tasks_in_cycle, start=1):
                lines.append(
                    f"  {idx}. **[重点] [{_md_cell(_task_issue_label(it))}] {_md_cell(it.get('title'))}：** "
                    "计划推进该任务并聚焦关键技术实现与风险控制。"
                )
    else:
        lines.append("1. **[重点] 暂无 To Do 任务数据：** 建议在 Linear 补充本周计划。")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("### 🗣️ 五、 需在周会上 Request for Comments (RFC)")
    lines.append("> **Agent 逻辑：** 抓取带有 `Needs Discussion` 标签的 Linear 任务，或开发者自己手写补充。")
    lines.append("")
    lines.append("* 建议讨论：跨模块接口边界、潜在回归风险、以及下周容量评估。")
    lines.append(f"* 数据来源：superteam-linear / superteam-git（生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}）")
    return "\n".join(lines)


def _render_precondition_failed_markdown(
    member: str,
    week_mode: str,
    week_start: date,
    week_end: date,
    linear_data: dict[str, Any],
) -> str:
    title = "本周周报" if week_mode == "this" else "上周周报"
    sync_date = week_end + timedelta(days=1)
    err = linear_data.get("fetch_error") or "Linear 查询失败"
    lines: list[str] = []
    lines.append(f"# 🚀 研发周报 | {member}")
    lines.append(f"**周期：** {week_start.strftime('%Y.%m.%d')} - {week_end.strftime('%Y.%m.%d')}")
    lines.append(f"**同步日期：** {sync_date.strftime('%Y.%m.%d')} (周一)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"### ⚠️ {title} 生成受阻")
    lines.append(f"* **失败原因：** {_md_cell(err)}")
    lines.append(f"* **查询退出码：** {_md_cell(linear_data.get('raw_fetch_exit_code'))}")
    lines.append("* **处理建议：**")
    lines.append("  * 确认当前环境可访问 `mcp.linear.app`。")
    lines.append("  * 在 Cursor 中为当前工作区开启网络权限后重试 `/superteam-report`。")
    return "\n".join(lines)


def _render_workspace_precondition_failed_markdown(
    member: str,
    week_mode: str,
    week_start: date,
    week_end: date,
) -> str:
    title = "本周周报" if week_mode == "this" else "上周周报"
    sync_date = week_end + timedelta(days=1)
    lines: list[str] = []
    lines.append(f"# 🚀 研发周报 | {member}")
    lines.append(f"**周期：** {week_start.strftime('%Y.%m.%d')} - {week_end.strftime('%Y.%m.%d')}")
    lines.append(f"**同步日期：** {sync_date.strftime('%Y.%m.%d')} (周一)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"### ⚠️ {title} 生成受阻")
    lines.append("* **失败原因：** 未配置 `SUPERTEAM_GIT_WORKSPACE`。")
    lines.append("* **处理建议：**")
    lines.append(
        "  * 在 `~/.superteam/config` 增加：`SUPERTEAM_GIT_WORKSPACE=/目录1:/目录2`（macOS/Linux 用 `:` 分隔多个根目录；Windows 用 `;`）。"
    )
    lines.append("  * 该配置用于定位你的代码仓库目录，避免扫错目录和漏统提交。")
    lines.append("  * 配置后重试 `/superteam-report`。")
    return "\n".join(lines)


def _week_number(week_start: date) -> int:
    # Use ISO week number for "Wxx" naming.
    return int(week_start.isocalendar()[1])


def _week_folder_name(week_start: date) -> str:
    # DingTalk weekly folder naming: 26W15 / 26W16 ...
    yy = week_start.year % 100
    wk = _week_number(week_start)
    return f"{yy:02d}W{wk:02d}"


def _safe_filename_name(name: str) -> str:
    # Keep filename filesystem-safe and readable.
    cleaned = re.sub(r"[\\/:*?\"<>|]", "-", (name or "").strip())
    return cleaned or "未知成员"


def _build_publish_meta(
    member_name: str,
    week_start: date,
    week_end: date,
    markdown: str,
) -> dict[str, Any]:
    wk = _week_number(week_start)
    week_folder_name = _week_folder_name(week_start)
    final_name = _safe_filename_name(member_name)
    filename = f"W{wk}-{final_name}.md"
    return {
        "ready": True,
        "target": {
            "platform": "dingtalk_docs",
            "root_folder_url": REPORT_ROOT_FOLDER_URL,
            "root_folder_id": REPORT_ROOT_FOLDER_ID,
            "week_folder_name": week_folder_name,
        },
        "document": {
            "name": filename,
            "week_label": f"W{wk}",
            "week_folder_name": week_folder_name,
            "week_range": [week_start.isoformat(), week_end.isoformat()],
            "markdown_length": len(markdown),
        },
        "mcp": {
            "check_required": True,
            "required_tools": ["list_nodes", "create_document"],
            "resolve_week_folder": {
                "tool": "list_nodes",
                "args_template": {"folderId": REPORT_ROOT_FOLDER_ID},
                "match": {
                    "name": week_folder_name,
                    "nodeType": "folder",
                },
                "resolved_folder_id_field": "nodeId",
            },
            "publish_tool": "create_document",
            "publish_args_template": {
                "name": filename,
                "folderId": "<resolved-week-folder-id>",
                "markdown": "<superteam-report-markdown>",
            },
            "if_missing": "请用户先在当前 Agent 中配置并授权钉钉 MCP，然后重试发布。",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="superteam-report generator v2")
    parser.add_argument("query", nargs="?", default="", help="自然语言请求（可空）")
    parser.add_argument("--member", "-m", default="me", help="Linear assignee（默认 me）")
    parser.add_argument(
        "--publish-name",
        default="",
        help="发布文件名中的姓名（可选，默认取 Linear member_name 或 --member）",
    )
    parser.add_argument("--week", "-w", choices=["this", "last"], help="this=本周, last=上周")
    parser.add_argument("--format", "-f", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--linear-first", type=int, default=100000, help="Linear 一次拉取任务数量")
    parser.add_argument(
        "--require-linear",
        choices=["true", "false"],
        default="true",
        help="是否要求 Linear 连通后才生成周报（默认 true）。",
    )
    args = parser.parse_args()

    week_mode = _resolve_week_mode(args.query, args.week)
    week_start, week_end = _week_range(week_mode)
    start_dt = datetime.combine(week_start, time.min).astimezone()
    end_dt = datetime.combine(week_end, time.max).astimezone()
    require_linear = args.require_linear == "true"
    git_workspace_hint = _resolve_git_workspace_hint()

    # 前提条件：必须显式配置 SUPERTEAM_GIT_WORKSPACE，避免默认目录导致误报/漏报
    if not bool(git_workspace_hint.get("configured")):
        output = {
            "skill": "superteam-report",
            "status": "precondition_failed",
            "member": args.member,
            "week_mode": week_mode,
            "week_range": [week_start.isoformat(), week_end.isoformat()],
            "preconditions": {
                "git_workspace_configured": False,
                "reason": "missing SUPERTEAM_GIT_WORKSPACE",
            },
            "sources": {},
            "markdown": _render_workspace_precondition_failed_markdown(
                args.member,
                week_mode,
                week_start,
                week_end,
            ),
        }
        if args.format == "json":
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            print(output["markdown"])
        return

    # 前提条件：优先检查 Linear MCP 域名可解析，先给出“需要申请网络权限”的明确提示
    if require_linear:
        net_check = _check_linear_network_precondition()
        if not net_check.get("ok"):
            linear_data = {
                "raw_fetch_exit_code": 1,
                "fetch_error": net_check.get("reason", "Linear 网络前置检查失败"),
            }
            output = {
                "skill": "superteam-report",
                "status": "precondition_failed",
                "member": args.member,
                "week_mode": week_mode,
                "week_range": [week_start.isoformat(), week_end.isoformat()],
                "preconditions": {
                    "linear_mcp_network_access": False,
                    "reason": linear_data["fetch_error"],
                    "git_workspace_configured": bool(git_workspace_hint.get("configured")),
                    "git_workspace_path": git_workspace_hint.get("path"),
                },
                "sources": {
                    "superteam-linear": linear_data,
                },
                "markdown": _render_precondition_failed_markdown(
                    args.member,
                    week_mode,
                    week_start,
                    week_end,
                    linear_data,
                ),
            }
            if args.format == "json":
                print(json.dumps(output, ensure_ascii=False, indent=2))
            else:
                print(output["markdown"])
            return

    linear_data = _collect_linear(args.member, start_dt, end_dt, args.linear_first)
    precondition_failed = require_linear and (linear_data.get("raw_fetch_exit_code", 0) != 0)

    if precondition_failed:
        output = {
            "skill": "superteam-report",
            "status": "precondition_failed",
            "member": args.member,
            "week_mode": week_mode,
            "week_range": [week_start.isoformat(), week_end.isoformat()],
            "preconditions": {
                "linear_mcp_accessible": False,
                "git_workspace_configured": bool(git_workspace_hint.get("configured")),
                "git_workspace_path": git_workspace_hint.get("path"),
            },
            "sources": {
                "superteam-linear": linear_data,
            },
            "markdown": _render_precondition_failed_markdown(
                args.member,
                week_mode,
                week_start,
                week_end,
                linear_data,
            ),
        }
        if args.format == "json":
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            print(output["markdown"])
        return

    git_data = _collect_git(week_start, week_end)

    output = {
        "skill": "superteam-report",
        "status": "live-v2",
        "member": args.member,
        "week_mode": week_mode,
        "week_range": [week_start.isoformat(), week_end.isoformat()],
        "preconditions": {
            "git_workspace_configured": bool(git_workspace_hint.get("configured")),
            "git_workspace_path": git_workspace_hint.get("path"),
        },
        "sources": {
            "superteam-linear": linear_data,
            "superteam-git": git_data,
        },
        "markdown": _render_markdown(
            args.member,
            week_mode,
            week_start,
            week_end,
            linear_data,
            git_data,
            git_workspace_hint,
        ),
    }

    display_name = str(
        args.publish_name.strip()
        or linear_data.get("member_name")
        or args.member
    )
    output["publish"] = _build_publish_meta(
        member_name=display_name,
        week_start=week_start,
        week_end=week_end,
        markdown=output["markdown"],
    )

    if args.format == "json":
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(output["markdown"])


if __name__ == "__main__":
    main()
