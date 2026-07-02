"""Unit tests for DingTalk markdown chunking."""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import generate_team_weekly_report as gtw  # noqa: E402


def test_split_markdown_single_chunk():
    assert gtw._split_markdown_chunks("hello", max_len=100) == ["hello"]


def test_split_markdown_multiple_chunks():
    text = ("para one\n\n" * 500) + "tail"
    chunks = gtw._split_markdown_chunks(text, max_len=2000)
    assert len(chunks) >= 2
    assert all(len(c) <= 2000 for c in chunks)
    assert "".join(chunks).replace("\n", "") == text.replace("\n", "")
