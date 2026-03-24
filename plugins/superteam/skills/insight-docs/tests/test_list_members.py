"""Unit tests for list_members.py (thin CLI with subcommands)."""
import json
import sys
import pytest
from unittest.mock import MagicMock, patch, call

# conftest.py already added SCRIPTS_DIR to sys.path and stubbed psycopg2.

import list_members as lm  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_conn(rows, columns=("user_id", "username", "real_name", "role", "created_at")):
    cur = MagicMock()
    cur.description = [(c,) for c in columns]
    cur.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


def _run_argv(argv, rows, columns=None):
    """Run lm.main() with given argv, return (exit_code, stdout_lines, cur)."""
    if columns is None:
        columns = ("user_id", "username", "real_name", "role", "created_at")
    conn, cur = _make_mock_conn(rows, columns)
    output_lines = []

    mock_pg = sys.modules["psycopg2"]
    mock_pg.connect.return_value = conn

    with patch.object(sys, "argv", ["list_members.py"] + argv), \
         patch("list_members.env", return_value="postgresql://fake/db"), \
         patch("builtins.print", side_effect=lambda *a, **kw: output_lines.append(a[0] if a else "")):
        code = lm.main()

    return code, output_lines, cur


# ---------------------------------------------------------------------------
# TestCmdList – basic member listing
# ---------------------------------------------------------------------------

class TestCmdList:
    _COLUMNS = ("user_id", "username", "real_name", "real_name_en",
                 "email", "role", "verified", "aliases", "created_at")

    def test_no_filters_returns_all(self):
        """list subcommand with no flags → SELECT without WHERE; all rows returned."""
        rows = [
            (1, "alice", "Alice Chen", "Alice", "alice@example.com", "engineer", True, "[]", None),
            (2, "bob", "Bob Li", "Bob", "bob@example.com", "pm", True, "[]", None),
        ]
        code, lines, cur = _run_argv(["list"], rows, self._COLUMNS)

        assert code == 0
        # cur.execute calls: [0]=SET search_path, [1]=SELECT
        sql_calls = [c for c in cur.execute.call_args_list if "SELECT" in str(c)]
        assert sql_calls, "Expected at least one SELECT call"
        sql = str(sql_calls[0])
        assert "WHERE" not in sql
        json_line = next((l for l in lines if isinstance(l, str) and l.startswith("[")), None)
        assert json_line is not None
        result = json.loads(json_line)
        assert len(result) == 2

    def test_name_filter_ilike(self):
        """list --name '张' → WHERE contains ILIKE and '%张%' in params."""
        rows = [(3, "zhang", "张伟", "Zhang Wei", "z@x.com", "engineer", True, "[]", None)]
        code, lines, cur = _run_argv(["list", "--name", "张"], rows, self._COLUMNS)

        assert code == 0
        sql_calls = [c for c in cur.execute.call_args_list if "SELECT" in str(c)]
        sql = str(sql_calls[0])
        params = sql_calls[0][0][1] if sql_calls[0][0][1:] else []
        assert "ILIKE" in sql
        assert any("张" in str(p) for p in params)

    def test_role_filter_exact(self):
        """list --role 'engineer' → WHERE role = %s with 'engineer' in params."""
        rows = [(4, "li", "Li Ming", "Ming Li", "li@x.com", "engineer", True, "[]", None)]
        code, lines, cur = _run_argv(["list", "--role", "engineer"], rows, self._COLUMNS)

        assert code == 0
        sql_calls = [c for c in cur.execute.call_args_list if "SELECT" in str(c)]
        sql = str(sql_calls[0])
        params = sql_calls[0][0][1] if sql_calls[0][0][1:] else []
        assert "role = %s" in sql
        assert "engineer" in params

    def test_user_id_filter(self):
        """list --user-id 42 → WHERE user_id = %s with 42 in params."""
        rows = [(42, "carol", "Carol Wang", "Carol", "c@x.com", "pm", True, "[]", None)]
        code, lines, cur = _run_argv(["list", "--user-id", "42"], rows, self._COLUMNS)

        assert code == 0
        sql_calls = [c for c in cur.execute.call_args_list if "SELECT" in str(c)]
        sql = str(sql_calls[0])
        params = sql_calls[0][0][1] if sql_calls[0][0][1:] else []
        assert "user_id = %s" in sql
        assert 42 in params

    def test_combined_filters(self):
        """list --name + --role → WHERE has both conditions with AND."""
        rows = [(5, "wu", "吴杰", "Wu Jie", "wu@x.com", "engineer", True, "[]", None)]
        code, lines, cur = _run_argv(["list", "--name", "吴", "--role", "engineer"],
                                      rows, self._COLUMNS)

        assert code == 0
        sql_calls = [c for c in cur.execute.call_args_list if "SELECT" in str(c)]
        sql = str(sql_calls[0])
        params = sql_calls[0][0][1] if sql_calls[0][0][1:] else []
        assert "AND" in sql
        assert "ILIKE" in sql
        assert "role = %s" in sql
        assert "engineer" in params
        assert any("吴" in str(p) for p in params)


