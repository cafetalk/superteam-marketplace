#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""带短时去重的 Linear save_issue（防「一次创建新任务却出现两条相同新单」）。

典型原因：Agent 同一会话内重复调用工具、用户重试、MCP/网络超时后自动重试等，导致 save_issue 被执行两次。
本脚本在本地 JSON 记录最近一次成功创建的 (标题规范化 + assignee)，在 guard 时间窗内若再次请求相同标题，
默认路径见 `_default_guard_cache_path()`（优先环境变量，其次可写的 ~/.superteam，否则当前目录 .superteam/），
则**不再调用** save_issue，直接返回已创建的 issue（stdout 为单一 JSON）。

若 save_issue 已在 Linear 侧成功但 stdout 解析失败，会再拉 list_issues：按**规范化标题 + team**匹配，
且 **createdAt 在 recover-within 秒内**的 issue 视为本次创建并写缓存，避免重复建单。

与 preflight_linear_issue.py 的区别：预检解决「和历史 issue 撞车」；本脚本解决「同一流程双次创建」。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from query_linear_stdout_json import extract_insight_linear_payload

_SKILLS_ROOT = Path(__file__).resolve().parent.parent.parent
_QUERY_LINEAR = _SKILLS_ROOT / "superteam-linear" / "scripts" / "query_linear.py"


def _default_guard_cache_path() -> Path:
    """去重缓存路径：避免 Agent 沙箱无法写 home 时 guard 完全失效。

    1. ``SUPERTEAM_LINEAR_ISSUE_GUARD_CACHE`` 显式指定
    2. 若 ``~/.superteam`` 可创建/写入探测文件，用 ``~/.superteam/linear_issue_create_guard.json``
    3. 否则 ``<cwd>/.superteam/linear_issue_create_guard.json``（工作区通常可写）
    """
    override = (os.environ.get("SUPERTEAM_LINEAR_ISSUE_GUARD_CACHE") or "").strip()
    if override:
        return Path(override).expanduser()
    preferred = Path.home() / ".superteam" / "linear_issue_create_guard.json"
    parent = preferred.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        probe = parent / ".linear_issue_guard_write_probe"
        probe.write_text("", encoding="utf-8")
        probe.unlink(missing_ok=True)  # py3.8: use try/except if needed - project is 3.9+
        return preferred
    except OSError:
        return Path.cwd() / ".superteam" / "linear_issue_create_guard.json"


def normalize_title(s: str) -> str:
    t = (s or "").lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t


def find_reusable_entry(
    entries: list[dict[str, Any]],
    title_norm: str,
    assignee: str,
    now: float,
    window_sec: float,
) -> dict[str, Any] | None:
    for e in reversed(entries):
        if str(e.get("title_norm", "")) != title_norm:
            continue
        if str(e.get("assignee", "")) != assignee:
            continue
        try:
            ts = float(e.get("ts", 0))
        except (TypeError, ValueError):
            continue
        if now - ts <= window_sec:
            return e
    return None


