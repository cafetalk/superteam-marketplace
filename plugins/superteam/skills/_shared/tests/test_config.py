"""Tests for _shared/config.py"""
import os, sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


class TestEnv:
    def test_reads_os_environ(self):
        with patch.dict("os.environ", {"FOO": "bar"}):
            assert config.env("FOO") == "bar"

    def test_falls_back_to_config_file(self, tmp_path):
        cfg = tmp_path / ".test-skills" / "config"
        cfg.parent.mkdir()
        cfg.write_text("MY_KEY=secret123\n")
        with patch.dict("os.environ", {}, clear=True), \
             patch.object(config, "CONFIG_DIRS", [".test-skills"]), \
             patch("pathlib.Path.home", return_value=tmp_path):
            config._CONFIG_CACHE = None
            assert config.env("MY_KEY") == "secret123"

    def test_env_returns_default(self):
        with patch.dict("os.environ", {}, clear=True):
            config._CONFIG_CACHE = {}
            assert config.env("NONEXISTENT", "fallback") == "fallback"

    def test_os_environ_takes_priority(self, tmp_path):
        cfg = tmp_path / ".test-skills" / "config"
        cfg.parent.mkdir()
        cfg.write_text("KEY=from_file\n")
        with patch.dict("os.environ", {"KEY": "from_env"}), \
             patch.object(config, "CONFIG_DIRS", [".test-skills"]), \
             patch("pathlib.Path.home", return_value=tmp_path):
            config._CONFIG_CACHE = None
            assert config.env("KEY") == "from_env"

    def test_reads_superteam_config(self, tmp_path):
        """config.py should read ~/.superteam/config."""
        superteam_dir = tmp_path / ".superteam"
        superteam_dir.mkdir()
        (superteam_dir / "config").write_text("SUPERTEAM_MCP_URL=https://example.com/mcp\n")
        with patch.dict("os.environ", {}, clear=True), \
             patch("pathlib.Path.home", return_value=tmp_path):
            config._CONFIG_CACHE = None
            assert config.env("SUPERTEAM_MCP_URL") == "https://example.com/mcp"

    def test_source_docs_root_default(self, tmp_path):
        with patch.dict(os.environ, {}, clear=True), \
             patch("pathlib.Path.home", return_value=tmp_path):
            config._CONFIG_CACHE = None
            assert config.source_docs_root() == tmp_path / ".superteam" / "source_docs"

    def test_source_docs_root_from_env(self, tmp_path):
        custom = str(tmp_path / "sandbox" / "source_docs")
        with patch.dict(os.environ, {"SUPERTEAM_SOURCE_DIR": custom}):
            config._CONFIG_CACHE = None
            assert config.source_docs_root() == Path(custom)

    def test_source_docs_root_from_config_file(self, tmp_path):
        superteam_dir = tmp_path / ".superteam"
        superteam_dir.mkdir()
        custom = str(tmp_path / "from_config" / "docs")
        (superteam_dir / "config").write_text(f"SUPERTEAM_SOURCE_DIR={custom}\n")
        with patch.dict(os.environ, {}, clear=True), \
             patch("pathlib.Path.home", return_value=tmp_path):
            config._CONFIG_CACHE = None
            assert config.source_docs_root() == Path(custom)
