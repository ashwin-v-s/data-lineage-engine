# Kairos Backend

The product demo uses the team's shared Supabase project for authentication and hosted Postgres. The Python/FastAPI service remains the application API and ingestion-compute layer; no local Postgres installation is required for normal product work.

## Run against the shared Supabase project

1. Use the existing ignored `.env` if one is present. Do not overwrite it. If it is missing, create it from the root `.env.example` and fill in the shared Supabase settings.
2. Follow [`../docs/SUPABASE_SETUP.md`](../docs/SUPABASE_SETUP.md) to check configuration and apply migrations once.
3. Test the database connection with `python scripts/test_connection.py`.
4. Start the combined frontend/backend with `python scripts/run_ui.py`.

The legacy `scripts/run_migration.py` applies only `0001_core.sql`; it is not a complete migration runner. Apply migrations in numeric order using the Supabase setup guide.

## Optional local database

A local PostgreSQL instance is optional for offline development and isolated research/ProvSQL experiments. It is not the shared product database; local changes do not appear in the team's Supabase project. See [`../docs/POSTGRESQL_SETUP.md`](../docs/POSTGRESQL_SETUP.md).

## Related documentation

- Shared backend: [`../docs/SUPABASE_SETUP.md`](../docs/SUPABASE_SETUP.md)
- Schema and migrations: [`migrations/README.md`](migrations/README.md)
- Product/research architecture: [`../docs/KAIROS_FINAL_ARCHITECTURE.md`](../docs/KAIROS_FINAL_ARCHITECTURE.md)
- Research architecture and execution contract: [`../docs/FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md`](../docs/FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md)
