# scripts/submit.py
"""submit 命令：按一次提测(submission, 一个 dev 分支 / 一个微服务) 生成提测单 + per-repo 明细。
一次提测可关联多个 Linear issue；submission key = <date>_<name>（dev_<date>_<name> 去 dev_ 前缀）。"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sources                       # noqa
import gitlab_release                # noqa
import gitlab_mr                     # noqa
import subprocess                    # noqa
from model import TaskRecord, SystemChange  # noqa
from batch import resolve_batch, slugify    # noqa
from render import render_submission, render_repo_change  # noqa


def submission_key_of(dev_branch: str) -> str:
    """dev_<date>_<name> → <date>_<name>（= submission key = review_ 同名段）。"""
    if not re.fullmatch(r"dev_\d{6,8}_[\w.-]+", dev_branch):
        raise SystemExit(f"--dev-branch 不合规（应 dev_<date>_<name>）: {dev_branch}")
    return dev_branch[len("dev_"):]


def build(dev_branch: str, issues: list[str], batch, date):
    """取 FIRST issue 填 title/submitter/project（批次目标日期）；构造 TaskRecord。"""
    submission_key = submission_key_of(dev_branch)
    review_branch = "review_" + submission_key
    first = sources.fetch_issue(issues[0])
    proj = first.get("project") or {}
    slug = slugify(proj.get("name", "unknown"))
    target = proj.get("targetDate")
    resolved = resolve_batch(batch, date, slug, target)
    a = first.get("assignee")                       # Linear 可能返回字符串或 {name/displayName}
    submitter = a.get("name") or a.get("displayName") or "" if isinstance(a, dict) else (a or "")
    tr = TaskRecord(submission_key=submission_key, title=first.get("title", ""),
                    submitter=submitter, issues=list(issues),
                    mr_url="", review_branch=review_branch, systems=[])
    return tr, resolved


def write_records(dev_branch: str, issues: list[str], releases_root: Path, batch, date,
                  repo: str | None = None,
                  result: dict | None = None, dry_run: bool = False,
                  mr_override: dict | None = None) -> list[Path]:
    """生成 trex-releases 的 submission.md + （MR 模式下）该微服务 repo 的 per-repo 明细。
    返回**预期写入文件的绝对路径列表**（run_cli 据此算相对 releases_root 的 relpath 来 stage）。
    dry_run=True 时只计算路径、不落盘（与 spec §9「不落盘」一致）。
    per-repo 明细写进业务 repo 工作区但**不在此提交**：由工程师随代码在 review_* 分支一起提交
    （trex-releases 侧才由本 skill 自动 commit/push）。某 repo 写失败只记入
    result['repos'][name]，不中断其余（跨 repo 失败隔离）。"""
    tr, resolved = build(dev_branch, issues, batch, date)
    repo_root = None    # 微服务 repo 工作区路径（MR 模式 = --repo）
    if mr_override:
        # MR 模式：skill 替工程师开了提测 MR，故握有 MR URL / review 分支 / 所在 repo
        # （= 受影响系统）。覆盖 build 留空的字段。
        tr.mr_url = mr_override.get("web_url", "")
        tr.review_branch = mr_override["review_branch"]
        repo_name = mr_override["repo"]
        tr.systems = [SystemChange(repo_name, tr.review_branch, "",
                                   tr.submitter, "", False, {})]
        # 自动把 per-repo 明细写进 --repo 工作区（该 repo 即微服务）
        repo_root = repo
    written: list[Path] = []
    task_dir = releases_root / "releases" / resolved / "submissions" / tr.submission_key
    hp = (task_dir / "submission.md").resolve()
    if not dry_run:
        task_dir.mkdir(parents=True, exist_ok=True)
        hp.write_text(render_submission(tr, resolved), encoding="utf-8")
    written.append(hp)
    # per-repo 明细：写进微服务 repo 的工作区。互链回 trex-releases 的 submission.md。
    if tr.systems and repo_root:
        repo_name = tr.systems[0].name
        try:
            repo_dir = Path(repo_root) / "releases" / resolved
            handoff_link = (f"../../../trex-releases/releases/{resolved}"
                            f"/submissions/{tr.submission_key}/submission.md")
            rp = (repo_dir / f"{tr.submission_key}.md").resolve()
            if not dry_run:
                repo_dir.mkdir(parents=True, exist_ok=True)
                rp.write_text(
                    render_repo_change(repo_name, tr, resolved, handoff_link), encoding="utf-8")
            written.append(rp)
            if result is not None:
                # 提示：该文件落在业务 repo 工作区，需工程师随代码在 review_* 分支一起提交
                result.setdefault("repos", {})[repo_name] = {
                    "ok": True, "path": str(rp), "note": "请随代码在 review_* 分支提交此文件"}
        except Exception as e:   # 单 repo 写失败不影响其余
            if result is not None:
                result.setdefault("repos", {})[repo_name] = {"ok": False, "error": str(e)}
    return written


def _git_remote_url(repo: str) -> str:
    """读业务 repo 的 origin remote（解析 GitLab project path 用）。"""
    res = subprocess.run(["git", "-C", repo, "remote", "get-url", "origin"],
                         capture_output=True, text=True, timeout=30)
    if res.returncode != 0:
        raise RuntimeError(f"读 {repo} 的 origin remote 失败: {res.stderr.strip()}")
    return res.stdout.strip()


def _read_gitlab_token() -> str:
    """从 ~/.superteam/config 读 GITLAB_TOKEN（python 读 + split，-a 安全，不走 shell）。"""
    cfg = Path.home() / ".superteam" / "config"
    if not cfg.exists():
        raise RuntimeError("未找到 ~/.superteam/config，无法读取 GITLAB_TOKEN")
    for line in cfg.read_text(encoding="utf-8").splitlines():
        if "GITLAB_TOKEN=" in line:
            return line.split("GITLAB_TOKEN=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("~/.superteam/config 缺少 GITLAB_TOKEN")


def _set_linear_in_review(issue: str) -> None:
    """best-effort 把 Linear issue 置 In Review（失败由调用方吞为 warning）。"""
    sources._run_json(["python3", str(sources.LINEAR), "--tool", "save_issue",
                       "--args-json", json.dumps({"id": issue, "state": "In Review"})])


def _under(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


def _batch_of(written: list[Path]) -> str:
    # 写入路径形如 <root>/releases/<batch>/...，取 releases 后一段
    for p in written:
        parts = p.parts
        if "releases" in parts:
            return parts[parts.index("releases") + 1]
    raise RuntimeError("无法从写入路径推断 batch")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="生成提测单（一次提测 = 一个 dev 分支 / 一个微服务，可关联多个 Linear issue）")
    p.add_argument("--dev-branch", required=True,
                   help="dev_<date>_<name>（submission key = <date>_<name>；推导 review_*）")
    p.add_argument("--issue", action="append", required=True,
                   help="TREX-<id>（可重复，关联多个 Linear issue）")
    p.add_argument("--batch", default=None)
    p.add_argument("--date", default=None)
    p.add_argument("--releases-root", required=True, help="trex-releases 本地 clone 路径")
    p.add_argument("--repo", default=None,
                   help="微服务 repo 路径（MR 模式：开提测 MR + 标识受影响系统 + 自动写 per-repo 明细）")
    p.add_argument("--reviewer", default=None,
                   help="GitLab 用户名（MR reviewer/assignee）；缺则按 team-leads.json 解析")
    p.add_argument("--yes", action="store_true", help="跳过首建批次分支的确认闸，直接 push")
    p.add_argument("--no-push", action="store_true", help="只本地 commit，不 push")
    p.add_argument("--no-mr", action="store_true", help="push 但不开 MR")
    p.add_argument("--dry-run", action="store_true")
    return p


def run_cli(argv=None):
    args = _build_parser().parse_args(argv)
    root = Path(args.releases_root).resolve()
    result: dict = {"dry_run": args.dry_run}
    if args.dry_run:
        print("[note] --dry-run：本地生成记录文件供预览，不做 git", file=sys.stderr)

    issues = args.issue                  # list（action="append"）
    submission_key = submission_key_of(args.dev_branch)

    mr_override = None
    if args.repo:
        # MR 模式：从微服务 repo origin 解析 GitLab project → 解析 reviewer →
        # 建 review_* + dev_*→review_* 提测 MR（多个 issue 全写进 description；dry-run 透传，零 GitLab 写）。
        remote_url = _git_remote_url(args.repo)
        project_path = gitlab_mr.parse_project_path(remote_url)
        reviewer = gitlab_mr.resolve_reviewer(
            project_path, args.reviewer, gitlab_mr.load_team_leads())
        token = _read_gitlab_token()
        mr_override = gitlab_mr.open_handoff_mr(
            token, project_path, args.dev_branch, issues, reviewer,
            dry_run=args.dry_run)
        result["mr"] = mr_override

    written = write_records(args.dev_branch, issues, root, args.batch, args.date,
                            repo=args.repo, result=result,
                            dry_run=args.dry_run, mr_override=mr_override)
    relpaths = [str(p.relative_to(root)) for p in written if _under(p, root)]
    result["written"] = [str(w) for w in written]
    if not args.dry_run and relpaths:
        branch = gitlab_release.record_branch_name(_batch_of(written))
        trailers = "\n".join(f"Tracks Linear {i}" for i in issues)
        gitlab_release.ensure_branch(root, branch)
        gitlab_release.stage(root, relpaths)
        gitlab_release.commit(root, f"release: 提测记录 {submission_key}\n\n{trailers}")
        if gitlab_release.needs_confirm(root, branch, assume_yes=args.yes):
            result["confirm_required"] = True            # 首建批次分支：打印 diff，等人确认，不 push
            print(gitlab_release._git(root, "log", "-1", "--stat"))
        elif not args.no_push:
            gitlab_release.push(root, branch)
            if not args.no_mr:
                result["release_record_mr"] = gitlab_release.open_mr(
                    root, branch, "master", f"release: 记录 {branch}")
    # MR 模式：把每个关联 Linear issue 置 In Review（逐个 best-effort，失败只告警不阻断）。
    if mr_override and not args.dry_run:
        for issue in issues:
            try:
                _set_linear_in_review(issue)
            except Exception as e:
                result.setdefault("warnings", []).append(
                    f"Linear issue {issue} → In Review 失败（不影响 MR/记录）: {e}")
    print(json.dumps(result, ensure_ascii=False))
    return 0


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
