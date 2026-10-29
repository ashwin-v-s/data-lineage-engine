# Project scripts

- `python scripts/run_ui.py` builds the React frontend and starts the FastAPI app.
  Install Python dependencies from the repository root with `python -m pip install -e ".[dev]"` and frontend dependencies with `npm --prefix frontend ci` first.
- `python scripts/check_import_boundaries.py` enforces the leakage and independence rules used by CI.
- `python scripts/make_fixtures.py` regenerates the mock fixtures; review its output before committing.
- `python scripts/test_connection.py` checks the configured database connection and requires valid environment settings and network access to Supabase.
- `python scripts/run_migration.py` is a legacy helper that applies only migration 0001; use the numbered migration instructions in `docs/SUPABASE_SETUP.md` for a complete setup.
