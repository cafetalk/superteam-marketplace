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