def _load_cache(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ent = data.get("entries")
        if isinstance(ent, list):
            return [x for x in ent if isinstance(x, dict)]
    except Exception:
        pass
    return []


def _write_cache(path: Path, entries: list[dict[str, Any]], max_entries: int = 50) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    trimmed = entries[-max_entries:]
    payload = {"entries": trimmed}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _call_save_issue(title: str, team: str, state: str, assignee: str) -> dict[str, Any]:
    args_obj = {
        "title": title,
        "team": team,
        "state": state,
        "assignee": assignee,
    }
    proc = subprocess.run(
        [
            sys.executable,
            str(_QUERY_LINEAR),
            "--tool",
            "save_issue",
            "--args-json",
            json.dumps(args_obj, ensure_ascii=False),
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    raw = (proc.stdout or "") + "\n" + (proc.stderr or "")
    payload = extract_insight_linear_payload(raw)
    if proc.returncode != 0 and not payload:
        return {"_error": f"save_issue subprocess exit {proc.returncode}", "_raw": raw[-2000:]}
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        return {"_error": "no result in MCP response", "_payload_keys": list(payload.keys()) if isinstance(payload, dict) else []}
    iid = str(result.get("id") or "").strip()
    if not iid:
        return {"_error": "save_issue returned no id", "result": result}
    return result


def _parse_created_ts(issue: dict[str, Any]) -> float | None:
    raw = str(issue.get("createdAt") or "").strip()
    if not raw:
        return None
    try:
        s = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (TypeError, ValueError):
        return None


def _call_list_issues(assignee: str, first: int) -> list[dict[str, Any]]:
    if not _QUERY_LINEAR.is_file():
        return []
    proc = subprocess.run(
        [
            sys.executable,
            str(_QUERY_LINEAR),
            "--tool",
            "list_issues",
            "--args-json",
            json.dumps(
                {"assignee": assignee, "includeArchived": False, "first": first},
                ensure_ascii=False,
            ),
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
    return [x for x in issues if isinstance(x, dict)]


def pick_recent_matching_issue(
    issues: list[dict[str, Any]],
    title_norm: str,
    team: str,
    now: float,
    within_sec: float,
) -> dict[str, Any] | None:
    """用于测试：在 issues 里找规范化标题一致、team 一致且创建时间在窗口内的最新一条。"""
    team_l = str(team or "").strip().lower()
    candidates: list[tuple[float, dict[str, Any]]] = []
    for it in issues:
        if normalize_title(str(it.get("title") or "")) != title_norm:
            continue
        if team_l and str(it.get("team") or "").strip().lower() != team_l:
            continue
        ts = _parse_created_ts(it)
        if ts is None:
            continue
        if now - ts > within_sec:
            continue
        iid = str(it.get("id") or "").strip()
        if not iid:
            continue
        candidates.append((ts, it))
    if not candidates:
        if not team_l:
            return None
        for it in issues:
            if normalize_title(str(it.get("title") or "")) != title_norm:
                continue
            ts = _parse_created_ts(it)
            if ts is None or now - ts > within_sec:
                continue
            iid = str(it.get("id") or "").strip()
            if iid:
                candidates.append((ts, it))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _recover_issue_via_list(
    title_norm: str,
    team: str,
    assignee: str,
    now: float,
    within_sec: float,
    list_first: int,
) -> dict[str, Any] | None:
    issues = _call_list_issues(assignee, list_first)
    hit = pick_recent_matching_issue(issues, title_norm, team, now, within_sec)
    if not hit:
        return None
    return {
        "id": str(hit.get("id") or "").strip(),
        "url": str(hit.get("url") or ""),
        "title": str(hit.get("title") or ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="save_issue with short-window idempotency guard.")
    ap.add_argument("--title", required=True)
    ap.add_argument("--team", required=True)
    ap.add_argument("--state", default="In Progress")
    ap.add_argument("--assignee", default="me")
    ap.add_argument("--guard-seconds", type=float, default=180.0, help="同标题+assignee 在此秒数内不重复创建")
    ap.add_argument(
        "--cache-file",
        type=Path,
        default=None,
        help="去重缓存路径；省略则按 SUPERTEAM_LINEAR_ISSUE_GUARD_CACHE / home 可写性 / cwd .superteam 选择",
    )
    ap.add_argument(
        "--force-new",
        action="store_true",
        help="跳过去重（确需极短时间内建两条同标题任务时使用）",
    )
    ap.add_argument(
        "--recover-within-seconds",
        type=float,
        default=300.0,
        help="save 后解析失败时，list_issues 只认领 createdAt 在此秒数内的同标题同 team 任务（默认 300）",
    )
    ap.add_argument(
        "--list-first",
        type=int,
        default=80,
        help="回收时 list_issues 的 first 参数",
    )
    args = ap.parse_args()

    title_norm = normalize_title(args.title)
    assignee = str(args.assignee).strip() or "me"
    now = time.time()
    cache_path: Path = (
        args.cache_file.expanduser() if args.cache_file is not None else _default_guard_cache_path()
    )

    entries = _load_cache(cache_path)

    if not args.force_new:
        reuse = find_reusable_entry(
            entries, title_norm, assignee, now, float(args.guard_seconds)
        )
        if reuse:
            out = {
                "skill": "superteam-git",
                "tool": "save_issue_guarded",
                "reused": True,
                "reason": "same_title_and_assignee_within_guard_window",
                "issue": {
                    "id": str(reuse.get("issue_id", "")),
                    "title": str(reuse.get("title", args.title)),
                    "url": str(reuse.get("url", "")),
                },
                "guard": {
                    "window_seconds": args.guard_seconds,
                    "cache_path": str(cache_path),
                },
            }
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0

    if not _QUERY_LINEAR.is_file():
        print(
            json.dumps(
                {"skill": "superteam-git", "error": "query_linear.py not found", "path": str(_QUERY_LINEAR)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    # 上一进程可能已在 Linear 创建成功，但写 ~/.superteam 缓存失败（如 Agent 沙箱不可写）后退出；
    # 本地无缓存时若直接再打 save_issue 会重复建单。save 前先 list 认领近期同标题单。
    if not args.force_new:
        preexisting = _recover_issue_via_list(
            title_norm,
            args.team,
            assignee,
            now,
            float(args.recover_within_seconds),
            int(args.list_first),
        )
        if preexisting and str(preexisting.get("id") or "").strip():
            iid0 = str(preexisting["id"]).strip()
            url0 = str(preexisting.get("url") or "")
            title0 = str(preexisting.get("title") or args.title)
            entries.append(
                {
                    "title_norm": title_norm,
                    "issue_id": iid0,
                    "url": url0,
                    "title": title0,
                    "ts": now,
                    "assignee": assignee,
                }
            )
            cache_warn: str | None = None
            try:
                _write_cache(cache_path, entries)
            except OSError as e:
                cache_warn = f"cache_write_failed: {e}"
            out_pre: dict[str, Any] = {
                "skill": "superteam-git",
                "tool": "save_issue_guarded",
                "reused": True,
                "reason": "recent_matching_issue_on_linear_before_save",
                "issue": {"id": iid0, "title": title0, "url": url0},
                "guard": {
                    "window_seconds": args.guard_seconds,
                    "cache_path": str(cache_path),
                },
            }
            if cache_warn:
                out_pre["warning"] = cache_warn
            print(json.dumps(out_pre, ensure_ascii=False, indent=2))
            return 0

    result = _call_save_issue(args.title, args.team, args.state, assignee)
    recovered = False
    if "_error" in result:
        fallback = _recover_issue_via_list(
            title_norm,
            args.team,
            assignee,
            now,
            float(args.recover_within_seconds),
            int(args.list_first),
        )
        if fallback and str(fallback.get("id") or "").strip():
            result = fallback
            recovered = True
        else:
            print(json.dumps({"skill": "superteam-git", "error": result["_error"], "detail": result}, ensure_ascii=False, indent=2))
            return 1

    iid = str(result.get("id", "")).strip()
    url = str(result.get("url", ""))
    title_saved = str(result.get("title", args.title))

    entries.append(
        {
            "title_norm": title_norm,
            "issue_id": iid,
            "url": url,
            "title": title_saved,
            "ts": now,
            "assignee": assignee,
        }
    )
    cache_write_err: str | None = None
    try:
        _write_cache(cache_path, entries)
    except OSError as e:
        # 仍返回成功 JSON，避免调用方误判失败再次 save_issue 导致重复建单
        cache_write_err = str(e)

    out: dict[str, Any] = {
        "skill": "superteam-git",
        "tool": "save_issue_guarded",
        "reused": False,
        "issue": {"id": iid, "title": title_saved, "url": url},
        "guard": {
            "window_seconds": args.guard_seconds,
            "cache_path": str(cache_path),
        },
    }
    if recovered:
        out["recovered"] = True
        out["recovered_reason"] = "list_issues_recent_title_team_match_after_save_ambiguous_response"
    if cache_write_err:
        out["warning"] = f"cache_write_failed: {cache_write_err}"
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
