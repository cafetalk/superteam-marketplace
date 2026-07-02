"""执行 PAI 规划：子进程调用 worker 脚本（结构化 CLI，不传用户提示词）。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_SKILLS = _SCRIPTS.parent.parent
_REPO_ROOT = _SKILLS.parent
_SHARED = _SKILLS / "_shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from config import env, pulse_output_root  # noqa: E402

from _registry import STEPS, StepDef  # noqa: E402


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", file=sys.stderr)


def resolve_python_cmd() -> list[str]:
    uv_bin = env("SUPERTEAM_UV")
    if uv_bin and Path(uv_bin).is_file():
        return [uv_bin, "run", "--python", "python3"]
    uv = shutil.which("uv")
    if uv:
        return [uv, "run", "--python", "python3"]
    vpy = _REPO_ROOT / ".venv" / "bin" / "python"
    if vpy.is_file():
        _log(f"WARN: uv not in PATH; using {vpy}")
        return [str(vpy)]
    raise RuntimeError(
        "未找到 uv 且不存在 .venv/bin/python。请安装 uv 或在仓库执行 ./setup.sh",
    )


def require_pg_url() -> None:
    if not env("KB_TREX_PG_URL"):
        raise RuntimeError(
            "KB_TREX_PG_URL 未设置。请在 ~/.superteam/config 配置后再跑 pulse 入库步骤",
        )


def build_argv(step: StepDef, *, snapshot_date: str, pulse_dir: Path, extra: list[str]) -> list[str]:
    script = _SKILLS / step.script
    if not script.is_file():
        raise FileNotFoundError(f"worker script not found: {step.script}")
    cmd = resolve_python_cmd() + [str(script)]
    if step.pulse_upload:
        cmd.extend(["--date", snapshot_date, "--out-dir", str(pulse_dir), "--upload"])
    if step.extra_args:
        cmd.extend(step.extra_args)
    if extra:
        cmd.extend(extra)
    return cmd


def execute_plan(
    plan: dict[str, Any],
    *,
    extra_args: list[str] | None = None,
    continue_on_error: bool = True,
) -> dict[str, Any]:
    """运行 plan 中各 step；不把 plan['prompt'] 传给 worker。"""
    snapshot_date = plan.get("snapshot_date") or datetime.now().astimezone().date().isoformat()
    pulse_dir = pulse_output_root()
    pulse_dir.mkdir(parents=True, exist_ok=True)
    (pulse_dir / snapshot_date).mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    any_fail = False
    forwarded = list(extra_args or [])

    for item in plan.get("steps") or []:
        sid = item["id"]
        step = STEPS.get(sid)
        if not step:
            results.append({"id": sid, "status": "skipped", "error": "unknown step"})
            any_fail = True
            if not continue_on_error:
                break
            continue

        if step.requires_pg:
            require_pg_url()

        step_extra = forwarded if sid in ("team-weekly", "personal") else []
        argv = build_argv(step, snapshot_date=snapshot_date, pulse_dir=pulse_dir, extra=step_extra)

        _log(f"--- {sid} start ---")
        _log(f"exec: {' '.join(argv)}")

        proc = subprocess.run(argv, cwd=str(_REPO_ROOT), env=os.environ.copy())
        ok = proc.returncode == 0
        results.append({
            "id": sid,
            "skill": step.skill,
            "script": step.script,
            "exit_code": proc.returncode,
            "status": "ok" if ok else "failed",
        })
        _log(f"--- {sid} {'done' if ok else 'FAILED'} (exit={proc.returncode}) ---")

        if not ok:
            any_fail = True
            if not continue_on_error:
                break

    return {
        "plan": plan,
        "results": results,
        "status": "failed" if any_fail else "ok",
    }
