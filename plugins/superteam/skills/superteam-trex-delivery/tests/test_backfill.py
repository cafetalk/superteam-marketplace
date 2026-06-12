# tests/test_backfill.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import backfill  # noqa


def test_parse_master_sheet_to_systems():
    rows = [
        ["系统名称", "系统变更链接", "提测分支", "修改范围", "本次发布是否涉及", "是否拥有配置", "开发负责人", "操作已完成", "运维执行人"],
        ["drex-core", "drex-core", "", "配置变更", "FALSE", "TRUE", "王冲", "", ""],
        ["persona-feast", "persona-feast", "review_260605_worldcup", "修改", "TRUE", "TRUE", "裴斐飞", "", ""],
    ]
    systems = backfill.parse_master(rows)
    names = {s.name: s for s in systems}
    assert "persona-feast" in names
    assert names["persona-feast"].dev_owner == "裴斐飞"
    assert names["persona-feast"].review_branch == "review_260605_worldcup"


def test_parse_system_sheet_two_env_keeps_only_nonempty():
    # 真实 2-env 形态：变更项 | beta | prod | 涉及 | 操作人 | 检查
    rows = [
        ["drex-event"],
        ["变更项", "drex-event系统变更内容", "", "本次发布是否涉及", "操作人", "检查已完成"],
        ["", "beta", "prod", "", "", ""],
        ["MSE配置", "新增配置X", "新增配置X", "TRUE", "", ""],
        ["RDS DDL", "", "", "FALSE", "", ""],
    ]
    dims = backfill.parse_system_sheet(rows)
    assert "MSE配置" in dims and "RDS DDL" not in dims
    assert dims["MSE配置"]["beta"] == "新增配置X"


def test_parse_system_sheet_three_env_columns():
    # 真实 3-env 形态（如 auth-center）：变更项 | beta | pre | prod | 涉及 | 操作人 | 检查
    rows = [
        ["auth-center"],
        ["变更项", "auth-center系统变更内容", "", "", "本次发布是否涉及", "操作人", "检查已完成"],
        ["", "beta", "pre", "prod", "", "", ""],
        ["容器镜像", "build beta", "", "deploy prod", "TRUE", "ops", "FALSE"],
    ]
    dims = backfill.parse_system_sheet(rows)
    assert dims["容器镜像"]["beta"] == "build beta"
    assert dims["容器镜像"]["prod"] == "deploy prod"
    assert dims["容器镜像"]["operator"] == "ops"
    assert dims["容器镜像"]["checked"] is False     # "FALSE" → 未完成


def test_parse_system_sheet_merged_beta_prod():
    # 真实合并形态（如 drex-endpoint）：变更项 | beta/prod | 涉及 | 操作人 | 检查
    rows = [
        ["drex-endpoint"],
        ["变更项", "drex-endpoint系统变更内容", "本次发布是否涉及", "操作人", "检查已完成"],
        ["", "beta/prod", "", "", ""],
        ["MQ配置", "新增 topic", "TRUE", "", ""],
    ]
    dims = backfill.parse_system_sheet(rows)
    assert dims["MQ配置"]["beta"] == "新增 topic"
    assert dims["MQ配置"]["prod"] == "新增 topic"
