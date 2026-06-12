# scripts/render.py
"""模板渲染：把 TaskRecord / SystemChange 填进 templates/*.tmpl。"""
from __future__ import annotations
from pathlib import Path
from model import TaskRecord, SystemChange
from dimensions import render_system_matrix

TPL = Path(__file__).resolve().parent.parent / "templates"


def _tpl(name: str) -> str:
    return (TPL / name).read_text(encoding="utf-8")


def render_submission(tr: TaskRecord, batch: str) -> str:
    return _tpl("submission.md.tmpl").format(
        submission_key=tr.submission_key, title=tr.title, batch=batch,
        submitter=tr.submitter, issues=", ".join(tr.issues),
        mr_url=tr.mr_url, review_branch=tr.review_branch,
        system_matrix=render_system_matrix(tr.systems))


def render_release_auto(batch: str, systems: list[SystemChange],
                        submissions: list[tuple[str, str, str]]) -> str:
    """auto 区内容：系统变更总表 + 各系统明细 + 本批提测单索引。
    submissions: (submission_key, title, submitter) 元组列表。"""
    head = ["## 系统变更总表", "",
            "| 系统 | review 分支 | 变更范围 | dev owner | 运维执行人 | 完成 |",
            "|---|---|---|---|---|---|"]
    for s in systems:
        chk = "☑" if s.done else "☐"
        head.append(f"| {s.name} | {s.review_branch} | {s.scope} | {s.dev_owner} | {s.ops_executor} | {chk} |")
    detail = ["", "## 各系统变更明细", "", render_system_matrix(systems)]
    idx = ["", "## 本批提测单"]
    for submission_key, title, submitter in submissions:
        idx.append(f"- [{submission_key}](submissions/{submission_key}/submission.md) — {title} — {submitter}")
    return "\n".join(head + detail + idx) + "\n"


def render_repo_change(repo: str, tr: TaskRecord, batch: str, handoff_link: str,
                       scope_body: str = "- <本 repo 改动点>") -> str:
    sysmd = render_system_matrix([s for s in tr.systems if s.name == repo] or tr.systems)
    return _tpl("repo-change.md.tmpl").format(
        repo=repo, submission_key=tr.submission_key, batch=batch, handoff_link=handoff_link,
        scope_body=scope_body, system_matrix=sysmd)
