import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load the repo-root .env (if present) so integration tests can detect the
# shared Supabase configuration the same way backend.app.db does.
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=_env_file, override=False)
    except ImportError:
        pass


def _live_backend_opted_in() -> bool:
    """True only when live API integration tests are explicitly requested.

    The API is fail-closed: every route requires a verified Supabase session and
    a workspace-scoped database connection.  Merely *having* credentials in
    ``.env`` is not enough — a developer's local ``.env`` would otherwise make
    the offline suite depend on network and shared-database state.  Opt in by
    setting ``KAIROS_LIVE_API_TESTS=1`` alongside ``DATABASE_URL`` and
    ``SUPABASE_URL``.
    """
    if os.getenv("KAIROS_LIVE_API_TESTS", "").strip().lower() not in {"1", "true", "yes"}:
        return False
    has_db = bool(os.getenv("DATABASE_URL"))
    has_auth = bool(os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL"))
    return has_db and has_auth


requires_live_backend = pytest.mark.skipif(
    not _live_backend_opted_in(),
    reason=(
        "Live API integration tests are opt-in. Set KAIROS_LIVE_API_TESTS=1 "
        "together with DATABASE_URL and SUPABASE_URL to run them against the "
        "shared Supabase project."
    ),
)
