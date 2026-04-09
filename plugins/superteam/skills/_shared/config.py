"""Unified config loading: os.environ > ~/.superteam/config."""
from __future__ import annotations
import os
from pathlib import Path

CONFIG_DIRS = [".superteam"]
_CONFIG_CACHE: dict[str, str] | None = None

_DEFAULT_SOURCE_DOCS = ".superteam/source_docs"
_DEFAULT_TMP = ".superteam/tmp"


def tmp_root() -> Path:
    """Root directory for temporary/intermediate files.

    Configure via ``SUPERTEAM_TMP_DIR`` in the environment or ``~/.superteam/config``.
    Default: ``~/.superteam/tmp``.

    Subdirectories:
      - pipeline_state.json   — sync pipeline state for downstream steps
      - extraction_tmp/       — binary file download staging
      - chunks_{source}.ndjson — chunking output
      - db_dumps/             — database dump archives
    """
    root = env("SUPERTEAM_TMP_DIR")
    if root:
        return Path(root).expanduser()
    return Path.home() / _DEFAULT_TMP


def source_docs_root() -> Path:
    """Root directory for synced markdown (dingtalk/, google_drive/, notion/ underneath).

    Configure via ``SUPERTEAM_SOURCE_DIR`` in the environment or ``~/.superteam/config``.
    Default: ``~/.superteam/source_docs``. Use a writable path in sandboxes / CI.
    """
    root = env("SUPERTEAM_SOURCE_DIR")
    if root:
        return Path(root).expanduser()
    return Path.home() / _DEFAULT_SOURCE_DOCS


def _load_config() -> dict[str, str]:
    """Load config from file(s).

    Resolution order:
      1. ``SUPERTEAM_CONFIG`` env var → absolute path to config file
      2. ``~/.superteam/config`` (default)
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    _CONFIG_CACHE = {}

    # Collect candidate config file paths
    paths: list[Path] = []
    explicit = os.environ.get("SUPERTEAM_CONFIG")
    if explicit:
        paths.append(Path(explicit).expanduser())
    for name in CONFIG_DIRS:
        paths.append(Path.home() / name / "config")

    for cfg_path in paths:
        if cfg_path.exists():
            for line in cfg_path.read_text().splitlines():
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    _CONFIG_CACHE.setdefault(k.strip(), v.strip())
    return _CONFIG_CACHE


def env(key: str, default: str | None = None) -> str | None:
    """Read from os.environ first, then config files."""
    v = os.environ.get(key)
    if v:
        return v
    return _load_config().get(key, default)


def env_list(key: str) -> list[str]:
    """Read a comma-separated config value as a list of strings.

    Example config::

        SUPERTEAM_GOOGLE_DRIVE_FOLDER_IDS=id1,id2,id3

    Returns ``["id1", "id2", "id3"]``, or ``[]`` if not set.
    Whitespace around each item is stripped; empty items are dropped.
    """
    raw = env(key)
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]
