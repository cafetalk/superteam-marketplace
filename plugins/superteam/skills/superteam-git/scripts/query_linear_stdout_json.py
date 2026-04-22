# -*- coding: utf-8 -*-
"""从 query_linear.py 的合并 stdout/stderr 中提取 superteam-linear 工具结果。

mcp-remote 会在同一流里输出 JSON-RPC 与日志行；若只取「最后一个 {」起截断解析，
常会落到不完整的 RPC 片段或其它 JSON，导致 `result` 缺失。本模块用括号平衡扫描
所有顶层 JSON 对象，再选取 `skill == "superteam-linear"` 且含 `result` 的包裹 dict。
"""
from __future__ import annotations

import json
from typing import Any


def extract_insight_linear_payload(text: str) -> dict[str, Any]:
    """返回形如 {\"skill\": \"superteam-linear\", \"result\": {...}, ...} 的 dict；失败返回 {}。"""
    if not text:
        return {}
    candidates: list[dict[str, Any]] = []
    n = len(text)
    i = 0
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        start = i
        j = i
        while j < n:
            c = text[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    chunk = text[start : j + 1]
                    try:
                        obj = json.loads(chunk)
                    except json.JSONDecodeError:
                        i = j + 1
                        break
                    if (
                        isinstance(obj, dict)
                        and obj.get("skill") == "superteam-linear"
                        and isinstance(obj.get("result"), dict)
                    ):
                        candidates.append(obj)
                    i = j + 1
                    break
            j += 1
        else:
            i += 1

    if not candidates:
        return {}

    # 优先带 issue id 的 save_issue/get_issue 形态，其次 list_issues（issues 数组）
    for d in reversed(candidates):
        r = d["result"]
        if str(r.get("id") or "").strip():
            return d
    for d in reversed(candidates):
        r = d["result"]
        if isinstance(r.get("issues"), list):
            return d
    return candidates[-1]
