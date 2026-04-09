#!/usr/bin/env python3
"""superteam:version — show version, installed skills, config status."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parent.parent.parent  # skills/
VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def get_version() -> str:
    """Read version from VERSION file."""
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return "unknown"


def get_installed_skills() -> list[dict]:
    """Scan sibling directories for SKILL.md files."""
    skills = []
    for skill_md in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
        skill_dir = skill_md.parent
        if skill_dir.name.startswith("_"):
            continue
        # Parse name from frontmatter
        name = skill_dir.name
        has_scripts = (skill_dir / "scripts").is_dir()
        status = "ready" if has_scripts else "planned"
        for line in skill_md.read_text().splitlines():
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip()
                break
        skills.append({"name": name, "dir": skill_dir.name, "status": status})
    return skills


def get_config_status() -> dict:
    """Check which config keys are set in ~/.superteam/config."""
    import os
    config_file = Path(os.environ["SUPERTEAM_CONFIG"]).expanduser() if os.environ.get("SUPERTEAM_CONFIG") else Path.home() / ".superteam" / "config"
    keys_to_check = {
        "KB_TREX_PG_URL": "Database (Direct mode)",
        "SUPERTEAM_MCP_URL": "MCP Server",
        "DASHSCOPE_API_KEY": "Embedding (DashScope)",
        "DINGTALK_APP_KEY": "DingTalk",
        "GOOGLE_SERVICE_ACCOUNT_KEY_PATH": "Google Drive",
        "NOTION_INTEGRATION_TOKEN": "Notion",
        "OSS_BACKUP_BUCKET": "OSS Backup",
    }

    configured = {}
    if config_file.exists():
        for line in config_file.read_text().splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k = line.split("=", 1)[0].strip()
                if k in keys_to_check:
                    configured[k] = True

    result = {}
    for key, label in keys_to_check.items():
        result[key] = {"label": label, "set": key in configured}
    return result


def get_mode(config_status: dict) -> str:
    """Determine running mode based on config."""
    has_mcp = config_status.get("SUPERTEAM_MCP_URL", {}).get("set", False)
    has_pg = config_status.get("KB_TREX_PG_URL", {}).get("set", False)
    if has_mcp and has_pg:
        return "dual (MCP for queries, Direct for writes)"
    elif has_mcp:
        return "MCP (read-only)"
    elif has_pg:
        return "Direct (read-write)"
    else:
        return "not configured"


def main() -> None:
    parser = argparse.ArgumentParser(description="Show superteam version info")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    version = get_version()
    skills = get_installed_skills()
    config_status = get_config_status()
    mode = get_mode(config_status)

    ready_count = sum(1 for s in skills if s["status"] == "ready")
    planned_count = sum(1 for s in skills if s["status"] == "planned")

    if args.json:
        print(json.dumps({
            "version": version,
            "mode": mode,
            "skills": skills,
            "skills_ready": ready_count,
            "skills_planned": planned_count,
            "config": {k: v["set"] for k, v in config_status.items()},
        }, ensure_ascii=False, indent=2))
    else:
        print(f"superteam v{version}")
        print(f"mode: {mode}")
        print(f"skills: {ready_count} ready, {planned_count} planned")
        print()
        for s in skills:
            icon = "✅" if s["status"] == "ready" else "📋"
            print(f"  {icon} {s['name']}")
        print()
        print("config:")
        for key, info in config_status.items():
            icon = "✅" if info["set"] else "  "
            print(f"  {icon} {info['label']}")


if __name__ == "__main__":
    main()
