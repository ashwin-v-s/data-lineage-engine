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
