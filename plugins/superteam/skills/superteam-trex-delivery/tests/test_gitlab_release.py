# tests/test_gitlab_release.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import gitlab_release as gr  # noqa
import pytest  # noqa


def test_record_branch_name_rule_compliant():
    import re
    # t-rex push rule 的分支名正则（trex-releases 现行）
    rule = re.compile(r"(((pre|auto|dev|alpha|beta|feature|hotfix|review)"
                      r"(|_(\d{8}|\d{6}|\d{4})_[\.A-Za-z0-9\-]{2,30}))|^dev$|^beta$|^master$|^main$)")
    b1 = gr.record_branch_name("20260605-world-cup")
    assert b1 == "auto_20260605_world-cup" and rule.fullmatch(b1)
    # 中文 slug → keyword 清成 ASCII，仍合规
    b2 = gr.record_branch_name("20260604-campaign抽象大改动")
    assert b2 == "auto_20260604_campaign" and rule.fullmatch(b2)
    # 纯中文 slug → 兜底 keyword，仍合规
    b3 = gr.record_branch_name("20260604-世界杯")
    assert rule.fullmatch(b3)


def test_stage_uses_explicit_paths(monkeypatch):
    calls = []
    monkeypatch.setattr(gr, "_git", lambda repo, *a: calls.append(list(a)))
    gr.stage(Path("/r"), ["releases/b/RELEASE.md", "releases/b/TREX-1/handoff.md"])
    assert calls == [["add", "--", "releases/b/RELEASE.md", "releases/b/TREX-1/handoff.md"]]
    flat = [x for c in calls for x in c]
    assert "-A" not in flat and "." not in flat and "-u" not in flat


def test_confirm_gate_requires_confirm_when_branch_new(monkeypatch):
    monkeypatch.setattr(gr, "remote_branch_exists", lambda repo, b: False)
    assert gr.needs_confirm(Path("/r"), "release-record/b", assume_yes=False) is True
    assert gr.needs_confirm(Path("/r"), "release-record/b", assume_yes=True) is False


def test_confirm_gate_skips_when_branch_exists(monkeypatch):
    monkeypatch.setattr(gr, "remote_branch_exists", lambda repo, b: True)
    assert gr.needs_confirm(Path("/r"), "release-record/b", assume_yes=False) is False
