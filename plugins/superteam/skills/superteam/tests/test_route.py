"""Tests for superteam route.py — intent classification and deep mode routing."""
import sys
import pytest
from unittest.mock import patch

import route as route_mod


class TestClassifyIntent:
    """Test keyword-based intent classification."""

    @staticmethod
    def _top_route(query: str):
        return route_mod.classify_intents(query)[0][0]

    def test_deep_research_keywords(self):
        """Deep mode keywords should route to deep_search.py."""
        deep_queries = [
            "深入研究这份文档的内容",
            "请帮我深入分析这个方案",
            "我需要原文内容",
            "获取文档全文",
            "起草一份方案",
            "撰写一份报告",
            "deep research on this topic",
            "需要完整内容来做分析",
        ]
        for q in deep_queries:
            route = self._top_route(q)
            assert "deep_search" in route.script, \
                f"Query '{q}' should route to deep_search, got {route.script}"

    def test_normal_search_fallback(self):
        """Queries without deep keywords should fallback to search_docs.py."""
        route = self._top_route("什么是微服务架构")
        assert "search_docs" in route.script

    def test_member_query(self):
        route = self._top_route("团队成员有哪些")
        assert "list_members" in route.script

    def test_doc_list_query(self):
        route = self._top_route("已同步文档列表")
        assert "list_source_docs" in route.script

    def test_task_query(self):
        route = self._top_route("迭代25的进度如何")
        assert "query_linear" in route.script

    def test_weekly_report_query(self):
        route = self._top_route("帮我生成本周周报")
        assert "generate_report" in route.script

    def test_personal_weekly_phrases(self):
        for q in ("个人周报", "研发周报", "上周工作总结", "my weekly report"):
            route = self._top_route(q)
            assert "generate_report" in route.script, q

    def test_team_weekly_report_query(self):
        route = self._top_route("输出团队迭代周报")
        assert "generate_team_weekly" in route.script

    def test_bare_weekly_hits_personal_report(self):
        route = self._top_route("周报")
        assert "generate_report" in route.script

    def test_team_weekly_excludes_personal_report(self):
        routes = route_mod.classify_intents("团队周报")
        scripts = [r.script for r, _ in routes]
        assert any("generate_team_weekly" in s for s in scripts)
        assert not any("generate_report" in s for s in scripts)

    def test_team_weekly_english_skips_member_route(self):
        routes = route_mod.classify_intents("team weekly report")
        scripts = [r.script for r, _ in routes]
        assert any("generate_team_weekly" in s for s in scripts)
        assert not any("list_members" in s for s in scripts)

    def test_pulse_snapshot_routes_sprint_only(self):
        routes = route_mod.classify_intents("跑一下 pulse 快照")
        scripts = [r.script for r, _ in routes]
        assert any("snapshot_sprint" in s for s in scripts)
        assert not any("snapshot_member" in s for s in scripts)
        assert not any("query_linear" in s for s in scripts)

    def test_sprint_daily_snapshot_only(self):
        routes = route_mod.classify_intents("生成 sprint 日报")
        scripts = [r.script for r, _ in routes]
        assert any("snapshot_sprint" in s for s in scripts)
        assert not any("snapshot_member" in s for s in scripts)
        assert not any("query_linear" in s for s in scripts)

    def test_member_snapshot_only(self):
        routes = route_mod.classify_intents("同步成员负载快照")
        scripts = [r.script for r, _ in routes]
        assert any("snapshot_member" in s for s in scripts)
        assert not any("snapshot_sprint" in s for s in scripts)
        assert not any("list_members" in s for s in scripts)

    def test_superteam_pai_slash_command(self):
        for q in ("/superteam-pai", "superteam-pai"):
            route = self._top_route(q)
            assert route.skill == "superteam-pai"
            assert "run_pai" in route.script
            assert route.pass_query is True

    def test_update_dashboard_routes_pai_orchestrator(self):
        for q in ("更新看板", "刷新看板", "今日 pulse 全量", "跑 pulse 入库"):
            route = self._top_route(q)
            assert route.skill == "superteam-pai"
            assert "run_pai" in route.script

    def test_pai_orchestrator_suppresses_single_pulse_workers(self):
        routes = route_mod.classify_intents("更新看板")
        scripts = [r.script for r, _ in routes]
        assert any("run_pai" in s for s in scripts)
        assert not any("snapshot_sprint" in s for s in scripts)
        assert not any("snapshot_pai" in s for s in scripts)
        assert not any("snapshot_member" in s for s in scripts)

    def test_pai_daily_routes_report_insight(self):
        route = self._top_route("生成 pai 日报")
        assert route.skill == "superteam-report-insight"
        assert "snapshot_pai" in route.script

    def test_pai_snapshot_skips_linear(self):
        routes = route_mod.classify_intents("生成 pai 日报")
        scripts = [r.script for r, _ in routes]
        assert any("snapshot_pai" in s for s in scripts)
        assert not any("query_linear" in s for s in scripts)
        assert not any("list_members" in s for s in scripts)


class TestBuildResult:

    def test_result_structure(self):
        scored_routes = route_mod.classify_intents("深入研究这份文档")
        result = route_mod.build_result("深入研究这份文档", scored_routes)

        assert result["skill"] == "superteam-knowledgebase"
        assert "deep_search" in result["script"]
        assert result["status"] == "live"
        assert "深度搜索" in result["description"]


class TestDeepModeRouteExists:

    def test_deep_route_in_routes_list(self):
        """Verify deep_search route exists in ROUTES."""
        deep_routes = [r for r in route_mod.ROUTES if "deep_search" in r.script]
        assert len(deep_routes) == 1
        assert deep_routes[0].skill == "superteam-knowledgebase"
        assert deep_routes[0].status == "live"
        assert len(deep_routes[0].keywords) > 0
