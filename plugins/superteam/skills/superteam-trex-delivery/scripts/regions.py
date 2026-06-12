# scripts/regions.py
"""RELEASE.md 的 auto/manual 区块合并。auto 区整段重生成，manual 区保留。"""
from __future__ import annotations

AUTO_BEGIN = "<!-- trex-delivery:auto:begin -->"
AUTO_END = "<!-- trex-delivery:auto:end -->"


def merge_release(existing: str | None, auto_body: str, template: str) -> str:
    """existing 为 None → 用 template（含 %AUTO% 占位）首次生成；
    否则只替换 existing 中 AUTO_BEGIN..AUTO_END 之间的内容，manual 区原样保留。"""
    auto_block = f"{AUTO_BEGIN}\n{auto_body}\n{AUTO_END}"
    if existing is None:
        if "%AUTO%" not in template:
            raise ValueError("template 缺少 %AUTO% 占位")
        return template.replace("%AUTO%", auto_block)
    if AUTO_BEGIN not in existing or AUTO_END not in existing:
        raise ValueError("existing RELEASE.md 缺少 auto 区块标记，拒绝覆盖")
    if existing.index(AUTO_BEGIN) > existing.index(AUTO_END):
        raise ValueError("existing RELEASE.md 的 auto 区块标记顺序异常（END 在 BEGIN 前），拒绝覆盖")
    pre = existing.split(AUTO_BEGIN, 1)[0]
    post = existing.split(AUTO_END, 1)[1]
    return f"{pre}{auto_block}{post}"
