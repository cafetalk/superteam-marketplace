import sys, yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from release import run_v2  # noqa

def _mk_changes(d: Path, task: str, svc: str):
    d.mkdir(parents=True, exist_ok=True)
    (d / "changes.yaml").write_text(yaml.safe_dump({
        "task": task, "iteration": "20260612-x", "title": "T", "linear": ["TREX-1"],
        "submit_branch": f"review_{task}",
        "services": {svc: {"mr": "u", "changes": [{"dim": "容器镜像", "beta": "b", "prod": "同 beta"}]}}},
        allow_unicode=True), encoding="utf-8")

def test_release_globs_changes_yaml(tmp_path):
    it = tmp_path / "releases" / "20260612-x"
    _mk_changes(it / "submissions" / "260603_a", "260603_a", "trex-hexagonal")
    _mk_changes(it / "submissions" / "260604_b", "260604_b", "trex-web")
    rp = run_v2(tmp_path, "20260612-x", dry_run=False)
    md = Path(rp).read_text(encoding="utf-8")
    assert "trex-hexagonal" in md and "trex-web" in md
    assert "系统变更总表" in md
    # 标记结构: 恰好一对 auto:begin/end (模板 %AUTO% 必须裸放, merge_release 才不双标记)
    assert md.count("<!-- trex-delivery:auto:begin -->") == 1
    assert md.count("<!-- trex-delivery:auto:end -->") == 1
    # manual 区在 auto:end 之后
    assert md.index("## 灰度方案") > md.index("<!-- trex-delivery:auto:end -->")

def test_release_rerun_keeps_single_marker_pair(tmp_path):
    # 重跑后标记仍恰好一对 (双标记 bug 会在第二次跑留 orphan end marker)
    it = tmp_path / "releases" / "20260612-x"
    _mk_changes(it / "submissions" / "260603_a", "260603_a", "trex-hexagonal")
    rp = Path(run_v2(tmp_path, "20260612-x", dry_run=False))
    run_v2(tmp_path, "20260612-x", dry_run=False)   # 第二次
    md = rp.read_text(encoding="utf-8")
    assert md.count("<!-- trex-delivery:auto:begin -->") == 1
    assert md.count("<!-- trex-delivery:auto:end -->") == 1

def test_release_orphan_skip(tmp_path):
    it = tmp_path / "releases" / "20260612-x"
    _mk_changes(it / "submissions" / "260603_a", "260603_a", "trex-hexagonal")
    orphan = it / "submissions" / "260604_b"; orphan.mkdir(parents=True)
    (orphan / "release.md").write_text("旧手写", encoding="utf-8")
    rp = run_v2(tmp_path, "20260612-x", dry_run=False)
    assert "trex-hexagonal" in Path(rp).read_text(encoding="utf-8")

def test_release_preserves_manual_region(tmp_path):
    it = tmp_path / "releases" / "20260612-x"
    _mk_changes(it / "submissions" / "260603_a", "260603_a", "trex-hexagonal")
    rp = Path(run_v2(tmp_path, "20260612-x", dry_run=False))
    edited = rp.read_text(encoding="utf-8").replace("<待发布负责人填>", "灰度 10%→50%→100%")
    rp.write_text(edited, encoding="utf-8")
    run_v2(tmp_path, "20260612-x", dry_run=False)
    assert "灰度 10%→50%→100%" in rp.read_text(encoding="utf-8")


def test_release_cli_beta_to_master(tmp_path, monkeypatch):
    """发布记录 MR 走 beta_<date>_<keyword> → master（镜像代码发布）。"""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import release
    rp = tmp_path / "releases" / "20260612-x" / "release.md"
    rp.parent.mkdir(parents=True); rp.write_text("x", encoding="utf-8")
    monkeypatch.setattr(release, "run", lambda root, batch, dry_run=False: rp)
    for fn in ("ensure_branch", "stage", "commit", "push"):
        monkeypatch.setattr(release.gitlab_release, fn, lambda *a, **k: None)
    monkeypatch.setattr(release.gitlab_release, "needs_confirm", lambda *a, **k: False)
    calls = {}
    monkeypatch.setattr(release.gitlab_release, "open_mr",
                        lambda repo, src, tgt, title: calls.update(src=src, tgt=tgt) or {"ok": True})
    release.run_cli(["--batch", "20260612-x", "--releases-root", str(tmp_path),
                     "--beta", "beta_260612_world", "--yes"])
    assert calls["src"] == "beta_260612_world" and calls["tgt"] == "master"
