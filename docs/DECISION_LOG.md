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

---

## Research-D01 — Kill criteria K1–K8 thresholds

**Status:** DECIDED — 2026-11-02
**Owner:** M5 (Pranav `pranav-samal`)
**Affects:** `research/protocol/v1.yaml`, experiment runner, findings report

**Decision:**
Kill criteria thresholds set for a 10-case SQL-subset benchmark.
Conservative thresholds reflecting the limited scope:

| Criterion | Threshold | Verdict if failed |
|---|---|---|
| K1 | proposed false_refutation < B2 at level 0 | Rejected |
| K2 | false_refutation ≤ 0.15 at level 0 | Rejected |
| K3 | false_observation ≤ 0.20 at level 0 | Inconclusive |
| K4 | unknown_rate ≤ 0.40 at level 0 | Inconclusive |
| K5 | recall_strict ≥ B1 recall_strict at level 0 | Inconclusive |
| K6 | recall_strict[90] ≤ recall_strict[0] (monotone erosion) | Inconclusive |
| K7 | false_refutation == 0 at level 0 | Rejected |
| K8 | committed_accuracy > B3 committed_accuracy at level 0 | Inconclusive |

Full text in `research/protocol/v1.yaml` §kill_criteria.

---

## Research-D02 — Primary metric (D-05)

**Status:** DECIDED — 2026-11-02
**Owner:** M5 (Pranav `pranav-samal`)
**Affects:** `research/protocol/v1.yaml`, findings report

**Decision:**
Primary metric is `false_refutation` — the rate at which a PROPAGATED truth
dependency is predicted REFUTED_FOR_RUN. This is the central safety property:
the system must not confidently deny propagation when it actually occurred.
The proposed engine must beat B2 (negative assumption baseline) on this metric.

---

## Research-D03 — Contribution semantics (D-11)

**Status:** DECIDED — 2026-11-02
**Owner:** M5 (Pranav `pranav-samal`)
**Affects:** ground-truth construction, benchmark case design

**Decision:**
Where-provenance: a dependency is PROPAGATED if at least one source column
value contributed to at least one target column value in the run.
Why-provenance (which rules triggered) is out of scope for this benchmark.

---

## Research-D04 — Prediction-unit universe (D-12)

**Status:** DECIDED — 2026-11-02
**Owner:** M5 (Pranav `pranav-samal`)
**Affects:** experiment runner, metrics

**Decision:**
The prediction universe is the union of:
1. All static candidates (pairs with any StaticEvidence)
2. All pairs with at least one RUNTIME_POSITIVE evidence record
The full cross-product of all possible column pairs is NOT used (would inflate
trivial non-dependency correct predictions).

---

## Research-D05 — Zero-arrival semantics

**Status:** DECIDED — 2026-11-02
**Owner:** M5 (Pranav `pranav-samal`)
**Affects:** MCAR loss simulator, capture manifest

**Decision:**
Option B: a run with 0 events produces no evidence records (not a negative
evaluation). The engine receives no RuntimeEvidence and falls to R4 (POSSIBLE)
or R5 (UNKNOWN). Zero arrival is NOT treated as proof of non-propagation.
This is consistent with the core "missing events ≠ refutation" property.

---

## Research-D06 — Confidence interval method (D-08)

**Status:** DECIDED — 2026-11-02
**Owner:** M5 (Pranav `pranav-samal`)
**Affects:** findings report, metrics

**Decision:**
Bootstrap 95% CI, 1000 resamples, percentile method.
Chosen for its assumption-free properties on small samples (10 cases).

---

## Research-D07 — Aggregation across cases and loss levels (D-05)

**Status:** DECIDED — 2026-11-02
**Owner:** M5 (Pranav `pranav-samal`)
**Affects:** experiment runner, findings report

**Decision:**
Macro-average across cases at each loss level independently.
Do not pool across loss levels into a single aggregate number.
Report one row per (loss_level, method) in the findings table.

---

## Research-D08 — AQ-1: UNSUPPORTED + positive evidence → OBSERVED or UNKNOWN

**Status:** DECIDED — 2026-11-02
**Owner:** M5 (Pranav `pranav-samal`)
**Affects:** `research/reasoning/engine.py`, `tests/test_engine_rules.py`

**Decision:**
The engine returns UNKNOWN when parser_status == UNSUPPORTED even if positive
runtime evidence exists. Rationale: the engine cannot verify that the static
semantics support the observed propagation. The runtime event may be at dataset
granularity while the dependency is column-level; without a parseable static
candidate the column-level claim is unverifiable.

The existing test `test_r1_unsupported_static_gives_unknown_even_with_positive_evidence`
correctly locks this behavior. The architecture §14 expanded table is inconsistent
with this decision; the table will be corrected in the next architecture update.
