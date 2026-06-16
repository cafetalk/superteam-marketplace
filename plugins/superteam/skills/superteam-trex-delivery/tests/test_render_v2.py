import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from render import render_change_table  # noqa
from model import Change  # noqa


def test_change_table_simple_rows_and_code_blocks():
    rows = [
        Change("容器镜像", "CI build", "同 beta"),                       # 单行 → 表格
        Change("Redis", "新 key prism:profile", "同 beta", confirm=True), # 单行 → 表格
        Change("MSE配置", "web.prism-base-url=http://x\nrate.enabled=true",  # 多行 → 代码块
               "同 beta", lang="properties"),
        Change("服务器终端脚本", "curl -X POST ...\n  -d '{}'", "同 beta", lang="bash"),
    ]
    md = render_change_table(rows)
    assert "| 变更项 | beta | prod | 操作人 | 检查 |" in md
    assert "容器镜像" in md and "Redis" in md
    assert "RDS DDL" not in md                       # 没列的不出现
    assert "⚠️" in md                                # confirm:true 标记
    assert "#### MSE配置" in md and "```properties" in md
    assert "rate.enabled=true" in md                 # 多行内容原样, 不 <br>
    assert "#### 服务器终端脚本" in md and "```bash" in md
    assert "<br>" not in md                          # 多行不被压平进 cell


def test_change_table_empty():
    assert "无涉及维度" in render_change_table([])


from render import render_service_release, render_submission_release  # noqa
from changes import load_changes  # noqa
FIX = Path(__file__).resolve().parent / "fixtures" / "changes_prism.yaml"


def test_service_release_single_service():
    doc = load_changes(FIX)
    md = render_service_release(doc, "trex-hexagonal")
    assert "trex-hexagonal" in md and "260603_prism-v2" in md
    assert "trex-web" not in md          # 只该服务


def test_submission_release_all_services():
    doc = load_changes(FIX)
    md = render_submission_release(doc)
    for s in ("trex-hexagonal", "trex-web", "trex-core"):
        assert f"## {s}" in md
    assert "TREX-524" in md


from render import render_iteration_auto  # noqa


def test_iteration_auto_master_and_detail():
    doc = load_changes(FIX)
    auto = render_iteration_auto("20260612-2b-onboarding-20", [doc])
    assert "系统变更总表" in auto and "各系统详细变更" in auto
    assert "trex-hexagonal" in auto and "trex-web" in auto
    assert "260603_prism-v2" in auto


def test_service_release_three_sections_and_fix_mrs():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from model import ChangesDoc, ServiceChanges, Change
    import render
    doc = ChangesDoc("260612_x", "20260612-it", "标题", ["TREX-1", "TREX-2"], "review_260612_x",
                     services=[ServiceChanges("trex-core", "MR-MAIN",
                                              [Change("容器镜像", "build", "同 beta")],
                                              fix_mrs=["MR-FIX-1", "MR-FIX-2"])])
    md = render.render_service_release(doc, "trex-core")
    # 三章节
    assert "# 变更项" in md and "# 提测代码" in md and "# 关联任务" in md
    # 提测代码：分支 + 主MR + 修复MR
    assert "提测分支：`review_260612_x`" in md
    assert "主 MR：MR-MAIN" in md
    assert "修复问题的 MR：" in md and "MR-FIX-1" in md and "MR-FIX-2" in md
    # 关联任务：迭代 + 任务列表
    assert "迭代：`20260612-it`" in md and "- TREX-1" in md and "- TREX-2" in md


def test_service_release_no_fix_mrs_shows_none():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from model import ChangesDoc, ServiceChanges, Change
    import render
    doc = ChangesDoc("260612_x", "20260612-it", "T", ["TREX-1"], "review_260612_x",
                     services=[ServiceChanges("svc", "MR-MAIN", [Change("Redis", "k", "同 beta")])])
    md = render.render_service_release(doc, "svc")
    assert "修复问题的 MR：无" in md
