"""PAI v2：以 Linear sprint 项目行为基础，为 Project Lead 生成项目简报。

无 SPI/RDI/OCI 等复合指标；信号直接来自 Linear 字段（进度、open、里程碑、risk_short、participants）。
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Literal

_SHARED = Path(__file__).resolve().parents[2] / "_shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))
from linear_profile import linear_workspace_from_url

PAI_VERSION = "2"

Severity = Literal["red", "yellow", "green"]
Signal = Literal[
    "milestone_critical",
    "blocked",
    "unassigned",
    "schedule_tight",
    "ownership_risk",
    "momentum_down",
    "stale_work",
    "healthy",
]

_RISK_PART_RE = re.compile(r"^(.+?)×(\d+)$")
_SEV_RANK = {"red": 3, "yellow": 2, "green": 1}

_SIGNAL_ORDER: tuple[Signal, ...] = (
    "milestone_critical",
    "blocked",
    "unassigned",
    "momentum_down",
    "schedule_tight",
    "ownership_risk",
    "stale_work",
    "healthy",
)


def parse_risk_short(risk_short: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for part in (risk_short or "").strip().split("；"):
        part = part.strip()
        if not part:
            continue
        m = _RISK_PART_RE.match(part)
        if m:
            out[m.group(1).strip()] = int(m.group(2))
    return out


def _parse_days(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _project_name(proj: dict[str, Any]) -> str:
    return str(proj.get("name") or "").strip()


def _norm_person(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _unassigned_open(proj: dict[str, Any], risk_counts: dict[str, int]) -> int:
    from_participants = 0
    for p in proj.get("participants") or []:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()
        if name in ("未分配", "Unassigned", ""):
            from_participants = max(from_participants, int(p.get("open_count") or 0))
    return max(risk_counts.get("未分配", 0), from_participants)


def _top_open_owner(linear: dict[str, Any]) -> tuple[str, int]:
    best_name, best_n = "", 0
    for p in linear.get("participants_open") or []:
        name = str(p.get("name") or "").strip()
        if not name or name in ("未分配", "Unassigned"):
            continue
        n = int(p.get("open_count") or 0)
        if n > best_n:
            best_name, best_n = name, n
    return best_name, best_n


def build_linear_snapshot(proj: dict[str, Any]) -> dict[str, Any]:
    risk_counts = parse_risk_short(str(proj.get("risk_short") or ""))
    open_total = int(proj.get("open_total") or 0)
    participants = [
        p for p in (proj.get("participants") or [])
        if isinstance(p, dict) and int(p.get("open_count") or 0) > 0
    ]
    participants.sort(key=lambda p: -int(p.get("open_count") or 0))
    days = _parse_days(proj.get("days_to_milestone"))
    milestone = str(proj.get("next_milestone") or "").strip() or None
    if milestone in ("—", "-", "None"):
        milestone = None

    return {
        "project_url": proj.get("project_url") or proj.get("url"),
        "status": proj.get("status") or proj.get("status_label"),
        "linear_status": proj.get("linear_status"),
        "linear_status_type": proj.get("linear_status_type"),
        "progress_done_pct": proj.get("progress_done_pct"),
        "progress_label": proj.get("progress_label"),
        "open_total": open_total,
        "done": int(proj.get("done") or 0),
        "in_progress": int(proj.get("in_progress") or 0),
        "todo": int(proj.get("todo") or 0),
        "backlog": int(proj.get("backlog") or 0),
        "next_milestone": milestone,
        "days_to_milestone": days,
        "risk_short": str(proj.get("risk_short") or ""),
        "risk_counts": risk_counts,
        "unassigned_open": _unassigned_open(proj, risk_counts),
        "participants_open": [
            {
                "name": str(p.get("name") or "").strip() or None,
                "open_count": int(p.get("open_count") or 0),
                "task_count": int(p.get("task_count") or 0),
            }
            for p in participants[:5]
        ],
    }


def _momentum_delta(
    linear: dict[str, Any],
    yesterday: dict[str, Any] | None,
) -> dict[str, Any]:
    if not yesterday:
        return {"has_slip": False, "details": []}
    details: list[str] = []
    y_open = int(yesterday.get("open_total") or 0)
    open_total = int(linear.get("open_total") or 0)
    if open_total > y_open:
        details.append(f"未完成 +{open_total - y_open}（{y_open}→{open_total}）")
    try:
        pct = float(linear["progress_done_pct"])
        y_pct = float(yesterday["progress_done_pct"])
        if pct < y_pct:
            details.append(f"进度 {pct - y_pct:.0f}%（{y_pct}%→{pct}%）")
    except (TypeError, ValueError, KeyError):
        pass
    return {"has_slip": bool(details), "details": details}


def _detect_signals(
    linear: dict[str, Any],
    *,
    yesterday: dict[str, Any] | None = None,
) -> dict[Signal, Severity]:
    """各 Linear 信号的严重度（无复合指标）。"""
    out: dict[Signal, Severity] = {}
    open_total = int(linear.get("open_total") or 0)
    days = linear.get("days_to_milestone")
    risk = linear.get("risk_counts") or {}
    unassigned = int(linear.get("unassigned_open") or 0)
    blocked = risk.get("Blocked", 0) + risk.get("受阻", 0)
    stale = risk.get("久未更新", 0)
    top_name, top_open = _top_open_owner(linear)
    momentum = _momentum_delta(linear, yesterday)

    if days is not None and days <= 1 and open_total > 0:
        out["milestone_critical"] = "red"
    elif days is not None and days <= 3 and open_total > 0:
        out["schedule_tight"] = "red" if days <= 1 else "yellow"

    if blocked >= 2:
        out["blocked"] = "red"
    elif blocked == 1:
        out["blocked"] = "yellow"

    if unassigned >= 2:
        out["unassigned"] = "red"
    elif unassigned == 1:
        out["unassigned"] = "yellow"

    if momentum["has_slip"]:
        out["momentum_down"] = "red" if any("进度" in d for d in momentum["details"]) else "yellow"

    if (
        open_total >= 3
        and days is not None
        and days <= 7
        and "schedule_tight" not in out
        and "milestone_critical" not in out
    ):
        out["schedule_tight"] = "yellow"

    if open_total >= 2 and top_open >= 2:
        share = top_open / max(1, open_total)
        if share >= 0.7 and top_open >= 4:
            out["ownership_risk"] = "red"
        elif share >= 0.55 and top_open >= 3:
            out["ownership_risk"] = "yellow"

    if stale >= 2:
        out["stale_work"] = "yellow"

    if not out:
        out["healthy"] = "green"
    return out


def pick_primary_signal(signals: dict[Signal, Severity]) -> Signal:
    if "milestone_critical" in signals:
        return "milestone_critical"
    for key in _SIGNAL_ORDER:
        if key in signals and key != "healthy":
            return key
    return "healthy"


def _overall_health(signals: dict[Signal, Severity]) -> Severity:
    worst = "green"
    for sev in signals.values():
        if _SEV_RANK.get(sev, 0) > _SEV_RANK.get(worst, 0):
            worst = sev  # type: ignore[assignment]
    return worst  # type: ignore[return-value]


def _risk_phrase(risk_counts: dict[str, int]) -> str:
    if not risk_counts:
        return ""
    return "、".join(f"{k}×{v}" for k, v in sorted(risk_counts.items(), key=lambda x: -x[1]))


def _milestone_day_phrase(days: int | None) -> str:
    """按 snapshot 日距里程碑天数生成表述（与 sprint ``days_to_milestone`` 一致）。"""
    if days is None:
        return "里程碑临近"
    if days < 0:
        return f"里程碑已过期 {abs(days)} 天"
    if days == 0:
        return "今天就是"
    if days == 1:
        return "明天就是"
    return f"距里程碑还有 {days} 天"


def _milestone_critical_headline(days: int | None) -> str:
    if days == 0:
        return "发布日就是今天：交付取舍还没写下来"
    if days == 1:
        return "发布日前夜：必达清单还没写下来"
    return "里程碑临近：交付取舍还没写下来"


def _situation_text(leader: str, linear: dict[str, Any], momentum: dict[str, Any]) -> str:
    bits: list[str] = []
    pct = linear.get("progress_done_pct")
    if pct is not None:
        bits.append(f"项目进度 {pct}%")
    open_total = linear.get("open_total")
    if open_total:
        bits.append(f"{open_total} 条 Linear 未完成")
    bits.append(
        f"进行中 {linear.get('in_progress')} / 待办 {linear.get('todo')}"
        + (f"+backlog {linear.get('backlog')}" if linear.get("backlog") else "")
    )
    ms, days = linear.get("next_milestone"), linear.get("days_to_milestone")
    if ms and days is not None:
        if days == 0:
            bits.append(f"里程碑「{ms}」今天到期")
        elif days < 0:
            bits.append(f"里程碑「{ms}」已过期 {abs(days)} 天")
        else:
            bits.append(f"里程碑「{ms}」剩 {days} 天")
    risk = _risk_phrase(linear.get("risk_counts") or {})
    if risk:
        bits.append(f"任务风险 {risk}")
    if momentum.get("details"):
        bits.append("较昨日 " + "；".join(momentum["details"]))
    return f"【{leader or '负责人'}】Linear：" + "；".join(bits) + "。"


def _leader_moves(
    signal: Signal,
    *,
    linear: dict[str, Any],
    momentum: dict[str, Any],
) -> list[dict[str, Any]]:
    risk_counts = linear.get("risk_counts") or {}
    unassigned = int(linear.get("unassigned_open") or 0)
    open_total = int(linear.get("open_total") or 0)
    milestone = linear.get("next_milestone") or "下一节点"
    days = linear.get("days_to_milestone")
    top_name, top_open = _top_open_owner(linear)
    blocked = risk_counts.get("Blocked", 0) + risk_counts.get("受阻", 0)
    moves: list[dict[str, Any]] = []

    if signal == "milestone_critical":
        day_hint = "今天到期" if days == 0 else (f"剩 {days} 天" if days is not None else "临近")
        moves.append({
            "what": f"在 Linear 写下「{milestone}」必达清单 vs 可延期清单，并 @ 全员",
            "why": f"{day_hint}仍有 {open_total} 条 open，没有书面取舍等于默认延期",
            "linear_signal": f"days={days}, open={open_total}",
        })
    elif signal == "blocked":
        moves.append({
            "what": f"对 {blocked} 条 Blocked issue 做 unblock 决策：升级、换人、或砍需求",
            "why": "阻塞不会自己消失，只有 Project Lead 能决定代价",
            "linear_signal": f"受阻/Blocked×{blocked}",
        })
    elif signal == "unassigned":
        moves.append({
            "what": f"亲自在 Linear assign 掉 {unassigned} 条未分配任务（今日 standup 前）",
            "why": "未分配 = 无人负责 = Lead 在替全队背锅",
            "linear_signal": f"未分配×{unassigned}",
        })
    elif signal == "schedule_tight":
        moves.append({
            "what": "召开 15 分钟 scope 裁决：砍掉或推迟非关键 issue，更新里程碑或 target date",
            "why": f"距「{milestone}」仅 {days} 天、{open_total} 条未完成，加班救不了范围膨胀",
            "linear_signal": f"days={days}, open={open_total}",
        })
    elif signal == "ownership_risk":
        owner = top_name or "主力同学"
        moves.append({
            "what": f"为 {owner} 的 {top_open} 条 open 指定备份负责人，或拆出并行子任务",
            "why": "单人扛盘时项目速度上限 = 一个人的带宽",
            "linear_signal": f"{owner} open={top_open}/{open_total}",
        })
    elif signal == "momentum_down":
        desc = "；".join(momentum.get("details") or [])
        moves.append({
            "what": "公布「今日必关闭」的 1–3 条 issue，并在晚 standup 验收状态",
            "why": desc or "较昨日动量在下滑，团队需要看见 closure",
            "linear_signal": "momentum_down",
        })
    elif signal == "stale_work":
        stale = risk_counts.get("久未更新", 0)
        moves.append({
            "what": f"逐条过 {stale} 条久未更新 issue：关单、换人、或拆小",
            "why": "沉默的任务在吞噬里程碑可信度",
            "linear_signal": f"久未更新×{stale}",
        })
    else:
        moves.append({
            "what": "保护专注：新需求进 backlog，今日不插播 scope",
            "why": "Linear 节奏健康，Lead 最大的贡献是不添乱",
            "linear_signal": "healthy",
        })

    if signal != "milestone_critical" and days is not None and days <= 3 and open_total > 0:
        moves.insert(0, {
            "what": f"对齐「{milestone}」必达范围（剩 {days} 天）",
            "why": "里程碑临近，书面取舍优先于催促",
            "linear_signal": f"days={days}",
        })
    return moves[:3]


def _briefing_copy(
    signal: Signal,
    *,
    leader: str,
    project: str,
    linear: dict[str, Any],
    momentum: dict[str, Any],
) -> dict[str, str]:
    who = leader or "负责人"
    open_total = int(linear.get("open_total") or 0)
    milestone = linear.get("next_milestone") or "下一节点"
    days = linear.get("days_to_milestone")
    risk_line = _risk_phrase(linear.get("risk_counts") or {})
    top_name, top_open = _top_open_owner(linear)
    mom = "；".join(momentum.get("details") or [])

    headlines: dict[Signal, str] = {
        "milestone_critical": _milestone_critical_headline(days),
        "blocked": "有任务卡住了整条链路",
        "unassigned": "有人在等你知道该谁干",
        "schedule_tight": "时间不够了，范围还没收",
        "ownership_risk": "看起来有人在干，其实只有一个人在扛",
        "momentum_down": "团队在输，即使没人说出口",
        "stale_work": "有些任务在 Linear 里已经「失联」",
        "healthy": "节奏尚可——今天别亲手打破",
    }
    asks: dict[Signal, str] = {
        "milestone_critical": (
            f"{who}，{_milestone_day_phrase(days)}「{milestone}」，Linear 里还有 {open_total} 条 open。"
            f"作为项目负责人，你今天只做一件事：写下必达 vs 可延期，并同步给全员。"
        ),
        "blocked": (
            f"{who}，「{project}」有阻塞任务（{risk_line or 'Blocked/受阻'}）。"
            f"今天你拍板：升级、换人、还是砍需求——不能留给 IC 自己猜。"
        ),
        "unassigned": (
            f"{who}，{open_total} 条未完成里有未分配任务。"
            f"在 Linear 里 assign 是最小的领导力动作——今天 standup 前做完。"
        ),
        "schedule_tight": (
            f"{who}，「{project}」距「{milestone}」仅 {days} 天，{open_total} 条未完成。"
            f"Leader 不是催更机器——今天请砍掉或推迟非关键 path。"
        ),
        "ownership_risk": (
            f"{who}，{top_name or '主力'} 一人扛着 {top_open}/{open_total} 条 open。"
            f"项目速度的上限是一个人的带宽——今天指定第二负责人。"
        ),
        "momentum_down": (
            f"{who}，较昨日 {mom or '交付在下滑'}。"
            f"团队需要一次「赢」——公开今日必达清单并验收 closure。"
        ),
        "stale_work": (
            f"{who}，Linear 标记久未更新：{risk_line}。"
            f"这些 issue 不会自己变好——今天 triage：关单、派活、或升级。"
        ),
        "healthy": (
            f"{who}，「{project}」Linear 节奏健康。"
            f"Leader 今天的功课是保护专注：新需求进 backlog，不插播 scope。"
        ),
    }
    moves = _leader_moves(signal, linear=linear, momentum=momentum)
    return {
        "headline": headlines[signal],
        "leader_ask": asks[signal],
        "today_one_thing": moves[0]["what"] if moves else "保持节奏，关注里程碑偏差",
        "signal": signal,
    }


def _attention_score(health: Severity, linear: dict[str, Any], signals: dict[Signal, Severity]) -> int:
    score = sum(40 if s == "red" else 22 if s == "yellow" else 0 for s in signals.values())
    days = linear.get("days_to_milestone")
    open_total = int(linear.get("open_total") or 0)
    if days is not None and open_total > 0:
        if days <= 1:
            score += 55
        elif days <= 3:
            score += 35
        elif days <= 7:
            score += 15
    if int(linear.get("unassigned_open") or 0) > 0:
        score += 12
    if health == "red":
        score += 20
    elif health == "yellow":
        score += 8
    return score


def _resolve_leader_profile_url(
    leader: str | None,
    proj: dict[str, Any],
    *,
    profile_index: dict[str, str],
) -> str | None:
    raw = proj.get("leader_profile_url")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if leader:
        return profile_index.get(_norm_person(leader))
    return None


def _workspace_from_sprint_projects(projects: list[dict[str, Any]]) -> str:
    for p in projects:
        if not isinstance(p, dict):
            continue
        url = p.get("project_url") or p.get("url")
        if url:
            return linear_workspace_from_url(str(url))
    return linear_workspace_from_url(None)


def build_project_briefing(
    proj: dict[str, Any],
    *,
    yesterday: dict[str, Any] | None = None,
    leader_profile_url: str | None = None,
) -> dict[str, Any] | None:
    name = _project_name(proj)
    if not name:
        return None

    leader = str(proj.get("leader") or "").strip() or None
    linear = build_linear_snapshot(proj)
    y_linear = build_linear_snapshot(yesterday) if yesterday else None
    momentum = _momentum_delta(linear, y_linear)
    signals = _detect_signals(linear, yesterday=y_linear)
    signal = pick_primary_signal(signals)
    health = _overall_health(signals)
    briefing = _briefing_copy(
        signal, leader=leader or "负责人", project=name, linear=linear, momentum=momentum,
    )

    return {
        "project": name,
        "leader": leader,
        "leader_profile_url": leader_profile_url,
        "health": health,
        "attention_score": _attention_score(health, linear, signals),
        "linear": linear,
        "momentum": momentum,
        "signals": {k: v for k, v in signals.items()},
        "primary_signal": signal,
        "briefing": {
            **briefing,
            "situation": _situation_text(leader or "负责人", linear, momentum),
        },
        "moves": _leader_moves(signal, linear=linear, momentum=momentum),
    }


_SIGNAL_LABEL: dict[str, str] = {
    "milestone_critical": "里程碑临界",
    "blocked": "任务阻塞",
    "unassigned": "未分配",
    "schedule_tight": "排期偏紧",
    "ownership_risk": "责任集中",
    "momentum_down": "交付下滑",
    "stale_work": "久未更新",
    "healthy": "节奏健康",
}


def _signal_problem_detail(signal: str, linear: dict[str, Any], momentum: dict[str, Any]) -> str:
    risk = linear.get("risk_counts") or {}
    open_total = int(linear.get("open_total") or 0)
    days = linear.get("days_to_milestone")
    milestone = linear.get("next_milestone") or "下一节点"
    unassigned = int(linear.get("unassigned_open") or 0)
    blocked = risk.get("Blocked", 0) + risk.get("受阻", 0)
    top_name, top_open = _top_open_owner(linear)

    details: dict[str, str] = {
        "milestone_critical": (
            f"「{milestone}」今天到期，{open_total} 条未完成"
            if days == 0
            else f"「{milestone}」剩 {days} 天，{open_total} 条未完成"
        ) if days is not None and days <= 1 else f"「{milestone}」临近，{open_total} 条未完成",
        "blocked": f"Blocked/受阻 {blocked} 条",
        "unassigned": f"未分配 {unassigned} 条",
        "schedule_tight": f"距「{milestone}」{days} 天，{open_total} 条 open",
        "ownership_risk": f"{top_name or '主力'} 承担 {top_open}/{open_total} 条 open",
        "momentum_down": "；".join(momentum.get("details") or []) or "较昨日交付变差",
        "stale_work": f"久未更新 {risk.get('久未更新', 0)} 条",
    }
    return details.get(signal, _risk_phrase(risk) or "")


def _build_problems(
    signals: dict[str, str],
    linear: dict[str, Any],
    momentum: dict[str, Any],
) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    for sig, sev in sorted(
        signals.items(),
        key=lambda x: (-_SEV_RANK.get(x[1], 0), _SIGNAL_ORDER.index(x[0]) if x[0] in _SIGNAL_ORDER else 99),
    ):
        if sig == "healthy":
            continue
        problems.append({
            "signal": sig,
            "signal_label": _SIGNAL_LABEL.get(sig, sig),
            "severity": sev,
            "detail": _signal_problem_detail(sig, linear, momentum),
        })
    risk_counts = linear.get("risk_counts") or {}
    seen_signals = set(signals.keys())
    for label, count in sorted(risk_counts.items(), key=lambda x: -x[1]):
        if count <= 0:
            continue
        if label in ("未分配",) and "unassigned" in seen_signals:
            continue
        if label in ("Blocked", "受阻") and "blocked" in seen_signals:
            continue
        if label == "久未更新" and "stale_work" in seen_signals:
            continue
        problems.append({
            "signal": "linear_risk",
            "signal_label": label,
            "severity": "red" if count >= 2 else "yellow",
            "detail": f"{label}×{count}",
        })
    return problems


def _project_entry_for_leader(row: dict[str, Any]) -> dict[str, Any]:
    """单项目条目（挂在 by_leader[].projects 下）。"""
    linear = row.get("linear") or {}
    momentum = row.get("momentum") or {"details": []}
    problems = _build_problems(row.get("signals") or {}, linear, momentum)
    return {
        "project": row.get("project"),
        "project_url": linear.get("project_url"),
        "leader_profile_url": row.get("leader_profile_url"),
        "health": row.get("health"),
        "attention_score": row.get("attention_score"),
        "status": linear.get("status"),
        "linear_status": linear.get("linear_status"),
        "progress_done_pct": linear.get("progress_done_pct"),
        "open_total": linear.get("open_total"),
        "next_milestone": linear.get("next_milestone"),
        "days_to_milestone": linear.get("days_to_milestone"),
        "primary_signal": row.get("primary_signal"),
        "signals": row.get("signals"),
        "risks": {
            "risk_short": linear.get("risk_short"),
            "risk_counts": linear.get("risk_counts"),
            "unassigned_open": linear.get("unassigned_open"),
        },
        "problems": problems,
        "briefing": row.get("briefing"),
        "moves": row.get("moves"),
    }


def _merge_risk_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for row in rows:
        for label, count in ((row.get("linear") or {}).get("risk_counts") or {}).items():
            merged[label] = merged.get(label, 0) + int(count)
    return dict(sorted(merged.items(), key=lambda x: -x[1]))


def build_by_leader_index(briefings: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in briefings:
        leader = str(row.get("leader") or "").strip() or "（未设 Lead）"
        buckets.setdefault(leader, []).append(row)

    out: dict[str, Any] = {}
    for leader, rows in sorted(buckets.items()):
        rows_sorted = sorted(rows, key=lambda r: -int(r.get("attention_score") or 0))
        project_entries = [_project_entry_for_leader(r) for r in rows_sorted]
        hot = [p for p in project_entries if p.get("health") != "green"]
        all_problems: list[dict[str, Any]] = []
        for pe in project_entries:
            for prob in pe.get("problems") or []:
                all_problems.append({**prob, "project": pe.get("project")})
        all_problems.sort(
            key=lambda p: (-_SEV_RANK.get(str(p.get("severity") or "green"), 0), str(p.get("project") or "")),
        )
        worst_health: Severity = "green"
        for r in rows_sorted:
            h = str(r.get("health") or "green")
            if _SEV_RANK.get(h, 0) > _SEV_RANK.get(worst_health, 0):
                worst_health = h  # type: ignore[assignment]
        top = project_entries[0] if project_entries else None
        open_sum = sum(int((p.get("open_total") or 0)) for p in project_entries)

        out[leader] = {
            "leader": leader,
            "linear_profile_url": next(
                (
                    str(r.get("leader_profile_url") or "").strip()
                    for r in rows_sorted
                    if str(r.get("leader_profile_url") or "").strip()
                ),
                None,
            ),
            "health": worst_health,
            "project_count": len(project_entries),
            "needs_attention": len(hot),
            "open_total": open_sum,
            "risks_aggregate": _merge_risk_counts(rows_sorted),
            "problems": all_problems,
            "headline": (top or {}).get("briefing", {}).get("headline"),
            "leader_ask": (top or {}).get("briefing", {}).get("leader_ask"),
            "today_one_thing": (top or {}).get("briefing", {}).get("today_one_thing"),
            "top_project": (top or {}).get("project"),
            "projects": project_entries,
        }
    return out


def build_pai_summary(briefings: list[dict[str, Any]], *, viewer: str | None = None) -> str:
    n = len(briefings)
    if not n:
        return "今日无进行中 Linear 项目。"
    leaders = {str(p.get("leader") or "").strip() for p in briefings if p.get("leader")}
    hot = [p for p in briefings if p.get("health") != "green"]
    red = sum(1 for p in briefings if p.get("health") == "red")
    who = f"，聚焦 {viewer}" if viewer else ""
    return (
        f"PAI v{PAI_VERSION}：{n} 个 Linear 项目、{len(leaders)} 位 Project Lead{who}；"
        f"{len(hot)} 个需今日介入（红 {red}）。详见 by_leader。"
    )


def build_pai_payload(
    sprint_payload: dict[str, Any],
    *,
    yesterday_sprint_payload: dict[str, Any] | None = None,
    snapshot_date: date,
    viewer: str | None = None,
    leader_profile_index: dict[str, str] | None = None,
) -> dict[str, Any]:
    projects_in = sprint_payload.get("projects") or []
    workspace = _workspace_from_sprint_projects(projects_in)
    profile_index = dict(leader_profile_index or {})

    y_index = {
        _project_name(p): p
        for p in (yesterday_sprint_payload or {}).get("projects") or []
        if _project_name(p)
    }

    briefings: list[dict[str, Any]] = []
    for p in projects_in:
        name = _project_name(p)
        if not name:
            continue
        leader = str(p.get("leader") or "").strip() or None
        profile_url = _resolve_leader_profile_url(leader, p, profile_index=profile_index)
        row = build_project_briefing(
            p,
            yesterday=y_index.get(name),
            leader_profile_url=profile_url,
        )
        if not row:
            continue
        if viewer and _norm_person(str(row.get("leader") or "")) != _norm_person(viewer):
            continue
        briefings.append(row)

    briefings.sort(key=lambda r: (-int(r.get("attention_score") or 0), str(r.get("project") or "")))
    by_leader = build_by_leader_index(briefings)
    hot_count = sum(v.get("needs_attention", 0) for v in by_leader.values())

    return {
        "version": PAI_VERSION,
        "snapshot_date": snapshot_date.isoformat(),
        "team": sprint_payload.get("team") or "trex",
        "iso_week": sprint_payload.get("iso_week"),
        "viewer": viewer,
        "data_source": "linear_sprint",
        "linear_workspace": workspace,
        "summary": build_pai_summary(briefings, viewer=viewer),
        "project_count": len(briefings),
        "leader_count": len(by_leader),
        "needs_attention_count": hot_count,
        "by_leader": by_leader,
    }
