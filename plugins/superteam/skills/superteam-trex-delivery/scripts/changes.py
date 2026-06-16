# scripts/changes.py
"""加载 + 校验 changes.yaml (依据 change-dimensions.yaml)。纯逻辑无 IO 写。"""
from __future__ import annotations
from pathlib import Path
import yaml
from model import ChangesDoc
from dimensions import dimension_keys

def load_changes(path) -> ChangesDoc:
    return ChangesDoc.from_dict(yaml.safe_load(Path(path).read_text(encoding="utf-8")))

def validate_changes(doc: ChangesDoc, expected_iteration: str | None = None) -> list[str]:
    """返回错误 list, 空 = 通过。fail fast 由调用方决定 (有错就 abort)。"""
    errs: list[str] = []
    if not doc.services:
        errs.append("services 为空: 一次提测至少改一个服务")
    if expected_iteration and doc.iteration != expected_iteration:
        errs.append(f"iteration 字段 {doc.iteration} != 路径 {expected_iteration}")
    keys = dimension_keys()
    for svc in doc.services:
        for c in svc.changes:
            if c.dim not in keys:
                errs.append(f"[{svc.name}] 非法维度 '{c.dim}' (不在 change-dimensions.yaml 22 维)")
    return errs
