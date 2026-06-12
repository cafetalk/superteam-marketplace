# scripts/batch.py
"""批次身份解析：<date>-<project-slug>。日期来源 --batch > --date > project target date > 报错。"""
from __future__ import annotations
import re


def slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^0-9a-z一-鿿\-]", "", s)   # 允许中文，去其他符号
    return re.sub(r"-+", "-", s).strip("-")


def _norm_date(d: str) -> str:
    """YYYY-MM-DD / YYYYMMDD → YYYYMMDD。"""
    digits = re.sub(r"\D", "", d)
    if len(digits) != 8:
        raise ValueError(f"日期格式不合法（需 YYYYMMDD 或 YYYY-MM-DD）: {d}")
    return digits


def resolve_batch(batch: str | None, date: str | None,
                  project_slug: str, project_target_date: str | None) -> str:
    if batch:
        return batch
    chosen = date or project_target_date
    if not chosen:
        raise ValueError(
            "无法确定批次日期：请用 --batch 或 --date 显式指定，"
            "或在 Linear Project 上设置 target date（绝不用今天兜底）")
    if not project_slug:
        raise ValueError("project slug 为空（Linear Project 名缺失？）—— 请用 --batch 显式指定批次名")
    return f"{_norm_date(chosen)}-{project_slug}"
