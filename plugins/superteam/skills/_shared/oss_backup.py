"""Shared OSS backup utility — sync local source_docs to Aliyun OSS.

Used by sync-* scripts (post-download hook) and backup-to-oss skill (standalone).
Gracefully no-ops when OSS is not configured, so sync scripts work without OSS.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from config import env, source_docs_root

# ---------------------------------------------------------------------------
# Configuration (all optional — if not set, OSS backup is silently skipped)
# ---------------------------------------------------------------------------
OSS_BUCKET = env("OSS_BACKUP_BUCKET")
OSS_ENDPOINT = env("OSS_BACKUP_ENDPOINT", "oss-ap-southeast-1.aliyuncs.com")
OSS_KEY_ID = env("OSS_ACCESS_KEY_ID")
OSS_KEY_SECRET = env("OSS_ACCESS_KEY_SECRET")
SOURCE_DIR = source_docs_root()


def is_configured() -> bool:
    """Return True if OSS backup is configured.

    Supports two auth modes:
    - AK/SK mode: OSS_BUCKET + OSS_ACCESS_KEY_ID + OSS_ACCESS_KEY_SECRET
    - RAM Role mode (ECS): OSS_BUCKET only (ossutil uses instance metadata)
    """
    return bool(OSS_BUCKET)


def _find_ossutil() -> str | None:
    """Return ossutil binary path or None."""
    return shutil.which("ossutil")


def sync_to_oss(
    local_dir: Path | None = None,
    *,
    dry_run: bool = False,
    delete: bool = True,
    quiet: bool = False,
) -> dict:
    """Incremental sync a local directory to OSS.

    Args:
        local_dir: Directory to upload (default: SOURCE_DIR).
        dry_run: Preview only, no transfer.
        delete: Mirror-sync (remove OSS files not present locally).
        quiet: Suppress stderr output.

    Returns:
        dict with *status* ("ok" | "skipped" | "error"), *message*, and
        optionally *stdout*/*stderr*/*returncode*.
    """
    if not is_configured():
        msg = "OSS backup not configured — skipping"
        if not quiet:
            print(f"  [oss] {msg}", file=sys.stderr)
        return {"status": "skipped", "message": msg}

    ossutil = _find_ossutil()
    if not ossutil:
        msg = "ossutil not installed — skipping OSS backup"
        if not quiet:
            print(f"  [oss] {msg}", file=sys.stderr)
        return {"status": "skipped", "message": msg}

    local_dir = local_dir or SOURCE_DIR
    if not local_dir.exists():
        msg = f"Source directory not found: {local_dir}"
        if not quiet:
            print(f"  [oss] {msg}", file=sys.stderr)
        return {"status": "error", "message": msg}

    oss_target = f"{OSS_BUCKET}/source_docs/"

    cmd = [
        ossutil, "sync",
        str(local_dir) + "/",
        oss_target,
        "--endpoint", OSS_ENDPOINT,
        "--update",
        "--retry-times", "3",
        "--parallel", "5",
    ]
    # AK/SK mode: pass credentials explicitly
    # RAM Role mode (ECS): omit — ossutil auto-detects instance metadata
    if OSS_KEY_ID and OSS_KEY_SECRET:
        cmd += ["--access-key-id", OSS_KEY_ID, "--access-key-secret", OSS_KEY_SECRET]
    if delete:
        cmd.append("--delete")
    if dry_run:
        cmd.append("--dry-run")

    if not quiet:
        action = "dry-run" if dry_run else "syncing"
        print(f"  [oss] {action}: {local_dir} -> {oss_target}", file=sys.stderr)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3600,
        )
    except subprocess.TimeoutExpired:
        msg = "OSS sync timed out (3600s)"
        if not quiet:
            print(f"  [oss] {msg}", file=sys.stderr)
        return {"status": "error", "message": msg}

    if result.returncode == 0:
        if not quiet:
            print(f"  [oss] backup completed successfully", file=sys.stderr)
        return {
            "status": "ok",
            "message": "OSS backup completed",
            "stdout": result.stdout,
            "returncode": 0,
        }
    else:
        msg = f"OSS sync failed (exit {result.returncode})"
        if not quiet:
            print(f"  [oss] {msg}", file=sys.stderr)
            if result.stderr:
                print(f"  [oss] {result.stderr[:300]}", file=sys.stderr)
        return {
            "status": "error",
            "message": msg,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
