"""Vercel Python Function entrypoint for the Kairos FastAPI API."""
import sys
from pathlib import Path

# Add repo root to sys.path so 'backend', 'contracts', 'ingestion', 'research' are importable
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.main import app

__all__ = ["app"]
