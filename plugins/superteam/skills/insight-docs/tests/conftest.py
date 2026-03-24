"""Shared fixtures for read-kb-pgsql tests."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
SHARED_DIR = Path(__file__).parent.parent.parent / "_shared"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SHARED_DIR))

sys.modules.setdefault("psycopg2", MagicMock())
sys.modules.setdefault("psycopg2.extras", MagicMock())

import pytest
