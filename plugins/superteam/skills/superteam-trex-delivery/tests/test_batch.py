# tests/test_batch.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from batch import slugify, resolve_batch  # noqa
import pytest  # noqa


def test_slugify():
    assert slugify("World Cup") == "world-cup"
    assert slugify("campaign 抽象大改动") == "campaign-抽象大改动"


def test_explicit_batch_wins():
    assert resolve_batch(batch="20260605-world-cup", date=None,
                         project_slug="x", project_target_date="20991231") == "20260605-world-cup"


def test_date_flag_over_project_date():
    assert resolve_batch(batch=None, date="20260605",
                         project_slug="world-cup", project_target_date="20991231") == "20260605-world-cup"


def test_falls_back_to_project_target_date():
    assert resolve_batch(batch=None, date=None,
                         project_slug="world-cup", project_target_date="2026-06-05") == "20260605-world-cup"


def test_no_date_raises_not_today():
    with pytest.raises(ValueError):
        resolve_batch(batch=None, date=None, project_slug="world-cup", project_target_date=None)


def test_empty_slug_raises():
    with pytest.raises(ValueError):
        resolve_batch(batch=None, date="20260605", project_slug="", project_target_date=None)
