import sys, subprocess
from pathlib import Path
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
FIX = Path(__file__).resolve().parent / "fixtures" / "changes_prism.yaml"

def _run(args):
    return subprocess.run(["python3", str(SCRIPTS / "validate.py"), *args],
                          capture_output=True, text=True)

def test_validate_good_fixture_exit0():
    r = _run(["--changes", str(FIX)])
    assert r.returncode == 0

def test_validate_bad_dim_exit1(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(FIX.read_text(encoding="utf-8").replace("Redis", "不存在的维度", 1), encoding="utf-8")
    r = _run(["--changes", str(bad)])
    assert r.returncode == 1
    assert "不存在的维度" in (r.stdout + r.stderr)
