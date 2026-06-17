import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from render import render_change_table, render_service_release, render_submission_release, render_iteration_auto  # noqa
from render import render_placeholder_table, render_data_contract, _redis_table  # noqa
from model import Change, ServiceChanges, ChangesDoc  # noqa
from changes import load_changes  # noqa

FIX = Path(__file__).resolve().parent / "fixtures" / "changes_prism.yaml"


# ---------------------------------------------------------------------------
# render_change_table
# ---------------------------------------------------------------------------

def test_change_table_empty():
    assert "无涉及维度" in render_change_table([])


def test_change_table_single_value_and_br():
    md = render_change_table([
        Change("容器镜像", "build → restart"),
        Change("MSE配置", "a=1\nb={x}", confirm=True),
    ])
    assert "| 变更项 | 内容 | 操作人 | 检查 |" in md
    assert "| 容器镜像 | build → restart |  | ☐ |" in md
    assert "| MSE配置 ⚠️ | a=1<br>b={x} |  | ☐ |" in md   # 多行 <br>，confirm ⚠️
    assert "####" not in md and "```" not in md           # 不再有代码块


# ---------------------------------------------------------------------------
# render_placeholder_table
# ---------------------------------------------------------------------------

def test_placeholder_table():
    none = render_placeholder_table([Change("Redis", "无额外操作")])
    assert none == []                                  # 无占位符 → 空
    lines = render_placeholder_table([
        Change("MSE配置", "x={lark}", placeholders=[
            {"key": "lark", "dev": "d", "beta": "b", "prod": "p"}])])
    txt = "\n".join(lines)
    assert "`{}` = 按环境取值" in txt
    assert "| key | dev | beta | prod |" in txt
    assert "| lark | d | b | p |" in txt


# ---------------------------------------------------------------------------
# render_data_contract / _redis_table
# ---------------------------------------------------------------------------

def test_data_contract_redis():
    assert render_data_contract(ServiceChanges("svc")) == []      # 无契约 → 空
    svc = ServiceChanges("svc", data_contract={"redis_keys": [
        {"key": "prism:profile:<h>", "purpose": "cache", "ttl": "7d"}]})
    lines = render_data_contract(svc)
    txt = "\n".join(lines)
    assert "# 数据契约" in txt and "## Redis Keys" in txt
    assert "| Key 模式 | 用途 | TTL |" in txt
    assert "| prism:profile:<h> | cache | 7d |" in txt
    # _redis_table 只出表、无标题（供 #2/#3 复用）
    assert _redis_table(svc.data_contract["redis_keys"])[0] == "| Key 模式 | 用途 | TTL |"


# ---------------------------------------------------------------------------
# render_service_release — fixture-driven
# ---------------------------------------------------------------------------

def test_service_release_single_service():
    doc = load_changes(FIX)
    md = render_service_release(doc, "trex-web")
    assert "trex-web" in md and "260603_prism-v2" in md
    assert "trex-core" not in md
    assert "| lark.webhook-url | （复用 v1，空） | （复用 v1，空） | 待 ops 配 |" in md
    assert "# 数据契约" in md and "prism:rate_limit:*" in md


# ---------------------------------------------------------------------------
# render_service_release — full v1.5 (inline doc)
# ---------------------------------------------------------------------------

def test_service_release_full_v15():
    doc = ChangesDoc("260603_x", "it-1", "T", ["TREX-1"], "review_260603_x",
                     services=[ServiceChanges(
                         "trex-web", "MR-MAIN",
                         changes=[Change("MSE配置", "a=1\nx={lark}", confirm=True,
                                         placeholders=[{"key": "lark", "dev": "d", "beta": "b", "prod": "p"}]),
                                  Change("Redis", "无额外操作（key 见数据契约）")],
                         data_contract={"redis_keys": [
                             {"key": "prism:profile:<h>", "purpose": "cache", "ttl": "7d"}]})])
    md = render_service_release(doc, "trex-web")
    # 章节顺序：变更项 → 数据契约 → 提测代码 → 关联任务
    assert md.index("# 变更项") < md.index("# 数据契约") < md.index("# 提测代码") < md.index("# 关联任务")
    assert "a=1<br>x={lark}" in md
    assert "| lark | d | b | p |" in md
    assert "## Redis Keys" in md and "prism:profile:<h>" in md
    assert "主 MR：MR-MAIN" in md
    assert "[TREX-1](https://linear.app/t-rex-v1/issue/TREX-1)" in md


# ---------------------------------------------------------------------------
# render_submission_release — fixture-driven
# ---------------------------------------------------------------------------

def test_submission_release_all_services():
    md = render_submission_release(load_changes(FIX))
    for s in ("trex-hexagonal", "trex-web", "trex-core"):
        assert f"## {s}" in md
    assert "[TREX-524](https://linear.app/t-rex-v1/issue/TREX-524)" in md
    assert "## trex-web · Redis Keys" in md


# ---------------------------------------------------------------------------
# render_iteration_auto — fixture-driven
# ---------------------------------------------------------------------------

def test_iteration_auto_master_and_detail():
    auto = render_iteration_auto("20260612-2b-onboarding-20", [load_changes(FIX)])
    assert "系统变更总表" in auto and "各系统详细变更" in auto
    assert "# 数据契约" in auto and "## trex-hexagonal · Redis Keys" in auto
    assert auto.index("# 变更项") < auto.index("# 数据契约") < auto.index("# 提测代码") < auto.index("# 关联任务")


# ---------------------------------------------------------------------------
# iteration_url renders as link
# ---------------------------------------------------------------------------

def test_iteration_url_renders_as_link():
    url = "https://linear.app/t-rex-v1/project/x"
    doc = ChangesDoc("t", "it-1", "T", ["TREX-1"], "review_260603_x",
                     services=[ServiceChanges("svc", "M", changes=[Change("Redis", "无")])],
                     iteration_url=url)
    md = render_service_release(doc, "svc")
    assert f"迭代：[it-1]({url})" in md
    auto = render_iteration_auto("it-1", [doc])
    assert f"迭代：[it-1]({url})" in auto
