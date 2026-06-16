# scripts/dimensions.py
"""Canonical 部署变更维度 — 从 templates/change-dimensions.yaml 加载。"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import yaml
from model import SystemChange

_TPL = Path(__file__).resolve().parent.parent / "templates" / "change-dimensions.yaml"


@lru_cache(maxsize=1)
def _load() -> dict:
    return yaml.safe_load(_TPL.read_text(encoding="utf-8"))


def load_dimensions() -> list[dict]:
    return _load()["dimensions"]


def dimension_keys() -> set[str]:
    return {d["key"] for d in load_dimensions()}


def dimension_order() -> dict[str, int]:
    return {d["key"]: i for i, d in enumerate(load_dimensions())}


def columns() -> list[str]:
    return _load()["columns"]


def render_system_matrix(systems: list[SystemChange]) -> str:
    if not systems:
        return "> 本次无系统改动。\n"
    order = dimension_order()
    blocks: list[str] = []
    for sc in systems:
        rows = []
        for key in sorted(sc.dimensions, key=lambda k: order.get(k, 999)):
            cell = sc.dimensions[key]
            beta = (cell.get("beta") or "").replace("\n", "<br>") or "-"
            prod = (cell.get("prod") or "").replace("\n", "<br>") or "-"
            op = cell.get("operator") or ""
            chk = "☑" if cell.get("checked") else "☐"
            rows.append(f"| {key} | {beta} | {prod} | {op} | {chk} |")
        # 即使维度未填也保留 ### 标题：提测刚生成时矩阵待人填，
        # 且 release 要靠 ### 反解系统名（见 release._parse_submission）。
        if rows:
            body = ("| 变更项 | beta | prod | 操作人 | 检查 |\n"
                    "|---|---|---|---|---|\n" + "\n".join(rows))
        else:
            body = "> 维度待填（本次该系统改动维度，提测后人工补充）。"
        blocks.append(f"### {sc.name}\n\n{body}\n")
    return "\n".join(blocks)
