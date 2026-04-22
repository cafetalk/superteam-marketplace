"""Unit tests for manage_members.py."""
import json
import sys
from contextlib import ExitStack
from unittest.mock import patch

import manage_members as mm  # noqa: E402


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.description = [
            ("user_id",),
            ("username",),
            ("real_name",),
            ("real_name_en",),
            ("email",),
            ("role",),
            ("aliases",),
            ("verified",),
        ]
        self.sql_calls = []

    def execute(self, sql, params=None):
        self.sql_calls.append((sql, params))

    def fetchone(self):
        if not self.rows:
            return None
        return self.rows.pop(0)

    def close(self):
        return None


class FakeConn:
    def __init__(self, rows):
        self.cursor_obj = FakeCursor(rows)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        return None


def _run(argv, patches):
    out = []
    ctx = [
        patch.object(sys, "argv", ["manage_members.py"] + argv),
        patch("builtins.print", side_effect=lambda *a, **k: out.append(a[0] if a else "")),
    ]
    ctx.extend(patches)
    with ExitStack() as stack:
        for cm in ctx:
            stack.enter_context(cm)
        code = mm.main()
    return code, out


def test_update_requires_any_field():
    code, out = _run(
        ["update", "--operator-user-id", "1", "--user-id", "2"],
        [],
    )
    assert code == 1
    payload = json.loads(out[0])
    assert payload["error_code"] == "INVALID_ARGUMENT"


def test_update_success_writes_audit():
    before = (2, "xuwei", "许伟", "Wei Xu", "old@example.com", None, "[]", True)
    after = (2, "xu.wei", "许伟", "Wei Xu", "new@example.com", "测试", "[]", True)
    conn = FakeConn([before, after])

    code, out = _run(
        [
            "update",
            "--operator-user-id",
            "1",
            "--user-id",
            "2",
            "--username",
            "xu.wei",
            "--email",
            "new@example.com",
            "--role",
            "测试",
        ],
        [
            patch("manage_members._get_conn", return_value=(conn, None)),
        ],
    )

    assert code == 0
    payload = json.loads(out[0])
    assert payload["ok"] is True
    assert payload["action"] == "update_profile"
    assert "role" in payload["changed_fields"]
    assert payload["audit"]["written"] is True
    assert conn.committed is True


def test_update_with_no_audit_flag_skips_audit_write():
    before = (2, "xuwei", "许伟", "Wei Xu", "old@example.com", None, "[]", True)
    after = (2, "xuwei", "许伟", "Wei Xu", "new@example.com", "测试", "[]", True)
    conn = FakeConn([before, after])

    code, out = _run(
        [
            "update",
            "--operator-user-id",
            "1",
            "--user-id",
            "2",
            "--email",
            "new@example.com",
            "--role",
            "测试",
            "--no-audit",
        ],
        [
            patch("manage_members._get_conn", return_value=(conn, None)),
            patch("manage_members._write_audit"),
        ],
    )

    assert code == 0
    payload = json.loads(out[0])
    assert payload["audit"]["written"] is False
    assert payload["audit"]["skipped_reason"] == "disabled_by_flag"


def test_update_auto_skips_when_audit_table_missing():
    before = (2, "xuwei", "许伟", "Wei Xu", "old@example.com", None, "[]", True)
    after = (2, "xuwei", "许伟", "Wei Xu", "new@example.com", "测试", "[]", True)
    conn = FakeConn([before, after])

    class UndefinedTableErr(Exception):
        pgcode = "42P01"

    code, out = _run(
        [
            "update",
            "--operator-user-id",
            "1",
            "--user-id",
            "2",
            "--email",
            "new@example.com",
            "--role",
            "测试",
        ],
        [
            patch("manage_members._get_conn", return_value=(conn, None)),
            patch("manage_members._write_audit", side_effect=UndefinedTableErr("relation does not exist")),
        ],
    )

    assert code == 0
    payload = json.loads(out[0])
    assert payload["audit"]["written"] is False
    assert payload["audit"]["skipped_reason"] == "audit_table_missing"


def test_update_without_operator_id_skips_audit_but_succeeds():
    before = (2, "xuwei", "许伟", "Wei Xu", "old@example.com", None, "[]", True)
    after = (2, "xuwei", "许伟", "Wei Xu", "new@example.com", "测试", "[]", True)
    conn = FakeConn([before, after])

    code, out = _run(
        [
            "update",
            "--user-id",
            "2",
            "--email",
            "new@example.com",
            "--role",
            "测试",
        ],
        [
            patch("manage_members._get_conn", return_value=(conn, None)),
            patch("manage_members._write_audit"),
        ],
    )

    assert code == 0
    payload = json.loads(out[0])
    assert payload["operator_user_id"] is None
    assert payload["audit"]["written"] is False
    assert payload["audit"]["skipped_reason"] == "missing_operator_user_id"
