#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Archive eligible Linear issues by issue ids, cycle, project, or project+cycle."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_ROOT = Path(__file__).resolve().parent.parent.parent
_SHARED = _ROOT / "_shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from config import env  # noqa: E402

_LINEAR_GRAPHQL_ISSUE_QUERY = """
query ArchiveIssueLookup($id: String!) {
  issue(id: $id) {
    id
    identifier
    title
    archivedAt
    state { name type }
    project { id name }
    cycle { id name number }
  }
}
"""

_LINEAR_GRAPHQL_ARCHIVE_MUTATION = """
mutation ArchiveIssue($id: String!, $trash: Boolean) {
  issueArchive(id: $id, trash: $trash) {
    success
    entity {
      id
      identifier
      title
      archivedAt
      state { name type }
    }
  }
}
"""


def _parse_cycle_selector(raw: str | None) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {"raw": None, "number": None, "name": None}
    if text.isdigit():
        return {"raw": text, "number": int(text), "name": None}
    lower = text.lower()
    if lower.startswith("cycle "):
        suffix = text[6:].strip()
        if suffix.isdigit():
            return {"raw": text, "number": int(suffix), "name": None}
    return {"raw": text, "number": None, "name": text}


def _error(code: str, message: str, extra: dict[str, Any] | None = None) -> int:
    payload: dict[str, Any] = {"ok": False, "error_code": code, "message": message}
    if extra:
        payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1


def _graphql_config() -> dict[str, str] | None:
    api_key = env("LINEAR_API_KEY")
    if not api_key:
        return None
    api_url = env("LINEAR_API_URL") or "https://api.linear.app/graphql"
    return {"api_key": api_key, "api_url": api_url}


def _issue_state(issue: dict[str, Any]) -> str:
    state = issue.get("state")
    if isinstance(state, dict):
        name = state.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
        type_name = state.get("type")
        if isinstance(type_name, str) and type_name.strip():
            return type_name.strip()
    if isinstance(state, str) and state.strip():
        return state.strip()
    for key in ("stateName", "stateType"):
        value = issue.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _is_terminal_state(issue: dict[str, Any]) -> bool:
    state_name = _issue_state(issue).strip().lower()
    state_obj = issue.get("state")
    state_type = ""
    if isinstance(state_obj, dict):
        raw_type = state_obj.get("type")
        if isinstance(raw_type, str):
            state_type = raw_type.strip().lower()
    return state_name in {"done", "canceled", "cancelled"} or state_type in {"completed", "canceled", "cancelled"}


