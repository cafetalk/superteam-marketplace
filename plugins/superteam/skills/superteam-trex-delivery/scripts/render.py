# scripts/render.py
"""模板渲染：把 TaskRecord / SystemChange 填进 templates/*.tmpl。"""
from __future__ import annotations
from pathlib import Path
from model import TaskRecord, SystemChange
from dimensions import render_system_matrix, dimension_order, columns

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


# ---------------------------------------------------------------------------
# v1.4.0 新渲染函数 — 基于 ChangesDoc / Change / ServiceChanges
# ---------------------------------------------------------------------------

def _is_code(c) -> bool:
    """多行内容 OR 显式 lang → 渲染成代码块 (config env / 脚本; Allen 偏好)。"""
    return bool(c.lang) or "\n" in (c.beta or "") or "\n" in (c.prod or "")


def render_change_table(changes: list) -> str:
    if not changes:
        return "> 本服务本次无涉及维度。\n"
    order = dimension_order()
    cols = columns()
    rows = sorted(changes, key=lambda c: order.get(c.dim, 999))
    simple = [c for c in rows if not _is_code(c)]
    coded = [c for c in rows if _is_code(c)]
    out: list[str] = []
    if simple:
        sep = "|" + "|".join(["---"] * len(cols)) + "|"   # 从 columns 数派生, 防 desync
        out += ["| " + " | ".join(cols) + " |", sep]
        for c in simple:
            flag = " ⚠️" if c.confirm else ""
            out.append(f"| {c.dim}{flag} | {c.beta or '-'} | {c.prod or '-'} |  | ☐ |")
        out.append("")
    for c in coded:
        flag = " ⚠️" if c.confirm else ""
        out += [f"#### {c.dim}{flag}", "", "**beta:**", f"```{c.lang}", c.beta, "```"]
        if c.prod and c.prod != "同 beta":
            out += ["**prod:**", f"```{c.lang}", c.prod, "```"]
        else:
            out.append(f"_prod_: {c.prod or '同 beta'}")
        out += ["_操作人_: <待发布填> · _检查_: ☐", ""]
    return "\n".join(out) + "\n"


def _mr_records(svc, indent: str = "") -> list[str]:
    """MR 记录子树：主 MR + 修复问题的 MR（indent 控制缩进，用于 #1 顶层 / #2#3 服务级嵌套）。"""
    out = [f"{indent}- 主 MR：{svc.mr or '—'}"]
    if svc.fix_mrs:
        out.append(f"{indent}- 修复问题的 MR：")
        out += [f"{indent}  - {u}" for u in svc.fix_mrs]
    else:
        out.append(f"{indent}- 修复问题的 MR：无")
    return out


def _related_tasks(doc) -> list[str]:
    """# 关联任务：迭代 + 任务列表。"""
    return ["# 关联任务", "", f"- 迭代：`{doc.iteration}`", "- 任务列表："] + \
           ([f"  - {i}" for i in doc.linear] or ["  - （无）"])


def render_service_release(doc, service_name: str) -> str:
    """#1 per-service：三章节（变更项 / 提测代码 / 关联任务）。"""
    svc = next((s for s in doc.services if s.name == service_name), None)
    out = [f"> 服务：{service_name} · {doc.title}", "", "# 变更项", ""]
    if svc is None:
        out += ["> 本服务本次无涉及维度。"]
        return "\n".join(out) + "\n"
    out += [render_change_table(svc.changes).rstrip(), "",
            "# 提测代码", "", f"- 提测分支：`{doc.submit_branch}`", "- MR 记录："]
    out += _mr_records(svc, indent="  ")
    out += [""] + _related_tasks(doc)
    return "\n".join(out) + "\n"


def render_submission_release(doc) -> str:
    """#2 提测汇总（task 跨服务）：三章节，变更项/提测代码 按服务分。"""
    out = [f"> 提测：{doc.task} · {doc.title}", "", "# 变更项", ""]
    for s in doc.services:
        out += [f"## {s.name}", "", render_change_table(s.changes).rstrip(), ""]
    out += ["# 提测代码", "", f"- 提测分支：`{doc.submit_branch}`", "- MR 记录："]
    for s in doc.services:
        out.append(f"  - {s.name}")
        out += _mr_records(s, indent="    ")
    out += [""] + _related_tasks(doc)
    return "\n".join(out) + "\n"


def render_iteration_auto(iteration: str, docs: list) -> str:
    """#3 迭代聚合 AUTO 区：三章节（变更项 / 提测代码 / 关联任务）。"""
    out = ["# 变更项", "", "## 系统变更总表", "",
           "| 系统 | 提测分支 | 主 MR | 修改范围 | 涉及 |", "|---|---|---|---|---|"]
    for doc in docs:
        for s in doc.services:
            dims = " / ".join(c.dim for c in s.changes) or "-"
            out.append(f"| {s.name} | {doc.submit_branch} | {s.mr} | {dims} | ✅ |")
    out += ["", "## 各系统详细变更", ""]
    for doc in docs:
        for s in doc.services:
            out.append(f"### {s.name} ({doc.task})\n\n{render_change_table(s.changes).rstrip()}\n")
    out += ["# 提测代码", ""]
    for doc in docs:
        out.append(f"- {doc.task}（分支 `{doc.submit_branch}`）")
        for s in doc.services:
            out.append(f"  - {s.name}")
            out += _mr_records(s, indent="    ")
    out += [""]
    out += ["# 关联任务", "", f"- 迭代：`{iteration}`", "- 任务列表："]
    for doc in docs:
        out.append(f"  - {doc.task}：{', '.join(doc.linear) or '（无）'}")
    return "\n".join(out) + "\n"
