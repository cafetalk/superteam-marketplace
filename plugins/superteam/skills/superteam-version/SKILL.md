---
name: superteam-version
description: Show superteam superteam-version, installed skills, and configuration status
---

# Version

Display superteam superteam-version, installed skills count, configuration status, and running mode.

## Usage

```bash
# Human-readable output
python3 skills/superteam-version/scripts/version.py

# JSON output
python3 skills/superteam-version/scripts/version.py --json
```

## Output

- Version number (from VERSION file)
- Installed skills (scanned from sibling directories)
- Configuration status (which keys are set in ~/.superteam/config)
- Running mode: Direct (KB_TREX_PG_URL) or MCP (SUPERTEAM_MCP_URL)
