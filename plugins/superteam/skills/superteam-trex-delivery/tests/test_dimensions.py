# tests/test_dimensions.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from dimensions import render_system_matrix, load_dimensions, dimension_keys  # noqa
from model import SystemChange  # noqa


def test_dimensions_complete():
    keys = dimension_keys()
    for k in ["MSE配置", "RDS DDL", "容器镜像", "RPC服务兼容性", "服务器终端脚本",
              "内部LB端口", "外部LB地址"]:
        assert k in keys
    assert len(load_dimensions()) == 22
    assert "内部LB" not in keys and "RPC兼容性" not in keys   # 旧合并/简称名废弃


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


def test_load_dimensions_from_yaml_has_22_keys():
    from dimensions import load_dimensions, dimension_keys
    dims = load_dimensions()
    assert len(dims) == 22
    keys = dimension_keys()
    assert "内部LB端口" in keys and "外部LB地址" in keys   # LB 拆 4
    assert "RPC服务兼容性" in keys and "服务器终端脚本" in keys  # 全名
    assert "内部LB" not in keys                            # 旧合并名废弃


def test_dimension_order_matches_yaml_sequence():
    from dimensions import dimension_order
    order = dimension_order()
    assert order["MSE配置"] == 0
    assert order["服务器终端脚本"] == 21
