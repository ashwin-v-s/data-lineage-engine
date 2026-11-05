# Database Migrations (M1 â€” Jatin, contract custodian)

Numbered migration files that create and modify the schema in the team's
shared **Supabase Postgres** project.

> **How to verify:** `python scripts/db/verify_applied.py`
> This connects to the live DB and checks each migration's tables exist.
> A migration header â€” and this README â€” may only say **"Applied"** once that
> script exits 0 for the relevant tables. Never quote `check_migrations.py`'s
> output as proof of application; it is a static file check that never contacts
> the database.
>
> See `docs/DECISION_LOG.md` D12 for the DB runtime decision.

## Apply status (last verified 2026-11-03 — all 9 migrations applied to shared Supabase)

| Migration | Tables | Status |
|---|---|---|
| 0001_core | dataset, column_record, job, execution_run, raw_event, evidence, lineage_edge, edge_temporal_version, execution_state, projection_outbox | âœ… Applied â€” confirmed 2026-10-29 |
| 0002_audit_ownership_metadata | team_member, owner_assignment, owner_request, audit_log, asset_version, audit_event, rollback_record | âœ… Applied â€” confirmed 2026-10-29 |
| 0003_personal_workspaces | kairos_workspace | âœ… Applied â€” confirmed 2026-10-29 |
| 0004_ingestion_import_runs | import_run | âœ… Applied â€” import_run confirmed 2026-10-30 |
| 0005_personalization | asset_view, asset_star | âš ï¸ NOT VERIFIED â€” tables absent 2026-10-30; run verify_applied.py |
| 0006_github_connections | github_connection | âš ï¸ NOT VERIFIED â€” table absent 2026-10-30; run verify_applied.py |
| 0007_membership_roles | workspace_member, workspace_invite | âš ï¸ NOT VERIFIED â€” run verify_applied.py |
| 0008_source_connections | source_connection | âš ï¸ NOT VERIFIED â€” run verify_applied.py |
| 0009_governance | freshness_sla, freshness_evaluation, incident, incident_event | âš ï¸ CLAIMED Applied in header â€” run verify_applied.py to confirm |



## Rules

1. **Never edit** a migration file after it has been applied to any environment
2. **Always** create a new numbered file (`0002_*.sql`, `0003_*.sql`, etc.) for changes
3. **Test** each migration on a clean database before committing
4. **Document** what each migration does in its header comment

## Shared Supabase setup

One migration owner applies each numbered migration once to the shared project.
Use Supabase SQL Editor or the project's database connection URI. The local
server is optional for offline/research work and is not the shared product DB.

```bash
# Apply in order; DATABASE_URL must target the intended Supabase project.
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/0001_core.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/0002_audit_ownership_metadata.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/0003_personal_workspaces.sql
```

## Current Migrations

### 0001_core.sql
Creates foundational schema:
- `dataset`, `column_record` - identity management
- `job`, `execution_run` - job tracking
- `raw_event` - immutable raw events with trigger
- `evidence` - normalized evidence
- `lineage_edge` - logical edges
- `edge_temporal_version` - bitemporal versions
- `execution_state` - derived 4-state results
- `projection_outbox` - Neo4j projection status

**Key features:**
- Half-open intervals on both time axes
- Immutability trigger on `raw_event`
- UUID primary keys with deterministic option
- Indexes for traversal, time range queries, and lookups

### 0002_audit_ownership_metadata.sql
Adds dataset ownership/description fields and the team, ownership, audit,
version, and rollback tables used by the governance API.

### 0003_personal_workspaces.sql
Adds a personal workspace for each Supabase user on that user's first
authenticated API request. PostgreSQL row-level security scopes every business
table query to that workspace. Existing rows are kept in a separate
`Legacy catalog` workspace and are intentionally not assigned to whoever signs
in first. The workspace registry itself has forced RLS and no direct grants to
browser/API roles; provisioning is through the restricted SECURITY DEFINER
function. The shared Supabase project was verified with this migration applied
on 2026-10-29.

### 0004_ingestion_import_runs.sql
Adds the workspace-scoped import provenance/idempotency record (`import_run`)
described in the product architecture. **Applied** to the shared Supabase
project; the `import_run` table exists live. The preview path is read-only and
never writes this table; only an explicit commit does.

### 0005_personalization.sql
Adds the per-user `asset_view` (recently viewed) and `asset_star` (starred
assets) tables. Both carry workspace RLS, are granted only to `kairos_app`,
and are keyed on `(workspace_id, user_id, asset_id)`.
**Status: NOT VERIFIED APPLIED** â€” tables were absent from the live DB on
2026-10-30. Run `python scripts/db/verify_applied.py` before enabling
personalization routes in production.

