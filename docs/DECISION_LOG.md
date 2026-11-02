# Kairos — Architecture Decision Log

Decisions that affect multiple streams or that cannot be reversed cheaply.
Each entry: date recorded, status (OPEN / DECIDED / SUPERSEDED), owner, and the
decision text.  All team members must read entries marked **DECIDED** before
building against them.

---

## D12 — Database runtime: shared Supabase vs. local Postgres

**Status:** DECIDED — 2026-11-02
**Owner:** M1 (Jatin `Jat-in32006`)
**Affects:** M1 (migrations), M2 (scheduler), M3 (live tests), M4 (governance), M5 (honesty gate)

**Decision:**
The team uses the shared Supabase project (`aws-0-ap-south-1.pooler.supabase.com`)
as the single authoritative database.  No separate local PostgreSQL instance is
maintained for integration purposes.

**Consequences:**

1. Credentials (`DATABASE_URL`) must be kept working and rotated in the team's
   shared secret store.  Any member who changes the Supabase password must
   immediately update `.env` for every member and re-run
   `python scripts/test_connection.py` to confirm (must exit 0).

2. `scripts/test_connection.py` is the gate: it must exit 0 before any
   migration is marked "Applied" and before any live test is run.
   `scripts/db/verify_applied.py` is the proof gate for applied migrations.

3. Scheduled jobs (freshness evaluator) **cannot** run inside a Vercel request
   (`maxDuration: 30`).  The runner will be a **Supabase Edge Function** or a
   **GitHub Actions scheduled workflow** — to be decided by M2 and M1 jointly
   in Wave 4.  Until decided, the freshness routes are available on-demand
   only; no automatic scheduler is running.

4. Migration chain must be applied in order 0001 → 0009 against the shared
   project.  `verify_applied.py` is the proof gate — a migration header may
   only say "Applied" once that script exits 0 for its expected tables.

**Current blocker (2026-11-02):**
`FATAL: password authentication failed for user "postgres"` — Supabase pooler
circuit breaker tripped after repeated auth failures.  Resolution: wait for the
breaker to reset (typically 5–15 min), then reset the `postgres` role password
in the Supabase dashboard → Settings → Database → Reset database password, then
update `DATABASE_URL` in `.env` and confirm `scripts/test_connection.py` exits 0.

---

## D7 — Workspace visibility selector (governance policies)

**Status:** OPEN
**Owner:** M1 (Jatin) + M4 (Gauree `gaureehatkar`)
**Affects:** M4 governance routes, RLS policies for glossary/domains/data products

**Question:** Should glossary terms, domains, and data products be
workspace-private (current default) or optionally shareable across workspaces
(as in OpenMetadata's "global" vs. "team" glossary)?

**Decision needed before:** Gauree writes `0010_glossary_domains.sql` — the
policy shape differs (`workspace_id IS NOT NULL` vs. nullable with a
cross-workspace read policy).

**Deadline:** before Wave 2 starts.

---

## D10 — Evidence/lineage export: client-side vs. server-side

**Status:** OPEN
**Owner:** M1 (Jatin) + M3 (Ashwin `ashwin-v-s`)
**Affects:** M3 evidence routes, M4 audit export, frontend bundle size

**Question:** Should large lineage/evidence exports be streamed from the server
(a `StreamingResponse` CSV/JSON endpoint) or assembled by the browser
(client-side JS from the paginated snapshot API)?

**Decision needed before:** Ashwin adds export endpoints.  The contract shape
and the OpenAPI spec differ between the two approaches, and building one after
the other deployed the other wastes migration + contract work.

---

## D6 — Rollback owner and mechanism

**Status:** OPEN
**Owner:** M1 (Jatin)
**Affects:** CI, deployment pipeline, `backend/migrations/`

**Question:** Who approves and executes a database migration rollback in
production?  Is there a rollback SQL script for each migration (`0009_down.sql`
style), or do we rely on Supabase point-in-time recovery (PITR)?

**Decision needed before:** Wave 4 deployment — a broken production migration
without a rollback story blocks the whole team.
