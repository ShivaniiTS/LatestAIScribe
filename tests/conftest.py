"""
tests/conftest.py — Shared test fixtures.
"""
import os
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set test environment variables
os.environ.setdefault("DATABASE_URL", "")
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")
os.environ.setdefault("STORAGE_ROOT", str(PROJECT_ROOT / "test_data"))
os.environ.setdefault("CORS_ORIGINS", "*")


@pytest.fixture
def tmp_storage(tmp_path):
    """Override storage root to a temp directory."""
    os.environ["STORAGE_ROOT"] = str(tmp_path)
    yield tmp_path
    os.environ["STORAGE_ROOT"] = str(PROJECT_ROOT / "test_data")
