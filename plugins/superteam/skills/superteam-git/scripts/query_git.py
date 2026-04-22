#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""superteam-git: auto discover git repos, collect commits, and analyze features.

Discovery rule:
- Recursively scan workspace
- If a directory contains `.git`, treat it as one repo
- Stop scanning deeper under that directory
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

_sys_path_shared = str(Path(__file__).resolve().parent.parent.parent / "_shared")
if _sys_path_shared not in sys.path:
    sys.path.insert(0, _sys_path_shared)
from config import env  # type: ignore


EXCLUDE_DIRS = {
    ".svn",
    ".hg",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "target",
    ".next",
}


@dataclass
class CommitItem:
    repo: str
    repo_path: str
    commit: str
    author: str
    author_email: str
    committed_at: str
    message: str
    files_changed: int
    insertions: int
    deletions: int
    files: list[str] = field(default_factory=list)
    feature_tags: list[str] = field(default_factory=list)
    feature_summary: str = ""
    work_summary: str = ""
    impact_summary: str = ""
    business_impact_summary: str = ""
    evidence: list[str] = field(default_factory=list)
    detailed_changes: list[str] = field(default_factory=list)
    message_full: str = ""


def _week_range(week_mode: str) -> tuple[date, date]:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    if week_mode == "last":
        monday = monday - timedelta(days=7)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _parse_date(value: str) -> date:
    # Accept: YYYY-MM-DD
    return datetime.strptime(value, "%Y-%m-%d").date()


def _resolve_time_window(
    week: str,
    since_date: str | None,
    until_date: str | None,
) -> tuple[datetime, datetime, str, list[str]]:
    notes: list[str] = []
    if since_date or until_date:
        if not since_date or not until_date:
            raise ValueError("--since-date 和 --until-date 必须同时提供")
        start_day = _parse_date(since_date)
        end_day = _parse_date(until_date)
        if start_day > end_day:
            raise ValueError("since-date 不能晚于 until-date")
        since_dt = datetime.combine(start_day, time.min)
        until_dt = datetime.combine(end_day, time.max)
        mode = "custom"
        notes.append("time_window_source=custom_date_range")
        return since_dt, until_dt, mode, notes

    week_start, week_end = _week_range(week)
    since_dt = datetime.combine(week_start, time.min)
    until_dt = datetime.combine(week_end, time.max)
    mode = week
    notes.append("time_window_source=week_mode")
    return since_dt, until_dt, mode, notes


def _extract_dates_from_query(query: str) -> tuple[str | None, str | None]:
    """Extract two dates from natural language query.

    Supports:
    - 3.15 / 4.1
    - 3-15 / 4-1
    - 3月15号 / 4月1日
    - 2026-03-15 / 2026-04-01
    """
    if not query:
        return None, None

    pattern = re.compile(r"(?:(\d{4})[年/\-.])?\s*(\d{1,2})[月/\-.](\d{1,2})(?:日|号)?")
    matches = list(pattern.finditer(query))
    if len(matches) < 2:
        return None, None

    year_now = datetime.now().year

    def to_iso(m: re.Match[str]) -> str:
        y_raw, mo_raw, d_raw = m.group(1), m.group(2), m.group(3)
        y = int(y_raw) if y_raw else year_now
        mo = int(mo_raw)
        d = int(d_raw)
        return date(y, mo, d).isoformat()

    try:
        since = to_iso(matches[0])
        until = to_iso(matches[1])
    except ValueError:
        return None, None
    return since, until


def split_workspace_env_value(raw: str) -> list[str]:
    """Split SUPERTEAM_GIT_WORKSPACE / CLI path list using OS path separator.

    Unix/macOS: `:` — e.g. `/Users/a/proj:/Users/b/work`.
    Windows: `;` — e.g. `C:\\a;D:\\b`.
    """
    return [p.strip() for p in raw.split(os.pathsep) if p.strip()]


def _resolve_workspaces(cli_paths: list[str] | None) -> list[Path]:
    """Resolve one or more workspace roots (CLI overrides env)."""
    if cli_paths:
        return [Path(p).expanduser().resolve() for p in cli_paths]
    cfg_val = env("SUPERTEAM_GIT_WORKSPACE")
    if cfg_val and cfg_val.strip():
        return [
            Path(segment).expanduser().resolve()
            for segment in split_workspace_env_value(cfg_val.strip())
        ]
    return [Path("~/code").expanduser().resolve()]


