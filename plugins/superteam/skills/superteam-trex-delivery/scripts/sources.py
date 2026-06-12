# scripts/sources.py
"""Linear / GitLab 数据源封装：子进程调既有 skill，stdout 抽 JSON。"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parent.parent.parent
LINEAR = SKILLS_ROOT / "superteam-linear" / "scripts" / "query_linear.py"


def _run_json(cmd: list[str], stdin: str | None = None) -> dict:
    res = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=120)
    text = (res.stdout or "").strip()
    if res.returncode != 0:
        # 子进程失败时（如 query_linear MCP 连接失败）即便 stdout 有 error JSON 也不能当成功结果
        raise RuntimeError(
            f"子进程退出 {res.returncode}：{(res.stderr or '')[:200]} / stdout={text[:200]}")
    for i in range(len(text) - 1, -1, -1):
        if text[i] == "{":
            try:
                return json.loads(text[i:])
            except json.JSONDecodeError:
                continue
    raise RuntimeError(
        f"无法从 stdout 解析 JSON（returncode={res.returncode}）：{text[:200]} / stderr={res.stderr[:200]}")


def fetch_issue(issue_id: str) -> dict:
    """返回 Linear issue（含 project.targetDate / assignee）。
    `〔已核实〕` Linear MCP 工具名 = `get_issue`，入参 `id`（issue identifier，如 TREX-123）。"""
    out = _run_json(["python3", str(LINEAR), "--tool", "get_issue",
                     "--args-json", json.dumps({"id": issue_id})])
    return out.get("issue") or out.get("result") or out


def _fetch_raw_mrs(issue_id: str) -> dict:
    """拉该 issue 关联 MR 的原始结果（IO 接缝，测试 mock 此函数的上游 `_run_json`）。
    `〔待接 GitLab — 唯一未 live-wire 的一步〕`：本 workspace 的 Linear `list_diffs` 返回空
    （团队未把 GitLab MR 关联进 Linear git 集成），MR/分支/repo 须走 GitLab：按
    'Tracks Linear <id>' 在 t-rex 各仓搜 MR description。接好前此调用在 live 下会失败 → 上层吞为 []。"""
    return _run_json(["python3", str(LINEAR), "--tool", "list_issue_mrs",
                      "--args-json", json.dumps({"id": issue_id})])


def fetch_issue_mrs(issue_id: str) -> list[dict]:
    """返回该 issue 关联的 GitLab MR（{web_url, target_branch, repo, description}），
    按 description 含 'Tracks Linear <id>' 过滤；首个 MR 的 target_branch 即 review_*。
    MR 源未接通时返回 []（不抛错）—— handoff 仍产出提测单主体，受影响系统矩阵留空待人填。"""
    try:
        out = _fetch_raw_mrs(issue_id)
    except Exception:
        return []
    mrs = out.get("mrs") or []
    return [m for m in mrs if f"Tracks Linear {issue_id}" in (m.get("description") or "")]