def _normalize_issue_ids(raw_values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        for item in str(raw or "").split(","):
            token = item.strip()
            if not token or token in seen:
                continue
            seen.add(token)
            out.append(token)
    return out


def _normalize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    cycle_value = None
    cycle = issue.get("cycle")
    if isinstance(cycle, dict):
        cycle_name = cycle.get("name")
        cycle_number = cycle.get("number")
        if isinstance(cycle_name, str) and cycle_name.strip():
            cycle_value = cycle_name.strip()
        elif cycle_number is not None:
            cycle_value = f"Cycle {int(cycle_number)}" if float(cycle_number).is_integer() else str(cycle_number)

    return {
        "uuid": issue.get("id"),
        "id": issue.get("identifier") or issue.get("id"),
        "title": issue.get("title") or "",
        "state": _issue_state(issue),
        "archived": bool(issue.get("archivedAt") or issue.get("archived", False)),
        "project": ((issue.get("project") or {}).get("name") if isinstance(issue.get("project"), dict) else None),
        "cycle": cycle_value,
    }


def _build_issues_query(project: str | None, cycle: str | None) -> tuple[str, dict[str, Any]]:
    parts: list[str] = []
    variables: dict[str, Any] = {"first": None, "after": None}
    if project:
        parts.append("project: { name: { eq: $project } }")
        variables["project"] = project

    cycle_selector = _parse_cycle_selector(cycle)
    if cycle_selector["number"] is not None:
        parts.append("cycle: { number: { eq: $cycleNumber } }")
        variables["cycleNumber"] = cycle_selector["number"]
    elif cycle_selector["name"]:
        parts.append("cycle: { name: { eq: $cycleName } }")
        variables["cycleName"] = cycle_selector["name"]

    var_defs = ["$first: Int!", "$after: String"]
    if project:
        var_defs.append("$project: String!")
    if cycle_selector["number"] is not None:
        var_defs.append("$cycleNumber: Float!")
    elif cycle_selector["name"]:
        var_defs.append("$cycleName: String!")

    filter_block = ""
    if parts:
        filter_block = "filter: { " + ", ".join(parts) + " },"

    query = f"""
query ArchiveIssues({", ".join(var_defs)}) {{
  issues(
    first: $first,
    after: $after,
    {filter_block}
  ) {{
    nodes {{
      id
      identifier
      title
      archivedAt
      state {{ name type }}
      project {{ id name }}
      cycle {{ id name number }}
    }}
    pageInfo {{
      hasNextPage
      endCursor
    }}
  }}
}}
"""
    return query, variables


def _post_linear_graphql(api_url: str, api_key: str, query: str, variables: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    auth = api_key.strip()
    try:
        import httpx  # type: ignore

        verify: object = True
        try:
            import certifi  # type: ignore
            verify = certifi.where()
        except Exception:
            verify = True

        resp = httpx.post(
            api_url,
            headers={"Content-Type": "application/json", "Authorization": auth},
            json={"query": query, "variables": variables},
            timeout=float(timeout_seconds),
            verify=verify,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Linear GraphQL HTTP {resp.status_code}: {resp.text[:500]}")
        payload = resp.json()
    except Exception:
        body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        req = Request(
            api_url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": auth},
        )
        try:
            with urlopen(req, timeout=timeout_seconds) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            raw = ""
            try:
                raw = exc.read().decode("utf-8", errors="replace")
            except Exception:
                raw = ""
            raise RuntimeError(f"Linear GraphQL HTTP {getattr(exc, 'code', None)}: {raw[:500]}") from exc
        except URLError as exc:
            raise RuntimeError(f"Linear GraphQL URL error: {getattr(exc, 'reason', exc)}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Linear GraphQL request failed: {exc}") from exc

    errors = payload.get("errors")
    if errors:
        raise RuntimeError(json.dumps(errors, ensure_ascii=False)[:1000])
    if not isinstance(payload.get("data"), dict):
        raise RuntimeError("Linear GraphQL response missing data")
    return payload


def _load_issue_ids(issue_ids: list[str], graphql_timeout: int = 45) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = _graphql_config()
    if cfg is None:
        raise RuntimeError("LINEAR_API_KEY not set")
    issues: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for issue_id in issue_ids:
        try:
            payload = _post_linear_graphql(cfg["api_url"], cfg["api_key"], _LINEAR_GRAPHQL_ISSUE_QUERY, {"id": issue_id}, graphql_timeout)
            issue = (payload.get("data") or {}).get("issue")
            if not isinstance(issue, dict):
                failures.append({"id": issue_id, "reason": "fetch_failed", "message": "issue payload missing"})
                continue
            issues.append(issue)
        except Exception as exc:
            failures.append({"id": issue_id, "reason": "fetch_failed", "message": str(exc)})
    return issues, failures


def _load_list_issues(*, project: str | None, cycle: str | None, first: int = 200, graphql_timeout: int = 45) -> list[dict[str, Any]]:
    cfg = _graphql_config()
    if cfg is None:
        raise RuntimeError("LINEAR_API_KEY not set")

    query, base_variables = _build_issues_query(project, cycle)
    variables = dict(base_variables)
    variables["first"] = min(first, 250)
    variables["after"] = None
    issues: list[dict[str, Any]] = []
    while len(issues) < first:
        payload = _post_linear_graphql(cfg["api_url"], cfg["api_key"], query, variables, graphql_timeout)
        data = (payload.get("data") or {}).get("issues") or {}
        nodes = data.get("nodes") or []
        page_info = data.get("pageInfo") or {}
        for node in nodes:
            if isinstance(node, dict):
                issues.append(node)
                if len(issues) >= first:
                    break
        if not page_info.get("hasNextPage"):
            break
        variables["after"] = page_info.get("endCursor")
        if not variables["after"]:
            break
    return issues


def _build_result(mode: str, input_type: str, filters: dict[str, Any], issues: list[dict[str, Any]], failures: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = []
    skipped = []
    ignored = []
    for raw in issues:
        issue = _normalize_issue(raw)
        if issue["archived"]:
            skipped.append({**issue, "reason": "already_archived"})
        elif _is_terminal_state(raw):
            eligible.append(issue)
        else:
            ignored.append({**issue, "reason": "not_done_or_canceled"})
    return {
        "skill": "superteam-linear",
        "tool": "archive_cycle_issues",
        "mode": mode,
        "input_type": input_type,
        "filters": filters,
        "scanned": len(issues),
        "matched": len(eligible),
        "eligible": eligible,
        "skipped": skipped,
        "ignored": ignored,
        "archived": [],
        "failed": failures,
    }


def _archive_issue(issue: dict[str, Any], config: dict[str, str]) -> dict[str, Any]:
    uuid = str(issue.get("uuid") or "").strip()
    if not uuid:
        raise RuntimeError(f"missing internal issue id for {issue.get('id')}")
    payload = _post_linear_graphql(
        config["api_url"],
        config["api_key"],
        _LINEAR_GRAPHQL_ARCHIVE_MUTATION,
        {"id": uuid, "trash": False},
        int(config.get("graphql_timeout", "45")),
    )
    archive_payload = (payload.get("data") or {}).get("issueArchive")
    if not isinstance(archive_payload, dict):
        raise RuntimeError("issueArchive returned no payload")
    if not archive_payload.get("success"):
        raise RuntimeError("issueArchive returned success=false")
    entity = archive_payload.get("entity")
    if not isinstance(entity, dict):
        raise RuntimeError("issueArchive returned no entity")
    normalized = _normalize_issue(entity)
    return {"id": normalized["id"], "title": normalized["title"], "state": normalized["state"]}


def _execute_archive(result: dict[str, Any], graphql_timeout: int = 45) -> tuple[int, dict[str, Any]]:
    cfg = _graphql_config()
    if cfg is None:
        return 1, {"ok": False, "error_code": "config_missing", "message": "LINEAR_API_KEY not set", "preview": result}
    exec_cfg = {"api_url": cfg["api_url"], "api_key": cfg["api_key"], "graphql_timeout": str(graphql_timeout)}
    archived = []
    failed = list(result["failed"])
    for issue in result["eligible"]:
        try:
            archived.append(_archive_issue(issue, exec_cfg))
        except Exception as exc:
            failed.append({
                "id": issue.get("id"),
                "title": issue.get("title") or "",
                "state": issue.get("state") or "",
                "reason": "archive_failed",
                "message": str(exc),
            })
    out = dict(result)
    out["archived"] = archived
    out["failed"] = failed
    return 0, out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Archive terminal Linear issues by issue ids, cycle, project, or project+cycle.")
    parser.add_argument("--cycle", default=None, help="Cycle name or id.")
    parser.add_argument("--project", default=None, help="Project name or id.")
    parser.add_argument("--issue-id", action="append", default=[], dest="issue_ids", help="Issue ids. Supports comma-separated values and repeated flags.")
    parser.add_argument("--execute", action="store_true", help="Execute archive writes. Default is dry-run.")
    parser.add_argument("--first", type=int, default=200, help="Maximum issues to fetch in list mode.")
    parser.add_argument("--graphql-timeout", type=int, default=45, dest="graphql_timeout", help="GraphQL timeout in seconds.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    issue_ids = _normalize_issue_ids(args.issue_ids)
    has_filter = bool(issue_ids or args.project or args.cycle)
    if not has_filter:
        return _error("INVALID_ARGUMENT", "one of --issue-id, --project, or --cycle is required")
    if issue_ids and (args.project or args.cycle):
        return _error("INVALID_ARGUMENT", "--issue-id cannot be mixed with --project or --cycle")
    if args.first <= 0:
        return _error("INVALID_ARGUMENT", "--first must be > 0")

    mode = "execute" if args.execute else "dry-run"
    filters = {"issue_ids": issue_ids, "project": args.project, "cycle": args.cycle}

    try:
        if issue_ids:
            input_type = "issue_ids"
            issues, failures = _load_issue_ids(issue_ids, graphql_timeout=args.graphql_timeout)
        else:
            input_type = "project_cycle" if args.project and args.cycle else ("project" if args.project else "cycle")
            issues = _load_list_issues(project=args.project, cycle=args.cycle, first=args.first, graphql_timeout=args.graphql_timeout)
            failures = []
    except Exception as exc:
        return _error("list_failed", str(exc), {"filters": filters})

    result = _build_result(mode, input_type, filters, issues, failures)
    if args.execute:
        code, payload = _execute_archive(result, graphql_timeout=args.graphql_timeout)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return code
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
