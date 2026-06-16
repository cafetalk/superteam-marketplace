import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import gitlab_mr as g  # noqa
import pytest  # noqa

def test_derive_review_branch():
    assert g.derive_review_branch("dev_260611_campaign") == "review_260611_campaign"
    assert g.derive_review_branch("dev_20260611_campaign") == "review_20260611_campaign"

def test_derive_review_branch_rejects_bad():
    with pytest.raises(ValueError):
        g.derive_review_branch("feature/x")        # 非 dev_<date>_<name>

def test_parse_project_path():
    assert g.parse_project_path("git@gitlab.com:Keccak256-evg/t-rex/agentic/superteam.git") == "Keccak256-evg/t-rex/agentic/superteam"
    assert g.parse_project_path("https://gitlab.com/Keccak256-evg/t-rex/anchor/anchor-core.git") == "Keccak256-evg/t-rex/anchor/anchor-core"

def test_resolve_reviewer_override_wins():
    assert g.resolve_reviewer("any/path", override="bob", config={"map":{}}) == "bob"

def test_resolve_reviewer_from_config_suffix():
    cfg={"map":{"agentic/superteam":"allen.qin"}}
    assert g.resolve_reviewer("Keccak256-evg/t-rex/agentic/superteam", override=None, config=cfg) == "allen.qin"

def test_resolve_reviewer_missing_raises():
    with pytest.raises(ValueError):
        g.resolve_reviewer("x/unknown", override=None, config={"map":{}})


def test_open_handoff_mr_dry_run_no_writes(monkeypatch):
    calls=[]
    monkeypatch.setattr(g, "_api", lambda *a, **k: calls.append((a,k)) or {})
    res = g.open_handoff_mr("tok","grp/repo","dev_260611_x",["TREX-9"],"allen.qin", dry_run=True)
    assert res["review_branch"]=="review_260611_x" and res["dry_run"] is True
    assert calls==[]                      # dry-run 不调 GitLab 写


def test_open_handoff_mr_creates(monkeypatch):
    seq=[{"id":111},                                   # GET project
         [{"id":7}],                                   # GET users?username
         {"name":"review_260611_x"},                   # POST branch (or 400 existing)
         {"web_url":"https://gitlab/mr/5","iid":5,"target_branch":"review_260611_x"}]  # POST MR
    it=iter(seq)
    monkeypatch.setattr(g,"_api", lambda *a, **k: next(it))
    res=g.open_handoff_mr("tok","grp/repo","dev_260611_x",["TREX-9"],"allen.qin")
    assert res["web_url"]=="https://gitlab/mr/5" and res["review_branch"]=="review_260611_x"


def test_create_mr_uses_rest_not_glab(monkeypatch):
    calls = []
    def fake_api(method, path, token, body=None, ok_codes=(200, 201)):
        calls.append((method, path)); return {"web_url": "https://gitlab/mr/77", "iid": 77}
    monkeypatch.setattr(g, "_api", fake_api)
    monkeypatch.setattr(g, "read_token", lambda: "tok")
    res = g.create_mr("grp/repo", "auto_260612_x", "master", "release: 记录")
    assert res["ok"] and res["web_url"] == "https://gitlab/mr/77"
    assert any(m == "POST" and "merge_requests" in p for m, p in calls)


def test_create_mr_failure_does_not_raise(monkeypatch):
    monkeypatch.setattr(g, "_api", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("nope")))
    monkeypatch.setattr(g, "read_token", lambda: "tok")
    res = g.create_mr("grp/repo", "auto_260612_x", "master", "t")
    assert res["ok"] is False and "nope" in res["error"]
