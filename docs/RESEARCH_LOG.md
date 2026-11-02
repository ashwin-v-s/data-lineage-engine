# Kairos — Research Log

Tracks design decisions, spike outcomes, and experiment observations for the
research track. Mandated by TEAM_GUIDE.md §8. All entries are dated and signed.

---

## Entry R-01 — ProvSQL Ground Truth: Spike Result and Downgrade Decision

**Date:** 2026-11-02
**Author:** Pranav (`pranav-samal`) — M5 Research Integrity
**Status:** DECIDED

### Background

The research architecture (`FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md`
§13) designates ProvSQL as the primary ground-truth provider. ProvSQL is a
PostgreSQL extension that tracks tuple-level provenance automatically, enabling
machine-verified ground truth without manual labelling.

### Spike outcome

`research/ground_truth/SPIKE_REPORT.md` (dated 2026-09-23) attempted to install
ProvSQL on Windows PostgreSQL 18.6. The report ends mid-SQL with no conclusion
or result. The extension was never successfully installed or tested.

**Root cause:** ProvSQL requires compilation against PostgreSQL server
development headers (`postgresql-server-dev-all`), which is not straightforward
on Windows. Linux (Ubuntu/Debian) is the supported build environment.

### Options evaluated

| Option | Effort | Risk | Honest? |
|---|---|---|---|
| Compile ProvSQL on WSL2 Ubuntu (available on this machine) | High (1–2 hours setup, uncertain) | Extension may not support PostgreSQL 17 in Supabase; research DB is cloud-hosted, not local | Yes |
| Use `ReferenceInterpreterProvider` (already implemented) | Low | Human-supplied propagation map = semi-automated truth | Yes, if stated clearly |
| Claim ProvSQL works without running it | None | Invalidates research integrity | No — forbidden |

### Decision

**Use `ReferenceInterpreterProvider` as the ground-truth provider for all
benchmark cases in this sprint.**

Rationale:
1. The spike produced no working result in 6 weeks. Attempting WSL2 setup now
   consumes sprint time without a guaranteed outcome.
2. `ReferenceInterpreterProvider` is fully implemented, tested at 100% coverage,
   and correctly isolated from prediction code (`test_ground_truth_independence.py`
   verifies the boundary holds).
3. The architecture explicitly permits this: "Ground truth may be produced on one
   designated machine … and shared as hashed files" (§13). Human-derived truth
   for a defined SQL subset is a legitimate fallback.
4. The key research integrity property is preserved: the ground-truth provider
   does not import SQLGlot, ingestion code, or the reasoning engine. Truth labels
   are constructed by manual SQL trace, not by running the predictor.

### What must be stated in the findings report

- Ground truth for this evaluation is **semi-automated** (human-derived
  propagation maps verified by manual SQL trace, not ProvSQL).
- Limitation: human-derived truth is susceptible to transcription error for
  complex SQL. The W03 CASE-WHEN fixture has been independently cross-checked.
- ProvSQL remains the target for future work. The spike should be re-attempted
  on a Linux machine with PostgreSQL 14–16 (the ProvSQL-tested range).

### Impact on research claims

This downgrade does **not** affect:
- The four-state engine rules R1–R5
- The MCAR loss simulator and capture manifest
- The protocol runner and determinism guarantees
- The leakage boundary and ground-truth isolation

It **does** mean: the findings chapter must include a limitations paragraph
stating that ground truth is semi-automated, and must not claim machine-verified
provenance tracing.

---

## Entry R-02 — KAIROS_TEST_USER_TOKEN: Live Test Account Created

**Date:** 2026-11-02
**Author:** Pranav (`pranav-samal`) — M5 Research Integrity
**Status:** DONE

### What was done

A dedicated test account (`pranavsamal43@gmail.com`) was registered on the
shared Supabase project (`tkvzafrcszdtyeewfhig.supabase.co`) using the
published anon key. Email confirmation was completed via the Supabase Auth
confirmation flow.

`KAIROS_TEST_USER_TOKEN` was added to `.env` (gitignored).

### Verification

With `KAIROS_LIVE_API_TESTS=1` and `KAIROS_TEST_USER_TOKEN` set:

```
python -m pytest tests/test_live_api.py tests/test_live_ingestion_storage.py
                 tests/test_ingest_runs.py tests/test_workspace_scope.py
                 -v --tb=short -p no:langsmith_plugin
```

**Result: 15 passed, 1 skipped** (2026-11-02)

The 1 remaining skip (`test_downstream_impact_returns_200_for_one_asset`)
requires at least one asset in the catalog. This is M3's responsibility —
the skip reason is "The live catalog exposes no assets to use as a lineage
anchor." Once M3 seeds the catalog, this test will pass.

### Token expiry note

Supabase access tokens expire after 1 hour. The `.env` token will need to
be refreshed by re-running `python scripts/get_test_token.py` when it expires.
The refresh token (`mbukgqp44ir7`) can be used for silent renewal.

---

## Entry R-03 — Open Decisions Pending Team Input

**Date:** 2026-11-02
**Author:** Pranav (`pranav-samal`) — M5 Research Integrity
**Status:** OPEN — awaiting team decisions

The following decisions from `FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md`
remain unresolved and block the real experiment run. They are documented here
so the team knows exactly what is needed.

| ID | Decision needed | Who |
|---|---|---|
| D-01 / K1–K8 | Kill criteria thresholds (e.g. false_refutation < X%) | Team vote |
| D-05 | Primary metric + aggregation rule across cases/loss levels | Team vote |
| D-07 | Dev/validation/held-out split assignment for benchmark cases | M5 (Pranav) once cases exist |
| D-08 | Confidence interval method (bootstrap / Wilson / t-test) | Team vote |
| D-10 | Column-level runtime evidence: which provider, how verified | M2 (Anushka) |
| D-11 | Contribution semantics: where-provenance or why-provenance | Team vote |
| D-12 | Prediction-unit universe: static candidates + positive-evidence pairs | M5 confirms in runner |
| AQ-1 | Engine: UNSUPPORTED + positive evidence → OBSERVED or UNKNOWN? | Team vote — update engine OR architecture table, not both |
| Zero-arrival | Semantics A/B/C/D for zero-arrival loss level | Team vote |