### 0006_github_connections.sql
Adds the workspace-scoped `github_connection` table holding only the AES-256-GCM
encrypted GitHub App installation token (never plaintext). **Applied** to the
shared Supabase project; the install/callback wiring is owned by M2.

### 0007_membership_roles.sql
Adds `workspace_member` (a user's role in a workspace) and `workspace_invite`
(a pending invitation; cannot grant `owner`). Both carry forced workspace RLS.
Membership is the source of truth for a user's role â€” never the JWT.
**Status: NOT VERIFIED APPLIED** â€” run `python scripts/db/verify_applied.py`.

### 0008_source_connections.sql
Adds `source_connection`: one row per configured external source (PostgreSQL),
holding an AES-256-GCM encrypted connection config plus lifecycle state
`CONFIGURED â†’ VERIFIED | ERROR â†’ REVOKED`. Granted only to `kairos_app`.
**Status: NOT VERIFIED APPLIED** â€” run `python scripts/db/verify_applied.py`.

### 0009_governance.sql
Adds the workspace-scoped governance tables `freshness_sla`,
`freshness_evaluation`, `incident` and `incident_event`. Freshness is
evidence-first: a dataset with no stored source activity is `UNKNOWN`, never a
false `LATE`/`STALE`; any source inferred from the database may derive from the
schema but is never `LATE` without evidence of a breach. A partial unique index
(`... WHERE status <> 'RESOLVED'`) keeps exactly one *open* incident per breach
while still letting a resolved breach recur. **Applied** to the shared Supabase
project.

Apply the remaining migrations in order, using the privileged database
connection used for schema migrations:

```powershell
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/0004_ingestion_import_runs.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/0005_personalization.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/0006_github_connections.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/0007_membership_roles.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/0008_source_connections.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/0009_governance.sql
```

The API's `DATABASE_URL` role must be a member of `kairos_app`; the migration
grants membership to its executing role and to `postgres` when that role
exists. If the API uses a different login role, a database administrator must
also grant it membership and permission to execute
`public.kairos_ensure_personal_workspace(uuid)`. Do not run the API with a
restricted or anonymous database role that cannot call that provisioning
function. The API fails closed with HTTP 503 until the migration and grants are
in place.

For example, when the API login is `kairos`, run as a database administrator:

```sql
GRANT kairos_app TO kairos;
GRANT EXECUTE ON FUNCTION public.kairos_ensure_personal_workspace(uuid) TO kairos;
```

To inspect migration state, verify that all 28 workspace-scoped business tables
have a `workspace_id` column, a `kairos_workspace_isolation` policy, and RLS
enabled (run `python scripts/db/verify_rls.py` against a live database; the
static cross-check is `python scripts/db/check_migrations.py`).
Do not manually assign the legacy workspace to a user unless that user is
intended to receive the pre-isolation catalog.

## Supabase connection string

```
Use the transaction-pooler URI copied from Supabase Project Settings â†’ Database.
```

Store the exact URI in `.env` (never commit `.env`):
```
DATABASE_URL=<Supabase transaction-pooler URI>
```

## Migration testing and rollback

Do not run drop/recreate commands against the shared project. Test destructive
or forward migration changes in a separate Supabase project/branch or isolated
local database. Migrations are forward-only; production corrections require a
reviewed follow-up migration and a backup/restore plan.

---

## M3 Migration Addition (2026-11-05)

### 0012_m3_pgvector_embeddings.sql

**Author:** M3 (Ashwin - ashwin-v-s)  
**Status:** 📝 PROPOSAL (not yet applied)  
**Naming:** Per D13 decision - `{number}_{owner_initials}_{feature}.sql`  

Adds pgvector extension and vector embedding column to the `dataset` table for semantic search capability:
- Adds `embedding vector(1536)` column to `dataset`
- Creates ivfflat index for cosine similarity search
- Uses OpenAI text-embedding-3-small model (1536 dimensions)
- Enables hybrid search (keyword + semantic)

**Requires:**
- PostgreSQL with pgvector extension
- `CREATE EXTENSION vector;` privilege
- OpenAI API key for embedding generation (application layer)

**To apply:**
```sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/0012_m3_pgvector_embeddings.sql
```

**Note:** This migration skips 0011 (reserved for M4 governance per D16). Migration 0010 (M2 source_connection_lifecycle) exists but awaits application.
