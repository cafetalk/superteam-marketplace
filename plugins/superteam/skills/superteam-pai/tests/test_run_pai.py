"""run_pai.py CLI smoke tests (dry-run only)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_RUN_PAI = _REPO / "skills" / "superteam-pai" / "scripts" / "run_pai.py"


def _run(*args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(_RUN_PAI), *args],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout)


def test_dry_run_job_daily():
    out = _run("--dry-run", "--job", "daily")
    assert out["status"] == "planned"
    ids = [s["id"] for s in out["plan"]["steps"]]
    assert ids == [
        "pulse-daily",
        "pulse-task-daily",
        "pulse-pai-daily",
        "pulse-member-daily",
    ]


def test_dry_run_prompt():
    out = _run("--dry-run", "--prompt", "只要 sprint")
    ids = [s["id"] for s in out["plan"]["steps"]]
    assert ids == ["pulse-daily"]
