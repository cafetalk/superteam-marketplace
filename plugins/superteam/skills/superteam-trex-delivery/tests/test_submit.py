# tests/test_submit.py
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import submit  # noqa


def test_build_task_record_from_sources(monkeypatch):
    monkeypatch.setattr(submit.sources, "fetch_issue", lambda i: {
        "identifier": "TREX-1234", "title": "loa 接世界杯", "assignee": "@pei",
        "project": {"name": "World Cup", "targetDate": "2026-06-05"}})
    tr, batch = submit.build("dev_260605_worldcup", ["TREX-1234"], batch=None, date=None)
    assert tr.submission_key == "260605_worldcup"
    assert tr.issues == ["TREX-1234"]
    assert tr.submitter == "@pei"
    assert batch == "20260605-world-cup"
    assert tr.review_branch == "review_260605_worldcup"


def test_submit_writes_files(tmp_path, monkeypatch):
    monkeypatch.setattr(submit.sources, "fetch_issue", lambda i: {
        "identifier": "TREX-1234", "title": "x", "assignee": "@p",
        "project": {"name": "World Cup", "targetDate": "2026-06-05"}})
    written = submit.write_records("dev_260605_worldcup", ["TREX-1234"],
                                   releases_root=tmp_path, batch=None, date=None)
    hp = tmp_path / "releases" / "20260605-world-cup" / "submissions" / "260605_worldcup" / "submission.md"
    assert hp.exists() and "TREX-1234" in hp.read_text(encoding="utf-8")
    assert any("submission.md" in str(p) for p in written)


def test_build_handles_string_project_schema(monkeypatch):
    """Linear MCP get_issue 返 project 为 string name 时不应 crash（Bug #1 regression）。
    需带 --date 兜底因为 string schema 没 targetDate。"""
    monkeypatch.setattr(submit.sources, "fetch_issue", lambda i: {
        "identifier": "TREX-5", "title": "prism v2 提测", "assignee": "@allen",
        "project": "2B Onboarding 2.0"})  # ← string, not dict
    tr, batch = submit.build("dev_260612_prism-v2", ["TREX-5"],
                             batch=None, date="2026-06-12")
    assert tr.submission_key == "260612_prism-v2"
    assert tr.submitter == "@allen"
    assert "2026" in batch or "260612" in batch  # date fallback 生效


def test_build_handles_none_project(monkeypatch):
    """project 缺失/None 时不应 crash（兜底既有 schema 也兜 None）。"""
    monkeypatch.setattr(submit.sources, "fetch_issue", lambda i: {
        "identifier": "TREX-6", "title": "t", "assignee": "@a",
        "project": None})
    tr, batch = submit.build("dev_260612_x", ["TREX-6"],
                             batch=None, date="2026-06-12")
    assert tr.submission_key == "260612_x"
