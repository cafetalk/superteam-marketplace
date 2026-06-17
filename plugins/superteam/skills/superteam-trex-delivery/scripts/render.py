# scripts/render.py
"""模板渲染：把 TaskRecord / SystemChange 填进 templates/*.tmpl。"""
from __future__ import annotations
import re
from pathlib import Path
from model import TaskRecord, SystemChange
from dimensions import render_system_matrix, dimension_order, columns

TPL = Path(__file__).resolve().parent.parent / "templates"

LINEAR_WORKSPACE = "t-rex-v1"   # Linear workspace slug，issue 链接基址 https://linear.app/<ws>/issue/<ID>


def _issue_link(issue: str) -> str:
    """把 TREX-524 渲染成显式 Linear 链接；非标准 issue key 原样返回（不强造链接）。"""
    key = issue.strip()
    if re.fullmatch(r"[A-Z]+-\d+", key):
        return f"[{key}](https://linear.app/{LINEAR_WORKSPACE}/issue/{key})"
    return key


def _iteration_link(iteration: str, url: str = "") -> str:
    """迭代有 iteration_url 时渲染成 Linear Project 链接，否则退回 `代码体` 纯文本。"""
    return f"[{iteration}]({url})" if url else f"`{iteration}`"


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

def render_change_table(changes: list) -> str:
    if not changes:
        return "> 本服务本次无涉及维度。\n"
    order = dimension_order()
    cols = columns()                                   # [变更项, 内容, 操作人, 检查]
    rows = sorted(changes, key=lambda c: order.get(c.dim, 999))
    out = ["| " + " | ".join(cols) + " |",
           "|" + "|".join(["---"] * len(cols)) + "|"]
    for c in rows:
        flag = " ⚠️" if c.confirm else ""
        val = (c.value or "-").replace("\n", "<br>")
        out.append(f"| {c.dim}{flag} | {val} |  | ☐ |")
    return "\n".join(out) + "\n"


def render_placeholder_table(changes: list) -> list[str]:
    """变更项表后的占位符取值表；service 内所有 change 的 placeholders 汇成一张。无则返回 []。"""
    phs = [p for c in changes for p in (getattr(c, "placeholders", None) or [])]
    if not phs:
        return []
    out = ["", "`{}` = 按环境取值（其余为固定值，各环境一致）：", "",
           "| key | dev | beta | prod |", "|---|---|---|---|"]
    for p in phs:
        out.append(f"| {p.get('key','')} | {p.get('dev','')} | {p.get('beta','')} | {p.get('prod','')} |")
    return out


def _redis_table(redis_keys: list) -> list[str]:
    out = ["| Key 模式 | 用途 | TTL |", "|---|---|---|"]
    for k in redis_keys:
        out.append(f"| {k.get('key','')} | {k.get('purpose','')} | {k.get('ttl','')} |")
    return out


def render_data_contract(svc) -> list[str]:
    """#1 单服务数据契约段；当前仅 Redis Keys。无契约 → []。"""
    redis = (getattr(svc, "data_contract", None) or {}).get("redis_keys") or []
    if not redis:
        return []
    return ["# 数据契约", "", "## Redis Keys", ""] + _redis_table(redis)


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
    return ["# 关联任务", "",
            f"- 迭代：{_iteration_link(doc.iteration, getattr(doc, 'iteration_url', ''))}",
            "- 任务列表："] + \
           ([f"  - {_issue_link(i)}" for i in doc.linear] or ["  - （无）"])


def render_service_release(doc, service_name: str) -> str:
    """#1 per-service：变更项(+占位符表) → 数据契约 → 提测代码 → 关联任务。"""
    svc = next((s for s in doc.services if s.name == service_name), None)
    out = [f"> 服务：{service_name} · {doc.title}", "", "# 变更项", ""]
    if svc is None:
        out += ["> 本服务本次无涉及维度。"]
        return "\n".join(out) + "\n"
    out += [render_change_table(svc.changes).rstrip()]
    out += render_placeholder_table(svc.changes)
    dc = render_data_contract(svc)
    if dc:
        out += [""] + dc
    out += ["", "# 提测代码", "", f"- 提测分支：`{doc.submit_branch}`", "- MR 记录："]
    out += _mr_records(svc, indent="  ")
    out += [""] + _related_tasks(doc)
    return "\n".join(out) + "\n"


def render_submission_release(doc) -> str:
    """#2 提测汇总（task 跨服务）：变更项/占位符 按服务分 → 数据契约(按服务) → 提测代码 → 关联任务。"""
    out = [f"> 提测：{doc.task} · {doc.title}", "", "# 变更项", ""]
    for s in doc.services:
        out += [f"## {s.name}", "", render_change_table(s.changes).rstrip()]
        out += render_placeholder_table(s.changes)
        out += [""]
    dc_services = [s for s in doc.services
                   if (getattr(s, "data_contract", None) or {}).get("redis_keys")]
    if dc_services:
        out += ["# 数据契约", ""]
        for s in dc_services:
            out += [f"## {s.name} · Redis Keys", ""] + _redis_table(s.data_contract["redis_keys"]) + [""]
    out += ["# 提测代码", "", f"- 提测分支：`{doc.submit_branch}`", "- MR 记录："]
    for s in doc.services:
        out.append(f"  - {s.name}")
        out += _mr_records(s, indent="    ")
    out += [""] + _related_tasks(doc)
    return "\n".join(out) + "\n"


def render_iteration_auto(iteration: str, docs: list) -> str:
    """#3 迭代聚合 AUTO 区：变更项总表/明细 → 数据契约(按服务) → 提测代码 → 关联任务。"""
    out = ["# 变更项", "", "## 系统变更总表", "",
           "| 系统 | 提测分支 | 主 MR | 修改范围 | 涉及 |", "|---|---|---|---|---|"]
    for doc in docs:
        for s in doc.services:
            dims = " / ".join(c.dim for c in s.changes) or "-"
            out.append(f"| {s.name} | {doc.submit_branch} | {s.mr} | {dims} | ✅ |")
    out += ["", "## 各系统详细变更", ""]
    for doc in docs:
        for s in doc.services:
            out.append(f"### {s.name} ({doc.task})\n\n{render_change_table(s.changes).rstrip()}")
            ph = render_placeholder_table(s.changes)
            if ph:
                out += ph
            out.append("")
    dc_pairs = [(doc, s) for doc in docs for s in doc.services
                if (getattr(s, "data_contract", None) or {}).get("redis_keys")]
    if dc_pairs:
        out += ["# 数据契约", ""]
        for doc, s in dc_pairs:
            out += [f"## {s.name} · Redis Keys", ""] + _redis_table(s.data_contract["redis_keys"]) + [""]
    out += ["# 提测代码", ""]
    for doc in docs:
        out.append(f"- {doc.task}（分支 `{doc.submit_branch}`）")
        for s in doc.services:
            out.append(f"  - {s.name}")
            out += _mr_records(s, indent="    ")
    out += [""]
    it_url = next((getattr(d, "iteration_url", "") for d in docs if getattr(d, "iteration_url", "")), "")
    out += ["# 关联任务", "", f"- 迭代：{_iteration_link(iteration, it_url)}", "- 任务列表："]
    for doc in docs:
        links = ", ".join(_issue_link(i) for i in doc.linear) or "（无）"
        out.append(f"  - {doc.task}：{links}")
    return "\n".join(out) + "\n"
