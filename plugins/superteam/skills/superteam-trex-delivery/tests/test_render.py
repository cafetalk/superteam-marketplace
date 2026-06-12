# tests/test_render.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from render import render_submission, render_release_auto  # noqa
from model import TaskRecord, SystemChange  # noqa


def test_render_submission_has_fields_and_matrix():
    tr = TaskRecord("260605_worldcup", "loa 接世界杯", "@pei",
                    ["TREX-1234", "TREX-1240"], "https://mr/1",
                    "review_260605_worldcup",
                    [SystemChange("persona-feast", "review_260605_worldcup", "修改", "@pei", "", False,
                                  {"RDS DDL": {"beta": "执行 ddl.sql", "prod": "同 beta", "operator": "", "checked": False}})])
    md = render_submission(tr, batch="20260605-world-cup")
    assert "260605_worldcup" in md and "review_260605_worldcup" in md
    assert "TREX-1234" in md and "TREX-1240" in md   # 多个关联 issue
    assert "persona-feast" in md and "RDS DDL" in md
    assert "## 回滚预案" in md


def test_render_release_auto_transposes_systems():
    systems = [SystemChange("drex-core", "review_260605_worldcup", "配置变更", "@wang", "", False,
                            {"MSE配置": {"beta": "改", "prod": "改", "operator": "", "checked": False}})]
    auto = render_release_auto(batch="20260605-world-cup", systems=systems,
                               submissions=[("260605_worldcup", "x", "@wang")])
    assert "系统变更总表" in auto and "drex-core" in auto
    assert "260605_worldcup" in auto
