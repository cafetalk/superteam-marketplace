# scripts/gitlab_mr.py
"""提测 MR 创建：纯函数（推导 review 分支 / 解析 project path / 解析 reviewer）+ GitLab IO。"""
from __future__ import annotations
import json, os, re, urllib.error, urllib.parse, urllib.request
from pathlib import Path

GITLAB_API = "https://gitlab.com/api/v4"


def derive_review_branch(dev_branch: str) -> str:
    if not re.fullmatch(r"dev_\d{6,8}_[\w.-]+", dev_branch):
        raise ValueError(f"dev 分支名不合规（应 dev_<date>_<name>）: {dev_branch}")
    return "review_" + dev_branch[len("dev_"):]


def parse_project_path(remote_url: str) -> str:
    s = remote_url.strip()
    s = re.sub(r"^git@[^:]+:", "", s)
    s = re.sub(r"^https?://[^/]+/", "", s)
    return re.sub(r"\.git$", "", s)


def resolve_reviewer(project_path: str, override: str | None, config: dict) -> str:
    if override:
        return override
    for key, user in (config.get("map") or {}).items():
        if project_path == key or project_path.endswith("/" + key) or project_path.endswith(key):
            return user
    raise ValueError(
        f"未找到 {project_path} 的 team lead reviewer —— 请在 references/team-leads.json 配置，或用 --reviewer 指定")


def load_team_leads() -> dict:
    p = Path(__file__).resolve().parent.parent / "references" / "team-leads.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"map": {}}


# ---------------------------------------------------------------------------
# GitLab REST IO （测试 mock `_api`，不打真接口）
# ---------------------------------------------------------------------------

def _api(method: str, path: str, token: str, body: dict | None = None,
         ok_codes: tuple = (200, 201)):
    """调 GitLab REST。method/path（相对 GITLAB_API）+ token；body 走 JSON。
    返回解析后的 JSON（dict/list）；非预期状态码抛 RuntimeError（带响应体）。"""
    url = GITLAB_API + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("PRIVATE-TOKEN", token)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace") if hasattr(e, "read") else ""
        if e.code in ok_codes:
            return json.loads(raw) if raw else {}
        raise RuntimeError(f"GitLab {method} {path} → HTTP {e.code}: {raw[:500]}")


def open_handoff_mr(token: str, project_path: str, dev_branch: str, issues: list[str],
                    reviewer: str, dry_run: bool = False) -> dict:
    """建（或复用）提测 MR：dev_<date>_<name> → review_<date>_<name>。
    issues 为关联的 Linear issue 列表（≥1）；description 首部每行一个 `Tracks Linear <id>`，
    GitLab 自动各自联动。dry_run=True → 零 `_api` 调用，只算 review 分支并返回。
    否则：解析 project id → reviewer user id → 确保 review 分支（已存在吞 400）→
    建 MR（同源同目标已开则复用）。返回 {web_url, iid, review_branch, repo, dry_run}。"""
    review_branch = derive_review_branch(dev_branch)
    repo = project_path.rsplit("/", 1)[-1]
    if dry_run:
        # 形状与正常返回一致（含 repo / web_url），下游 mr_override 不会 KeyError
        return {"web_url": "", "iid": None, "review_branch": review_branch,
                "repo": repo, "dry_run": True}

    enc_path = urllib.parse.quote(project_path, safe="")
    project = _api("GET", f"/projects/{enc_path}", token)
    pid = project["id"]

    users = _api("GET", f"/users?username={urllib.parse.quote(reviewer)}", token)
    if not users:
        raise RuntimeError(f"GitLab 上找不到 reviewer 用户名: {reviewer}")
    uid = users[0]["id"]

    # 确保 review 分支存在：已存在时 GitLab 返回 400 → 吞掉继续。
    _api("POST",
         f"/projects/{pid}/repository/branches"
         f"?branch={urllib.parse.quote(review_branch)}&ref=master",
         token, ok_codes=(200, 201, 400))

    # 建 MR；同源同目标已有 open MR 时 GitLab 返回 409 → 复用，不重复建。
    tracks = "\n".join(f"Tracks Linear {i}" for i in issues)   # 每个 issue 一行，GitLab 各自联动
    mr = _api("POST", f"/projects/{pid}/merge_requests", token, ok_codes=(200, 201, 409), body={
        "source_branch": dev_branch,
        "target_branch": review_branch,
        "title": f"提测: {dev_branch} → {review_branch}",
        "description": f"{tracks}\n\n由 superteam-trex-delivery submit 代建提测 MR。",
        "reviewer_ids": [uid],   # team lead 作 reviewer（assignee 留默认=作者/开发，符合 handbook common/03）
    })
    if not mr.get("web_url"):
        # 409（已存在）或空响应 → GET 同源同目标的 open MR 复用。
        existing = _api(
            "GET",
            f"/projects/{pid}/merge_requests"
            f"?source_branch={urllib.parse.quote(dev_branch)}"
            f"&target_branch={urllib.parse.quote(review_branch)}&state=opened",
            token)
        if existing:
            mr = existing[0]
    return {"web_url": mr.get("web_url", ""), "iid": mr.get("iid"),
            "review_branch": review_branch, "repo": repo, "dry_run": False}
