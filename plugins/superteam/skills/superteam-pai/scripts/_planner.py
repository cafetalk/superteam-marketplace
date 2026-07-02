"""规则型规划器（B 方案 V1）：自然语言 / job 名 → 执行计划。不把提示词透传给子 skill。"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from _registry import JOBS, STEPS, expand_dependencies, plan_steps_dict, sort_step_ids

_DATE_ISO_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")


def default_snapshot_date() -> str:
    return datetime.now().astimezone().date().isoformat()


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def extract_snapshot_date(prompt: str, *, override: str | None = None) -> str:
    if override:
        return override
    m = _DATE_ISO_RE.search(prompt or "")
    if m:
        return m.group(1)
    if any(k in (prompt or "") for k in ("今天", "今日", "当天")):
        return default_snapshot_date()
    if any(k in (prompt or "") for k in ("昨天", "昨日")):
        return (datetime.now().astimezone().date() - timedelta(days=1)).isoformat()
    return default_snapshot_date()


def _match_job_name(text: str) -> str | None:
    """精确 job 名（含 run_reports 别名）。"""
    t = _normalize(text)
    if not t:
        return None
    # 去掉常见前缀
    for prefix in ("跑", "执行", "运行", "触发", "开始"):
        if t.startswith(prefix):
            t = t[len(prefix) :].strip()
    # 直接 job id
    if t in JOBS:
        return t
    aliases = {
        "all": "all",
        "daily": "daily",
        "pulse-daily": "pulse-daily",
        "pulse-task-daily": "pulse-task-daily",
        "pulse-pai-daily": "pulse-pai-daily",
        "pulse-member-daily": "pulse-member-daily",
        "team-weekly": "team-weekly",
        "team": "team-weekly",
        "weekly": "personal",
        "personal": "personal",
        "pulse": "pulse",
        "pai-daily": "pulse-pai-daily",
        "pai": "pulse-pai-daily",
        "insight": "insight",
        "sprint": "sprint",
        "task": "task",
        "member": "member",
    }
    return aliases.get(t)


def plan_from_job(job: str, *, snapshot_date: str | None = None) -> dict[str, Any]:
    key = job.strip()
    if key not in JOBS:
        known = ", ".join(sorted(JOBS))
        raise ValueError(f"unknown job '{job}'; known: {known}")
    snap = snapshot_date or default_snapshot_date()
    return plan_steps_dict(list(JOBS[key]), snapshot_date=snap, source=f"job:{key}")


def plan_from_prompt(prompt: str, *, snapshot_date: str | None = None) -> dict[str, Any]:
    text = (prompt or "").strip()
    if not text:
        return plan_from_job("daily", snapshot_date=snapshot_date)

    snap = extract_snapshot_date(text, override=snapshot_date)

    # 显式 job 名
    job = _match_job_name(text)
    if job:
        return plan_from_job(job, snapshot_date=snap)

    t = _normalize(text)
    selected: set[str] = set()

    def add(*ids: str) -> None:
        selected.update(ids)

    # 周报类（优先于泛化 pulse）
    if any(k in t for k in ("团队周报", "迭代周报", "全团队", "team weekly", "team-weekly")):
        add("team-weekly")
    elif any(k in t for k in ("个人周报", "我的周报", "personal", "研发周报")) and "团队" not in text:
        add("personal")

    # 排除语义：不要 task / member
    exclude_task = any(k in t for k in ("不要 task", "不含 task", "跳过 task", "不要任务", "不含任务"))
    exclude_member = any(k in t for k in ("不要 member", "不含 member", "跳过 member", "不要成员", "不含成员"))

    # 细粒度 pulse
    want_sprint = any(k in t for k in ("sprint", "pulse-daily", "项目快照", "项目进度", "迭代律动"))
    want_task = not exclude_task and any(
        k in t for k in ("task", "pulse-task", "任务快照", "任务日", "逾期", "即将逾期")
    )
    want_insight = any(
        k in t for k in (
            "insight", "pulse-pai", "pai-daily", "pai 洞察", "pai洞察",
            "project lead", "简报", "洞察",
        )
    ) or (("pai" in t or "洞察" in t) and "superteam-pai" not in t.replace(" ", ""))
    want_member = not exclude_member and any(
        k in t for k in ("member", "pulse-member", "成员大盘", "成员快照", "人员大盘", "超级成员")
    )

    # 泛化 pulse / 看板 / daily
    want_all_pulse = any(
        k in t for k in (
            "今日 pulse", "今日pulse", "跑 pulse", "pulse 全", "pulse全", "看板",
            "daily", "日快照", "四类", "全量 pulse", "更新看板", "pulse 入库",
        )
    ) or (("pulse" in t or "看板" in t) and not any([want_sprint, want_task, want_insight, want_member]))

    if want_all_pulse:
        add("pulse-daily", "pulse-task-daily", "pulse-pai-daily", "pulse-member-daily")
    else:
        if want_sprint:
            add("pulse-daily")
        if want_task:
            add("pulse-task-daily")
        if want_insight:
            add("pulse-pai-daily")
        if want_member:
            add("pulse-member-daily")

    if exclude_task:
        selected.discard("pulse-task-daily")
    if exclude_member:
        selected.discard("pulse-member-daily")

    if not selected:
        # 无法解析时：与 cron 默认一致
        add("pulse-daily", "pulse-task-daily", "pulse-pai-daily", "pulse-member-daily")

    ordered = expand_dependencies(sort_step_ids(list(selected)))
    reason = _infer_reason(text, ordered)
    plan = plan_steps_dict(ordered, snapshot_date=snap, source="prompt")
    plan["prompt"] = text
    plan["reason"] = reason
    return plan


def _infer_reason(text: str, step_ids: list[str]) -> str:
    if not text:
        return "empty prompt → default daily pulse pipeline"
    if len(step_ids) == len(STEPS) - 2:  # all pulse steps
        if "pulse" in text.lower() or "看板" in text:
            return "matched pulse/dashboard keywords → full daily pipeline"
    return f"matched keywords → steps: {', '.join(step_ids)}"


def plan(
    *,
    prompt: str | None = None,
    job: str | None = None,
    snapshot_date: str | None = None,
) -> dict[str, Any]:
    if job:
        return plan_from_job(job, snapshot_date=snapshot_date)
    return plan_from_prompt(prompt or "", snapshot_date=snapshot_date)
