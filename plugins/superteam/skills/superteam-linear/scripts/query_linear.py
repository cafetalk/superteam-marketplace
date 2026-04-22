#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Linear 工单查询：通过本机 Linear MCP（`mcp-remote`）直连 `https://mcp.linear.app/mcp`。

默认即启用 local-mcp：本脚本会启动

  npx -y mcp-remote https://mcp.linear.app/mcp

并通过 stdio JSON-RPC 调用 `tools/list` / `tools/call`。

作为“通用 MCP 调用器”：
- 不传 `--tool`：输出 Linear MCP 的全部工具清单（含 input schema）
- 传 `--tool <name>`：按你提供的 `--args-json`（或 stdin JSON）原样调用该工具
- `--tool save_issue`：可用 `--issue-kind task|demand|bug` 合并标签；新建且无 `priority` 时默认 `3`（见 SKILL.md）
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SHARED = str(Path(__file__).resolve().parent.parent.parent / "_shared")
if _SHARED not in sys.path:
    sys.path.insert(0, _SHARED)


@dataclass
class _Tool:
    name: str
    input_schema: dict | None


class _LocalMcpError(Exception):
    pass


class _StdioMcpClient:
    """Minimal MCP stdio JSON-RPC client for `mcp-remote`."""

    def __init__(self, cmd: list[str]):
        self._cmd = cmd
        self._proc: subprocess.Popen[str] | None = None
        self._next_id = 1

    def __enter__(self):
        self._proc = subprocess.Popen(
            self._cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,  # inherit to show OAuth prompts/URLs
            text=True,
            bufsize=1,
        )
        self._call("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "superteam-linear", "version": "0.1.0"},
        })
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def _call(self, method: str, params: dict) -> dict:
        if not self._proc or not self._proc.stdin or not self._proc.stdout:
            raise _LocalMcpError("local mcp process not started")
        req_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        self._proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

        # Read line-delimited JSON responses until id matches.
        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise _LocalMcpError("local mcp closed stdout unexpectedly")
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                # Some transports may emit non-JSON lines; ignore.
                continue
            if msg.get("id") != req_id:
                continue
            if "error" in msg:
                err = msg["error"] or {}
                code = err.get("code", "unknown")
                message = err.get("message", "")
                raise _LocalMcpError(f"{code}: {message}")
            return msg.get("result", {}) or {}

    def list_tools(self) -> list[_Tool]:
        res = self._call("tools/list", {})
        tools = res.get("tools", [])
        out: list[_Tool] = []
        if isinstance(tools, list):
            for t in tools:
                if isinstance(t, dict) and isinstance(t.get("name"), str):
                    out.append(_Tool(name=t["name"], input_schema=t.get("inputSchema")))
        return out

    def call_tool(self, name: str, arguments: dict) -> Any:
        res = self._call("tools/call", {"name": name, "arguments": arguments})
        structured = (res.get("structuredContent") or {}).get("result")
        if structured is not None:
            return structured
        content = res.get("content", [])
        if content and isinstance(content, list) and isinstance(content[0], dict):
            if content[0].get("type") == "text":
                text = content[0].get("text", "")
                try:
                    return json.loads(text)
                except Exception:
                    return text
        return res


def _emit_json(payload: dict[str, Any]) -> bool:
    """Write JSON payload to stdout robustly for non-blocking pipes."""
    try:
        text = json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n"
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.buffer.flush()
        return True
    except (BlockingIOError, BrokenPipeError) as e:
        print(f"[superteam-linear] failed to write JSON output: {e}", file=sys.stderr, flush=True)
        return False


def _truncate_issues(result: Any, max_items: int) -> tuple[Any, bool, int | None]:
    """Truncate `result.issues` to max_items; return (result, truncated, total)."""
    if not isinstance(result, dict):
        return result, False, None
    issues = result.get("issues")
    if not isinstance(issues, list):
        return result, False, None
    total = len(issues)
    if total <= max_items:
        return result, False, total
    out = dict(result)
    out["issues"] = issues[:max_items]
    return out, True, total


def _read_args_json(args_json: str | None) -> dict:
    """Read JSON arguments from --args-json or stdin (if piped)."""
    if args_json:
        try:
            obj = json.loads(args_json)
        except json.JSONDecodeError as e:
            raise _LocalMcpError(f"--args-json 不是合法 JSON: {e}") from e
        if not isinstance(obj, dict):
            raise _LocalMcpError("--args-json 必须是 JSON object（字典）")
        return obj

    if not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if not raw:
            return {}
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as e:
            raise _LocalMcpError(f"stdin 不是合法 JSON: {e}") from e
        if not isinstance(obj, dict):
            raise _LocalMcpError("stdin JSON 必须是 object（字典）")
        return obj

    return {}


_ISSUE_ID_RE = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")


def _looks_like_issue_id(s: str) -> bool:
    return bool(_ISSUE_ID_RE.match((s or "").strip()))


