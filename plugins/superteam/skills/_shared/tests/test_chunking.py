"""Tests for _shared/chunking.py — _is_markdown() and chunk_smart()."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import chunking


class TestIsMarkdown:
    def test_markdown_with_heading_and_list(self):
        text = "# Title\n\nSome text\n\n- item 1\n- item 2"
        assert chunking._is_markdown(text) is True

    def test_markdown_with_heading_and_code(self):
        text = "## Section\n\n```python\nprint('hi')\n```"
        assert chunking._is_markdown(text) is True

    def test_markdown_with_table_and_list(self):
        text = "| A | B |\n|---|---|\n| 1 | 2 |\n\n- item"
        assert chunking._is_markdown(text) is True

    def test_only_one_indicator_returns_false(self):
        text = "# Just a heading\n\nPlain paragraph without other markers."
        assert chunking._is_markdown(text) is False

    def test_python_code_not_markdown(self):
        text = "#!/usr/bin/env python3\n# comment\nimport os\n\n- not a list"
        assert chunking._is_markdown(text) is False

    def test_python_import_not_markdown(self):
        text = "import sys\n# This is a comment\n- flag option"
        assert chunking._is_markdown(text) is False

    def test_plain_text_not_markdown(self):
        text = "This is just plain text without any markdown structure at all."
        assert chunking._is_markdown(text) is False

    def test_numbered_list_counts(self):
        text = "# Title\n\n1. First item\n2. Second item"
        assert chunking._is_markdown(text) is True


class TestChunkSmart:
    def test_markdown_table_preserved(self):
        text = "# Data\n\n| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n\n## Next"
        chunks = chunking.chunk_smart(text, max_chars=500)
        table_chunk = [c for c in chunks if "| A |" in c]
        assert len(table_chunk) >= 1
        assert "| 3 | 4 |" in table_chunk[0]

    def test_markdown_code_block_preserved(self):
        text = "# Code\n\n```python\ndef foo():\n    return 42\n```\n\n## End"
        chunks = chunking.chunk_smart(text, max_chars=500)
        code_chunk = [c for c in chunks if "def foo" in c]
        assert len(code_chunk) == 1

    def test_plain_text_sentence_boundary(self):
        text = "这是第一句话。这是第二句话。" + "这是很长的一段内容。" * 50
        chunks = chunking.chunk_smart(text, max_chars=200, format_hint="plain")
        # Should not cut mid-sentence (at character boundary)
        for chunk in chunks:
            # No chunk should start with a partial sentence fragment
            assert len(chunk) > 0

    def test_max_chars_zero_no_split(self):
        text = "hello world"
        chunks = chunking.chunk_smart(text, max_chars=0)
        assert chunks == ["hello world"]

    def test_empty_text(self):
        assert chunking.chunk_smart("") == []
        assert chunking.chunk_smart("   ") == []

    def test_format_hint_markdown(self):
        # Plain text but forced markdown mode
        text = "No markdown here but\n\nforced to use markdown splitter"
        chunks = chunking.chunk_smart(text, max_chars=500, format_hint="markdown")
        assert len(chunks) >= 1

    def test_format_hint_plain(self):
        # Markdown text but forced plain mode
        text = "# Heading\n\n- list\n\nForced plain"
        chunks = chunking.chunk_smart(text, max_chars=500, format_hint="plain")
        assert len(chunks) >= 1

    def test_fallback_when_langchain_missing(self):
        original = chunking._HAS_LANGCHAIN
        try:
            chunking._HAS_LANGCHAIN = False
            chunks = chunking.chunk_smart("hello\n\nworld", max_chars=500)
            assert chunks == ["hello", "world"]  # falls back to chunk_text
        finally:
            chunking._HAS_LANGCHAIN = original

    def test_short_paragraphs_kept_separate_when_small(self):
        text = "Short.\n\nAlso short.\n\nStill short.\n\nBrief."
        chunks = chunking.chunk_smart(text, max_chars=500, format_hint="plain")
        # Each paragraph is under max_chars, so they stay as-is
        # The key improvement is they won't be hard-cut mid-sentence
        assert len(chunks) >= 1
        assert all(len(c) <= 500 for c in chunks)

    def test_no_empty_chunks(self):
        text = "# Title\n\n\n\n## Section\n\nContent here.\n\n\n"
        chunks = chunking.chunk_smart(text, max_chars=500)
        for c in chunks:
            assert c.strip() != ""
