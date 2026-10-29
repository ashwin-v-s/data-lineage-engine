# Database Migrations (M3)

Numbered migration files that create and modify the PostgreSQL schema.

## Rules

1. **Never edit** a migration file after it has been applied to any environment
2. **Always** create a new numbered file (`0002_*.sql`, `0003_*.sql`, etc.) for changes
3. **Test** each migration on a clean database before committing
4. **Document** what each migration does in its header comment

## Setup

### Install PostgreSQL

**Windows (native):**
```powershell
winget install PostgreSQL.PostgreSQL
```

**Windows (WSL2) - recommended for ProvSQL compatibility:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo service postgresql start
```

### Create Database

```bash
# Create database
createdb kairos

# Or via psql:
psql -U postgres
CREATE DATABASE kairos;
\q
```

### Apply Migrations

```bash
# Apply migration 0001
psql kairos < backend/migrations/0001_core.sql

# Verify tables were created
psql kairos -c "\dt"
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
in first.

Apply 0003 only after 0001 and 0002, using the privileged database connection
used for schema migrations:

```powershell
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/0003_personal_workspaces.sql
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

To inspect migration state, verify that all 17 business tables have a
`workspace_id` column, `kairos_workspace_isolation` policy, and RLS enabled.
Do not manually assign the legacy workspace to a user unless that user is
intended to receive the pre-isolation catalog.

## Connection String Format

```
postgresql://username:password@localhost:5432/kairos
```

Store in `.env` (never commit `.env`):
```
DATABASE_URL=postgresql://postgres:password@localhost:5432/kairos
```

## Testing Migrations

```bash
# Drop and recreate database
dropdb kairos && createdb kairos

# Apply migration
psql kairos < backend/migrations/0001_core.sql

# Should succeed without errors
echo $?  # Should print 0
```

## Rollback

Migrations are forward-only. To "rollback":
1. Drop the database: `dropdb kairos`
2. Recreate it: `createdb kairos`
3. Apply migrations up to the desired point

For production, create explicit rollback scripts if needed.
