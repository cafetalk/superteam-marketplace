#!/usr/bin/env python3
"""PAI 调度框架（B 方案）：规则规划 + worker 执行 + 定时注册。

Usage:
  python skills/superteam-pai/scripts/run_pai.py --job daily
  python skills/superteam-pai/scripts/run_pai.py schedule add --job daily --every 3h
  python skills/superteam-pai/scripts/run_pai.py schedule run-due
  python skills/superteam-pai/scripts/run_pai.py "每3小时刷新看板" --schedule
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _executor import execute_plan  # noqa: E402
from _planner import plan  # noqa: E402
from _registry import JOBS  # noqa: E402
from _scheduler import (  # noqa: E402
    add_schedule,
    disable_schedule,
    handle_schedule_intent,
    list_schedules,
    parse_schedule_intent,
    run_due_schedules,
    schedules_path,
)


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _build_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="superteam-pai 立即执行")
    parser.add_argument("prompt", nargs="?", default=None)
    parser.add_argument("--prompt", dest="prompt_opt", default=None)
    parser.add_argument("--job", choices=sorted(JOBS.keys()), default=None)
    parser.add_argument("--date", dest="snapshot_date", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--schedule", action="store_true")
    parser.add_argument("--run-now", action="store_true")
    parser.add_argument("extra", nargs=argparse.REMAINDER)
    return parser


def _recover_flags_from_extra(args: argparse.Namespace) -> list[str]:
    """REMAINDER 会把 positional 之后的 --flag 吞进 extra，需手动还原。"""
    extra = [x for x in (args.extra or []) if x != "--"]
    for flag, attr in (("--schedule", "schedule"), ("--run-now", "run_now")):
        if flag in extra:
            setattr(args, attr, True)
            extra = [x for x in extra if x != flag]
    return extra


def _run_once(argv: list[str]) -> int:
    args = _build_run_parser().parse_args(argv)
    prompt = args.prompt_opt or args.prompt
    extra = _recover_flags_from_extra(args)

    if args.schedule and prompt:
        intent = parse_schedule_intent(prompt)
        if intent:
            try:
                out = handle_schedule_intent(intent, run_now=args.run_now)
            except ValueError as e:
                _print_json({"status": "error", "error": str(e)})
                return 1
            _print_json(out)
            return 0

    try:
        execution_plan = plan(prompt=prompt, job=args.job, snapshot_date=args.snapshot_date)
    except ValueError as e:
        _print_json({"status": "error", "error": str(e)})
        return 1

    if args.dry_run:
        _print_json({"status": "planned", "plan": execution_plan})
        return 0

    try:
        outcome = execute_plan(execution_plan, extra_args=extra, continue_on_error=not args.fail_fast)
    except (RuntimeError, FileNotFoundError) as e:
        _print_json({"status": "error", "error": str(e), "plan": execution_plan})
        return 1

    _print_json(outcome)
    return 0 if outcome.get("status") == "ok" else 1


def _schedule_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="superteam-pai 定时任务")
    sub = parser.add_subparsers(dest="cmd", required=True)

    add_p = sub.add_parser("add")
    add_p.add_argument("--job", choices=sorted(JOBS.keys()), default="daily")
    add_p.add_argument("--every", default=None)
    add_p.add_argument("--id", dest="id", default=None)
    add_p.add_argument("--note", default=None)
    add_p.add_argument("--run-now", action="store_true")

    sub.add_parser("list")
    dis_p = sub.add_parser("disable")
    dis_p.add_argument("--id", required=True)

    due_p = sub.add_parser("run-due")
    due_p.add_argument("--dry-run", action="store_true")
    due_p.add_argument("--fail-fast", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "add":
        try:
            out = add_schedule(
                job=args.job,
                every=args.every,
                schedule_id=args.id,
                note=args.note,
                run_now=args.run_now,
            )
        except ValueError as e:
            _print_json({"status": "error", "error": str(e)})
            return 1
        _print_json(out)
        return 0

    if args.cmd == "list":
        _print_json({"status": "ok", "path": str(schedules_path()), "schedules": list_schedules()})
        return 0

    if args.cmd == "disable":
        try:
            out = disable_schedule(args.id)
        except ValueError as e:
            _print_json({"status": "error", "error": str(e)})
            return 1
        _print_json(out)
        return 0

    out = run_due_schedules(execute_plan, dry_run=args.dry_run, fail_fast=args.fail_fast)
    _print_json(out)
    if args.dry_run:
        return 0
    failed = [r for r in out.get("runs") or [] if r.get("status") not in ("ok", "planned")]
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if argv and argv[0] == "schedule":
        return _schedule_main(argv[1:])
    return _run_once(argv)


if __name__ == "__main__":
    sys.exit(main())
