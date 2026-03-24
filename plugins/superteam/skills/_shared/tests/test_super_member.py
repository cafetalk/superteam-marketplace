"""Tests for SuperMember resolve logic."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch

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
    from super_member import SuperMember
    with patch.object(SuperMember, '_load_members', return_value=list(FAKE_MEMBERS)):
        with patch.object(SuperMember, '_load_aliases', return_value=dict(FAKE_ALIASES)):
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
        """Match by email parameter even when name doesn't match."""
        assert sm.resolve("Some Name", email="allen.qin@evgtecc.com") == 1

    def test_no_exact_match_falls_through(self, sm):
        with patch.object(sm, '_llm_match', return_value=("new", None, "no match")):
            with patch.object(sm, '_create_unverified_member', return_value=99):
                result = sm.resolve("Unknown Person", platform="notion")
                assert result == 99

class TestAliasMatch:
    def test_match_by_alias_cache(self, sm):
        assert sm.resolve("Peng", platform="google-drive") == 1

    def test_alias_miss_different_platform(self, sm):
        with patch.object(sm, '_llm_match', return_value=("new", None, "no match")):
            with patch.object(sm, '_create_unverified_member', return_value=99):
                result = sm.resolve("Peng", platform="notion")
                assert result == 99

class TestInMemoryDedup:
    def test_same_name_resolves_once(self, sm):
        with patch.object(sm, '_llm_match', return_value=("new", None, "no match")) as llm:
            with patch.object(sm, '_create_unverified_member', return_value=99):
                r1 = sm.resolve("New Person", platform="dingtalk")
                r2 = sm.resolve("New Person", platform="dingtalk")
                assert r1 == r2 == 99
                llm.assert_called_once()

class TestLLMMatch:
    def test_llm_match_success(self, sm):
        with patch.object(sm, '_llm_match', return_value=("match", 1, "拼音匹配")):
            with patch.object(sm, '_write_alias'):
                result = sm.resolve("Qin Peng", platform="notion")
                assert result == 1
                assert sm.get_stats()["llm_match"] == 1

    def test_llm_error_creates_unverified(self, sm):
        with patch.object(sm, '_llm_match', side_effect=RuntimeError("API down")):
            with patch.object(sm, '_create_unverified_member', return_value=99):
                result = sm.resolve("New Guy", platform="dingtalk")
                assert result == 99
                assert sm.get_stats()["error"] == 1

class TestStats:
    def test_stats_exact(self, sm):
        sm.resolve("秦鹏")
        assert sm.get_stats()["exact"] == 1

    def test_stats_alias(self, sm):
        sm.resolve("Peng", platform="google-drive")
        assert sm.get_stats()["alias"] == 1

class TestEmptyInput:
    def test_empty_name(self, sm):
        with patch.object(sm, '_create_unverified_member', return_value=99):
            result = sm.resolve("")
            assert result == 99

    def test_none_name_like(self, sm):
        with patch.object(sm, '_create_unverified_member', return_value=99):
            result = sm.resolve("   ")
            assert result == 99
