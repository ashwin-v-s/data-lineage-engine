# Optional Local PostgreSQL for Research/Offline Development

Kairos product development and the shared demo use the team's Supabase project,
including its hosted Postgres database. Follow [`SUPABASE_SETUP.md`](SUPABASE_SETUP.md)
for the shared product setup. Do not install or configure a local database for
the normal shared demo workflow.

A separate local PostgreSQL instance may be useful for:

- offline development without changing shared project data;
- testing destructive migrations against an isolated database; or
- the independent ProvSQL/research feasibility work, if that experiment needs it.

Changes in a local database are not shared with teammates and do not appear in
the Supabase catalog. Never point destructive test commands at the team's
Supabase `DATABASE_URL`.

If a local research instance is needed, install PostgreSQL using the official
installer for your operating system, create a separate research database, and
use a separate local connection string. Keep it out of the product `.env` when
running the shared demo. For migration procedures, see
[`../backend/migrations/README.md`](../backend/migrations/README.md).
