# tests/test_git_wiring.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import submit  # noqa


def test_dry_run_does_not_touch_git(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(submit.sources, "fetch_issue", lambda i: {
        "identifier": "TREX-1", "title": "x", "assignee": "@p",
        "project": {"name": "World Cup", "targetDate": "2026-06-05"}})
    called = []
    monkeypatch.setattr(submit.gitlab_release, "stage", lambda *a, **k: called.append("stage"))
    submit.run_cli(["--dev-branch", "dev_260605_x", "--issue", "TREX-1",
                    "--releases-root", str(tmp_path), "--dry-run"])
    assert called == []      # dry-run 不动 git
    # dry-run 也不落盘（spec §9）
    assert not (tmp_path / "releases").exists()


def test_non_dry_run_stages_explicit_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(submit.sources, "fetch_issue", lambda i: {
        "identifier": "TREX-1", "title": "x", "assignee": "@p",
        "project": {"name": "World Cup", "targetDate": "2026-06-05"}})
    staged = {}
    monkeypatch.setattr(submit.gitlab_release, "stage", lambda root, paths: staged.update(paths=paths))
    monkeypatch.setattr(submit.gitlab_release, "ensure_branch", lambda *a, **k: None)
    monkeypatch.setattr(submit.gitlab_release, "commit", lambda *a, **k: None)
    monkeypatch.setattr(submit.gitlab_release, "needs_confirm", lambda *a, **k: False)
    monkeypatch.setattr(submit.gitlab_release, "push", lambda *a, **k: None)
    submit.run_cli(["--dev-branch", "dev_260605_x", "--issue", "TREX-1",
                    "--releases-root", str(tmp_path), "--yes"])
    assert staged["paths"]                                   # 非空：显式 relpath 列表
    assert all(not p.startswith("-") for p in staged["paths"])   # 绝无 -A/. 等
