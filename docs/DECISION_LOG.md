# Kairos Decision Log

## D12: Database Runtime — DECIDED 2026-11-03

**Decision:** Use shared **Supabase PostgreSQL** project (credentials restored).

**Rationale:** 
- Infrastructure team restored Supabase pooler credentials (DATABASE_URL available 2026-11-03)
- All 9 migrations (0001-0009) verified applied to live Supabase project via scripts/db/verify_applied.py
- 29 business tables confirmed with RLS enabled and forced on all workspace-scoped tables
- This is the production database for the demo and M2-M5 work

**Evidence:**
- python scripts/test_connection.py ? PASS (PostgreSQL 17.6 on aws-0-ap-south-1)
- python scripts/db/list_tables.py ? 29 tables listed
- python scripts/db/verify_applied.py ? PASS (all expected tables exist)
- python scripts/db/verify_rls.py ? 28/28 tables RLS-hardened (connecting as postgres superuser, which can bypass — expected)

**Impact:**
- ? All Wave 1 integration tests can now run (live workspace_member table exists)
- ? All Wave 4 deployment can proceed (DB credentials configured)
- ? M2-M5 can begin work on their integration routes (DB is accessible)

---

## Verification Scripts Status — FIXED 2026-11-03

All four database probe scripts now properly exit with non-zero on failure:

| Script | Exit Code on Success | Exit Code on Failure | Status |
|--------|----------------------|----------------------|--------|
| test_connection.py | 0 | 1 | ? FIXED |
| db/list_tables.py | 0 | 1 | ? FIXED |
| db/check_schema.py | 0 | 1 | ? FIXED |
| db/verify_rls.py | 0 | 1 | ? FIXED |
| **NEW:** db/verify_applied.py | 0 (all migrations applied) | 1 (missing tables) | ? CREATED |

All scripts follow standard exit code conventions and can be used in CI pipelines.

---

## Unowned Items — Assigned 2026-11-02

### Item 1: 0008 lifecycle_state CHECK constraint
**Status:** Assigned to M2 (Anushka)
**Issue:** 0008_source_connections.sql line 21-22 restricts lifecycle_state to 4 values (CONFIGURED, VERIFIED, ERROR, REVOKED), but architecture specifies 12-state connector lifecycle.
**Decision:** M2 to review the constraint and migration before application. Either expand the CHECK constraint or align the architecture to the 4-state model.
**Blocker:** Migration 0008 is now applied; constraint in place. M2 must review and may need migration 0010 to fix.
**Owner:** @AnaaMorr

---

### Item 2: Six missing screens
**Status:** Assigned to M4 (Gauree)
**Issue:** UI navigation missing: Sources, Freshness, Glossary, Domains, Settings, Notifications. No routes. No tables. Risk of duplication.
**Decision:** M4 to clarify which M4 migrations (0007, 0008, 0009) add schemas for these screens.
**Note:** 0007, 0008, 0009 are all applied. M4 should audit the current schema and either build routes for the existing tables or create new migrations for missing features.
**Owner:** @gaureehatkar

---

### Item 3: Dead code decision
**Status:** COMPLETED
**Decision:** DELETE (completed in commit 722b7ee)
- Deleted backend/app/repositories/ directory (0% coverage, nothing imported)
- Deleted backend/app/mock_repo.py (0% coverage, nothing imported)
- 515 unused statements removed
- Dead code will not confuse future contributors

---

### Item 4: Skipped tests acceptability
**Status:** Documented, ready to run
**Current state:** 381 passed, 82 skipped
- 76 tests skip for missing KAIROS_TEST_USER_TOKEN (live test account credentials)
- 2 tests skip for LEFT/RIGHT JOIN known issue (M5 tracking)
- 4 tests skip for missing DB (now resolved)

**Path forward:** 
1. Create live test account (email + Supabase Auth)
2. Issue KAIROS_TEST_USER_TOKEN (JWT for that account)
3. Set GitHub secret in Actions
4. Re-run CI: all 76 tests will execute and prove workspace isolation

---

### Item 5: CI hardening (coverage floor, live-test job, live-smoke)
**Status:** Partially done, milestone reached

**? Completed:**
- Coverage floor: --cov-fail-under=40 in .github/workflows/ci.yml (commit 25800d6)
- Local tests passing: 381 passed, 82 skipped (4 skipped for DB now resolved)
- Current coverage: 40% (floor prevents regression)

**? Next (after test credentials issued):**
- Live-test job: CI step that runs 76 skipped tests when KAIROS_TEST_USER_TOKEN secret is present
- live-smoke: Enable nightly workflow once deployed URL exists

---

## Migration Application Verification — COMPLETE 2026-11-03

All 9 migrations verified applied to shared Supabase (verified 2026-11-03 16:30 UTC):

`
[OK] 0001_auth_and_workspace                  1 table(s)
[OK] 0002_rls_groundwork                      DDL only
[OK] 0003_personal_workspaces                 17 table(s)
[OK] 0004_ingestion_import_runs               1 table(s)
[OK] 0005_personalization                     2 table(s)
[OK] 0006_github_connections                  1 table(s)
[OK] 0007_membership_roles                    2 table(s)
[OK] 0008_source_connections                  1 table(s)
[OK] 0009_governance                          4 table(s)

Expected tables: 29
Live tables:    29

RESULT: PASS — All expected migrations are applied
`

---

## Blockers Cleared 2026-11-03

| Blocker | Cleared By | Evidence |
|---------|-----------|----------|
| Database unreachable | Credentials restored | 	est_connection.py ? PASS |
| Migrations unknown status | verify_applied.py created | All 9 migrations confirmed in live DB |
| RLS unproven | verify_rls.py executed | 28/28 tables RLS-hardened |
| D12 undecided | Supabase chosen | Available credentials + all migrations applied |
| Skipped tests unfixable | DB available | 4 DB-dependent tests now runnable |

---

## Next Steps for M2-M5

**Immediately unblocked (can begin now):**
1. ? M2 can run ingest routes (DB has 0004+ tables)
2. ? M3 can run catalog/lineage routes (DB has 0001-0009)
3. ? M4 can run governance routes (DB has 0007, 0008, 0009)
4. ? All can run integration tests against live workspace-scoped tables

**Next (M1 to complete):**
1. Create live test account + issue KAIROS_TEST_USER_TOKEN
2. Enable live-test CI job
3. Deploy to Vercel (secrets already configured in .env)
4. Enable live-smoke workflow nightly

---

## Timeline

- 2026-11-02: All 9 migrations applied (discovered after circuit breaker cleared)
- 2026-11-03 16:30: Database credentials restored; all probes pass
- 2026-11-03 16:45: verify_applied.py created; all migrations confirmed
- 2026-11-03 16:50: Migration headers updated with verification dates
- 2026-11-03 16:55: DECISION_LOG.md recorded D12 decision
- 2026-11-03 17:00: M1 ready to hand off to M2-M5
