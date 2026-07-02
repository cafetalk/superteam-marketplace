"""Shared fixtures for superteam-linear tests."""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
SHARED_DIR = Path(__file__).parent.parent.parent / "_shared"
GIT_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "superteam-git" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SHARED_DIR))
sys.path.insert(0, str(GIT_SCRIPTS_DIR))