def _merge_save_issue_defaults(arguments: dict[str, Any], issue_kind: str | None) -> dict[str, Any]:
    """save_issue：按 issue-kind 合并标签；新建且未指定 priority 时默认 3（Medium/Normal 刻度）。

    带 `id` 的更新请求不自动改 priority，避免覆盖已有优先级。
    """
    out = dict(arguments)
    raw_id = out.get("id")
    is_create = raw_id is None or (isinstance(raw_id, str) and not raw_id.strip())

    if issue_kind:
        labels = out.get("labels")
        if labels is None:
            out["labels"] = [issue_kind]
        elif isinstance(labels, list):
            lower = {str(x).lower() for x in labels if x is not None}
            if issue_kind.lower() not in lower:
                out["labels"] = [*labels, issue_kind]
        else:
            out["labels"] = [issue_kind]

    if is_create and "priority" not in out:
        out["priority"] = 3
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Query Linear via local MCP (mcp-remote).")
    parser.add_argument(
        "query",
        nargs="?",
        default="",
        help="自然语言查询或 Issue ID（如 SUP-7）。不填则默认列出 issues。",
    )
    parser.add_argument(
        "--first",
        type=int,
        default=50,
        help="自动 list_issues 返回数量（默认 50）。",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=50,
        help="输出中 issues 最大条数（默认 50，超出会截断并标记 truncated）。",
    )
    parser.add_argument(
        "--tool",
        help="高级模式：直接调用指定 MCP tool（不限制工具名）。",
    )
    parser.add_argument(
        "--args-json",
        help="高级模式：传给 tool 的 arguments（JSON object 字符串）。也可通过 stdin 传 JSON。",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="输出 tools/list（工具清单）。",
    )
    parser.add_argument(
        "--issue-kind",
        choices=["task", "demand", "bug"],
        default=None,
        help="仅在与 --tool save_issue 联用时：合并对应标签名，并在未指定 priority 时默认 3（与 superteam-linear SKILL 约定一致）。",
    )
    args = parser.parse_args()
    if args.max_items <= 0:
        raise _LocalMcpError("--max-items 必须 > 0")

    cmd = ["npx", "-y", "mcp-remote", "https://mcp.linear.app/mcp"]
    try:
        with _StdioMcpClient(cmd) as client:
            tools = client.list_tools()

            if args.list_tools:
                ok = _emit_json({
                    "skill": "superteam-linear",
                    "mode": "local-mcp",
                    "type": "tools_list",
                    "tools": [
                        {"name": t.name, "inputSchema": t.input_schema}
                        for t in tools
                    ],
                })
                return 0 if ok else 1

            # Advanced generic tool call (optional)
            if args.tool:
                selected = next((t for t in tools if t.name == args.tool), None)
                if not selected:
                    raise _LocalMcpError(f"未知 tool: {args.tool}（先用 --list-tools 查看可用工具名）")

                call_args = _read_args_json(args.args_json)
                # Convenience: pass positional query into `query` if tool supports it.
                if args.query and "query" not in call_args and selected.input_schema:
                    props = selected.input_schema.get("properties") if isinstance(selected.input_schema, dict) else None
                    if isinstance(props, dict) and "query" in props:
                        call_args["query"] = args.query

                if selected.name == "save_issue":
                    call_args = _merge_save_issue_defaults(call_args, args.issue_kind)

                result = client.call_tool(selected.name, call_args)
                result, truncated, total = _truncate_issues(result, args.max_items)

                output = {
                    "skill": "superteam-linear",
                    "mode": "local-mcp",
                    "type": "tool_call",
                    "tool": selected.name,
                    "arguments": call_args,
                    "result": result,
                }
                if truncated:
                    output["truncated"] = True
                    output["total"] = total
                    output["max_items"] = args.max_items

                ok = _emit_json(output)
                return 0 if ok else 1

            # Default auto mode (no tool selection)
            tool_names = {t.name for t in tools}
            if _looks_like_issue_id(args.query):
                tool_name = "get_issue" if "get_issue" in tool_names else "linear_get_issue"
                if tool_name not in tool_names:
                    raise _LocalMcpError("找不到 get_issue 工具（可用 --list-tools 查看）")
                result = client.call_tool(tool_name, {"id": args.query})
                output = {
                    "skill": "superteam-linear",
                    "mode": "local-mcp",
                    "type": "auto_get_issue",
                    "tool": tool_name,
                    "issue_id": args.query,
                    "result": result,
                }
            else:
                tool_name = "list_issues" if "list_issues" in tool_names else "linear_list_issues"
                if tool_name not in tool_names:
                    raise _LocalMcpError("找不到 list_issues 工具（可用 --list-tools 查看）")
                call_args: dict[str, Any] = {"first": args.first}
                if args.query:
                    call_args["query"] = args.query
                result = client.call_tool(tool_name, call_args)
                result, truncated, total = _truncate_issues(result, args.max_items)
                output = {
                    "skill": "superteam-linear",
                    "mode": "local-mcp",
                    "type": "auto_list_issues",
                    "tool": tool_name,
                    "query": args.query,
                    "arguments": call_args,
                    "result": result,
                }
                if truncated:
                    output["truncated"] = True
                    output["total"] = total
                    output["max_items"] = args.max_items

            ok = _emit_json(output)
            return 0 if ok else 1
    except FileNotFoundError:
        ok = _emit_json({
            "skill": "superteam-linear",
            "error": "local_mcp_missing",
            "message": "npx not found. Install Node.js (includes npx) to use this script.",
        })
        return 1 if ok else 1
    except _LocalMcpError as e:
        ok = _emit_json({
            "skill": "superteam-linear",
            "error": "local_mcp_failed",
            "message": str(e),
        })
        return 1 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
