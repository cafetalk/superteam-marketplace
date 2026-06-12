# scripts/gitlab_release.py
"""跨 repo git：显式 stage / 建分支 / commit / push / MR + 确认闸。
安全栏：永不 git add -A/./-u；push/MR 默认开但首建批次记录要确认。"""
from __future__ import annotations
import re
import subprocess
from pathlib import Path


def record_branch_name(batch: str) -> str:
    """trex-releases 记录分支名，合规于 t-rex push rule：`auto_<date>_<keyword>`。
    `auto` 前缀在白名单内；keyword 取 batch 的 slug 段并清成 ASCII（规则 name 段不含 / 与中文）。
    batch 形如 <date>-<slug>（如 20260605-world-cup / 20260604-campaign抽象大改动）。"""
    date, _, slug = batch.partition("-")
    kw = re.sub(r"[^A-Za-z0-9-]", "", slug)[:30] or "rec"
    if len(kw) < 2:
        kw = (kw + "rec")[:30]
    return f"auto_{date}_{kw}"


def _git(repo: Path, *args: str) -> str:
    res = subprocess.run(["git", "-C", str(repo), *args],
                         capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败: {res.stderr.strip()}")
    return res.stdout.strip()


def stage(repo: Path, paths: list[str]) -> None:
    if not paths:
        return
    for p in paths:
        if p in ("-A", ".", "-u") or p.startswith("-"):
            raise ValueError(f"拒绝危险 stage 参数: {p}")
    _git(repo, "add", "--", *paths)


def remote_branch_exists(repo: Path, branch: str) -> bool:
    out = _git(repo, "ls-remote", "--heads", "origin", branch)
    return bool(out.strip())


def needs_confirm(repo: Path, branch: str, assume_yes: bool) -> bool:
    if assume_yes:
        return False
    return not remote_branch_exists(repo, branch)   # 首次建该批次记录分支 → 需确认


def ensure_branch(repo: Path, branch: str) -> None:
    try:
        _git(repo, "checkout", branch)
    except RuntimeError:
        _git(repo, "checkout", "-b", branch)


def commit(repo: Path, message: str) -> None:
    _git(repo, "commit", "-m", message)


def push(repo: Path, branch: str) -> None:
    _git(repo, "push", "-u", "origin", branch)


def open_mr(repo: Path, source: str, target: str, title: str) -> dict:
    """建 MR；失败不抛（跨 repo 失败隔离），返回结构化结果供汇总。"""
    try:
        res = subprocess.run(
            ["glab", "mr", "create", "-R", str(repo), "--source-branch", source,
             "--target-branch", target, "--title", title, "--fill", "--yes"],
            capture_output=True, text=True, timeout=120)
    except (FileNotFoundError, OSError) as e:   # glab 未安装 / 不可执行 —— 不抛，记录原因
        return {"ok": False, "output": "", "error": f"glab 不可用: {e}"}
    return {"ok": res.returncode == 0,
            "output": (res.stdout or "").strip(),
            "error": (res.stderr or "").strip() if res.returncode != 0 else ""}
