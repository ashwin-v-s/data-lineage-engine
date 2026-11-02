# Kairos Decision Log

## Unowned Items — Assigned 2026-11-02

### Item 1: 0008 lifecycle_state CHECK constraint
**Status:** Assigned to M2 (Anushka)
**Issue:** 0008_source_connections.sql line 21-22 restricts lifecycle_state to 4 values (CONFIGURED, VERIFIED, ERROR, REVOKED), but architecture specifies 12-state connector lifecycle. This will break M2's code.
**Decision:** M2 to review the constraint and migration before application. Either expand the CHECK constraint or align the architecture to the 4-state model.
**Blocker:** This migration cannot be applied until resolved.
**Owner:** @AnaaMorr

---

### Item 2: Six missing screens
**Status:** Assigned to M4 (Gauree)
**Issue:** UI navigation missing: Sources, Freshness, Glossary, Domains, Settings, Notifications. No routes. No tables. Risk of duplication.
**Decision:** M4 to clarify which M4 migrations (0007, 0008, 0009) add schemas for these screens, so M3 and M2 don't build them twice.
**Owner:** @gaureehatkar

---

### Item 3: Dead code decision
**Status:** M1 decision (Jatin)
**Issue:** 515 statements at 0% coverage in backend/app/repositories/, mock_repo.py, legacy schemas.py — nothing imports them.
**Decision:** DELETE (these are leftover stubs). Frontend and API routes are the active implementation.
**Rationale:** Keeping dead code signals "this is how we do it" to future contributors. Cleaner to remove.
**Target:** Remove before M2-M5 handoff to prevent confusion.
**Owner:** @Jat-in32006

---

### Item 4: Skipped tests acceptability
**Status:** Documented as limitation, awaiting real credentials
**Issue:** 80 tests skipped: 76 for missing KAIROS_TEST_USER_TOKEN, 2 for LEFT/RIGHT JOIN weakness.
**Decision:** Acceptable for internal demo. For production release, all 76 must run with live test account.
**Path forward:** Once test user exists, these become executable proofs of isolation.
**Owner:** All

---

### Item 5: CI hardening (coverage floor, live-test job, live-smoke)
**Status:** Partially done, tracking
**Progress:**
- ✅ Coverage floor: --cov-fail-under=40 added to CI (commit 25800d6)
- ✅ CI reports coverage: pytest-cov added as dev dependency
- ⏳ Live-test job: awaits live credentials (KAIROS_TEST_USER_TOKEN secret)
- 🚫 live-smoke: permanently red, awaits deployment URL

**Owner:** @Jat-in32006

---

## Architecture Decisions Pending (D1-D15)

| Decision | Owner | Status | Notes |
|----------|-------|--------|-------|
| D6 | Rollback owner naming | ⏳ PENDING | Who owns reversing schema changes? |
| D7 | Visibility selector shape | ⏳ PENDING | Impacts 0007+ RLS policies |
| D10 | Client vs server export | ⏳ PENDING | Blocks M3/M4 export routes |
| D12 | Scheduled jobs runtime | ⏳ PENDING | Vercel maxDuration:30 prevents migrations in request path |

---

## Deployment Blockers

1. **Supabase circuit breaker:** Reset credentials or provision new pooler
2. **Vercel sync:** Fix directory detection
3. Once both resolved: Apply migrations 0004-0009, run list_tables.py to verify
