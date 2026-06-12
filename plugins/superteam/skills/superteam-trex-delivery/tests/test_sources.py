# tests/test_sources.py
import sys, json
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import sources  # noqa


def test_fetch_issue_parses_json(monkeypatch):
    payload = {"issue": {"identifier": "TREX-1234", "title": "x",
                         "assignee": "a", "project": {"name": "World Cup", "targetDate": "2026-06-05"}}}
    monkeypatch.setattr(sources, "_run_json",
                        lambda *a, **k: payload)
    issue = sources.fetch_issue("TREX-1234")
    assert issue["identifier"] == "TREX-1234"
    assert issue["project"]["targetDate"] == "2026-06-05"


def test_fetch_issue_mrs_filters_by_tracks(monkeypatch):
    monkeypatch.setattr(sources, "_run_json", lambda *a, **k: {
        "mrs": [
            {"web_url": "u1", "description": "Tracks Linear TREX-1234", "target_branch": "review_260605_worldcup", "repo": "drex-core"},
            {"web_url": "u2", "description": "unrelated", "target_branch": "x", "repo": "y"},
        ]})
    mrs = sources.fetch_issue_mrs("TREX-1234")
    assert [m["repo"] for m in mrs] == ["drex-core"]


def test_run_json_extracts_last_json(monkeypatch):
    fake = mock.Mock(stdout='log line\n{"a":1}\n', returncode=0, stderr="")
    monkeypatch.setattr(sources.subprocess, "run", lambda *a, **k: fake)
    assert sources._run_json(["echo"]) == {"a": 1}


def test_run_json_raises_on_nonzero_returncode(monkeypatch):
    # 子进程失败但 stdout 仍是合法 error JSON —— 不能当成功结果
    import pytest
    fake = mock.Mock(stdout='{"error":"local_mcp_missing"}', returncode=1, stderr="boom")
    monkeypatch.setattr(sources.subprocess, "run", lambda *a, **k: fake)
    with pytest.raises(RuntimeError):
        sources._run_json(["echo"])
