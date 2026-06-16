# scripts/validate.py
"""validate 命令: 校验 changes.yaml (CI 可挂)。合法 exit 0, 非法 exit 1 + 打印错误。"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from changes import load_changes, validate_changes  # noqa


def run_cli(argv=None) -> int:
    p = argparse.ArgumentParser(description="校验 changes.yaml 是否合规")
    p.add_argument("--changes", required=True, help="changes.yaml 路径")
    p.add_argument("--iteration", default=None, help="可选: 校验 iteration 字段匹配")
    args = p.parse_args(argv)
    doc = load_changes(args.changes)
    errs = validate_changes(doc, expected_iteration=args.iteration)
    if errs:
        print("changes.yaml 校验失败:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"changes.yaml OK: {doc.task} ({len(doc.services)} services)")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
