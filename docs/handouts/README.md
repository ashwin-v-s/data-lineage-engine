# Five-Member Handouts — Completion Sprint

Companions: [KAIROS_ARCHITECTURE_V2.md](../KAIROS_ARCHITECTURE_V2.md) (what we are building — §4 invariants, §5 contracts, §9 source access incl. **§9.2 the complete source set**, §10 demo spec, §11 open decisions D1–D12) · [KAIROS_PRODUCT_SPEC_PERPLEXITY.md](../KAIROS_PRODUCT_SPEC_PERPLEXITY.md) (the screen-by-screen component inventory distilled from the Perplexity spec, incl. §14 features it wrongly assumes exist) · **[VERIFICATION_2026-11-02.md](../VERIFICATION_2026-11-02.md) (what I actually ran today and what it did)** · [PROJECT_STATUS_2026-11-02.md](../PROJECT_STATUS_2026-11-02.md) (what is real today).

Each handout now has a **§2b "Executed today — defects that are yours"** table: the command, the output, and the consequence. Read §2b before §3 — those items come first because they are measured, not inferred.

Each handout has the same shape: **what you already shipped** (with commit/PR evidence) → **what is not done** (with the file/command that proves it) → **what you need to do** (wave-ordered) → **definition of done** → **do not**.

| Stream | Owner | Mission | Gate |
|---|---|---|---|
| [M1 — Platform, Identity, Deployment & Contract](M1_JATIN_platform_identity_deployment.md) | Jatin `Jat-in32006` | a stranger signs up, is isolated, and reaches a deployed URL | signup + 401 fail-closed + two-workspace isolation + green `live-smoke` |
| [M2 — Connectors & Ingestion Engine](M2_ANUSHKA_connectors_ingestion.md) | Anushka `AnaaMorr` | every authorized source materializes honestly | connect → preview (no writes) → commit once → read back; idempotent replay |
| [M3 — Catalog, Lineage & Evidence](M3_ASHWIN_catalog_lineage_evidence.md) | Ashwin `ashwin-v-s` | every conclusion shows *why* | every edge traces to stored evidence; no fixture looks observed; time travel |
| [M4 — Governance & Product Shell](M4_GAUREE_governance_shell.md) | Gauree `gaureehatkar` | the workspace a user lives in | a breach creates one incident + notification from stored evidence; 7 demo screens live |
| [M5 — Research Integrity, Findings & Demo Honesty](M5_PRANAV_research_integrity_demo_honesty.md) | Pranav `pranav-samal` | real findings, no fabricated claims | zero TBD protocol, real experiment artifacts, E2E honesty gate |

## Shared rules for this sprint

1. **Wave 0 first** (M1 leads): restore shared-DB credentials, commit/push the working tree as per-stream PRs, re-verify every "APPLIED to the shared Supabase project" header, replace the `@M1-handle` placeholders in `.github/CODEOWNERS`. Four of five members have ≤2 merged PRs — the routing failure is the reason, so fixing CODEOWNERS is not paperwork.
2. **One stream, one vertical slice**: your own migration + routes + screens + tests + docs. No backend-only or CSS-only ownership.
3. **Frozen interfaces** (Architecture v2 §5) are the contract between you. Changing one needs M1 plus every consumer in review, in the same PR.
4. **Never claim what you did not run.** Paste the command and its output into the PR body. This sprint's biggest risk is not missing features — it is unverified status claims (three migrations already assert an applied state nobody can currently check).
5. Ownership can be swapped between members, but only as a whole slice, and by agreement recorded in `docs/DECISION_LOG.md`.
6. **Tick a gap or a task in these handouts only with evidence attached** — a screenshot, the API response, or the test name and its output. A checkbox with no evidence behind it is a status claim, and status claims are what this sprint is fixing (see §4 rule 4 and `PROJECT_STATUS_2026-11-02.md` §5.9).
