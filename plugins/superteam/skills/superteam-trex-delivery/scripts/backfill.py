# scripts/backfill.py
"""一次性：回迁最近 2 次钉钉 .axls 发布文档 → trex-releases RELEASE.md。"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import SystemChange         # noqa
from render import render_release_auto, TPL  # noqa
from regions import merge_release      # noqa


def _truthy(s) -> bool:
    """钉钉单元格里是 'TRUE'/'FALSE'/空 字符串，不能用 bool(str) 判断；防御 None。"""
    return str(s or "").strip().upper() in ("TRUE", "✓", "☑", "DONE", "YES", "Y", "是")


def parse_master(rows: list[list[str]]) -> list[SystemChange]:
    """系统变更列表主表 → SystemChange（跳过分组行 / 表头 / review分支行）。
    **按表头列名取值**（不同批次表里可能插列，如 campaign 多了 'Code Review'），
    避免固定下标错位。"""
    out, hidx = [], None
    for r in rows:
        c = [x.strip() for x in r]
        if c and c[0].startswith("系统名称"):
            hidx = {label: i for i, label in enumerate(c) if label}
            continue
        if hidx is None or not c or not c[0] or c[0].startswith("～") or c[0] == "review分支":
            continue

        def col(label: str) -> str:
            i = hidx.get(label)
            return c[i] if i is not None and i < len(c) else ""

        out.append(SystemChange(
            name=c[0], review_branch=col("提测分支"), scope=col("修改范围"),
            dev_owner=col("开发负责人"), ops_executor=col("运维执行人"),
            done=_truthy(col("操作已完成")), dimensions={}))
    return out


def parse_system_sheet(rows: list[list[str]]) -> dict:
    """单系统 sheet → {dim: {beta, prod, operator, checked}}，只保留有内容的维度。
    自适应环境列形态：beta|prod / beta|pre|prod / 合并 beta/prod。"""
    dims: dict[str, dict] = {}
    # 1) 找 env 子表头行：含以 beta 开头的单元格（覆盖 'beta' 与 'beta/prod'）。
    env_idx = next((i for i, r in enumerate(rows)
                    if any(x.strip().lower().startswith("beta") for x in r)), None)
    if env_idx is None:
        return dims
    header = [x.strip().lower() for x in rows[env_idx]]
    env_cols = [j for j, x in enumerate(header)
                if re.fullmatch(r"beta|pre|prod", x) or "/" in x]  # 精确匹配，避免 product/preview 误判；合并列 beta/prod 由 "/" 捕获
    if not env_cols:
        return dims
    beta_i, prod_i = env_cols[0], env_cols[-1]
    op_i, chk_i = prod_i + 2, prod_i + 3          # 涉及(prod+1) / 操作人(prod+2) / 检查(prod+3)
    # 2) env 行之后是数据行。
    for r in rows[env_idx + 1:]:
        c = [x.strip() for x in r] + [""] * (chk_i + 1)
        key = c[0]
        if not key or key == "变更项" or key.endswith("变更项"):
            continue
        beta, prod = c[beta_i], c[prod_i]
        if beta or prod:                              # 只留非空
            dims[key] = {"beta": beta, "prod": prod,
                         "operator": c[op_i], "checked": _truthy(c[chk_i])}
    return dims


def _load_reader():
    """动态加载 superteam-source-dingtalk-spreadsheet/scripts/read_spreadsheet.py。"""
    import importlib.util
    path = (Path(__file__).resolve().parent.parent.parent
            / "superteam-source-dingtalk-spreadsheet" / "scripts" / "read_spreadsheet.py")
    spec = importlib.util.spec_from_file_location("read_spreadsheet", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_rows(rs, tok, op, node_id, sid, rng, tries=6):
    """读指定小范围单元格，对钉钉 503/限流做退避重试（per-system sheet 很小，无需整表分页）。"""
    import time
    last = None
    for i in range(tries):
        try:
            return rs._fetch_range(tok, op, node_id, sid, rng)
        except Exception as e:   # noqa: 503/网络抖动 → 退避重试
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def build_release_from_workbook(node_id: str, batch: str) -> str:
    """读一个钉钉 .axls「发布文档」→ 渲染本 skill 格式的 RELEASE.md 文本。
    只保留实际有部署变更（非空维度）的系统，去掉钉钉里大量 FALSE 空行。"""
    rs = _load_reader()
    tok = rs.get_access_token()
    op = rs._load_config().get("DINGTALK_OPERATOR_ID") or rs.env("DINGTALK_OPERATOR_ID")
    sheets = rs.list_sheets(tok, op, node_id)
    by_name = {s.get("name"): (s.get("id") or s.get("sheetId")) for s in sheets}
    master_id = by_name.get("系统变更列表")
    if not master_id:
        raise RuntimeError(f"workbook {node_id} 缺少『系统变更列表』主表")
    master_rows = _read_rows(rs, tok, op, node_id, master_id, "A1:I200")
    systems = parse_master(master_rows)
    # 主表 c0=系统名 c1=系统变更链接(=对应 sheet 名)，建 name→sheet 名映射用于定位明细 sheet
    link_of = {}
    for r in master_rows:
        c = [x.strip() for x in r]
        if len(c) >= 2 and c[0] and c[1]:
            link_of[c[0]] = c[1]
    for sc in systems:
        sheet_name = link_of.get(sc.name, sc.name)
        sid = by_name.get(sheet_name) or by_name.get(sc.name)
        if sid:
            sc.dimensions = parse_system_sheet(_read_rows(rs, tok, op, node_id, sid, "A1:G40"))
    # 只留本批改动的系统：有部署明细维度，或 master 标了修改范围 / 提测分支
    involved = [sc for sc in systems if sc.dimensions or sc.scope or sc.review_branch]
    # 同名系统去重（master 里同一系统可能出现多行），合并维度、保留信息更全的元数据
    merged: dict[str, SystemChange] = {}
    for sc in involved:
        ex = merged.get(sc.name)
        if ex is None:
            merged[sc.name] = sc
        else:
            ex.dimensions.update(sc.dimensions)
            ex.scope = ex.scope or sc.scope
            ex.review_branch = ex.review_branch or sc.review_branch
            ex.dev_owner = ex.dev_owner or sc.dev_owner
            ex.ops_executor = ex.ops_executor or sc.ops_executor
    auto = render_release_auto(batch, list(merged.values()), tasks=[])
    template = (TPL / "release.md.tmpl").read_text(encoding="utf-8").replace("{batch}", batch)
    return merge_release(None, auto, template)


def main() -> int:
    p = argparse.ArgumentParser(
        description="回迁钉钉发布文档 .axls → trex-releases RELEASE.md（按 workbook 显式指定）")
    p.add_argument("--workbook", action="append", default=[],
                   help="nodeId=batch（可重复），如 YMyQ...=20260605-world-cup")
    p.add_argument("--releases-root", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    out = {"written": [], "dry_run": args.dry_run}
    for spec in args.workbook:
        if "=" not in spec:
            raise SystemExit(f"--workbook 需 nodeId=batch 格式: {spec}")
        node_id, batch = spec.split("=", 1)
        content = build_release_from_workbook(node_id.strip(), batch.strip())
        rp = Path(args.releases_root) / "releases" / batch.strip() / "RELEASE.md"
        if not args.dry_run:
            rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_text(content, encoding="utf-8")
        out["written"].append(str(rp))
    print(json.dumps(out, ensure_ascii=False))
    return 0


# `〔自动发现〕` 钉钉「提测版本」下"最近 2 个批次"的 nodeId 需用 dingtalk MCP list_nodes 取
# （脚本无该 API）；取到后以 --workbook nodeId=batch 传入。迁移当次由调用方提供 nodeId。
if __name__ == "__main__":
    raise SystemExit(main())
