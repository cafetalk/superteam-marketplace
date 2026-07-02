#!/usr/bin/env python3
"""TREX-493：workspace 级「进行中项目」日快照（不按 Linear Team 分条）。

全 workspace 合并 issue 后按**项目**输出一条记录（``team=trex``），不会出现 trex/superteam 等多条。
payload.projects[] = Linear 状态为 Planned / In Progress 的全部项目；任务统计按项目下全部 issue。

Usage:
  python skills/superteam-report/scripts/snapshot_sprint.py
  python skills/superteam-report/scripts/snapshot_sprint.py --date 2026-05-22 --dry-run
  python skills/superteam-report/scripts/snapshot_sprint.py --upload   # 落盘 + upsert_pulse 入库
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_SHARED = Path(__file__).resolve().parents[2] / "_shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))
from linear_profile import (
    build_member_profile_index,
    leader_profile_url_from_project_meta,
    linear_workspace_from_url,
)
from pulse_snapshot_common import (
    cycle_to_json,
    default_pulse_out_root,
    default_snapshot_date,
    linear_client,
    list_teams,
    load_report_module,
    resolve_out_dir,
    resolve_target_cycles,
    upload_envelopes_to_pg,
    write_pulse_file,
)

# sp_trex_pulse / 落盘文件名：trex-sprint-daily.json（workspace 合并，不按 Team 拆多条）
SPRINT_TEAM_KEY = "trex"

_LINEAR_REACTION_DATA_QUERY = """
query IssueReactionData($id: String!) {
  issue(id: $id) {
    id
    identifier
    reactionData
  }
}
"""

_LINEAR_USERS_BY_IDS_QUERY = """
query UsersByIds($ids: [ID!]!) {
  users(filter: { id: { in: $ids } }) {
    nodes { id name displayName }
  }
}
"""


def _load_config_env(key: str) -> str | None:
    """Read config value from env or ~/.superteam/config via shared config.env()."""
    try:
        shared = (Path(__file__).resolve().parents[2] / "_shared").resolve()
        if str(shared) not in sys.path:
            sys.path.insert(0, str(shared))
        from config import env  # type: ignore

        return env(key)
    except Exception:
        return None


def _post_linear_graphql(
    api_url: str,
    api_key: str,
    query: str,
    variables: dict[str, Any],
) -> dict[str, Any] | None:
    # Linear GraphQL expects raw API key in Authorization header (NOT "Bearer <key>").
    auth = api_key.strip()

    # Prefer httpx + certifi to avoid local OpenSSL CA issues.
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
            timeout=45.0,
            verify=verify,
        )
        if resp.status_code != 200:
            return {"_error": "http_error", "status": resp.status_code, "body": resp.text[:2000]}
        return resp.json()
    except Exception:
        # Fallback: urllib (may fail on CA); keep structured error.
        body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        req = Request(
            api_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": auth,
            },
        )
        try:
            with urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            try:
                b = e.read().decode("utf-8", errors="replace")
            except Exception:
                b = ""
            return {"_error": "http_error", "status": getattr(e, "code", None), "body": b[:2000]}
        except URLError as e:
            return {"_error": "url_error", "reason": str(getattr(e, "reason", e))[:300]}
        except (OSError, json.JSONDecodeError) as e:
            return {"_error": "exception", "message": str(e)[:300]}


def _member_name_to_role(gtw: Any) -> dict[str, dict[str, str]]:
    """Map member display name/aliases -> {role, role_bucket}.

    注意：sprint「产品创建任务」需要识别产品角色，因此这里使用全量成员表（不做周报角色过滤）。
    """
    idx: dict[str, dict[str, str]] = {}

    members: list[dict[str, Any]]
    # Prefer direct DB read when available to avoid MCP-side filtering/dedup
    # that may hide non-deleted rows for the same name.
    try:
        shared = (Path(__file__).resolve().parents[2] / "_shared").resolve()
        if str(shared) not in sys.path:
            sys.path.insert(0, str(shared))
        from config import env  # type: ignore
        kb_url = env("KB_TREX_PG_URL")
        if kb_url:
            import psycopg2  # type: ignore
            from queries import query_list_members  # type: ignore

            conn = psycopg2.connect(kb_url)
            try:
                cur = conn.cursor()
                cur.execute("SET search_path TO trex_hub, public")
                cur.close()
                members = query_list_members(conn)
            finally:
                conn.close()
        else:
            members = gtw.list_members()
    except Exception:
        try:
            members = gtw.list_members()
        except Exception:
            members = []

    def _norm(s: str) -> str:
        return " ".join((s or "").strip().lower().split())

    # Build with priority: product > design > test > engineering buckets > other.
    # This avoids a "deleted/merged" row overwriting an active role mapping when
    # name/alias overlaps.
    _prio = {
        "product": 50,
        "design": 40,
        "test": 30,
        "architect": 20,
        "backend": 20,
        "frontend": 20,
        "other": 0,
    }

    for m in members:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "")
        r = role.strip().lower()
        if r in ("deleted", "merged"):
            continue

        bucket: str
        if getattr(gtw, "_role_bucket_for_weekly", None) and gtw._role_bucket_for_weekly(role) is not None:
            bucket = gtw._role_bucket_for_weekly(role)
        elif getattr(gtw, "_role_string_indicates_qa", None) and gtw._role_string_indicates_qa(role):
            bucket = "test"
        elif ("产品" in role) or (r in ("pm", "po", "product-manager")) or ("product-manager" in r):
            bucket = "product"
        elif "设计" in role or "design" in r or r in ("ux", "ui"):
            bucket = "design"
        else:
            bucket = "other"

        for nm in getattr(gtw, "_member_display_names", lambda _m: [])(m):
            if nm and str(nm).strip():
                raw = str(nm).strip()
                info = {"role": role, "role_bucket": bucket}
                for key in (raw, _norm(raw)):
                    cur = idx.get(key)
                    if cur is None or _prio.get(info["role_bucket"], 0) > _prio.get(cur.get("role_bucket", "other"), 0):
                        idx[key] = info

    return idx


def _issue_emojo_for_identifier(
    identifier: str,
    *,
    gtw: Any,
    role_by_name: dict[str, dict[str, str]],
) -> dict[str, Any] | None:
    """Fetch issue emoji reactions via GraphQL ``reactionData`` (who reacted with which emoji).

    Hosted Linear MCP does not expose reaction detail; each row is one person + one emoji.
    """
    def _norm(s: str) -> str:
        return " ".join((s or "").strip().lower().split())

    api_key = _load_config_env("LINEAR_API_KEY")
    api_url = _load_config_env("LINEAR_API_URL") or "https://api.linear.app/graphql"
    if not api_key:
        return None
    payload = _post_linear_graphql(api_url, api_key, _LINEAR_REACTION_DATA_QUERY, {"id": identifier})
    if not isinstance(payload, dict) or payload.get("_error") or payload.get("errors"):
        return None
    issue = (payload.get("data") or {}).get("issue") if isinstance(payload.get("data"), dict) else None
    if not isinstance(issue, dict):
        return {"identifier": identifier, "emojo": []}
    reaction_data = issue.get("reactionData")
    if not isinstance(reaction_data, list):
        return {"identifier": identifier, "emojo": []}

    pending: list[tuple[str, str, str | None]] = []  # (user_id, emoji, reacted_at)
    for row in reaction_data:
        if not isinstance(row, dict):
            continue
        emoji = str(row.get("emoji") or "").strip()
        if not emoji:
            continue
        reactions = row.get("reactions") if isinstance(row.get("reactions"), list) else []
        for r in reactions:
            if not isinstance(r, dict):
                continue
            uid = str(r.get("userId") or "").strip()
            if not uid:
                continue
            pending.append((uid, emoji, str(r.get("reactedAt") or "").strip() or None))
    if not pending:
        return {"identifier": identifier, "emojo": []}

    user_ids = sorted({uid for uid, _, _ in pending})
    users_payload = _post_linear_graphql(api_url, api_key, _LINEAR_USERS_BY_IDS_QUERY, {"ids": user_ids})
    if not isinstance(users_payload, dict) or users_payload.get("_error") or users_payload.get("errors"):
        return {"identifier": identifier, "emojo": []}
    nodes = (((users_payload.get("data") or {}).get("users") or {}).get("nodes")) or []
    by_id: dict[str, dict[str, Any]] = {}
    for u in nodes:
        if isinstance(u, dict):
            uid = str(u.get("id") or "").strip()
            if uid:
                by_id[uid] = u

    emojo: list[dict[str, Any]] = []
    for uid, emoji, reacted_at in pending:
        u = by_id.get(uid) or {}
        display_name = str(u.get("displayName") or "").strip()
        real_name = str(u.get("name") or "").strip()
        key = display_name or real_name or uid
        role_info = (
            role_by_name.get(display_name)
            or role_by_name.get(_norm(display_name))
            or role_by_name.get(real_name)
            or role_by_name.get(_norm(real_name))
            or {"role": "", "role_bucket": "other"}
        )
        emojo.append({
            "emoji": emoji,
            "name": key,
            "display_name": display_name or None,
            "real_name": real_name or None,
            "reacted_at": reacted_at,
            **role_info,
        })
    emojo.sort(key=lambda x: (str(x.get("emoji") or ""), str(x.get("role_bucket") or ""), str(x.get("name") or "")))
    return {"identifier": identifier, "emojo": emojo}


def _snapshot_ref_datetime(gtw: Any, snapshot_date: date) -> datetime:
    """快照口径「截至 snapshot_date 当日」；回填历史日用当日 23:59:59 本地时区。"""
    now = gtw._now_utc()
    if gtw._to_local_date(now) <= snapshot_date:
        return now
    local_tz = now.tzinfo
    return datetime.combine(snapshot_date, time(23, 59, 59), tzinfo=local_tz)


def _overview_to_chart_row(overview: dict[str, Any]) -> dict[str, Any]:
    """周报 §1 项目行 → pulse 折线图友好结构（数字字段与 progress_counts 分列）。"""
    pc = overview.get("progress_counts") or {}
    todo = int(pc.get("todo") or 0)
    backlog = int(pc.get("backlog") or 0)
    return {
        "name": overview.get("name"),
        "cycle_task_count": overview.get("cycle_task_count"),
        "done": int(pc.get("done") or 0),
        "in_progress": int(pc.get("in_progress") or 0),
        "todo": todo,
        "backlog": backlog,
        "todo_and_backlog": todo + backlog,
        "other": int(pc.get("other") or 0),
        "progress_done_pct": overview.get("progress_done_pct"),
        "progress_label": overview.get("progress_label"),
        "progress_kind": overview.get("progress_kind"),
        "status_label": overview.get("status_label"),
        "next_milestone": overview.get("next_milestone"),
        "days_to_milestone": overview.get("days_to_milestone"),
        "current_handlers": overview.get("current_handlers"),
        "bugs_cycle": overview.get("bugs_cycle", 0),
        "bugs_open": overview.get("bugs_open", 0),
        "risk_short": overview.get("risk_short") or "",
        "test_date": overview.get("test_date"),
        "release_date": overview.get("release_date"),
    }


def _apply_project_wide_progress(
    row: dict[str, Any],
    project_issues: list[dict[str, Any]],
    *,
    gtw: Any,
    status_type_map: dict[str, str],
) -> None:
    """Sprint「项目进度」与 participants 同口径：统计项目下全部未取消任务。

    周报 §1 在测试/开发阶段会按职能子集展示「测试进度/开发进度」；sprint 律动看板
    应对用户展示全项目完成数，避免 QA 子集仅 1 条进行中时完成数显示为 0。
    """
    active = [
        it for it in project_issues
        if isinstance(it, dict)
        and gtw._state_bucket_for_issue(it, status_type_map) != "canceled"
    ]
    n_done, n_ip, n_todo, n_bl, n_other, _nc, _na, pct = gtw._count_cycle_issue_buckets(
        active, status_type_map,
    )
    phase_label = row.get("progress_label")
    row["done"] = n_done
    row["in_progress"] = n_ip
    row["todo"] = n_todo
    row["backlog"] = n_bl
    row["other"] = n_other
    row["todo_and_backlog"] = n_todo + n_bl
    row["progress_done_pct"] = round(pct, 1)
    row["progress_label"] = "项目进度"
    row["progress_scope"] = "project"
    if phase_label and phase_label != "项目进度":
        row["progress_label_phase"] = phase_label


def _enrich_project_status_fields(
    row: dict[str, Any],
    *,
    gtw: Any,
    proj_stat: dict[str, Any],
    project_meta: dict[str, Any],
) -> None:
    """补充项目状态字段：status（项目阶段）与 Linear 原生项目状态。"""
    status_label = str(
        row.get("status_label") or proj_stat.get("status_label") or "",
    ).strip()
    if status_label:
        row["status"] = status_label
        row["status_label"] = status_label

    linear_name = str(
        proj_stat.get("linear_status")
        or gtw._project_linear_status_name(project_meta)
        or "",
    ).strip()
    if linear_name:
        row["linear_status"] = linear_name

    st = project_meta.get("status")
    if isinstance(st, dict):
        stype = str(st.get("type") or "").strip().lower()
        if stype:
            row["linear_status_type"] = stype


def _project_participants_by_owner(
    project_issues: list[dict[str, Any]],
    status_type_map: dict[str, str],
    *,
    gtw: Any,
) -> dict[str, dict[str, int]]:
    """项目参与人：按 assignee 统计任务总数与未完成数（已取消不计）。"""
    out: dict[str, dict[str, int]] = defaultdict(
        lambda: {"task_count": 0, "open_count": 0},
    )
    for it in project_issues:
        if gtw._state_bucket_for_issue(it, status_type_map) == "canceled":
            continue
        owner = (gtw._assignee_name(it) or "未分配").strip() or "未分配"
        out[owner]["task_count"] += 1
        if gtw._state_bucket_for_issue(it, status_type_map) not in ("done", "canceled"):
            out[owner]["open_count"] += 1
    return dict(out)


def _participants_json(
    by_owner: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    rows = [
        {
            "name": owner,
            "task_count": int(c.get("task_count") or 0),
            "open_count": int(c.get("open_count") or 0),
        }
        for owner, c in by_owner.items()
        if int(c.get("task_count") or 0) > 0
    ]
    rows.sort(key=lambda r: (-int(r["task_count"]), str(r["name"])))
    return rows


def _cycle_issues_by_project(
    cycle_issues: list[dict[str, Any]],
    *,
    gtw: Any,
) -> dict[str, list[dict[str, Any]]]:
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in cycle_issues:
        by_name[gtw._issue_project_name(it)].append(it)
    return dict(by_name)


def _build_in_progress_proj_stats_list(
    *,
    gtw: Any,
    status_type_map: dict[str, str],
    now: datetime,
    active_linear_projects: list[dict[str, Any]],
    project_meta_by_name: dict[str, dict[str, Any]],
    project_issues_by_name: dict[str, list[dict[str, Any]]],
    rd_member_names: set[str],
    cycle_issues_by_project: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """纳入项目清单：经 _filter_linear_projects_for_report 筛选后，任务统计用项目下全部 issue。"""
    active_names = gtw._active_report_project_names(active_linear_projects)
    proj_stats: list[dict[str, Any]] = []
    for p in active_linear_projects:
        pname = str(p.get("name") or "").strip()
        if not pname or pname not in active_names:
            continue
        project_issues = project_issues_by_name.get(pname, [])
        stats = gtw._summarize_project_cycle_stats(
            pname,
            project_issues,
            status_type_map,
            now,
            project_meta=p,
            project_issues=project_issues,
            rd_names=rd_member_names,
        )
        # NOTE: historical field name; sprint payload now uses it as "dev_task_count"
        # (no longer tied to current cycle).
        stats["cycle_task_count"] = None
        proj_stats.append(stats)
    proj_stats.sort(key=gtw._project_overview_sort_key)
    return proj_stats


def build_sprint_payload(
    proj_stats: list[dict[str, Any]],
    *,
    gtw: Any,
    iso_week: str,
    status_type_map: dict[str, str],
    project_issues_by_name: dict[str, list[dict[str, Any]]],
    project_meta_by_name: dict[str, dict[str, Any]],
    cycles: list[dict[str, Any]],
    cycle_notes: list[str],
) -> dict[str, Any]:
    role_by_name = _member_name_to_role(gtw)
    projects: list[dict[str, Any]] = []
    for s in proj_stats:
        overview = gtw._proj_stats_to_overview_json(s)
        row = _overview_to_chart_row(overview)
        row["project_task_count"] = int(s.get("total") or 0)
        pname = str(row.get("name") or "")
        project_issues = project_issues_by_name.get(pname, [])
        pm = project_meta_by_name.get(pname) or {}
        _enrich_project_status_fields(row, gtw=gtw, proj_stat=s, project_meta=pm)
        row["project_url"] = (
            str(pm.get("url") or "").strip()  # Linear Project URL（若 MCP 返回）
            or None
        )

        def _issue_team_key(it: dict[str, Any]) -> str:
            # Linear MCP issue payload usually has "team" (string key), sometimes nested dict.
            v = it.get("team")
            if isinstance(v, str):
                return v.strip().lower()
            if isinstance(v, dict):
                key = str(v.get("key") or v.get("name") or "").strip()
                return key.lower()
            return str(it.get("teamName") or "").strip().lower()

        def _norm(s: str) -> str:
            return " ".join((s or "").strip().lower().split())

        def _role_info_for_name(name: str) -> dict[str, str]:
            key = (name or "").strip()
            if not key:
                return {}
            return role_by_name.get(key) or role_by_name.get(_norm(key)) or {}

        def _is_product_manager_issue(it: dict[str, Any]) -> bool:
            """Exclude tasks owned/created by product-manager (role_bucket=product)."""
            for who in (
                str(it.get("createdBy") or "").strip(),
                (gtw._assignee_name(it) or "").strip(),
            ):
                if not who or who == "未分配":
                    continue
                info = _role_info_for_name(who)
                role = str(info.get("role") or "").strip().lower()
                if role == "product-manager" or info.get("role_bucket") == "product":
                    return True
            return False

        def _is_manage_product_issue(it: dict[str, Any]) -> bool:
            team_key = _issue_team_key(it)
            # 兼容：manage-product / manage_product / trex-manage-product 等
            t = team_key.replace("_", "-")
            return ("manage" in t and "product" in t) or t.endswith("manage-product")

        def _is_test_issue(it: dict[str, Any]) -> bool:
            team_key = _issue_team_key(it)
            t = team_key.replace("_", "-")
            return ("test" in t) or ("qa" in t) or ("测试" in team_key)

        # 用户口径：cycle_task_count = 开发阶段任务数（排除 manage-product、测试团队、product-manager 任务；不与 cycle 关联）
        dev_task_count = 0
        for it in project_issues:
            if not isinstance(it, dict):
                continue
            if gtw._state_bucket_for_issue(it, status_type_map) == "canceled":
                continue
            if _is_manage_product_issue(it) or _is_test_issue(it) or _is_product_manager_issue(it):
                continue
            dev_task_count += 1
        row["cycle_task_count"] = int(dev_task_count)

        lead = gtw._project_lead_name(pm)
        row["leader"] = lead or None
        ws = linear_workspace_from_url(str(row.get("project_url") or pm.get("url") or ""))
        row["leader_profile_url"] = leader_profile_url_from_project_meta(pm, workspace=ws)
        participants = _participants_json(
            _project_participants_by_owner(
                project_issues, status_type_map, gtw=gtw,
            ),
        )
        row["participants"] = participants
        row["participant_count"] = len(participants)
        row["open_total"] = sum(int(p.get("open_count") or 0) for p in participants)
        _apply_project_wide_progress(
            row, project_issues, gtw=gtw, status_type_map=status_type_map,
        )

        # 产品创建任务：创建人（createdBy）在成员表中的 role_bucket=product
        product_candidates: list[dict[str, Any]] = []

        for it in project_issues:
            if not isinstance(it, dict):
                continue
            creator = str(it.get("createdBy") or "").strip()
            if not creator:
                continue
            creator_info = role_by_name.get(creator) or role_by_name.get(_norm(creator)) or {}
            if creator_info.get("role_bucket") == "product":
                product_candidates.append(it)
        product_candidates.sort(key=lambda x: str(x.get("createdAt") or ""), reverse=True)
        product_task = product_candidates[0] if product_candidates else None
        if isinstance(product_task, dict):
            task_id = str(gtw._issue_key(product_task) or "")
            emojo_info = _issue_emojo_for_identifier(
                task_id,
                gtw=gtw,
                role_by_name=role_by_name,
            )
            row["product_creation_task"] = {
                "task_id": task_id or None,
                "title": str(product_task.get("title") or "").strip() or None,
                "url": str(product_task.get("url") or "").strip() or None,
                "created_by": str(product_task.get("createdBy") or "").strip() or None,
                "created_by_role": (
                    (role_by_name.get(str(product_task.get("createdBy") or "").strip()) or {}).get("role")
                    or (role_by_name.get(_norm(str(product_task.get("createdBy") or "").strip())) or {}).get("role")
                    or ""
                ),
                "created_by_role_bucket": (
                    (role_by_name.get(str(product_task.get("createdBy") or "").strip()) or {}).get("role_bucket")
                    or (role_by_name.get(_norm(str(product_task.get("createdBy") or "").strip())) or {}).get("role_bucket")
                    or "other"
                ),
                "emojo": (emojo_info or {}).get("emojo", []) if isinstance(emojo_info, dict) else [],
                "emojo_source": "linear_graphql_reactionData" if emojo_info is not None else "unavailable",
            }
        else:
            row["product_creation_task"] = None
        projects.append(row)
    cycles_json = [cycle_to_json(c, gtw) for c in cycles]
    primary_cycle = cycles_json[0] if cycles_json else None
    return {
        "section": "进行中的项目",
        "iso_week": iso_week,
        "team": SPRINT_TEAM_KEY,
        "cycle": primary_cycle,
        "cycles": cycles_json,
        "cycle_notes": cycle_notes,
        "project_count": len(projects),
        "data_scope": {
            "scope": "workspace 全 Team 合并；入库 team=trex，不按 Team 分多条",
            "project_selection": (
                "Linear Project 仅纳入 Planned / In Progress（status.type=planned|started）；"
                "排除 Backlog / Completed / Canceled；不按 startDate / targetDate 过滤"
            ),
            "task_counts": "进度三数按该项目下全部 issue（跨 Team 去重合并）",
            "cycle_task_count": (
                "开发阶段任务数（排除 manage-product 团队、测试团队、"
                "product-manager 角色创建或 assignee 的任务；历史字段名；不与 cycle 关联）"
            ),
            "project_url": "Linear Project 链接（来自 list_projects 返回的 url 字段；若缺失则为 null）",
            "leader": "Linear Project Lead",
            "leader_profile_url": "Linear Project Lead 个人页（https://linear.app/<workspace>/profiles/<slug>）",
            "participants": "项目下未取消任务的 assignee；含 task_count（总）与 open_count（未完成）",
            "open_total": "该项目未完成任务总数（participants 的 open_count 之和）",
            "status": "项目阶段（与 status_label 相同，如 开发中 / 测试中 / 延期上线）",
            "linear_status": "Linear Project 原生状态名（如 Planned / In Progress）",
            "linear_status_type": "Linear Project 状态类型（planned / started / completed / canceled）",
            "risk_short": "Linear issue 风险标签汇总（如 未分配×2；久未更新×1）",
            "product_creation_task": (
                "项目下由产品角色创建的任务（issue.createdBy 在成员表 role_bucket=product）；"
                "emojo 为该产品任务全部表情反应（谁发了什么 emoji），来源 linear_graphql_reactionData"
            ),
        },
        "projects": projects,
    }


def snapshot_sprint(
    *,
    snapshot_date: date,
    out_root: Path,
    dry_run: bool = False,
    upload_to_pg: bool = False,
    include_archived_teams: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    gtw = load_report_module()
    iso_week = gtw._iso_week_for_date(snapshot_date)
    report_week_start = gtw._report_week_start_date(iso_week)
    ref_now = _snapshot_ref_datetime(gtw, snapshot_date)
    out_dir = resolve_out_dir(out_root, snapshot_date)
    results: list[dict[str, Any]] = []
    envelopes: list[dict[str, Any]] = []

    for client, mcp, tool_names in linear_client(gtw):
        all_linear_projects = gtw._enrich_linear_projects(
            mcp,
            client,
            tool_names,
            mcp.list_projects(client, tool_names),
        )
        project_meta_by_name = gtw._build_project_meta_by_name(all_linear_projects)
        active_linear_projects, _excluded_notes = gtw._filter_linear_projects_for_report(
            all_linear_projects,
            report_week_start=report_week_start,
            ref=ref_now.date(),
        )
        excluded_project_names = gtw._excluded_report_project_names(
            all_linear_projects,
            ref=ref_now.date(),
            report_week_start=report_week_start,
        )
        rd_member_names = gtw._rd_member_names()

        merged_status_map: dict[str, str] = {}
        project_issues_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        merged_cycle_issues: list[dict[str, Any]] = []
        seen_issue_keys: set[str] = set()
        cycles_hit: list[dict[str, Any]] = []
        seen_cycle_ids: set[str] = set()
        cycle_notes: list[str] = []

        for t in list_teams(gtw, mcp, client, tool_names, include_archived=include_archived_teams):
            team_id = t.get("id") or t.get("teamId")
            if not team_id:
                continue
            team_name = str(t.get("name") or team_id)
            for s in mcp.list_issue_statuses(client, tool_names, team_id=team_id):
                if isinstance(s, dict):
                    merged_status_map[s.get("name", "")] = s.get("type", "")

            team_all_issues = mcp.list_issues_for_team(client, tool_names, team_id=team_id)
            team_all_issues = gtw._filter_issues_excluding_projects(
                team_all_issues, excluded_project_names,
            )
            team_proj_issues = [
                it for it in team_all_issues
                if gtw._issue_project_name(it) != "未关联项目"
            ]
            gtw._merge_issues_into_project_index(project_issues_by_name, team_proj_issues)

            current_cycles = resolve_target_cycles(
                mcp, client, tool_names, team_id=team_id, iso_week=iso_week, gtw=gtw,
            )
            for cycle in current_cycles[:1]:
                cycle_id = str(cycle.get("id") or cycle.get("cycleId") or "")
                if not cycle_id:
                    continue
                if cycle_id not in seen_cycle_ids:
                    seen_cycle_ids.add(cycle_id)
                    cycles_hit.append(cycle)
                num = cycle.get("number")
                label = f"{team_name} #{num}" if num is not None else team_name
                if label not in cycle_notes:
                    cycle_notes.append(label)
                batch = mcp.list_issues_in_cycle(
                    client, tool_names, team_id=team_id, cycle_id=cycle_id,
                )
                batch = gtw._filter_issues_excluding_projects(
                    batch, excluded_project_names,
                )
                gtw._merge_issues_into_project_index(project_issues_by_name, batch)
                for it in batch:
                    k = gtw._issue_key(it)
                    if k in seen_issue_keys:
                        continue
                    seen_issue_keys.add(k)
                    merged_cycle_issues.append(it)

        proj_stats = _build_in_progress_proj_stats_list(
            gtw=gtw,
            status_type_map=merged_status_map,
            now=ref_now,
            active_linear_projects=active_linear_projects,
            project_meta_by_name=project_meta_by_name,
            project_issues_by_name=dict(project_issues_by_name),
            rd_member_names=rd_member_names,
            cycle_issues_by_project=_cycle_issues_by_project(merged_cycle_issues, gtw=gtw),
        )
        payload = build_sprint_payload(
            proj_stats,
            gtw=gtw,
            iso_week=iso_week,
            status_type_map=merged_status_map,
            project_issues_by_name=dict(project_issues_by_name),
            project_meta_by_name=project_meta_by_name,
            cycles=cycles_hit,
            cycle_notes=cycle_notes,
        )
        envelope = {
            "type": "sprint",
            "period": "daily",
            "snapshot_date": snapshot_date.isoformat(),
            "team": SPRINT_TEAM_KEY,
            "payload": payload,
        }
        entry = {
            "team": SPRINT_TEAM_KEY,
            "type": "sprint",
            "period": "daily",
            "project_count": payload["project_count"],
            "cycle_issue_count": len(merged_cycle_issues),
            "payload": payload,
        }
        if not dry_run:
            entry["file"] = str(write_pulse_file(out_dir, envelope))
        if upload_to_pg and not dry_run:
            envelopes.append(envelope)
        results.append(entry)

    upload_count = 0
    if upload_to_pg and not dry_run:
        upload_count = upload_envelopes_to_pg(envelopes)
        for entry in results:
            entry["uploaded"] = True

    return results, upload_count


def main() -> int:
    p = argparse.ArgumentParser(
        description="Sprint daily pulse — 进行中的项目（按项目阶段，非 Cycle 涉及项目）",
    )
    p.add_argument("--date", default=None, help="snapshot_date YYYY-MM-DD（默认今天）")
    p.add_argument(
        "--out-dir",
        default=str(default_pulse_out_root()),
        help="输出根目录 <out-dir>/<YYYY-MM-DD>/（默认 ~/.superteam/pulse）",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--upload",
        action="store_true",
        help="写入 JSON 后 upsert 到 sp_trex_pulse（需 KB_TREX_PG_URL）",
    )
    p.add_argument("--include-archived-teams", action="store_true")
    args = p.parse_args()

    snapshot_date = default_snapshot_date(args.date)
    out_root = Path(args.out_dir)

    try:
        rows, upload_count = snapshot_sprint(
            snapshot_date=snapshot_date,
            out_root=out_root,
            dry_run=args.dry_run,
            upload_to_pg=args.upload,
            include_archived_teams=args.include_archived_teams,
        )
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "type": "sprint",
                "period": "daily",
                "snapshot_date": snapshot_date.isoformat(),
                "out_dir": str(resolve_out_dir(out_root, snapshot_date)),
                "uploaded": bool(args.upload and not args.dry_run),
                "upload_count": upload_count,
                "teams": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
