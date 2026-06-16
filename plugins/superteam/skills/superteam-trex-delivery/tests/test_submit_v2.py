import sys, pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from submit import submit_from_changes  # noqa
FIX = Path(__file__).resolve().parent / "fixtures" / "changes_prism.yaml"

def _seed(tmp_path):
    it = "20260612-2b-onboarding-20"; task = "260603_prism-v2"
    d = tmp_path / "trex-releases" / "releases" / it / "submissions" / task
    d.mkdir(parents=True)
    cp = d / "changes.yaml"; cp.write_text(FIX.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path / "trex-releases", cp

def test_submit_changes_renders_two_levels(tmp_path):
    root, cp = _seed(tmp_path)
    repos = {n: tmp_path / n for n in ("trex-hexagonal", "trex-web", "trex-core")}
    for p in repos.values(): p.mkdir()
    submit_from_changes(cp, root, repo_map={k: str(v) for k, v in repos.items()},
                        no_mr=True, no_push=True)
    assert (root / "releases" / "20260612-2b-onboarding-20" / "submissions"
            / "260603_prism-v2" / "release.md").exists()
    sr = (repos["trex-hexagonal"] / "releases" / "20260612-2b-onboarding-20"
          / "260603_prism-v2" / "release.md")
    assert sr.exists() and "trex-hexagonal" in sr.read_text(encoding="utf-8")

def test_submit_changes_aborts_on_bad_dim(tmp_path):
    root, cp = _seed(tmp_path)
    cp.write_text(cp.read_text(encoding="utf-8").replace("Redis", "不存在的维度", 1), encoding="utf-8")
    with pytest.raises(SystemExit):
        submit_from_changes(cp, root, repo_map={}, no_mr=True, no_push=True)