def _run_git(args: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(args, capture_output=True, text=True, cwd=cwd)
    return proc.returncode, proc.stdout, proc.stderr


def _get_default_author_patterns() -> list[str]:
    patterns: list[str] = []
    for key in ("user.email", "user.name"):
        code, out, _ = _run_git(["git", "config", "--global", "--get", key])
        if code == 0 and out.strip():
            patterns.append(out.strip())
    seen = set()
    deduped = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped


def discover_repos(workspace: Path) -> list[Path]:
    repos: list[Path] = []
    # 当 workspace 直接指向裸仓根（如 mirror 的 foo.git）时立即返回，避免 os.walk 进入 objects/
    if workspace.is_dir():
        w = workspace.resolve()
        if (w / "HEAD").is_file() and (w / "objects").is_dir() and not (w / ".git").exists():
            return [w]

    for root, dirs, _files in os.walk(workspace, topdown=True):
        if ".git" in dirs:
            repos.append(Path(root))
            dirs[:] = []  # stop descending this repo
            continue
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
    return repos


def discover_repos_multi(workspaces: list[Path]) -> list[Path]:
    """Discover repos under multiple roots; same repo path only once."""
    seen: set[str] = set()
    out: list[Path] = []
    for ws in workspaces:
        for repo in discover_repos(ws):
            key = str(repo.resolve())
            if key in seen:
                continue
            seen.add(key)
            out.append(repo)
    return out


def _parse_log_output(repo: Path, text: str) -> list[CommitItem]:
    commits: list[CommitItem] = []
    current: CommitItem | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("__COMMIT__"):
            if current:
                commits.append(current)
            payload = line.replace("__COMMIT__", "", 1)
            parts = payload.split("|", 4)
            if len(parts) != 5:
                current = None
                continue
            current = CommitItem(
                repo=repo.name,
                repo_path=str(repo),
                commit=parts[0],
                author=parts[1],
                author_email=parts[2],
                committed_at=parts[3],
                message=parts[4],
                files_changed=0,
                insertions=0,
                deletions=0,
            )
            continue

        # numstat line: "12 3 path/to/file"
        if current:
            fields = line.split("\t")
            if len(fields) >= 3:
                ins_raw, del_raw = fields[0], fields[1]
                ins = int(ins_raw) if ins_raw.isdigit() else 0
                dels = int(del_raw) if del_raw.isdigit() else 0
                path = fields[2]
                current.insertions += ins
                current.deletions += dels
                current.files_changed += 1
                current.files.append(path)

    if current:
        commits.append(current)
    return commits


def _dedupe_commits_by_hash(commits: list[CommitItem]) -> list[CommitItem]:
    seen: set[str] = set()
    out: list[CommitItem] = []
    for c in commits:
        if c.commit in seen:
            continue
        seen.add(c.commit)
        out.append(c)
    return out


def _list_local_branch_short_names(repo: Path) -> list[str]:
    code, out, _ = _run_git(
        [
            "git",
            "-C",
            str(repo),
            "for-each-ref",
            "--format=%(refname:short)",
            "refs/heads/",
        ]
    )
    if code != 0:
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def _rev_has_commits_in_window(
    repo: Path,
    rev: str,
    since: str,
    until: str,
    author: str,
) -> bool:
    cmd = [
        "git",
        "-C",
        str(repo),
        "log",
        rev,
        f"--since={since}",
        f"--until={until}",
        "--oneline",
        "-n",
        "1",
    ]
    if author:
        cmd.append(f"--author={author}")
    code, out, _ = _run_git(cmd)
    return code == 0 and bool(out.strip())


def _collect_log_for_rev(
    repo: Path,
    since_dt: datetime,
    until_dt: datetime,
    author_patterns: list[str],
    *,
    rev: str | None = None,
    use_all: bool = False,
) -> tuple[list[CommitItem], str | None]:
    since = since_dt.strftime("%Y-%m-%d %H:%M:%S")
    until = until_dt.strftime("%Y-%m-%d %H:%M:%S")
    all_items: list[CommitItem] = []

    patterns = author_patterns or [""]
    for author in patterns:
        cmd: list[str] = [
            "git",
            "-C",
            str(repo),
            "log",
            f"--since={since}",
            f"--until={until}",
            "--pretty=format:__COMMIT__%H|%an|%ae|%ad|%s",
            "--date=iso",
            "--numstat",
        ]
        if use_all:
            cmd.append("--all")
        elif rev:
            cmd.append(rev)
        if author:
            cmd.append(f"--author={author}")
        code, out, err = _run_git(cmd)
        if code != 0:
            return [], err.strip() or "git log failed"
        all_items.extend(_parse_log_output(repo, out))

    # de-dup commits merged from multiple author patterns
    return _dedupe_commits_by_hash(all_items), None


def collect_repo_commits(
    repo: Path,
    since_dt: datetime,
    until_dt: datetime,
    author_patterns: list[str],
    branch_scope: str = "active",
) -> tuple[list[CommitItem], str | None]:
    """Collect commits in the time window.

    branch_scope:
    - active: only local branches that have >=1 matching commit in the window, then merge + dedupe
    - head: only current HEAD (same as historical default)
    - all: git log --all (all refs)
    """
    patterns = author_patterns or [""]
    since_s = since_dt.strftime("%Y-%m-%d %H:%M:%S")
    until_s = until_dt.strftime("%Y-%m-%d %H:%M:%S")

    if branch_scope == "head":
        return _collect_log_for_rev(
            repo, since_dt, until_dt, author_patterns, rev=None, use_all=False
        )

    if branch_scope == "all":
        return _collect_log_for_rev(
            repo, since_dt, until_dt, author_patterns, rev=None, use_all=True
        )

    branches = _list_local_branch_short_names(repo)
    active_branches: list[str] = []
    for b in branches:
        for author in patterns:
            if _rev_has_commits_in_window(repo, b, since_s, until_s, author):
                active_branches.append(b)
                break

    if not active_branches:
        return _collect_log_for_rev(
            repo, since_dt, until_dt, author_patterns, rev=None, use_all=False
        )

    merged: list[CommitItem] = []
    for b in active_branches:
        batch, err = _collect_log_for_rev(
            repo, since_dt, until_dt, author_patterns, rev=b, use_all=False
        )
        if err:
            return [], err
        merged.extend(batch)

    return _dedupe_commits_by_hash(merged), None


def _get_commit_message_full(repo: Path, commit_hash: str) -> str:
    """Return full commit message (subject + body/footer)."""
    code, out, _ = _run_git(
        ["git", "-C", str(repo), "show", "-s", "--format=%B", commit_hash]
    )
    if code != 0:
        return ""
    return out.strip()


def _get_patch_excerpt(repo: Path, commit_hash: str, max_lines: int = 220) -> str:
    cmd = [
        "git", "-C", str(repo), "show",
        "--no-color",
        "--pretty=format:",
        "--unified=0",
        commit_hash,
    ]
    code, out, _ = _run_git(cmd)
    if code != 0:
        return ""
    picked: list[str] = []
    for line in out.splitlines():
        if len(picked) >= max_lines:
            break
        if (
            line.startswith("diff --git")
            or line.startswith("@@")
            or line.startswith("+")
            or line.startswith("-")
        ):
            if line.startswith("+++") or line.startswith("---"):
                continue
            picked.append(line)
    return "\n".join(picked)


def _analyze_commit_feature(commit: CommitItem, patch_excerpt: str) -> tuple[list[str], str]:
    text = (
        f"{commit.message}\n"
        + "\n".join(commit.files)
        + "\n"
        + patch_excerpt
    ).lower()
    tags: list[str] = []

    def add(tag: str, cond: bool) -> None:
        if cond and tag not in tags:
            tags.append(tag)

    add("feature", any(k in text for k in ["feat", "feature", "新增", "新建", "add "]))
    add("bugfix", any(k in text for k in ["fix", "bug", "修复", "hotfix", "问题"]))
    add("refactor", any(k in text for k in ["refactor", "重构", "cleanup"]))
    add("docs", any(
        k in text for k in [".md", ".adoc", "readme", "文档", "周报", "changelog"]
    ))
    add("test", any(k in text for k in ["test", "pytest", "spec", "单测", "测试"]))
    add("api", any(k in text for k in ["api", "endpoint", "controller", "route", "graphql"]))
    add("database", any(k in text for k in ["sql", "migration", "schema", "db", "postgres"]))
    add("config", any(k in text for k in [".yml", ".yaml", ".json", "config", ".env"]))
    add("frontend", any(k in text for k in [".tsx", ".jsx", ".vue", "frontend", "ui", "css"]))
    add("backend", any(k in text for k in [".py", ".go", ".java", ".kt", "service", "backend"]))
    add("ci-cd", any(k in text for k in ["github/workflows", "gitlab-ci", "dockerfile", "ci"]))

    if not tags:
        tags = ["misc"]

    # first 1-2 tags as short summary
    if len(tags) == 1:
        summary = tags[0]
    else:
        summary = f"{tags[0]} + {tags[1]}"
    return tags, summary


def _infer_areas(files: list[str]) -> list[str]:
    areas: list[str] = []
    text = "\n".join(files).lower()

    def add(area: str, cond: bool) -> None:
        if cond and area not in areas:
            areas.append(area)

    add("provider", "provider" in text)
    add("graphql", "graphql" in text or ".graphql" in text)
    add("mcp", "mcp" in text)
    add("session/tunnel", any(k in text for k in ["session", "tunnel"]))
    add("database", any(k in text for k in ["migration", "sql", "repository", "db/"]))
    add("docs", any(k in text for k in ["docs/", ".md", ".adoc", "readme"]))
    add("config", any(k in text for k in ["config", ".json", ".yml", ".yaml", ".env"]))
    add("tests", any(k in text for k in ["test", "spec"]))
    add("server", any(k in text for k in ["server", "handler", "service"]))
    add("client/ui", any(k in text for k in [".tsx", ".jsx", ".vue", "ui/", "frontend"]))

    if not areas:
        areas = ["general"]
    return areas


def _summarize_commit_work(commit: CommitItem) -> tuple[str, str, str]:
    areas = _infer_areas(commit.files)
    primary = areas[0]

    if "feature" in commit.feature_tags:
        work = f"新增/扩展 {primary} 能力"
    elif "bugfix" in commit.feature_tags:
        work = f"修复 {primary} 相关问题"
    elif "refactor" in commit.feature_tags:
        work = f"重构 {primary} 代码结构"
    else:
        work = f"更新 {primary} 相关实现"

    impact_parts: list[str] = []
    if "api" in commit.feature_tags:
        impact_parts.append("影响接口行为或调用方式")
    if "database" in commit.feature_tags:
        impact_parts.append("影响数据模型/持久化逻辑")
    if "config" in commit.feature_tags:
        impact_parts.append("影响环境配置与部署参数")
    if "docs" in commit.feature_tags:
        impact_parts.append("补充实现文档与操作说明")
    if "test" in commit.feature_tags:
        impact_parts.append("提升可验证性与回归保障")
    if not impact_parts:
        impact_parts.append("对现有功能进行增量改进")

    impact = "；".join(impact_parts)
    business_parts: list[str] = []
    if "provider" in areas:
        business_parts.append("扩展可接入能力，提升合作方接入效率与覆盖面")
    if "graphql" in areas or "api" in commit.feature_tags:
        business_parts.append("提升数据可查询性，支持更快的业务联调与迭代")
    if "session/tunnel" in areas or "security" in commit.message.lower():
        business_parts.append("增强链路稳定性与安全性，降低线上故障与风控风险")
    if "database" in commit.feature_tags:
        business_parts.append("提升数据一致性与可追溯性，支撑业务分析决策")
    if "docs" in commit.feature_tags:
        business_parts.append("降低协作沟通成本，缩短新人和跨团队对齐时间")
    if "test" in commit.feature_tags:
        business_parts.append("提升交付质量，减少回归问题对业务进度的影响")
    if "config" in commit.feature_tags:
        business_parts.append("提升部署与环境切换效率，减少发布阻塞")
    if not business_parts:
        business_parts.append("持续优化研发交付效率，支持业务稳定推进")

    business = "；".join(dict.fromkeys(business_parts))
    return work, impact, business


def _extract_changed_symbols(patch_excerpt: str) -> list[str]:
    symbols: list[str] = []
    patterns = [
        r"(?:^|\s)def\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"(?:^|\s)class\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"(?:^|\s)function\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"(?:^|\s)const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=",
        r"(?:^|\s)async\s+function\s+([A-Za-z_][A-Za-z0-9_]*)",
    ]
    for line in patch_excerpt.splitlines():
        if not (line.startswith("+") or line.startswith("-")):
            continue
        text = line[1:]
        for p in patterns:
            m = re.search(p, text)
            if m:
                sym = m.group(1)
                if sym not in symbols:
                    symbols.append(sym)
    return symbols[:20]


def _build_evidence(commit: CommitItem, patch_excerpt: str) -> list[str]:
    ev: list[str] = []
    for f in commit.files[:8]:
        ev.append(f"file:{f}")
    for s in _extract_changed_symbols(patch_excerpt)[:8]:
        ev.append(f"symbol:{s}")
    # endpoint / graphql hints from patch
    endpoint_hits = re.findall(r"/api/[A-Za-z0-9_/\-]+", patch_excerpt)
    for ep in endpoint_hits[:5]:
        ev.append(f"endpoint:{ep}")
    gql_hits = re.findall(r"\b(query|mutation)\s+([A-Za-z_][A-Za-z0-9_]*)", patch_excerpt, flags=re.I)
    for kind, name in gql_hits[:5]:
        ev.append(f"graphql:{kind.lower()} {name}")
    # de-dup
    out: list[str] = []
    seen = set()
    for x in ev:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _extract_detailed_changes(commit: CommitItem, patch_excerpt: str) -> list[str]:
    """Extract concrete code-level changes with project-role meaning."""
    findings: list[str] = []
    current_file = ""

    def file_role(path: str) -> str:
        p = path.lower()
        if "/handlers/" in p or "/controller" in p:
            return "请求入口层"
        if "/services/" in p:
            return "业务服务层"
        if "/repository/" in p or "/dao/" in p:
            return "数据访问层"
        if "schema" in p or "resolver" in p or ".graphql" in p:
            return "接口契约层"
        if "/models/" in p or "migration" in p or ".sql" in p:
            return "数据模型层"
        if "/docs/" in p:
            return "文档与协作层"
        return "实现层"

    for raw in patch_excerpt.splitlines():
        line = raw.strip()
        if line.startswith("diff --git "):
            m = re.search(r" b/(.+)$", line)
            if m:
                current_file = m.group(1)
            continue
        if not line.startswith("+"):
            continue
        code = line[1:].strip()
        if not code:
            continue

        role = file_role(current_file) if current_file else "实现层"
        file_part = f"{current_file}" if current_file else (commit.files[0] if commit.files else "unknown")

        # Condition / guard
        if re.search(r"^(if|elif|else if)\b", code):
            findings.append(
                f"在 `{file_part}`（{role}）新增条件判断：`{code[:120]}`，会改变该分支下的执行路径和边界行为。"
            )
            continue
        if "return" in code and ("if " in code or "if(" in code):
            findings.append(
                f"在 `{file_part}`（{role}）增加保护性返回：`{code[:120]}`，可提前拦截异常路径并减少后续副作用。"
            )
            continue

        # API route / endpoint
        if "/api/" in code or re.search(r"\b(router|app)\.(get|post|put|delete|patch)\b", code):
            findings.append(
                f"在 `{file_part}`（{role}）新增/调整接口定义：`{code[:120]}`，会直接影响调用方请求行为。"
            )
            continue

        # Function / class
        if re.search(r"^(def|async def|function|async function|class)\b", code):
            findings.append(
                f"在 `{file_part}`（{role}）新增/变更核心符号：`{code[:120]}`，会影响该模块职责与调用链。"
            )
            continue
        if re.search(r"^(const|let|var)\s+[A-Za-z_][A-Za-z0-9_]*\s*=", code):
            findings.append(
                f"在 `{file_part}`（{role}）引入关键变量/配置：`{code[:120]}`，可能改变运行时参数与逻辑分支。"
            )
            continue

        # Data model / schema
        if re.search(r"\b(interface|type|enum)\b", code) or re.search(r"\b(create table|alter table|add column)\b", code, flags=re.I):
            findings.append(
                f"在 `{file_part}`（{role}）调整模型/结构：`{code[:120]}`，会影响上下游数据契约和兼容性。"
            )
            continue

        # Keep only high-signal lines
        if any(k in code.lower() for k in ["graphql", "provider", "session", "tunnel", "redis", "security", "rate"]):
            findings.append(
                f"在 `{file_part}`（{role}）改动关键逻辑：`{code[:120]}`，对对应能力路径有直接影响。"
            )

    # de-dup and limit
    out: list[str] = []
    seen = set()
    for x in findings:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out[:12]


def _derive_grounded_business_impact(commit: CommitItem, patch_excerpt: str) -> tuple[str, str]:
    """Return evidence-grounded (technical_impact, business_impact)."""
    corpus = (
        " ".join(commit.files).lower()
        + "\n"
        + commit.message.lower()
        + "\n"
        + patch_excerpt.lower()
    )

    tech: list[str] = []
    biz: list[str] = []

    def hit(keys: list[str]) -> bool:
        return any(k in corpus for k in keys)

    # Provider capability
    if hit(["provider", "list_providers", "search_providers", "get_provider"]):
        tech.append("新增/增强 provider 查询与检索能力")
        biz.append("业务侧可更快定位与接入可用 provider，缩短方案验证与上线准备时间")

    # GraphQL capability
    if hit(["graphql", ".graphql", "resolver", "mutation", "query "]):
        tech.append("扩展 GraphQL schema / resolver 查询能力")
        biz.append("上层业务系统可直接消费结构化查询接口，降低接口对接摩擦")

    # Session / tunnel / callback path
    if hit(["session", "tunnel", "claimtunnel", "callback"]):
        tech.append("改造会话/隧道链路逻辑")
        biz.append("降低链路中断与重试成本，减少任务执行失败对业务流程的影响")

    # Redis / cache / persistence
    if hit(["redis", "cache", "repository", "migration", "sql", "postgres", "db/"]):
        tech.append("调整数据存储或缓存访问路径")
        biz.append("提升数据一致性与读取稳定性，支撑统计与决策数据的可信度")

    # Security / rate limit
    if hit(["security", "rate-limiter", "kyc", "auth", "verify"]):
        tech.append("增强安全与风控相关逻辑")
        biz.append("降低异常调用和滥用风险，减少潜在业务损失与合规风险")

    # Docs / scripts
    if hit(["docs/", "readme", ".adoc", ".md", "curl", "guide"]):
        tech.append("补充操作文档与联调脚本")
        biz.append("跨团队协作与交接成本下降，需求交付节奏更稳定")

    # Tests
    if hit(["test", "pytest", "spec"]):
        tech.append("补强测试覆盖与回归保障")
        biz.append("回归风险下降，减少缺陷返工对排期的冲击")

    if not tech:
        tech = ["未从改动中识别出明确技术主题（需人工复核）"]
    if not biz:
        biz = ["未从改动中识别出明确业务影响（需人工复核）"]

    return "；".join(dict.fromkeys(tech)), "；".join(dict.fromkeys(biz))


def _analyze_commits(repo: Path, commits: list[CommitItem], max_analyze: int) -> None:
    if not commits:
        return
    for idx, c in enumerate(commits):
        # Ref footer usually lives in body, keep full message for downstream matching.
        if not c.message_full:
            c.message_full = _get_commit_message_full(repo, c.commit) or c.message
        if idx >= max_analyze:
            c.feature_tags = ["analysis-skipped"]
            c.feature_summary = "analysis-skipped"
            c.work_summary = "analysis-skipped"
            c.impact_summary = "analysis-skipped"
            c.business_impact_summary = "analysis-skipped"
            c.evidence = []
            c.detailed_changes = []
            continue
        excerpt = _get_patch_excerpt(repo, c.commit)
        tags, summary = _analyze_commit_feature(c, excerpt)
        c.feature_tags = tags
        c.feature_summary = summary
        work, _impact_old, _business_old = _summarize_commit_work(c)
        impact, business = _derive_grounded_business_impact(c, excerpt)
        c.work_summary = work
        c.impact_summary = impact
        c.business_impact_summary = business
        c.evidence = _build_evidence(c, excerpt)
        c.detailed_changes = _extract_detailed_changes(c, excerpt)


def _to_output(
    workspaces: list[Path],
    window_mode: str,
    since_dt: datetime,
    until_dt: datetime,
    notes: list[str],
    author_patterns: list[str],
    branch_scope: str,
    repos: list[Path],
    commits: list[CommitItem],
    repo_errors: list[dict[str, str]],
) -> dict[str, Any]:
    by_repo: dict[str, dict[str, Any]] = {}
    for c in commits:
        bucket = by_repo.setdefault(
            c.repo_path,
            {
                "name": c.repo,
                "path": c.repo_path,
                "commit_count": 0,
                "files_changed": 0,
                "insertions": 0,
                "deletions": 0,
            },
        )
        bucket["commit_count"] += 1
        bucket["files_changed"] += c.files_changed
        bucket["insertions"] += c.insertions
        bucket["deletions"] += c.deletions

    ws_strs = [str(w) for w in workspaces]
    return {
        "skill": "superteam-git",
        "status": "ok",
        "workspace": ", ".join(ws_strs),
        "workspaces": ws_strs,
        "git_branch_scope": branch_scope,
        "window_mode": window_mode,
        "time_range": [
            since_dt.strftime("%Y-%m-%d %H:%M:%S"),
            until_dt.strftime("%Y-%m-%d %H:%M:%S"),
        ],
        "notes": notes,
        "author_patterns": author_patterns,
        "summary": {
            "repos_discovered": len(repos),
            "repos_with_commits": len(by_repo),
            "total_commits": len(commits),
            "total_files_changed": sum(c.files_changed for c in commits),
            "total_insertions": sum(c.insertions for c in commits),
            "total_deletions": sum(c.deletions for c in commits),
            "repo_errors": repo_errors,
        },
        "repos": sorted(by_repo.values(), key=lambda x: x["commit_count"], reverse=True),
        "commits": [
            {
                "repo": c.repo,
                "repo_path": c.repo_path,
                "commit": c.commit,
                "author": c.author,
                "author_email": c.author_email,
                "committed_at": c.committed_at,
                "message": c.message,
                "message_full": c.message_full or c.message,
                "files_changed": c.files_changed,
                "insertions": c.insertions,
                "deletions": c.deletions,
                "files": c.files,
                "feature_tags": c.feature_tags,
                "feature_summary": c.feature_summary,
                "work_summary": c.work_summary,
                "impact_summary": c.impact_summary,
                "business_impact_summary": c.business_impact_summary,
                "evidence": c.evidence,
                "detailed_changes": c.detailed_changes,
                "code_evidence_text": " ".join(c.files + c.evidence + c.detailed_changes),
            }
            for c in commits
        ],
        "feature_overview": _build_feature_overview(commits),
        "analysis": _build_work_analysis(commits),
        "details": _build_repo_daily_details(commits),
        "project_summaries": _build_project_summaries(commits),
        "global_analysis": _build_global_analysis(commits),
    }


def _build_feature_overview(commits: list[CommitItem]) -> dict[str, Any]:
    tag_counter: dict[str, int] = {}
    for c in commits:
        for t in c.feature_tags:
            tag_counter[t] = tag_counter.get(t, 0) + 1
    top = sorted(tag_counter.items(), key=lambda x: x[1], reverse=True)
    return {
        "top_tags": [{"tag": t, "count": n} for t, n in top[:10]],
        "unique_tags": len(tag_counter),
    }


def _build_work_analysis(commits: list[CommitItem]) -> dict[str, Any]:
    if not commits:
        return {
            "work_items": [],
            "impact_summary": [],
            "business_impact_summary": [],
            "repo_work_summary": [],
        }

    ranked = sorted(
        commits,
        key=lambda c: (c.insertions + c.deletions, c.files_changed),
        reverse=True,
    )
    work_items = [
        {
            "repo": c.repo,
            "commit": c.commit[:8],
            "message": c.message,
                "message_full": c.message_full or c.message,
            "work": c.work_summary,
            "impact": c.impact_summary,
            "tags": c.feature_tags,
            "files_changed": c.files_changed,
            "detailed_changes": c.detailed_changes[:3],
        }
        for c in ranked[:10]
    ]

    impact_counter: dict[str, int] = {}
    for c in commits:
        if not c.impact_summary:
            continue
        for seg in c.impact_summary.split("；"):
            seg = seg.strip()
            if not seg:
                continue
            impact_counter[seg] = impact_counter.get(seg, 0) + 1
    impact_summary = [
        {"impact": k, "count": v}
        for k, v in sorted(impact_counter.items(), key=lambda x: x[1], reverse=True)[:8]
    ]

    biz_counter: dict[str, int] = {}
    for c in commits:
        if not c.business_impact_summary:
            continue
        for seg in c.business_impact_summary.split("；"):
            seg = seg.strip()
            if not seg:
                continue
            biz_counter[seg] = biz_counter.get(seg, 0) + 1
    business_impact_summary = [
        {"business_impact": k, "count": v}
        for k, v in sorted(biz_counter.items(), key=lambda x: x[1], reverse=True)[:8]
    ]

    by_repo: dict[str, dict[str, Any]] = {}
    for c in commits:
        item = by_repo.setdefault(
            c.repo_path,
            {"repo": c.repo, "work_tags": {}, "commit_count": 0},
        )
        item["commit_count"] += 1
        for t in c.feature_tags:
            item["work_tags"][t] = item["work_tags"].get(t, 0) + 1

    repo_work_summary: list[dict[str, Any]] = []
    for info in by_repo.values():
        tags_sorted = sorted(info["work_tags"].items(), key=lambda x: x[1], reverse=True)[:5]
        repo_work_summary.append(
            {
                "repo": info["repo"],
                "commit_count": info["commit_count"],
                "focus": [{"tag": t, "count": n} for t, n in tags_sorted],
            }
        )
    repo_work_summary.sort(key=lambda x: x["commit_count"], reverse=True)

    return {
        "work_items": work_items,
        "impact_summary": impact_summary,
        "business_impact_summary": business_impact_summary,
        "repo_work_summary": repo_work_summary,
    }


def _build_repo_daily_details(commits: list[CommitItem]) -> dict[str, Any]:
    repo_map: dict[str, dict[str, Any]] = {}
    for c in commits:
        bucket = repo_map.setdefault(
            c.repo_path,
            {
                "repo": c.repo,
                "repo_path": c.repo_path,
                "commit_count": 0,
                "commits": [],
            },
        )
        bucket["commit_count"] += 1
        bucket["commits"].append(
            {
                "commit": c.commit[:8],
                "committed_at": c.committed_at,
                "message": c.message,
                "message_full": c.message_full or c.message,
                "work": c.work_summary,
                "impact": c.impact_summary,
                "business_impact": c.business_impact_summary,
                "evidence": c.evidence,
                "detailed_changes": c.detailed_changes[:4],
                "tags": c.feature_tags,
                "files_changed": c.files_changed,
                "insertions": c.insertions,
                "deletions": c.deletions,
            }
        )

    by_repo = sorted(repo_map.values(), key=lambda x: x["commit_count"], reverse=True)
    for item in by_repo:
        item["commits"].sort(key=lambda x: x["committed_at"], reverse=True)

    day_map: dict[str, dict[str, Any]] = {}
    for c in commits:
        day_key = c.committed_at.split(" ")[0] if c.committed_at else "unknown"
        day_bucket = day_map.setdefault(
            day_key,
            {
                "date": day_key,
                "commit_count": 0,
                "repos": {},
                "commits": [],
            },
        )
        day_bucket["commit_count"] += 1
        day_bucket["repos"][c.repo] = day_bucket["repos"].get(c.repo, 0) + 1
        day_bucket["commits"].append(
            {
                "repo": c.repo,
                "commit": c.commit[:8],
                "committed_at": c.committed_at,
                "message": c.message,
                "message_full": c.message_full or c.message,
                "work": c.work_summary,
                "impact": c.impact_summary,
                "business_impact": c.business_impact_summary,
                "evidence": c.evidence,
                "detailed_changes": c.detailed_changes[:4],
                "tags": c.feature_tags,
                "files_changed": c.files_changed,
                "insertions": c.insertions,
                "deletions": c.deletions,
            }
        )

    by_day = sorted(day_map.values(), key=lambda x: x["date"], reverse=True)
    for item in by_day:
        item["repos"] = [
            {"repo": r, "count": n}
            for r, n in sorted(item["repos"].items(), key=lambda x: x[1], reverse=True)
        ]
        item["commits"].sort(key=lambda x: x["committed_at"], reverse=True)

    return {"by_repo": by_repo, "by_day": by_day}


def _build_project_summaries(commits: list[CommitItem]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for c in commits:
        item = grouped.setdefault(
            c.repo_path,
            {
                "project_name": c.repo,
                "project_path": c.repo_path,
                "commit_count": 0,
                "insertions": 0,
                "deletions": 0,
                "total_changed_lines": 0,
                "feature_counter": {},
                "impact_counter": {},
                "business_impact_counter": {},
                "file_counter": {},
                "representative_commits": [],
            },
        )
        item["commit_count"] += 1
        item["insertions"] += c.insertions
        item["deletions"] += c.deletions
        item["total_changed_lines"] += (c.insertions + c.deletions)
        for t in c.feature_tags:
            item["feature_counter"][t] = item["feature_counter"].get(t, 0) + 1
        for f in c.files:
            item["file_counter"][f] = item["file_counter"].get(f, 0) + 1
        for seg in c.impact_summary.split("；"):
            seg = seg.strip()
            if seg:
                item["impact_counter"][seg] = item["impact_counter"].get(seg, 0) + 1
        for seg in c.business_impact_summary.split("；"):
            seg = seg.strip()
            if seg:
                item["business_impact_counter"][seg] = item["business_impact_counter"].get(seg, 0) + 1
        item["representative_commits"].append(
            {
                "commit": c.commit[:8],
                "committed_at": c.committed_at,
                "message": c.message,
                "message_full": c.message_full or c.message,
                "work": c.work_summary,
                "impact": c.impact_summary,
                "business_impact": c.business_impact_summary,
                "evidence": c.evidence,
                "detailed_changes": c.detailed_changes[:4],
                "files_changed": c.files_changed,
                "changed_lines": c.insertions + c.deletions,
            }
        )

    out: list[dict[str, Any]] = []
    for item in grouped.values():
        feature_top = sorted(item["feature_counter"].items(), key=lambda x: x[1], reverse=True)[:8]
        impact_top = sorted(item["impact_counter"].items(), key=lambda x: x[1], reverse=True)[:8]
        biz_top = sorted(item["business_impact_counter"].items(), key=lambda x: x[1], reverse=True)[:8]
        files_top = sorted(item["file_counter"].items(), key=lambda x: x[1], reverse=True)[:12]
        reps = sorted(item["representative_commits"], key=lambda x: x["changed_lines"], reverse=True)[:8]
        out.append(
            {
                "project_name": item["project_name"],
                "project_path": item["project_path"],
                "commit_count": item["commit_count"],
                "insertions": item["insertions"],
                "deletions": item["deletions"],
                "total_changed_lines": item["total_changed_lines"],
                "feature_focus": [{"tag": k, "count": v} for k, v in feature_top],
                "impact_focus": [{"impact": k, "count": v} for k, v in impact_top],
                "business_impact_focus": [{"business_impact": k, "count": v} for k, v in biz_top],
                "key_files": [{"file": k, "count": v} for k, v in files_top],
                "representative_commits": reps,
            }
        )
    out.sort(key=lambda x: x["commit_count"], reverse=True)
    return out


def _build_global_analysis(commits: list[CommitItem]) -> dict[str, Any]:
    if not commits:
        return {
            "touched_repos": 0,
            "touched_files": 0,
            "themes": [],
            "system_impacts": [],
            "business_impacts": [],
        }

    repo_set = {c.repo_path for c in commits}
    file_set: set[str] = set()
    for c in commits:
        for f in c.files:
            file_set.add(f"{c.repo}:{f}")

    # Theme clustering based on aggregated tags + area hints
    theme_map: dict[str, dict[str, Any]] = {}
    for c in commits:
        joined_files = " ".join(c.files).lower()

        themes: list[str] = []
        if "provider" in joined_files:
            themes.append("provider 能力建设")
        if "graphql" in joined_files or "api" in c.feature_tags:
            themes.append("查询接口与数据访问")
        if any(k in joined_files for k in ["session", "tunnel", "callback"]):
            themes.append("会话链路与稳定性")
        if "database" in c.feature_tags or any(k in joined_files for k in ["migration", "sql", "redis", "repository"]):
            themes.append("数据层与存储治理")
        if "test" in c.feature_tags:
            themes.append("测试与质量保障")
        if "docs" in c.feature_tags:
            themes.append("文档与协作效率")
        if not themes:
            themes.append("其他增量改动")

        for t in themes:
            bucket = theme_map.setdefault(
                t,
                {
                    "theme": t,
                    "commit_count": 0,
                    "repos": {},
                    "sample_commits": [],
                },
            )
            bucket["commit_count"] += 1
            bucket["repos"][c.repo] = bucket["repos"].get(c.repo, 0) + 1
            if len(bucket["sample_commits"]) < 5:
                bucket["sample_commits"].append(
                    {
                        "repo": c.repo,
                        "commit": c.commit[:8],
                        "message": c.message,
                "message_full": c.message_full or c.message,
                    }
                )

    themes = sorted(theme_map.values(), key=lambda x: x["commit_count"], reverse=True)
    for t in themes:
        t["repos"] = [{"repo": r, "count": n} for r, n in sorted(t["repos"].items(), key=lambda x: x[1], reverse=True)]

    # Global impacts from dominant themes
    system_impacts: list[str] = []
    business_impacts: list[str] = []
    theme_names = {t["theme"] for t in themes[:6]}
    if "provider 能力建设" in theme_names:
        system_impacts.append("跨仓库持续扩展 provider 能力，接口覆盖面明显扩大")
        business_impacts.append("可支持更多合作方/场景接入，缩短业务方案落地前置周期")
    if "查询接口与数据访问" in theme_names:
        system_impacts.append("查询与数据访问路径被强化，系统可观测/可检索能力提升")
        business_impacts.append("业务联调和问题定位更快，需求验证闭环时间缩短")
    if "会话链路与稳定性" in theme_names:
        system_impacts.append("会话与链路处理逻辑集中优化，失败路径治理增强")
        business_impacts.append("线上任务中断与重试成本下降，稳定性风险可控")
    if "数据层与存储治理" in theme_names:
        system_impacts.append("数据存储/缓存访问路径调整，数据一致性与性能更可控")
        business_impacts.append("统计数据可信度提升，支撑业务决策与复盘准确性")
    if "测试与质量保障" in theme_names:
        system_impacts.append("回归保障增强，关键改动可验证性提升")
        business_impacts.append("缺陷返工概率下降，迭代节奏更稳定")
    if "文档与协作效率" in theme_names:
        system_impacts.append("文档与脚本完善，跨团队对齐成本降低")
        business_impacts.append("多人协作交付效率提升，新成员上手时间缩短")

    if not system_impacts:
        system_impacts.append("本周期改动较分散，系统级影响需人工复核")
    if not business_impacts:
        business_impacts.append("本周期业务级影响不显著或证据不足，建议结合需求单复核")

    return {
        "touched_repos": len(repo_set),
        "touched_files": len(file_set),
        "themes": themes,
        "system_impacts": system_impacts,
        "business_impacts": business_impacts,
    }


def _print_text(payload: dict[str, Any]) -> None:
    print("=== superteam-git 分析结果 ===")
    print(f"workspace(s): {payload['workspace']}")
    print(f"branch_scope: {payload.get('git_branch_scope', 'active')}")
    print(f"time: {payload['time_range'][0]} ~ {payload['time_range'][1]}")
    print(f"总项目数: {payload['summary']['repos_discovered']}")
    print(f"总提交数: {payload['summary']['total_commits']}")
    ga = payload.get("global_analysis", {})
    print(f"全局触达项目数: {ga.get('touched_repos', 0)}")
    print(f"全局触达文件数: {ga.get('touched_files', 0)}")
    print("")
    print("全局主题分析:")
    for t in ga.get("themes", [])[:10]:
        repos = ", ".join(f"{r['repo']}({r['count']})" for r in t.get("repos", [])[:4])
        print(f"- {t['theme']}：{t['commit_count']} commits；仓库分布 {repos}")
    print("系统级影响（全局）:")
    for s in ga.get("system_impacts", [])[:6]:
        print(f"- {s}")
    print("业务级影响（全局）:")
    for b in ga.get("business_impacts", [])[:6]:
        print(f"- {b}")
    print("")
    print("各个项目:")
    for proj in payload.get("project_summaries", []):
        print("")
        print(f"项目名: {proj['project_name']}")
        print(f"提交次数: {proj['commit_count']}")
        print(
            f"提交行数: +{proj['insertions']} / -{proj['deletions']} "
            f"(总变更 {proj['total_changed_lines']})"
        )
        print("代码改动汇总（非流水账）:")
        work_items: list[str] = []
        for c in proj.get("representative_commits", []):
            work_txt = str(c.get("work", "")).strip()
            if work_txt and work_txt not in work_items:
                work_items.append(work_txt)
        if work_items:
            print(f"- 主要改动方向：{'；'.join(work_items[:3])}")
        else:
            print("- 主要改动方向：本周期以常规优化与迭代为主")
        print("提交带来的影响（必须详细）:")
        for im in proj.get("impact_focus", [])[:8]:
            print(f"- {im['impact']}（{im['count']} 次）")
        print("提交带来的业务影响（必须详细）:")
        for bm in proj.get("business_impact_focus", [])[:8]:
            print(f"- {bm['business_impact']}（{bm['count']} 次）")
        print("代表性提交（汇总）：")
        for c in proj.get("representative_commits", [])[:3]:
            print(
                f"- {c['committed_at']} {c['commit']} {c['message']} | "
                f"{c['work']} | 影响: {c['impact']}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query local git activity by scanning workspace repos."
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="",
        help="自然语言查询，例如：查看我3.15号到4.1号的记录",
    )
    parser.add_argument(
        "--workspace",
        action="append",
        dest="workspaces",
        metavar="PATH",
        help="Workspace root (repeatable). Overrides SUPERTEAM_GIT_WORKSPACE.",
    )
    parser.add_argument(
        "--week",
        choices=["this", "last"],
        default="this",
        help="Time window: this week or last week (Mon~Sun).",
    )
    parser.add_argument(
        "--since-date",
        help="Custom start date: YYYY-MM-DD (must be used with --until-date).",
    )
    parser.add_argument(
        "--until-date",
        help="Custom end date: YYYY-MM-DD (must be used with --since-date).",
    )
    parser.add_argument(
        "--author",
        action="append",
        default=[],
        help="Author filter pattern. Repeatable. Default uses global git user name/email.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--max-analyze",
        type=int,
        default=200,
        help="Max commits to run code-level feature analysis.",
    )
    parser.add_argument(
        "--branch-scope",
        choices=["active", "head", "all"],
        default="active",
        help="Which refs to scan: active=local branches with commits in window (default); "
        "head=current checkout only; all=git log --all.",
    )
    args = parser.parse_args()

    query_lower = args.query.lower()
    week_mode = args.week
    if args.query and ("上周" in args.query or "last week" in query_lower):
        week_mode = "last"
    elif args.query and ("本周" in args.query or "this week" in query_lower):
        week_mode = "this"

    since_date = args.since_date
    until_date = args.until_date
    if not since_date and not until_date and args.query:
        q_since, q_until = _extract_dates_from_query(args.query)
        since_date, until_date = q_since, q_until

    workspaces = _resolve_workspaces(args.workspaces)
    missing = [w for w in workspaces if not w.exists() or not w.is_dir()]
    if missing:
        print(
            json.dumps(
                {
                    "skill": "superteam-git",
                    "status": "error",
                    "error": "workspace not found or not a directory: "
                    + ", ".join(str(m) for m in missing),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

    try:
        since_dt, until_dt, window_mode, notes = _resolve_time_window(
            week=week_mode,
            since_date=since_date,
            until_date=until_date,
        )
    except ValueError as exc:
        print(
            json.dumps(
                {"skill": "superteam-git", "status": "error", "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

    author_patterns = args.author or _get_default_author_patterns()
    repos = discover_repos_multi(workspaces)
    notes.append(f"git_branch_scope={args.branch_scope}")

    all_commits: list[CommitItem] = []
    repo_errors: list[dict[str, str]] = []
    for repo in repos:
        commits, err = collect_repo_commits(
            repo,
            since_dt,
            until_dt,
            author_patterns,
            branch_scope=args.branch_scope,
        )
        if err:
            repo_errors.append({"repo": str(repo), "error": err})
            continue
        _analyze_commits(repo, commits, args.max_analyze)
        all_commits.extend(commits)

    all_commits.sort(key=lambda c: c.committed_at, reverse=True)
    payload = _to_output(
        workspaces=workspaces,
        window_mode=window_mode,
        since_dt=since_dt,
        until_dt=until_dt,
        notes=notes,
        author_patterns=author_patterns,
        branch_scope=args.branch_scope,
        repos=repos,
        commits=all_commits,
        repo_errors=repo_errors,
    )

    if args.format == "text":
        _print_text(payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
