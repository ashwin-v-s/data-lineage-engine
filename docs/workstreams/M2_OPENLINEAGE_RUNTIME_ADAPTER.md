# M2 — OpenLineage Runtime Adapter

**Owner:** Person 2 · **Timebox:** 2–3 hours · **Architecture:** [`../KAIROS_FINAL_ARCHITECTURE.md`](../KAIROS_FINAL_ARCHITECTURE.md)

## Goal

Normalize OpenLineage event JSON into runtime evidence without overstating what an event proves. Keep this work isolated from the product DB/API and from independent ground truth.

## Inspect first

- `ingestion/openlineage/` models, loader, normalizer, and tests.
- `contracts/evidence.py` and `contracts/interfaces.py` (identify any duplicate `RuntimeEvidence` representations; do not unify them without M3/M4 agreement).
- Research Sections 12–16 in `FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md`.

## Work

1. Trace each supported event type and field into normalized job, run, dataset, event time, source reference, and facets.
2. Add small fixtures for a complete event, missing optional facets, malformed event, and a run with multiple events.
3. Preserve event identity/order and event-time semantics. Keep dataset-level read/write observations dataset-level. Column evidence is emitted only where a valid column-lineage facet explicitly supplies it.
4. Emit structured diagnostics for unsupported/missing data. Missing event/capture is unknown or incomplete; never generate a negative edge or `REFUTED_FOR_RUN` from absence.
5. Report current coverage limits to M3/M4. Propose schema mapping changes in writing; M3 owns the shared ingest contract.

## Likely files

- `ingestion/openlineage/normalizer.py`, `models.py`, `loader.py`
- `tests/fixtures/openlineage/` and focused normalizer tests

## Acceptance

- Existing fixtures remain valid or changes are explicitly explained.
- Runtime evidence retains run ID and original event provenance.
- Dataset-only evidence does not masquerade as column-level propagation.
- No imports from `research/ground_truth`, no ground-truth labels, no DB/API/frontend edits.

