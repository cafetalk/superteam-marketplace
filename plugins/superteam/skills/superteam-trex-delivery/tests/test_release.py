# tests/test_release.py
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import release  # noqa

SEC = "## 受影响系统 / 部署变更\n"


def _seed_handoff(root: Path, batch: str, key: str, body: str):
    d = root / "releases" / batch / "submissions" / key
    d.mkdir(parents=True, exist_ok=True)
    (d / "submission.md").write_text(body, encoding="utf-8")


def _ho(key: str, title: str, systems_block: str, issues: str = "TREX-1") -> str:
    return (f"# 提测 — {key} · {title}\n\n"
            "| 字段 | 值 |\n|---|---|\n| 提测人 | @dev |\n"
            f"| 关联 Linear | {issues} |\n"
            "| 提测分支 | `review_260605_worldcup` |\n\n" + SEC + systems_block + "\n")


def test_aggregate_first_run_creates_release(tmp_path):
    _seed_handoff(tmp_path, "20260605-world-cup", "260605_a", _ho("260605_a", "t", "### drex-core\n"))
    release.run(tmp_path, "20260605-world-cup")
    txt = (tmp_path / "releases" / "20260605-world-cup" / "RELEASE.md").read_text(encoding="utf-8")
    assert "系统变更总表" in txt and "260605_a" in txt and "drex-core" in txt


def test_aggregate_rerun_preserves_manual(tmp_path):
    _seed_handoff(tmp_path, "20260605-world-cup", "260605_a", _ho("260605_a", "t", "### drex-core\n"))
    release.run(tmp_path, "20260605-world-cup")
    rp = tmp_path / "releases" / "20260605-world-cup" / "RELEASE.md"
    rp.write_text(rp.read_text(encoding="utf-8").replace("v<x.y.z>", "v1.2.3"), encoding="utf-8")
    _seed_handoff(tmp_path, "20260605-world-cup", "260605_b", _ho("260605_b", "u", "### kseq\n"))
    release.run(tmp_path, "20260605-world-cup")
    txt2 = rp.read_text(encoding="utf-8")
    assert "v1.2.3" in txt2          # manual 保留
    assert "260605_b" in txt2        # auto 更新


def test_aggregate_merges_same_system_across_tasks(tmp_path):
    _seed_handoff(tmp_path, "20260605-world-cup", "260605_a", _ho("260605_a", "a", "### drex-core\n"))
    _seed_handoff(tmp_path, "20260605-world-cup", "260605_b", _ho("260605_b", "b", "### drex-core\n"))
    release.run(tmp_path, "20260605-world-cup")
    txt = (tmp_path / "releases" / "20260605-world-cup" / "RELEASE.md").read_text(encoding="utf-8")
    assert txt.count("| drex-core |") == 1
    assert "260605_a" in txt and "260605_b" in txt


def test_aggregate_carries_filled_dimensions(tmp_path):
    # 工程师在提测单里填了维度矩阵 → RELEASE.md 明细必须带上真实部署内容（round-trip）
    block = ("### drex-core\n\n"
             "| 维度 | beta | prod | 操作人 | 检查 |\n"
             "|---|---|---|---|---|\n"
             "| MSE配置 | 改了beta配置 | 改了prod配置 | @ops | ☑ |\n")
    _seed_handoff(tmp_path, "20260605-world-cup", "260605_a", _ho("260605_a", "t", block))
    release.run(tmp_path, "20260605-world-cup")
    txt = (tmp_path / "releases" / "20260605-world-cup" / "RELEASE.md").read_text(encoding="utf-8")
    assert "MSE配置" in txt and "改了beta配置" in txt and "改了prod配置" in txt
    assert "维度待填" not in txt          # 不再是空骨架
    assert "@dev" in txt                  # 提测人反解进总表


def test_aggregate_ignores_prose_h3(tmp_path):
    # 自测记录里写了 ### 风险点 —— 不能被当成系统
    body = _ho("260605_a", "t", "### drex-core\n") + "\n## 自测记录\n### 风险点\n- xxx\n"
    _seed_handoff(tmp_path, "20260605-world-cup", "260605_a", body)
    release.run(tmp_path, "20260605-world-cup")
    txt = (tmp_path / "releases" / "20260605-world-cup" / "RELEASE.md").read_text(encoding="utf-8")
    assert "风险点" not in txt


def test_aggregate_missing_batch_dir_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        release.run(tmp_path, "20990101-nope")


def test_aggregate_dry_run_does_not_write(tmp_path):
    _seed_handoff(tmp_path, "20260605-world-cup", "260605_a", _ho("260605_a", "t", "### drex-core\n"))
    release.run(tmp_path, "20260605-world-cup", dry_run=True)
    assert not (tmp_path / "releases" / "20260605-world-cup" / "RELEASE.md").exists()
