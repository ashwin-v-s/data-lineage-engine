# backend (M5 API, M3 storage)

**Owner:** M5 for api/, schemas/, services/. M3 for migrations/, temporal/, identity/, repositories/.

---

## M3 Week 1 Status: ✅ COMPLETE

### What's Built
- ✅ `app/temporal/reference.py` - Python temporal oracle (16 tests passing)
- ✅ `app/identity/canonical_ids.py` - Identity system (32 tests passing)
- ✅ `migrations/0001_core.sql` - Database schema (10 tables)
- ✅ `migrations/README.md` - Migration guide

### What's Pending
- [ ] PostgreSQL installation
- [ ] `app/repositories/postgres.py` - Repository implementation
- [ ] SQL temporal queries
- [ ] Integration tests with database

---

## Quick Start

### For M3 (Storage)

1. **Install PostgreSQL:**
   ```bash
   winget install PostgreSQL.PostgreSQL
   ```

2. **Create Database:**
   ```bash
   psql -U postgres -c "CREATE DATABASE kairos;"
   ```

3. **Apply Migration:**
   ```bash
   psql -U postgres kairos < backend/migrations/0001_core.sql
   ```

4. **Verify:**
   ```bash
   psql -U postgres kairos -c "\dt"
   ```

5. **Run Tests:**
   ```bash
   pytest tests/test_temporal_oracle.py tests/test_identity.py -v
   ```

### For M5 (API)

Use mock repository (M3 repository coming in Week 2).

---

## Documentation

- Setup: `docs/POSTGRESQL_SETUP.md`
- Schema: `docs/DATA_MODEL.md`
- Checkpoint: `docs/M3_WEEK1_CHECKPOINT_REPORT.md`

---

First tasks: M5 scaffold FastAPI with /api/v1/health and the stable error shape, using a mock repository. M3 write migration 0001 and the first temporal tests. See docs pack Sections 32 and 34.
