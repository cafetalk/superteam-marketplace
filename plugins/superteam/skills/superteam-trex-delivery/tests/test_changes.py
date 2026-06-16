import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from changes import load_changes, validate_changes  # noqa

FIX = Path(__file__).resolve().parent / "fixtures" / "changes_prism.yaml"

def test_load_changes_parses_services():
    doc = load_changes(FIX)
    assert doc.task == "260603_prism-v2"
    assert {s.name for s in doc.services} == {"trex-hexagonal", "trex-web", "trex-core"}

def test_validate_passes_on_good_fixture():
    assert validate_changes(load_changes(FIX)) == []

def test_validate_rejects_unknown_dim():
    from model import ChangesDoc, ServiceChanges, Change
    doc = ChangesDoc("t", "i", "T", ["X"], "review_t",
                     services=[ServiceChanges("svc", "", [Change("不存在的维度", "b", "p")])])
    errs = validate_changes(doc)
    assert any("不存在的维度" in e for e in errs)

def test_validate_rejects_empty_services():
    from model import ChangesDoc
    doc = ChangesDoc("t", "i", "T", ["X"], "review_t", services=[])
    errs = validate_changes(doc)
    assert any("service" in e.lower() for e in errs)

def test_validate_iteration_mismatch():
    doc = load_changes(FIX)
    errs = validate_changes(doc, expected_iteration="wrong-iteration")
    assert any("iteration" in e.lower() for e in errs)
