"""Unit tests for pulse.py — upsert SQL, ON CONFLICT semantics, validation."""
import json
import sys
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, call

sys.path.insert(0, str(Path(__file__).parent.parent))


def _mock_conn():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


class TestUpsertPulse:
    def test_inserts_with_on_conflict(self):
        from pulse import upsert_pulse

        conn, cur = _mock_conn()
        upsert_pulse(
            conn,
            snapshot_date=date(2026, 5, 22),
            type="knowledge_base",
            payload={"total_docs": 100},
        )

        sql, params = cur.execute.call_args[0]
        assert "ON CONFLICT" in sql
        assert "DO UPDATE SET" in sql
        assert params[0] == date(2026, 5, 22)
        assert params[1] == "knowledge_base"
        assert params[2] == "daily"   # default period
        assert params[3] == ""        # default team
        assert json.loads(params[4]) == {"total_docs": 100}
        cur.close.assert_called_once()

    def test_custom_period_and_team(self):
        from pulse import upsert_pulse

        conn, cur = _mock_conn()
        upsert_pulse(
            conn,
            snapshot_date=date(2026, 5, 22),
            type="sprint",
            payload={"velocity": 42},
            period="weekly",
            team="backend",
        )
        _, params = cur.execute.call_args[0]
        assert params[2] == "weekly"
        assert params[3] == "backend"

    def test_invalid_type_raises(self):
        from pulse import upsert_pulse
        import pytest

        conn, _ = _mock_conn()
        with pytest.raises(ValueError, match="invalid type"):
            upsert_pulse(
                conn,
                snapshot_date=date(2026, 5, 22),
                type="bogus",
                payload={},
            )

    def test_invalid_period_raises(self):
        from pulse import upsert_pulse
        import pytest

        conn, _ = _mock_conn()
        with pytest.raises(ValueError, match="invalid period"):
            upsert_pulse(
                conn,
                snapshot_date=date(2026, 5, 22),
                type="member",
                payload={},
                period="monthly",
            )

    def test_non_dict_payload_raises(self):
        from pulse import upsert_pulse
        import pytest

        conn, _ = _mock_conn()
        with pytest.raises(TypeError, match="payload must be dict"):
            upsert_pulse(
                conn,
                snapshot_date=date(2026, 5, 22),
                type="knowledge_base",
                payload="not-a-dict",  # type: ignore
            )

    def test_does_not_commit(self):
        """Caller controls transaction — upsert_pulse must NOT commit."""
        from pulse import upsert_pulse

        conn, _ = _mock_conn()
        upsert_pulse(
            conn,
            snapshot_date=date(2026, 5, 22),
            type="knowledge_base",
            payload={},
        )
        conn.commit.assert_not_called()


class TestReadLatestPulse:
    def test_returns_row(self):
        from pulse import read_latest_pulse

        conn, cur = _mock_conn()
        cur.fetchone.return_value = (
            date(2026, 5, 22),
            json.dumps({"total_docs": 99}),
            datetime(2026, 5, 22, 3, 30),
        )

        result = read_latest_pulse(conn, type="knowledge_base")
        assert result is not None
        assert result["snapshot_date"] == "2026-05-22"
        assert result["payload"]["total_docs"] == 99

    def test_returns_none_when_no_row(self):
        from pulse import read_latest_pulse

        conn, cur = _mock_conn()
        cur.fetchone.return_value = None

        result = read_latest_pulse(conn, type="knowledge_base")
        assert result is None

    def test_invalid_type_raises(self):
        from pulse import read_latest_pulse
        import pytest

        conn, _ = _mock_conn()
        with pytest.raises(ValueError):
            read_latest_pulse(conn, type="unknown")

    def test_jsonb_dict_passthrough(self):
        """psycopg2 may return payload already as dict (jsonb auto-cast)."""
        from pulse import read_latest_pulse

        conn, cur = _mock_conn()
        cur.fetchone.return_value = (
            date(2026, 5, 22),
            {"total_docs": 5},   # already a dict, not a string
            None,
        )

        result = read_latest_pulse(conn, type="member")
        assert result["payload"]["total_docs"] == 5


class TestReadPulseOn:
    def test_passes_snapshot_date_to_query(self):
        from pulse import read_pulse_on

        conn, cur = _mock_conn()
        cur.fetchone.return_value = None
        target = date(2026, 5, 15)

        read_pulse_on(conn, type="sprint", snapshot_date=target)

        _, params = cur.execute.call_args[0]
        assert target in params


class TestComputeKbPulsePayload:
    def _setup_conn(self, side_effects):
        """side_effects: list of fetchone/fetchall return values, in call order."""
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchall.side_effect = [r for r in side_effects if isinstance(r, list)]
        # fetchone returns are interleaved with fetchall; use a counter approach
        # Patch both via side_effect on the underlying cursor mock
        return conn, cur

    def test_payload_shape(self):
        from pulse import compute_kb_pulse_payload

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur

        # Execute is called multiple times; fetchall/fetchone are called in order
        fetchall_results = [
            [("dingtalk", 50), ("notion", 42)],  # by_source_type
            [("PRD", 28), ("tech-design", 41)],  # by_doc_type
        ]
        # fetchone calls (fetchall calls above are independent):
        # synced_today, updated_today, last_sync_at, last_sync_doc_count, total_chunks, members_total
        fetchone_results = [
            (3,),
            (7,),
            (datetime(2026, 5, 22, 3, 12, 8),),
            (12,),
            (1834,),
            (29,),
        ]
        cur.fetchall.side_effect = fetchall_results
        cur.fetchone.side_effect = fetchone_results

        payload = compute_kb_pulse_payload(conn, date(2026, 5, 22))

        assert payload["total_docs"] == 92          # 50+42
        assert payload["by_source_type"]["dingtalk"] == 50
        assert payload["synced_today"] == 3
        assert payload["updated_today"] == 7
        assert payload["last_sync_doc_count"] == 12
        assert payload["total_chunks"] == 1834
        assert payload["members_total"] == 29
        assert "PRD" in payload["by_doc_type"]
        cur.close.assert_called_once()

    def test_no_last_sync_at(self):
        """When last_synced_at is NULL (empty KB), last_sync_doc_count stays 0."""
        from pulse import compute_kb_pulse_payload

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchall.side_effect = [[], []]
        cur.fetchone.side_effect = [
            (0,),   # synced_today
            (0,),   # updated_today
            (None,),  # last_sync_at — NULL
            (0,),   # total_chunks
            (0,),   # members_total
        ]

        payload = compute_kb_pulse_payload(conn, date(2026, 5, 22))
        assert payload["last_sync_at"] is None
        assert payload["last_sync_doc_count"] == 0
