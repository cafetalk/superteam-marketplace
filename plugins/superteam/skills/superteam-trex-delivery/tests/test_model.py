# tests/test_model.py
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from model import SystemChange, TaskRecord  # noqa


def test_system_change_roundtrip():
    sc = SystemChange(
        name="drex-core",
        review_branch="review_260605_worldcup",
        scope="配置变更",
        dev_owner="王冲",
        ops_executor="",
        done=False,
        dimensions={"MSE配置": {"beta": "替换 campaign-rule-configs", "prod": "同 beta", "operator": "", "checked": False}},
    )
    d = sc.to_dict()
    assert SystemChange.from_dict(d) == sc
    assert json.loads(json.dumps(d))["name"] == "drex-core"


def test_task_record_holds_multiple_systems():
    tr = TaskRecord(submission_key="260605_worldcup", title="x", submitter="a",
                    issues=["TREX-1234", "TREX-1240"], mr_url="u",
                    review_branch="review_260605_worldcup", systems=[])
    assert tr.submission_key == "260605_worldcup"
    assert tr.issues == ["TREX-1234", "TREX-1240"]
    assert tr.submitter == "a" and tr.systems == []
