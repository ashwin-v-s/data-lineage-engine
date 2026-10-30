# Project scripts

- `python scripts/run_ui.py` builds the React frontend and starts the FastAPI app.
  Install Python dependencies from the repository root with `python -m pip install -e ".[dev]"` and frontend dependencies with `npm --prefix frontend ci` first.
- `python scripts/check_import_boundaries.py` enforces the leakage and independence rules used by CI.
- `python scripts/check_openapi_drift.py` is the OpenAPI contract-drift gate: it regenerates the FastAPI schema, normalizes it, and compares it against the committed snapshot at `contracts/api/openapi.json`. It exits `0` when unchanged, `1` when the HTTP surface drifted (printing the added/removed paths and changed methods), and `2` on setup errors. Run `python scripts/check_openapi_drift.py --write` (or `--update`) to refresh the snapshot after an intentional API change.
- `python scripts/make_fixtures.py` regenerates the mock fixtures; review its output before committing.
- `python scripts/test_connection.py` checks the configured database connection and requires valid environment settings and network access to Supabase.
- `python scripts/db/verify_rls.py` verifies row-level-security hardening of the business tables; run it against a release database and expect a zero exit code.
- `python scripts/seed_demo_catalog.py --user-id <uuid>` prints the Olist sample assets it would load into that user's workspace; add `--apply` to write them as clearly-labelled demo data.
- `python scripts/run_migration.py` is a legacy helper that applies only migration 0001; use the numbered migration instructions in `docs/SUPABASE_SETUP.md` for a complete setup.
