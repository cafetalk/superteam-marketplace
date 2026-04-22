"""Unit tests for workspace list parsing (no git subprocess)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from query_git import split_workspace_env_value  # noqa: E402


def test_split_single_segment():
    assert split_workspace_env_value("/foo/bar") == ["/foo/bar"]


def test_split_strips_and_skips_empty():
    assert split_workspace_env_value(" /a/  :  : /b ") == ["/a/", "/b"]


def test_split_uses_pathsep():
    old = os.pathsep
    try:
        setattr(os, "pathsep", "|")
        assert split_workspace_env_value("p1|p2") == ["p1", "p2"]
    finally:
        setattr(os, "pathsep", old)


if __name__ == "__main__":
    test_split_single_segment()
    test_split_strips_and_skips_empty()
    test_split_uses_pathsep()
    print("ok")
