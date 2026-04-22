"""Tests for SuperMember resolve logic."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from super_member import SuperMember

FAKE_MEMBERS = [
    {"user_id": 1, "username": "allen.qin", "real_name": "秦鹏",
     "real_name_en": "Peng Qin", "email": "allen.qin@evgtecc.com",
     "role": "后端开发", "aliases": ["Allen", "秦总"], "verified": True},
    {"user_id": 2, "username": "zhangsan", "real_name": "张三",
     "real_name_en": "San Zhang", "email": "zhangsan@evgtecc.com",
     "role": "前端开发", "aliases": [], "verified": True},
]

FAKE_ALIASES = {
    ("peng", "google-drive"): 1,
}


@pytest.fixture
def sm():
    with patch.object(SuperMember, "_load_members", return_value=list(FAKE_MEMBERS)):
        with patch.object(SuperMember, "_load_aliases", return_value=dict(FAKE_ALIASES)):
            conn = MagicMock()
            instance = SuperMember(conn)
            return instance


class TestExactMatch:
    def test_match_by_real_name(self, sm):
        assert sm.resolve("秦鹏") == 1

    def test_match_by_real_name_en(self, sm):
        assert sm.resolve("Peng Qin") == 1

    def test_match_by_username(self, sm):
        assert sm.resolve("allen.qin") == 1

    def test_match_by_email(self, sm):
        assert sm.resolve("allen.qin@evgtecc.com") == 1

    def test_match_by_alias_in_members(self, sm):
        assert sm.resolve("Allen") == 1

    def test_match_case_insensitive(self, sm):
        assert sm.resolve("ALLEN.QIN") == 1

    def test_match_email_param(self, sm):
        assert sm.resolve("Some Name", email="allen.qin@evgtecc.com") == 1


class TestAliasMatch:
    def test_match_by_alias_cache(self, sm):
        assert sm.resolve("Peng", platform="google-drive") == 1


class TestInMemoryDedup:
    def test_same_name_resolves_once(self, sm):
        with patch.object(sm, "_llm_match", return_value=("new", None, "no match")) as llm:
            with patch.object(sm, "_create_unverified_member", return_value=99):
                r1 = sm.resolve("New Person", platform="dingtalk")
                r2 = sm.resolve("New Person", platform="dingtalk")
                assert r1 == r2 == 99
                llm.assert_called_once()
