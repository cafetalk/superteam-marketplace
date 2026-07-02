"""PAI 调度：可编排 step 与预定义 job（与 run_reports.sh 对齐）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REPO_ROOT_NAME = "superteam"


@dataclass(frozen=True)
class StepDef:
    id: str
    skill: str
    script: str  # relative to skills/
    description: str
    requires_pg: bool = True
    pulse_upload: bool = False  # 追加 --date --out-dir --upload
    depends_on: tuple[str, ...] = ()
    extra_args: tuple[str, ...] = ()


# 全局拓扑序（规划器按此排序选中 step）
STEP_ORDER: tuple[str, ...] = (
    "pulse-daily",
    "pulse-task-daily",
    "pulse-pai-daily",
    "pulse-member-daily",
    "team-weekly",
    "personal",
)

STEPS: dict[str, StepDef] = {
    "pulse-daily": StepDef(
        id="pulse-daily",
        skill="superteam-report",
        script="superteam-report/scripts/snapshot_sprint.py",
        description="Sprint 项目日快照",
        pulse_upload=True,
    ),
    "pulse-task-daily": StepDef(
        id="pulse-task-daily",
        skill="superteam-report",
        script="superteam-report/scripts/snapshot_task.py",
        description="任务日快照",
        pulse_upload=True,
    ),
    "pulse-pai-daily": StepDef(
        id="pulse-pai-daily",
        skill="superteam-report-insight",
        script="superteam-report-insight/scripts/snapshot_pai.py",
        description="PAI 洞察简报（依赖 sprint）",
        pulse_upload=True,
        depends_on=("pulse-daily",),
    ),
    "pulse-member-daily": StepDef(
        id="pulse-member-daily",
        skill="superteam-report",
        script="superteam-report/scripts/snapshot_member.py",
        description="成员周快照",
        pulse_upload=True,
    ),
    "team-weekly": StepDef(
        id="team-weekly",
        skill="superteam-report",
        script="superteam-report/scripts/generate_team_weekly_report.py",
        description="团队迭代周报",
        requires_pg=False,
        pulse_upload=False,
    ),
    "personal": StepDef(
        id="personal",
        skill="superteam-report",
        script="superteam-report/scripts/generate_report.py",
        description="个人研发周报数据",
        requires_pg=False,
        pulse_upload=False,
        extra_args=("--format", "json"),
    ),
}

# 与 run_reports.sh 子命令同名
JOBS: dict[str, tuple[str, ...]] = {
    "all": (
        "pulse-daily",
        "pulse-task-daily",
        "pulse-pai-daily",
        "pulse-member-daily",
    ),
    "daily": (
        "pulse-daily",
        "pulse-task-daily",
        "pulse-pai-daily",
        "pulse-member-daily",
    ),
    "pulse-daily": ("pulse-daily",),
    "pulse-task-daily": ("pulse-task-daily",),
    "pulse-pai-daily": ("pulse-pai-daily",),
    "pulse-member-daily": ("pulse-member-daily",),
    "team-weekly": ("team-weekly",),
    "personal": ("personal",),
    # 别名
    "pulse": (
        "pulse-daily",
        "pulse-task-daily",
        "pulse-pai-daily",
        "pulse-member-daily",
    ),
    "insight": ("pulse-pai-daily",),
    "pai": ("pulse-pai-daily",),
    "sprint": ("pulse-daily",),
    "task": ("pulse-task-daily",),
    "member": ("pulse-member-daily",),
}


def sort_step_ids(step_ids: list[str]) -> list[str]:
    order = {sid: i for i, sid in enumerate(STEP_ORDER)}
    return sorted(step_ids, key=lambda s: order.get(s, 999))


def expand_dependencies(step_ids: list[str]) -> list[str]:
    """按 depends_on 自动补齐前置 step。"""
    selected = set(step_ids)
    changed = True
    while changed:
        changed = False
        for sid in list(selected):
            step = STEPS.get(sid)
            if not step:
                continue
            for dep in step.depends_on:
                if dep not in selected:
                    selected.add(dep)
                    changed = True
    return sort_step_ids([s for s in STEP_ORDER if s in selected])


def plan_steps_dict(step_ids: list[str], *, snapshot_date: str, source: str) -> dict[str, Any]:
    ordered = expand_dependencies(step_ids)
    return {
        "version": 1,
        "planner": "rules",
        "source": source,
        "snapshot_date": snapshot_date,
        "steps": [
            {
                "id": sid,
                "skill": STEPS[sid].skill,
                "script": STEPS[sid].script,
                "description": STEPS[sid].description,
            }
            for sid in ordered
            if sid in STEPS
        ],
    }
