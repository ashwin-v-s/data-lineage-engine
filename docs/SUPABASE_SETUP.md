# Kairos Shared Supabase Setup

Kairos uses one shared Supabase project for the team's product demo. Supabase
provides Auth, hosted PostgreSQL (called **Supabase Postgres**), and optional
Storage. Teammates do not need to install PostgreSQL locally to use the product.

Postgres is the database engine inside Supabase, not a competing local service.
The Python/FastAPI service still connects to the shared Supabase database using
its server-only connection URI; Python ingestion and research code continue to
run in the Kairos service/repository. Supabase does not automatically run or
replace those adapters. A future Edge Functions migration would be a separate
architecture change.

## One-time project setup

1. Use the Kairos Supabase project shared with the team. Do not create a
   different project for each teammate.
2. In **Project Settings → API**, copy the project URL and the publishable key
   (older projects may label it `anon`). Never use the `service_role` key in the
   browser.
3. In **Project Settings → Database → Connection string**, select the URI for
   the **Transaction pooler** and copy it. Use the exact URI Supabase displays;
   it contains the project-specific pooler host and database password.
4. Put these values in a local, ignored `.env` copied from `.env.example`:

   ```dotenv
   SUPABASE_URL=https://PROJECT_REF.supabase.co
   SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
   DATABASE_URL=YOUR_SUPABASE_TRANSACTION_POOLER_URI
   FRONTEND_ORIGIN=http://127.0.0.1:8000
   ```

   `DATABASE_URL` and any password are secrets. Do not paste them into source,
   commit them, or send them in team chat. The Supabase URL and publishable key
   are public client configuration; service-role keys are not.

5. Set the project's Auth email and redirect settings for the local and hosted
   Kairos origins. Configure Google/GitHub/Microsoft providers in Supabase only
   when the respective provider credentials are available. Kairos social login
   is not enabled merely by adding a button.

## Apply schema once

One migration owner applies the repository migrations to the shared project in
numeric order: `0001_core.sql`, `0002_audit_ownership_metadata.sql`, then
`0003_personal_workspaces.sql`. Use the Supabase SQL Editor or `psql` connected
to the exact project's pooler URI. Do not run local reset/drop commands against
the shared project. Do not let multiple teammates run migrations concurrently.

Migration 0003 creates the personal workspace and RLS policies. Review the
database login grants described in [`../backend/migrations/README.md`](../backend/migrations/README.md).
Verify the migration and cross-workspace isolation with a controlled test
before putting real user data into the demo.

### Shared project verification (2026-10-29)

The configured shared project was checked directly. Migrations 0001–0003 are
applied. The 17 existing business tables have a `workspace_id` column and a
forced `kairos_workspace_isolation` policy. Existing catalog data was preserved
in one `Legacy catalog` workspace; new users start with an empty personal
workspace. A restricted-role check returned zero catalog rows without a
workspace context, and the workspace provisioning function passed a rolled-back
synthetic-user check.

Auth currently has email enabled with email confirmation required and zero
registered users. Google, GitHub, and Microsoft providers are disabled. No
Storage buckets exist; the current metadata-import demo does not require raw
file retention. Provider setup and email delivery still need an end-to-end
account verification. The M3 persistent import/preview API remains application
work and is not created by these database migrations. Its proposed `import_run`
table is drafted in `backend/migrations/0004_ingestion_import_runs.sql` but was
not applied; M3 must review the fields and authorize deployment first.
See [`SUPABASE_FEATURE_ADOPTION.md`](SUPABASE_FEATURE_ADOPTION.md) for the
feature-by-feature status and reasons Storage, Realtime, and Edge Functions
are not part of the current request path.

## Each teammate's local app

Each teammate clones the same GitHub branch, creates their own ignored `.env`
with the shared project settings, installs Python and frontend dependencies,
then runs `python scripts/run_ui.py`. The server and browser talk to the same
Supabase Auth/Postgres project; each Supabase user gets a separate personal
workspace. Do not share local `.env` files. Use the same migration history and
coordinate schema changes through Git PRs.

For local configuration checks, run `python scripts/test_connection.py` after
setting `DATABASE_URL`. For general app startup/build commands, see the root
README. A successful database connection alone does not verify Auth providers,
RLS policies, or the end-to-end import flow.

## Optional local PostgreSQL

Local Postgres is only for isolated/offline development, destructive migration
experiments, or the separate ProvSQL/research work. It is not the shared product
catalog and changes there will not appear in the team Supabase project.
