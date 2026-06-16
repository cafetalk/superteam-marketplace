# scripts/release.py
"""release 命令：汇总本批所有 submission.md → RELEASE.md（auto 区重生成，manual 保留）。"""
from __future__ import annotations
import argparse
import json
import re
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gitlab_release                  # noqa
from model import SystemChange         # noqa
from render import render_release_auto, render_iteration_auto, TPL  # noqa
from regions import merge_release      # noqa
from changes import load_changes, validate_changes  # noqa


def _section(text: str, heading: str) -> str:
    """取 '## <heading>' 到下一个 '## ' 之间的正文（不含别的二级段，避免误读 prose 里的 ###）。"""
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", text, flags=re.M | re.S)
    return m.group(1) if m else ""


def _parse_dim_table(block: str) -> dict:
    """解析单系统的维度表 | 维度 | beta | prod | 操作人 | 检查 | → dimensions dict。"""
    dims: dict[str, dict] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5 or cells[0] in ("维度", "") or set(cells[0]) <= set("-:"):
            continue                                  # 跳过表头 / 分隔行
        key, beta, prod, op, chk = cells[0], cells[1], cells[2], cells[3], cells[4]
        unbr = lambda s: "" if s == "-" else s.replace("<br>", "\n")   # noqa: E731
        dims[key] = {"beta": unbr(beta), "prod": unbr(prod),
                     "operator": op, "checked": chk == "☑"}
    return dims


def _parse_submission(text: str):
    """从 submission.md 反解 submission_key / title / review 分支 / 提测人 / issues / 各系统(含已填维度矩阵)。
    维度明细从『受影响系统 / 部署变更』段的表格读回，使 RELEASE.md 携带真实部署内容。"""
    m = re.search(r"#\s*提测\s*—\s*([\w.\-]+)\s*·\s*(.+)", text)
    submission_key = m.group(1) if m else "?"
    title = m.group(2).strip() if m else ""
    rb = re.search(r"review_\d{6,8}_[\w.-]+", text)    # 兼容 6 位与 8 位日期
    review = rb.group(0) if rb else ""
    sm = re.search(r"\|\s*提测人\s*\|\s*(.+?)\s*\|", text)
    submitter = sm.group(1).strip() if sm else ""
    im = re.search(r"\|\s*关联 Linear\s*\|\s*(.+?)\s*\|", text)
    issues = [s.strip() for s in im.group(1).split(",") if s.strip()] if im else []
    # 只在『受影响系统 / 部署变更』段内找 ### 系统块，避免把 prose 里的 ### 误当系统
    sec = _section(text, "受影响系统 / 部署变更")
    systems = []
    parts = re.split(r"^###\s+(.+)$", sec, flags=re.M)   # [pre, name1, body1, name2, body2, ...]
    for i in range(1, len(parts), 2):
        name = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        systems.append(SystemChange(name, review, "", submitter, "", False, _parse_dim_table(body)))
    return submission_key, title, submitter, issues, systems


def run(releases_root: Path, batch: str, dry_run: bool = False) -> Path:
    bdir = releases_root / "releases" / batch
    if not bdir.exists():
        raise FileNotFoundError(f"batch 目录不存在: {bdir}（--batch 拼写对吗？应先对该批次跑 submit）")
    submissions, sys_by_name = [], {}
    for hp in sorted(bdir.glob("submissions/*/submission.md")):
        submission_key, title, submitter, _issues, systems = _parse_submission(
            hp.read_text(encoding="utf-8"))
        submissions.append((submission_key, title, submitter))
        for s in systems:
            if s.name in sys_by_name:                  # 同系统多 submission：合并维度（union）
                sys_by_name[s.name].dimensions.update(s.dimensions)
            else:
                sys_by_name[s.name] = s
    auto = render_release_auto(batch, list(sys_by_name.values()), submissions)
    rp = bdir / "RELEASE.md"
    existing = rp.read_text(encoding="utf-8") if rp.exists() else None
    template = (TPL / "release.md.tmpl").read_text(encoding="utf-8").replace("{batch}", batch)
    merged = merge_release(existing, auto, template)
    if not dry_run:
        rp.write_text(merged, encoding="utf-8")
    return rp


def run_v2(releases_root, iteration: str, dry_run: bool = False):
    """v1.4.0: glob changes.yaml → render_iteration_auto → release.md (manual 区保留)。"""
    bdir = Path(releases_root) / "releases" / iteration
    if not bdir.exists():
        raise FileNotFoundError(f"iteration 目录不存在: {bdir}")

    docs = []
    for cp in sorted(bdir.glob("submissions/*/changes.yaml")):
        doc = load_changes(cp)
        if doc.iteration != iteration:
            raise SystemExit(
                f"changes.yaml iteration 字段 '{doc.iteration}' != 路径 iteration '{iteration}' "
                f"(文件: {cp})"
            )
        errs = validate_changes(doc, expected_iteration=iteration)
        if errs:
            raise SystemExit(f"changes.yaml 校验失败 ({cp}):\n" + "\n".join(f"  - {e}" for e in errs))
        docs.append(doc)

    # 孤儿检测：有 release.md 但无 changes.yaml 的子目录 → warn + skip
    for sub in sorted(bdir.glob("submissions/*")):
        if sub.is_dir() and (sub / "release.md").exists() and not (sub / "changes.yaml").exists():
            warnings.warn(f"orphan submission dir (no changes.yaml): {sub} — skipped", stacklevel=2)

    auto = render_iteration_auto(iteration, docs)
    rp = bdir / "release.md"
    existing = rp.read_text(encoding="utf-8") if rp.exists() else None
    template = (TPL / "release.iteration.md.tmpl").read_text(encoding="utf-8").replace("{batch}", iteration)
    merged = merge_release(existing, auto, template)
    if not dry_run:
        rp.write_text(merged, encoding="utf-8")
    return rp


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="汇总批次发布文档")
    p.add_argument("--batch", required=True)
    p.add_argument("--releases-root", required=True)
    p.add_argument("--yes", action="store_true", help="跳过首建批次分支的确认闸，直接 push")
    p.add_argument("--no-push", action="store_true", help="只本地 commit，不 push")
    p.add_argument("--no-mr", action="store_true", help="push 但不开 MR")
    p.add_argument("--dry-run", action="store_true")
    return p


def run_cli(argv=None):
    args = _build_parser().parse_args(argv)
    root = Path(args.releases_root).resolve()
    rp = run(root, args.batch, dry_run=args.dry_run)
    result = {"release": str(rp), "dry_run": args.dry_run, "written": not args.dry_run}
    if not args.dry_run:
        branch = gitlab_release.record_branch_name(args.batch)
        relpath = str(rp.relative_to(root)) if rp.is_absolute() else str(rp)
        gitlab_release.ensure_branch(root, branch)
        gitlab_release.stage(root, [relpath])
        gitlab_release.commit(root, f"release: 汇总发布文档 {args.batch}")
        if gitlab_release.needs_confirm(root, branch, assume_yes=args.yes):
            result["confirm_required"] = True            # 首建批次分支：打印 diff，等人确认，不 push
            print(gitlab_release._git(root, "log", "-1", "--stat"))
        elif not args.no_push:
            gitlab_release.push(root, branch)
            if not args.no_mr:
                result["mr"] = gitlab_release.open_mr(root, branch, "master",
                                                      f"release: 汇总发布 {branch}")
    print(json.dumps(result, ensure_ascii=False))
    return 0


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
