"""Vercel Python Function entrypoint for the Kairos FastAPI API."""
from backend.app.main import app

__all__ = ["app"]