# ---------------------------------------------------------------------------
# TestCmdResolve – delegates to SuperMember
# ---------------------------------------------------------------------------

class TestCmdResolve:
    def test_resolve_returns_user_id(self):
        """resolve keyword → SuperMember.resolve() called and user_id printed."""
        mock_sm_instance = MagicMock()
        mock_sm_instance.resolve.return_value = 99

        output_lines = []
        mock_pg = sys.modules["psycopg2"]
        mock_pg.connect.return_value = MagicMock()

        with patch.object(sys, "argv", ["list_members.py", "resolve", "张伟"]), \
             patch("list_members.env", return_value="postgresql://fake/db"), \
             patch("super_member.SuperMember", return_value=mock_sm_instance), \
             patch("builtins.print", side_effect=lambda *a, **kw: output_lines.append(a[0] if a else "")):
            code = lm.main()

        assert code == 0
        mock_sm_instance.resolve.assert_called_once_with("张伟", platform="")
        json_line = next((l for l in output_lines if isinstance(l, str) and l.startswith("{")), None)
        assert json_line is not None
        result = json.loads(json_line)
        assert result["user_id"] == 99
        assert result["keyword"] == "张伟"

    def test_resolve_with_platform(self):
        """resolve keyword --platform github → platform passed to SuperMember.resolve()."""
        mock_sm_instance = MagicMock()
        mock_sm_instance.resolve.return_value = 42

        output_lines = []
        mock_pg = sys.modules["psycopg2"]
        mock_pg.connect.return_value = MagicMock()

        with patch.object(sys, "argv", ["list_members.py", "resolve", "alice", "--platform", "github"]), \
             patch("list_members.env", return_value="postgresql://fake/db"), \
             patch("super_member.SuperMember", return_value=mock_sm_instance), \
             patch("builtins.print", side_effect=lambda *a, **kw: output_lines.append(a[0] if a else "")):
            code = lm.main()

        assert code == 0
        mock_sm_instance.resolve.assert_called_once_with("alice", platform="github")
        result = json.loads(next(l for l in output_lines if isinstance(l, str) and l.startswith("{")))
        assert result["platform"] == "github"


# ---------------------------------------------------------------------------
# TestBackwardCompat – no subcommand → list behavior
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    _COLUMNS = ("user_id", "username", "real_name", "real_name_en",
                 "email", "role", "verified", "aliases", "created_at")

    def test_no_subcommand_defaults_to_list(self):
        """No subcommand → cmd_list is called (backward compat)."""
        rows = [
            (1, "alice", "Alice", "Alice", "a@x.com", "engineer", True, "[]", None),
        ]
        code, lines, cur = _run_argv([], rows, self._COLUMNS)

        assert code == 0
        # Should have executed a SELECT query
        sql_calls = [c for c in cur.execute.call_args_list if "SELECT" in str(c)]
        assert sql_calls

    def test_no_subcommand_with_name_filter(self):
        """No subcommand + --name flag → filters applied (backward compat)."""
        rows = [(3, "zhang", "张伟", "Zhang Wei", "z@x.com", "engineer", True, "[]", None)]
        code, lines, cur = _run_argv(["--name", "张"], rows, self._COLUMNS)

        assert code == 0
        sql_calls = [c for c in cur.execute.call_args_list if "SELECT" in str(c)]
        assert sql_calls
        sql = str(sql_calls[0])
        assert "ILIKE" in sql

    def test_no_subcommand_with_role_filter(self):
        """No subcommand + --role → role filter applied (backward compat)."""
        rows = [(4, "li", "Li Ming", "Ming", "li@x.com", "engineer", True, "[]", None)]
        code, lines, cur = _run_argv(["--role", "engineer"], rows, self._COLUMNS)

        assert code == 0
        sql_calls = [c for c in cur.execute.call_args_list if "SELECT" in str(c)]
        assert sql_calls
        params = sql_calls[0][0][1] if sql_calls[0][0][1:] else []
        assert "engineer" in params
