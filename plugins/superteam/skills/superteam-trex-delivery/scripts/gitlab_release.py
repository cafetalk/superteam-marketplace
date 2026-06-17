# scripts/gitlab_release.py
"""跨 repo git：显式 stage / 建分支 / commit / push / MR + 确认闸。
安全栏：永不 git add -A/./-u；push/MR 默认开但首建批次记录要确认。"""
from __future__ import annotations
import re
import subprocess
from pathlib import Path


def record_branch_name(batch: str) -> str:
    """trex-releases 记录分支名（**仅 fallback** —— 无当次开发分支时按 iteration 派生）。
    合规于 t-rex push rule：`dev_<date>_<keyword>`（dev 前缀在白名单内；keyword 取 batch 的
    slug 段清成 ASCII，规则 name 段不含 / 与中文）。batch 形如 <date>-<slug>。
    正常路径用 `dev_branch_of(submit_branch, batch)`：复用本轮**公共 dev 分支名**，
    让 trex-releases 与各微服务仓分支名一致（见 handbook common/03〔多服务分支同名建议〕）。"""
    date, _, slug = batch.partition("-")
    kw = re.sub(r"[^A-Za-z0-9-]", "", slug)[:30] or "rec"
    if len(kw) < 2:
        kw = (kw + "rec")[:30]
    return f"dev_{date}_{kw}"


def dev_branch_of(submit_branch: str, batch: str) -> str:
    """本轮记录分支 = 本轮**公共 dev 分支名**。
    submit_branch 形如 `review_<date>_<name>`（与 dev_* 名字对齐，见 common/03）→ 换 `dev_<date>_<name>`；
    已是 `dev_*` 原样用；都不是则退回按 iteration 派生（`record_branch_name`）。"""
    sb = (submit_branch or "").strip()
    if sb.startswith("review_"):
        return "dev_" + sb[len("review_"):]
    if sb.startswith("dev_"):
        return sb
    return record_branch_name(batch)


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
    """建 MR；用 GitLab REST API + ~/.superteam/config 的 token（不依赖 glab CLI）。
    从 repo 的 origin remote 解析 GitLab project path。失败不抛（跨 repo 失败隔离），返回结构化结果。"""
    import gitlab_mr
    try:
        remote = _git(repo, "remote", "get-url", "origin")
        project_path = gitlab_mr.parse_project_path(remote)
    except Exception as e:
        return {"ok": False, "web_url": "", "error": f"解析 project path 失败: {e}"}
    return gitlab_mr.create_mr(project_path, source, target, title,
                               description="由 superteam-trex-delivery 自动生成的发布/提测记录 MR。")
