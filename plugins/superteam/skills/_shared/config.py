"""Unified config loading: os.environ > ~/.xxx-skills/config files."""
from __future__ import annotations
import os
from pathlib import Path

CONFIG_DIRS = [".superteam", ".dingtalk-skills", ".google-drive-skills", ".notion-skills"]
_CONFIG_CACHE: dict[str, str] | None = None


def _load_config() -> dict[str, str]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    _CONFIG_CACHE = {}
    for name in CONFIG_DIRS:
        cfg_path = Path.home() / name / "config"
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
