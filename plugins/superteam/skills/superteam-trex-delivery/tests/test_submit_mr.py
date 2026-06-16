# tests/test_submit_mr.py
"""submit MR 模式（--repo/--dev-branch/--reviewer）：mock open_handoff_mr + git remote 读取，
不打真 GitLab/Linear。断言 MR 模式回填 mr_url/review_branch/systems + 落 submission 含 MR 链接；
不带 flags 时退化 v1，不调 open_handoff_mr。"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import submit  # noqa


def _stub_sources(monkeypatch):
    monkeypatch.setattr(submit.sources, "fetch_issue", lambda i: {
        "identifier": "TREX-9", "title": "campaign 抽象", "assignee": "@allen",
        "project": {"name": "World Cup", "targetDate": "2026-06-11"}})


def test_mr_mode_populates_record_and_writes_link(tmp_path, monkeypatch):
    _stub_sources(monkeypatch)
    monkeypatch.setattr(submit, "_git_remote_url",
                        lambda repo: "git@gitlab.com:Keccak256-evg/t-rex/agentic/superteam.git")
    monkeypatch.setattr(submit, "_read_gitlab_token", lambda: "tok")
    seen = {}

    def fake_open(token, project_path, dev_branch, issues, reviewer, dry_run=False):
        seen.update(token=token, project_path=project_path, dev_branch=dev_branch,
                    issues=issues, reviewer=reviewer, dry_run=dry_run)
        return {"web_url": "https://gitlab/mr/5", "iid": 5,
                "review_branch": "review_260611_trex-release-skill",
                "repo": "superteam", "dry_run": False}

    monkeypatch.setattr(submit.gitlab_mr, "open_handoff_mr", fake_open)
    # Linear 状态更新 best-effort：mock 记录每个被置 In Review 的 issue
    in_review = []
    monkeypatch.setattr(submit, "_set_linear_in_review", lambda issue: in_review.append(issue))
    # trex-releases 侧 git：mock 掉，tmp_path 非 git repo
    for fn in ("ensure_branch", "stage", "commit", "push"):
        monkeypatch.setattr(submit.gitlab_release, fn, lambda *a, **k: None)
    monkeypatch.setattr(submit.gitlab_release, "needs_confirm", lambda *a, **k: False)

    rc = submit.run_cli([
        "--dev-branch", "dev_260611_trex-release-skill",
        "--issue", "TREX-1", "--issue", "TREX-2",
        "--releases-root", str(tmp_path),
        "--repo", "/ws/superteam", "--no-push"])
    assert rc == 0
    assert seen["project_path"] == "Keccak256-evg/t-rex/agentic/superteam"
    assert seen["reviewer"] == "allen.qin"      # 从 team-leads.json 后缀命中
    assert seen["issues"] == ["TREX-1", "TREX-2"]   # 多 issue 透传给 open_handoff_mr
    sp = (tmp_path / "releases" / "20260611-world-cup" / "submissions"
          / "260611_trex-release-skill" / "submission.md")
    assert sp.exists()
    txt = sp.read_text(encoding="utf-8")
    assert "https://gitlab/mr/5" in txt
    assert "review_260611_trex-release-skill" in txt
    assert "superteam" in txt                   # 受影响系统 = repo
    assert "TREX-1" in txt and "TREX-2" in txt   # 两个 issue 都在提测单里
    assert in_review == ["TREX-1", "TREX-2"]     # 两个 issue 都置 In Review


def test_no_flags_does_not_call_open_mr(tmp_path, monkeypatch):
    _stub_sources(monkeypatch)
    called = []
    monkeypatch.setattr(submit.gitlab_mr, "open_handoff_mr",
                        lambda *a, **k: called.append(1) or {})
    linear = []
    monkeypatch.setattr(submit, "_set_linear_in_review",
                        lambda issue: linear.append(1))
    rc = submit.run_cli([
        "--dev-branch", "dev_260611_x", "--issue", "TREX-9",
        "--releases-root", str(tmp_path), "--dry-run"])
    assert rc == 0
    assert called == []        # 无 --repo → 不开 MR
    assert linear == []        # 也不动 Linear 状态


def test_no_mr_with_repo_skips_handoff_mr(tmp_path, monkeypatch):
    """Bug #2 regression：`--repo --no-mr` 时不该调 open_handoff_mr，
    但 submission.md / per-repo 文件仍要写出（含 review_branch + 受影响系统）。"""
    _stub_sources(monkeypatch)
    monkeypatch.setattr(submit, "_git_remote_url",
                        lambda repo: "git@gitlab.com:Keccak256-evg/t-rex/agentic/superteam.git")
    monkeypatch.setattr(submit, "_read_gitlab_token", lambda: "tok")
    called = []
    monkeypatch.setattr(submit.gitlab_mr, "open_handoff_mr",
                        lambda *a, **k: called.append(1) or {})
    # team-lead 解析也不该被调（--no-mr 直接走 derive 路径）
    reviewer_calls = []
    monkeypatch.setattr(submit.gitlab_mr, "resolve_reviewer",
                        lambda *a, **k: reviewer_calls.append(1) or "x")
    # Linear 不该被动 — `--no-mr` 还没真正"开"提测，issue 不该置 In Review
    linear = []
    monkeypatch.setattr(submit, "_set_linear_in_review",
                        lambda issue: linear.append(issue))
    # trex-releases 侧 git：mock 掉
    for fn in ("ensure_branch", "stage", "commit", "push"):
        monkeypatch.setattr(submit.gitlab_release, fn, lambda *a, **k: None)
    monkeypatch.setattr(submit.gitlab_release, "needs_confirm", lambda *a, **k: False)
    # 释放记录 MR 也 mock 防止真调
    release_mr_calls = []
    monkeypatch.setattr(submit.gitlab_release, "open_mr",
                        lambda *a, **k: release_mr_calls.append(1) or {})

    rc = submit.run_cli([
        "--dev-branch", "dev_260612_prism-v2",
        "--issue", "TREX-1",
        "--releases-root", str(tmp_path),
        "--repo", "/ws/superteam",
        "--no-mr", "--no-push"])
    assert rc == 0
    assert called == []             # 提测 MR 没开
    assert reviewer_calls == []     # reviewer 解析也跳过
    assert release_mr_calls == []   # 释放记录 MR 也没开（与 --no-mr 一致）
    assert linear == []             # Linear issue 状态也不该被推到 In Review
    sp = (tmp_path / "releases" / "20260611-world-cup" / "submissions"
          / "260612_prism-v2" / "submission.md")
    assert sp.exists()
    txt = sp.read_text(encoding="utf-8")
    assert "review_260612_prism-v2" in txt   # review 分支仍写入
    assert "superteam" in txt                # 受影响系统 = repo
