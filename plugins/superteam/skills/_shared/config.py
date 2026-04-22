"""Unified config loading: os.environ > ~/.superteam/config."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

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


def _extract_mcp_http_urls(obj: Any, path: str = "") -> list[tuple[str, str]]:
    """Walk Cursor-style mcp.json (possibly nested ``mcpServers``) and collect (path, url)."""
    out: list[tuple[str, str]] = []
    if not isinstance(obj, dict):
        return out
    url = obj.get("url")
    if isinstance(url, str) and url.startswith("http"):
        out.append((path or "default", url))
    ms = obj.get("mcpServers")
    if isinstance(ms, dict):
        for k, v in ms.items():
            p = f"{path}/{k}" if path else str(k)
            if isinstance(v, dict):
                out.extend(_extract_mcp_http_urls(v, p))
        return out
    for k, v in obj.items():
        if k in ("headers", "env", "command", "args", "type"):
            continue
        if isinstance(v, dict):
            p = f"{path}/{k}" if path else str(k)
            out.extend(_extract_mcp_http_urls(v, p))
    return out


def dingtalk_mcp_url() -> str | None:
    """钉钉文档 MCP 的 HTTP endpoint。

    解析顺序：

    1. 环境变量 ``DINGTALK_MCP_URL``
    2. ``~/.superteam/config`` 等同名键
    3. ``~/.cursor/mcp.json`` 中带 ``dingtalk`` 的 URL，或路径名含「钉钉」的条目（兼容错误嵌套的 ``mcpServers``）
    """
    direct = env("DINGTALK_MCP_URL")
    if direct:
        return direct
    path = Path.home() / ".cursor" / "mcp.json"
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    for name, u in _extract_mcp_http_urls(raw, ""):
        if "dingtalk" in u.lower() or "钉钉" in str(name):
            return u
    return None


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
