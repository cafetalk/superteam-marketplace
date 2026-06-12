# tests/test_dimensions.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from dimensions import DIMENSIONS, render_system_matrix  # noqa
from model import SystemChange  # noqa


def test_dimensions_complete():
    keys = {d["key"] for d in DIMENSIONS}
    # 20 个 canonical 维度（含服务器脚本）
    for k in ["MSE配置", "RDS DDL", "RDS DML", "TableStore表", "容器镜像",
              "RPC兼容性", "调度任务", "服务器脚本"]:
        assert k in keys
    assert len(DIMENSIONS) == 20


def test_render_only_nonempty_dimensions():
    sc = SystemChange("drex-core", "review_260605_worldcup", "配置变更", "王冲", "", False,
                      {"MSE配置": {"beta": "改配置", "prod": "同 beta", "operator": "ops", "checked": False}})
    md = render_system_matrix([sc])
    assert "MSE配置" in md
    assert "RDS DDL" not in md          # 空维度不出现
    assert "drex-core" in md
    assert "| MSE配置 | 改配置 | 同 beta | ops | ☐ |" in md


def test_render_system_with_empty_dims_keeps_heading():
    # 提测刚生成时维度未填 —— 仍要有 ### 标题，aggregate 才能反解出系统名
    sc = SystemChange("persona-feast", "review_260605_worldcup", "", "", "", False, {})
    md = render_system_matrix([sc])
    assert "### persona-feast" in md
    assert "维度待填" in md


def test_render_empty_systems_says_none():
    assert "无" in render_system_matrix([])
