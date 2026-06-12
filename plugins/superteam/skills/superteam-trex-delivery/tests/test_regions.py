# tests/test_regions.py
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from regions import merge_release  # noqa

AUTO_BEGIN = "<!-- trex-delivery:auto:begin -->"
AUTO_END = "<!-- trex-delivery:auto:end -->"


def test_first_time_returns_full_template():
    out = merge_release(existing=None, auto_body="SYSTEMS", template="HEAD\n%AUTO%\nMANUAL")
    assert "SYSTEMS" in out and "MANUAL" in out and AUTO_BEGIN in out


def test_rerun_replaces_auto_keeps_manual():
    existing = (f"HEAD\n{AUTO_BEGIN}\nOLD\n{AUTO_END}\n"
                "## 灰度\n- [x] 5% 已观察")          # manual 区被人改过
    out = merge_release(existing=existing, auto_body="NEW", template="ignored")
    assert "NEW" in out and "OLD" not in out
    assert "- [x] 5% 已观察" in out                 # manual 保留


def test_missing_markers_raises():
    with pytest.raises(ValueError):
        merge_release(existing="no markers here", auto_body="X", template="t")


def test_reversed_markers_raises():
    bad = f"HEAD\n{AUTO_END}\nX\n{AUTO_BEGIN}\n"   # END 在 BEGIN 之前
    with pytest.raises(ValueError):
        merge_release(existing=bad, auto_body="NEW", template="t")
