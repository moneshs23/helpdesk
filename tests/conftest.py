"""Pytest configuration: isolate test data from real data."""
import os
import tempfile
from pathlib import Path

# Point storage at temp dirs BEFORE importing the app/config.
_tmp = Path(tempfile.mkdtemp(prefix="helpdesk_test_"))
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_tmp / 'test.db'}")
os.environ.setdefault("QDRANT_PATH", str(_tmp / "qdrant"))
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ENABLE_QUERY_REWRITE", "false")
